"""打印用眼镜 ArUco 单标记图纸：按物理尺寸精确渲染、自检并写出 PNG。

边界与约定：

- 本模块只生成并写出图案：**不开摄像头、不实例化鼠标、不读写任何校准文件**，
  也不被追踪链路调用，因此不会改变任何追踪行为。
- 字典、id、黑框边长直接取自 ``glasses_tracking`` 配置，避免「打印的标记」与
  「配置里的标记」尺寸不一致（尺寸不一致会让平移量整体按比例错）。
- 像素与物理换算的唯一来源是 PNG 的物理分辨率元数据（pHYs，整数 px/m），
  因此渲染前把尺寸吸附到「每格整数像素」，导出前再自检黑框像素边长与可检出性。
- 打印后必须由用户用直尺实测（图上自带 100 mm 参考条），实测值写回
  ``glasses_tracking.marker_size_m``；程序不猜真实尺寸。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from eyemouse.camera_calibration import CalibrationError, _write_png, resolve_dictionary

# 每英寸多少米：把 px/m 折算成 PNG 的 dpi 元数据
PX_PER_METER_PER_DPI = 39.37007874015748
# 默认按约 300 dpi 渲染（11811.02 px/m），随后吸附到「每格整数像素」
DEFAULT_PIXELS_PER_METER = 11811.023622047244
DEFAULT_QUIET_MARGIN_M = 0.010
DEFAULT_RULER_MM = 100.0
DEFAULT_BORDER_BITS = 1

# 版面尺寸（米）：一律按渲染比例换算成像素，避免不同 dpi 下版面比例漂移
PAD_M = 0.008
GAP_M = 0.006
LINE_M = 0.0058
TICK_LONG_M = 0.006
TICK_MID_M = 0.004
TICK_SHORT_M = 0.0025
THICKNESS_M = 0.00025
FONT_SCALE_PER_METER = 0.00010
MIN_FONT_SCALE = 0.40


@dataclass(frozen=True)
class MarkerSheetSpec:
    """打印图纸参数（长度单位：米）。"""

    dictionary: str = "DICT_5X5_50"
    marker_id: int = 0
    marker_size_m: float = 0.030
    quiet_margin_m: float = DEFAULT_QUIET_MARGIN_M
    pixels_per_meter: float = DEFAULT_PIXELS_PER_METER
    ruler_mm: float = DEFAULT_RULER_MM
    border_bits: int = DEFAULT_BORDER_BITS

    @staticmethod
    def from_config(cfg: Any) -> "MarkerSheetSpec":
        """从应用配置读取标记参数；只读 ``glasses_tracking`` 节，不修改配置。"""
        tracking = getattr(cfg, "glasses_tracking", None)
        if tracking is None:
            raise CalibrationError("配置缺少 glasses_tracking 节，无法确定标记参数")
        return MarkerSheetSpec(
            dictionary=str(getattr(tracking, "dictionary", "DICT_5X5_50")),
            marker_id=int(getattr(tracking, "marker_id", 0)),
            marker_size_m=float(getattr(tracking, "marker_size_m", 0.030)),
        )


@dataclass(frozen=True)
class MarkerGeometry:
    """渲染像素几何：所有像素与物理换算的唯一来源。"""

    cells: int
    cell_px: int
    marker_px: int
    quiet_px: int
    patch_px: int
    ruler_px: int
    marker_size_m: float
    pixels_per_meter: float

    @property
    def pixels_per_meter_int(self) -> int:
        """写入 PNG pHYs 的整数 px/m；打印比例按此还原。"""
        return int(round(self.pixels_per_meter))

    @property
    def dpi(self) -> float:
        """物理分辨率（dpi），等于 px/m 除以 39.37007874015748。"""
        return self.pixels_per_meter / PX_PER_METER_PER_DPI

    @property
    def marker_size_mm(self) -> float:
        """黑框边长（毫米），只用于显示与自检。"""
        return self.marker_px / self.pixels_per_meter * 1000.0

    @property
    def quiet_margin_mm(self) -> float:
        """每侧白边宽度（毫米）。"""
        return self.quiet_px / self.pixels_per_meter * 1000.0

    @property
    def ruler_mm(self) -> float:
        """参考尺长度（毫米）。"""
        return self.ruler_px / self.pixels_per_meter * 1000.0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于打印与测试断言。"""
        return {
            "cells": int(self.cells),
            "cell_px": int(self.cell_px),
            "marker_px": int(self.marker_px),
            "quiet_px": int(self.quiet_px),
            "patch_px": int(self.patch_px),
            "ruler_px": int(self.ruler_px),
            "marker_size_m": float(self.marker_size_m),
            "pixels_per_meter": float(self.pixels_per_meter),
            "pixels_per_meter_int": int(self.pixels_per_meter_int),
            "dpi": float(self.dpi),
        }


def marker_cell_count(spec: MarkerSheetSpec) -> int:
    """标记每边的格子数 = 数据位数 + 两侧黑边框位数。"""
    if int(spec.border_bits) < 1:
        raise CalibrationError("border_bits 至少为 1：ArUco 标记必须有黑色边框")
    dictionary = resolve_dictionary(str(spec.dictionary))
    bits = int(getattr(dictionary, "markerSize", 0) or 0)
    if bits <= 0:
        raise CalibrationError(f"无法确定字典 {spec.dictionary} 的每边位数 markerSize")
    return bits + 2 * int(spec.border_bits)


def marker_geometry(spec: MarkerSheetSpec) -> MarkerGeometry:
    """计算像素几何：先把黑框边长吸附到整数格，再由整像素反推真实 px/m。"""
    if not spec.marker_size_m > 0.0:
        raise CalibrationError("marker_size_m 必须为正数（单位：米）")
    if not spec.pixels_per_meter > 0.0:
        raise CalibrationError("pixels_per_meter 必须为正数")
    if spec.quiet_margin_m < 0.0:
        raise CalibrationError("quiet_margin_m 不能为负数")
    if not spec.ruler_mm > 0.0:
        raise CalibrationError("ruler_mm 必须为正数")
    cells = marker_cell_count(spec)
    cell_px = max(int(round(spec.marker_size_m * spec.pixels_per_meter / cells)), 1)
    marker_px = cells * cell_px
    pixels_per_meter = marker_px / spec.marker_size_m
    quiet_px = max(int(round(spec.quiet_margin_m * pixels_per_meter)), cell_px)
    ruler_px = max(int(round(spec.ruler_mm / 1000.0 * pixels_per_meter)), 1)
    return MarkerGeometry(
        cells=int(cells),
        cell_px=int(cell_px),
        marker_px=int(marker_px),
        quiet_px=int(quiet_px),
        patch_px=int(marker_px + 2 * quiet_px),
        ruler_px=int(ruler_px),
        marker_size_m=float(spec.marker_size_m),
        pixels_per_meter=float(pixels_per_meter),
    )


def measure_marker_bbox_px(image: np.ndarray) -> Optional[Tuple[int, int, int]]:
    """实测图中最大黑色连通域的外接框，返回 ``(x, y, 边长)``；非正方形返回 None。"""
    if image is None or getattr(image, "size", 0) == 0:
        return None
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    black = (gray < 128).astype(np.uint8)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(black, connectivity=8)
    if count <= 1:
        return None
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    width = int(stats[index, cv2.CC_STAT_WIDTH])
    height = int(stats[index, cv2.CC_STAT_HEIGHT])
    if width != height:
        return None
    return (
        int(stats[index, cv2.CC_STAT_LEFT]),
        int(stats[index, cv2.CC_STAT_TOP]),
        int(width),
    )


def detect_marker_ids(image: np.ndarray, dictionary: str) -> List[int]:
    """检测图中所有 ArUco 标记 id（未检出返回空列表）。"""
    if image is None or getattr(image, "size", 0) == 0:
        return []
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.dtype != np.uint8:
        gray = cv2.convertScaleAbs(gray)
    dictionary_obj = resolve_dictionary(str(dictionary))
    detector = cv2.aruco.ArucoDetector(dictionary_obj, cv2.aruco.DetectorParameters())
    try:
        _corners, ids, _rejected = detector.detectMarkers(gray)
    except cv2.error as exc:
        raise CalibrationError(f"标记检测失败：{exc}") from exc
    if ids is None:
        return []
    return [int(value) for value in np.asarray(ids).ravel().tolist()]


def render_marker_patch(spec: MarkerSheetSpec) -> Tuple[np.ndarray, MarkerGeometry]:
    """渲染「黑框标记 + 每侧白边」的灰度图，并自检像素边长、居中与可检出性。"""
    geometry = marker_geometry(spec)
    dictionary = resolve_dictionary(str(spec.dictionary))
    try:
        marker = cv2.aruco.generateImageMarker(
            dictionary,
            int(spec.marker_id),
            int(geometry.marker_px),
            borderBits=int(spec.border_bits),
        )
    except cv2.error as exc:
        raise CalibrationError(
            f"生成 ArUco 标记失败（字典 {spec.dictionary}，id={spec.marker_id}）：{exc}"
        ) from exc
    if tuple(marker.shape[:2]) != (geometry.marker_px, geometry.marker_px):
        raise CalibrationError(
            f"标记渲染尺寸异常：得到 {marker.shape[1]}x{marker.shape[0]}，"
            f"期望 {geometry.marker_px} 见方"
        )
    patch = cv2.copyMakeBorder(
        marker,
        geometry.quiet_px,
        geometry.quiet_px,
        geometry.quiet_px,
        geometry.quiet_px,
        cv2.BORDER_CONSTANT,
        value=255,
    )
    measured = measure_marker_bbox_px(patch)
    if measured is None:
        raise CalibrationError("标记渲染自检失败：未找到正方形黑色连通域")
    left, top, side = measured
    if side != geometry.marker_px or left != geometry.quiet_px or top != geometry.quiet_px:
        raise CalibrationError(
            f"标记渲染自检失败：黑框边长 {side}px 左上 ({left},{top})，"
            f"期望 {geometry.marker_px}px 左上 ({geometry.quiet_px},{geometry.quiet_px})"
        )
    if int(spec.marker_id) not in detect_marker_ids(patch, spec.dictionary):
        raise CalibrationError(
            f"标记渲染自检失败：渲染出的标记无法被检出"
            f"（字典 {spec.dictionary}，id={spec.marker_id}）"
        )
    return patch, geometry


def sheet_annotation_lines(spec: MarkerSheetSpec, geometry: MarkerGeometry) -> List[str]:
    """图纸上的标注文字；必须全为 ASCII，因为 ``cv2.putText`` 不支持中文。"""
    return [
        "EyeMouse glasses ArUco marker  |  print at 100% (ACTUAL SIZE)",
        "No fit-to-page, no scaling. Do not mirror or flip this sheet.",
        f"Dictionary {spec.dictionary}    id={int(spec.marker_id)}",
        f"Black square side = {geometry.marker_size_mm:.2f} mm  (outer black edge to outer edge)",
        f"White quiet zone = {geometry.quiet_margin_mm:.1f} mm on every side - keep it clean.",
        f"1 pixel = {1000.0 / geometry.pixels_per_meter:.4f} mm   PNG resolution = {geometry.dpi:.2f} dpi",
        f"1) Real ruler: marks 0 and 10 of the bar below = {geometry.ruler_mm:.1f} mm.",
        f"2) Measure the black square: it must be {geometry.marker_size_mm:.2f} mm.",
        "3) Put the measured side (in meters) into config.yaml:",
        "   glasses_tracking.marker_size_m",
        "4) Attach flat and matte, away from the eyes/blink area.",
    ]


def _ruler_tick_heights(geometry: MarkerGeometry) -> Tuple[int, int, int]:
    """参考尺的长/中/短刻度像素高度。"""
    ppm = geometry.pixels_per_meter
    return (
        max(int(round(TICK_LONG_M * ppm)), 6),
        max(int(round(TICK_MID_M * ppm)), 4),
        max(int(round(TICK_SHORT_M * ppm)), 3),
    )


def ruler_line_thickness(geometry: MarkerGeometry) -> int:
    """参考尺线条粗细（整数像素）；刻度一律按矩形绘制以保证中心间距精确。"""
    return max(int(round(THICKNESS_M * geometry.pixels_per_meter)), 1)


def ruler_band_height(
    geometry: MarkerGeometry, font: int, label_scale: float, thickness: int
) -> int:
    """参考尺区域高度（刻度 + 数字），用于预先分配画布。"""
    long_px, _mid_px, _short_px = _ruler_tick_heights(geometry)
    (_text_w, text_h), _baseline = cv2.getTextSize("0", font, label_scale, thickness)
    return long_px + max(ruler_line_thickness(geometry) * 2, 4) + text_h


def _draw_ruler(
    canvas: np.ndarray,
    geometry: MarkerGeometry,
    origin_x: int,
    top_y: int,
    font: int,
    label_scale: float,
    thickness: int,
) -> None:
    """在画布上画 0..ruler_mm 毫米刻度尺：基线在 top_y，刻度向下，厘米数字在刻度下。

    线条一律用 ``cv2.rectangle`` 画：``cv2.line`` 的粗线会把两端各外扩半个线宽，
    会让参考尺静默变长（实测 100 mm 会被画成约 100.4 mm）。矩形绘制的刻度中心间距
    严格等于 ``ruler_px``，用户量 0 与 ruler_mm 两个刻度即可核对打印比例。
    """
    long_px, mid_px, short_px = _ruler_tick_heights(geometry)
    line_w = ruler_line_thickness(geometry)
    half = line_w // 2
    px_per_mm = geometry.pixels_per_meter / 1000.0
    baseline_y = int(top_y)
    cv2.rectangle(
        canvas,
        (int(origin_x - half), baseline_y),
        (int(origin_x + geometry.ruler_px + half - 1), baseline_y + line_w - 1),
        0,
        -1,
    )
    total_mm = int(round(geometry.ruler_mm))
    for offset_mm in range(total_mm + 1):
        x = int(origin_x + int(round(offset_mm * px_per_mm)))
        if offset_mm % 10 == 0:
            height = long_px
        elif offset_mm % 5 == 0:
            height = mid_px
        else:
            height = short_px
        cv2.rectangle(
            canvas,
            (x - half, baseline_y),
            (x - half + line_w - 1, baseline_y + height - 1),
            0,
            -1,
        )
    label_offset = long_px + max(line_w * 2, 4)
    for offset_mm in range(0, total_mm + 1, 10):
        x = int(origin_x + int(round(offset_mm * px_per_mm)))
        text = str(offset_mm // 10)
        (text_w, text_h), _baseline = cv2.getTextSize(text, font, label_scale, thickness)
        cv2.putText(
            canvas,
            text,
            (x - text_w // 2, baseline_y + label_offset + text_h),
            font,
            label_scale,
            0,
            thickness,
            cv2.LINE_AA,
        )


def render_marker_sheet(spec: MarkerSheetSpec) -> Tuple[np.ndarray, MarkerGeometry]:
    """渲染整张图纸（BGR 灰度内容），返回 ``(image, geometry)``。"""
    patch, geometry = render_marker_patch(spec)
    ppm = geometry.pixels_per_meter
    pad = max(int(round(PAD_M * ppm)), 8)
    gap = max(int(round(GAP_M * ppm)), 8)
    line_h = max(int(round(LINE_M * ppm)), 14)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(FONT_SCALE_PER_METER * ppm, MIN_FONT_SCALE)
    thickness = max(int(round(THICKNESS_M * ppm)), 1)
    label_scale = font_scale * 0.8

    lines = sheet_annotation_lines(spec, geometry)
    text_width = 0
    for line in lines:
        (line_width, _line_height), _baseline = cv2.getTextSize(line, font, font_scale, thickness)
        text_width = max(text_width, line_width)

    ruler_band = ruler_band_height(geometry, font, label_scale, thickness)
    content_width = max(geometry.patch_px, geometry.ruler_px, text_width)
    width = content_width + 2 * pad
    height = (
        pad
        + geometry.patch_px
        + gap
        + len(lines) * line_h
        + gap
        + ruler_band
        + pad
    )
    canvas = np.full((int(height), int(width)), 255, dtype=np.uint8)

    patch_x = (width - geometry.patch_px) // 2
    canvas[pad : pad + geometry.patch_px, patch_x : patch_x + geometry.patch_px] = patch

    text_top = pad + geometry.patch_px + gap
    for index, line in enumerate(lines):
        baseline_y = text_top + line_h * (index + 1) - max(int(line_h * 0.25), 2)
        cv2.putText(canvas, line, (pad, baseline_y), font, font_scale, 0, thickness, cv2.LINE_AA)

    ruler_top = text_top + len(lines) * line_h + gap
    _draw_ruler(canvas, geometry, pad, ruler_top, font, label_scale, thickness)
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR), geometry


def write_marker_sheet(
    spec: MarkerSheetSpec, path: Any, image: Optional[np.ndarray] = None
) -> Path:
    """渲染并写出打印图纸（PNG + 物理分辨率元数据）；返回实际写入路径。

    ``image`` 可传入 :func:`render_marker_sheet` 的结果以避免重复渲染；不传时本函数自己渲染
    （含黑框像素边长与可检出性自检）。
    图纸可由配置完全重建，因此覆盖旧文件时不做备份（与 ``--write-charuco-board`` 一致）。
    """
    if image is None:
        image, _geometry = render_marker_sheet(spec)
    elif image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    geometry = marker_geometry(spec)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_png(target, image, geometry.pixels_per_meter, geometry.pixels_per_meter)
    return target
