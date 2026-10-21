"""摄像头内参标定：ChArUco 板检测、标定、质量检查与 JSON 存读。

约定：
- 长度单位一律为**米**；内参矩阵与畸变系数只对**未镜像**的原始画面有效。
- 标定分辨率与运行分辨率不一致时必须重新标定，禁止静默复用。
- 不使用 pickle；覆盖保存前自动备份。
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1
UNIT = "meter"


class CalibrationError(RuntimeError):
    """标定流程中的可预期错误（中文提示）。"""


@dataclass(frozen=True)
class CharucoBoardSpec:
    """ChArUco 标定板参数（长度单位：米）。"""

    dictionary: str = "DICT_5X5_50"
    squares_x: int = 8
    squares_y: int = 6
    square_length_m: float = 0.025
    marker_length_m: float = 0.018

    @property
    def corner_count(self) -> int:
        """棋盘内部角点数。"""
        return max(self.squares_x - 1, 0) * max(self.squares_y - 1, 0)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 可写结构。"""
        return {
            "dictionary": self.dictionary,
            "squares_x": int(self.squares_x),
            "squares_y": int(self.squares_y),
            "square_length_m": float(self.square_length_m),
            "marker_length_m": float(self.marker_length_m),
            "unit": UNIT,
        }

    @staticmethod
    def from_config(cfg: Any) -> "CharucoBoardSpec":
        """从配置节构造（任意带同名字段的对象）。"""
        return CharucoBoardSpec(
            dictionary=str(cfg.dictionary),
            squares_x=int(cfg.squares_x),
            squares_y=int(cfg.squares_y),
            square_length_m=float(cfg.square_length_m),
            marker_length_m=float(cfg.marker_length_m),
        )


@dataclass
class DetectedView:
    """一个成功检测的标定板视图。"""

    corners: np.ndarray  # (N, 1, 2) float32，未镜像画面像素坐标
    ids: np.ndarray  # (N, 1) int32，对应棋盘角点索引

    @property
    def count(self) -> int:
        """本视图角点数。"""
        return int(self.corners.shape[0])


@dataclass
class CameraCalibration:
    """标定结果。"""

    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    image_size: Tuple[int, int]
    rms_px: float
    per_view_rms_px: List[float] = field(default_factory=list)
    num_views: int = 0
    coverage_cells_hit: int = 0
    board: Optional[CharucoBoardSpec] = None
    schema_version: int = SCHEMA_VERSION
    saved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 结构。"""
        return {
            "schema_version": int(self.schema_version),
            "saved_at": self.saved_at or datetime.now().isoformat(timespec="seconds"),
            "unit": UNIT,
            "image_size": [int(self.image_size[0]), int(self.image_size[1])],
            "board": (self.board or CharucoBoardSpec()).to_dict(),
            "camera_matrix": np.asarray(self.camera_matrix, dtype=float).tolist(),
            "dist_coeffs": np.asarray(self.dist_coeffs, dtype=float).ravel().tolist(),
            "metrics": {
                "rms_px": float(self.rms_px),
                "per_view_rms_px": [float(v) for v in self.per_view_rms_px],
                "num_views": int(self.num_views),
                "coverage_cells_hit": int(self.coverage_cells_hit),
                "note": "rms_px 只是重投影残差，不是参数协方差或绝对姿态精度",
            },
        }


def resolve_dictionary(name: str) -> Any:
    """把字典名解析为 cv2.aruco 字典对象；未知名称抛出中文错误。"""
    if not isinstance(name, str) or not name.strip():
        raise CalibrationError(f"ArUco 字典名必须是非空字符串，当前为 {name!r}")
    key = name.strip()
    if not hasattr(cv2.aruco, key):
        raise CalibrationError(f"未知的 ArUco 字典名：{key}（例如 DICT_5X5_50）")
    value = getattr(cv2.aruco, key)
    if not isinstance(value, int):
        raise CalibrationError(f"ArUco 字典名不合法：{key}")
    return cv2.aruco.getPredefinedDictionary(value)


def make_charuco_board(spec: CharucoBoardSpec) -> Any:
    """按板参数创建 CharucoBoard。"""
    if (spec.squares_x * spec.squares_y) % 2 != 0:
        raise CalibrationError(
            f"squares_x*squares_y 必须为偶数（否则标记数不是整数）：{spec.squares_x}x{spec.squares_y}"
        )
    if spec.marker_length_m >= spec.square_length_m:
        raise CalibrationError(
            f"marker_length_m({spec.marker_length_m}) 必须小于 square_length_m({spec.square_length_m})"
        )
    dictionary = resolve_dictionary(spec.dictionary)
    return cv2.aruco.CharucoBoard(
        (int(spec.squares_x), int(spec.squares_y)),
        float(spec.square_length_m),
        float(spec.marker_length_m),
        dictionary,
    )


_DETECTOR_CACHE: Dict[Any, Any] = {}


def cached_detector(spec: CharucoBoardSpec) -> Any:
    """按板参数缓存 CharucoDetector；交互采集时避免每帧重建标定板。"""
    key = (
        str(spec.dictionary),
        int(spec.squares_x),
        int(spec.squares_y),
        float(spec.square_length_m),
        float(spec.marker_length_m),
    )
    detector = _DETECTOR_CACHE.get(key)
    if detector is None:
        detector = cv2.aruco.CharucoDetector(make_charuco_board(spec))
        _DETECTOR_CACHE.clear()
        _DETECTOR_CACHE[key] = detector
    return detector


def detect_view(gray: np.ndarray, spec: CharucoBoardSpec) -> Optional[DetectedView]:
    """在灰度图中检测 ChArUco 角点；未检出返回 None。"""
    if gray is None or gray.size == 0:
        return None
    detector = cached_detector(spec)
    corners, ids, _marker_corners, _marker_ids = detector.detectBoard(gray)
    if corners is None or ids is None or len(ids) == 0:
        return None
    corners = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2)
    ids = np.asarray(ids, dtype=np.int32).reshape(-1, 1)
    if not np.all(np.isfinite(corners)):
        return None
    return DetectedView(corners=corners, ids=ids)


def normalize_corners(corners: np.ndarray, image_size: Tuple[int, int]) -> np.ndarray:
    """把像素角点归一化到 [0,1]，用于覆盖度与重复视角判定。"""
    width = max(int(image_size[0]), 1)
    height = max(int(image_size[1]), 1)
    points = np.asarray(corners, dtype=np.float64).reshape(-1, 2)
    return points / np.array([width, height], dtype=np.float64)


def coverage_cells(
    corners: np.ndarray, image_size: Tuple[int, int], cells: int
) -> set:
    """返回角点命中的覆盖网格编号集合（cells x cells）。"""
    grid = max(int(cells), 1)
    points = normalize_corners(corners, image_size)
    hit = set()
    for x, y in points:
        column = min(max(int(x * grid), 0), grid - 1)
        row = min(max(int(y * grid), 0), grid - 1)
        hit.add((column, row))
    return hit


def is_duplicate_view(
    corners: np.ndarray,
    previous: Sequence[np.ndarray],
    image_size: Tuple[int, int],
    threshold: float,
) -> bool:
    """判断新视图是否与已有视图过于接近（归一化角点均方距离小于阈值）。"""
    if threshold <= 0.0 or not previous:
        return False
    new_norm = normalize_corners(corners, image_size)
    for other in previous:
        old_norm = normalize_corners(other, image_size)
        count = min(len(new_norm), len(old_norm))
        if count == 0:
            continue
        diff = new_norm[:count] - old_norm[:count]
        distance = float(np.mean(np.sum(diff * diff, axis=1)))
        if distance < float(threshold):
            return True
    return False


def view_reprojection_rms(
    object_points: np.ndarray,
    image_points: np.ndarray,
    rvec: np.ndarray,
    tvec: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> float:
    """计算单个视图的重投影误差 RMS（像素）。"""
    projected, _ = cv2.projectPoints(
        object_points, rvec, tvec, camera_matrix, dist_coeffs
    )
    projected = np.asarray(projected, dtype=np.float64).reshape(-1, 2)
    observed = np.asarray(image_points, dtype=np.float64).reshape(-1, 2)
    if projected.shape != observed.shape or projected.size == 0:
        return float("inf")
    diff = projected - observed
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def calibrate_from_views(
    views: Sequence[DetectedView],
    image_size: Tuple[int, int],
    spec: CharucoBoardSpec,
    min_views: int = 15,
    coverage_cells_n: int = 3,
    coverage_min_cells: int = 6,
) -> Tuple[CameraCalibration, List[str]]:
    """用多个视图做内参标定，返回结果与警告列表。"""
    if len(views) < max(int(min_views), 3):
        raise CalibrationError(
            f"有效视图不足：需要至少 {max(int(min_views), 3)} 个，当前 {len(views)} 个，请继续采集"
        )
    board = make_charuco_board(spec)
    chessboard_corners = np.asarray(board.getChessboardCorners(), dtype=np.float64)
    object_points: List[np.ndarray] = []
    image_points: List[np.ndarray] = []
    for view in views:
        ids = np.asarray(view.ids, dtype=np.int64).ravel()
        pts = np.asarray(view.corners, dtype=np.float64).reshape(-1, 2)
        if ids.size == 0 or ids.size != pts.shape[0]:
            raise CalibrationError("角点与角点编号数量不一致，标定中止")
        if ids.min() < 0 or ids.max() >= chessboard_corners.shape[0]:
            raise CalibrationError("角点编号超出标定板范围，标定中止")
        if not np.all(np.isfinite(pts)):
            raise CalibrationError("角点包含非有限值，标定中止")
        # cv2.calibrateCamera 要求 Point3f/Point2f（float32）
        object_points.append(chessboard_corners[ids].astype(np.float32))
        image_points.append(pts.astype(np.float32))

    width, height = int(image_size[0]), int(image_size[1])
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        (width, height),
        None,
        None,
    )
    if not np.all(np.isfinite(camera_matrix)) or not np.all(np.isfinite(dist_coeffs)):
        raise CalibrationError("标定结果包含非有限值，已拒绝保存")

    per_view = [
        view_reprojection_rms(objp, imgp, rvec, tvec, camera_matrix, dist_coeffs)
        for objp, imgp, rvec, tvec in zip(object_points, image_points, rvecs, tvecs)
    ]
    if not all(np.isfinite(per_view)):
        raise CalibrationError("个别视图重投影误差为非有限值，已拒绝保存")

    hit: set = set()
    for view in views:
        hit |= coverage_cells(view.corners, image_size, coverage_cells_n)

    warnings: List[str] = []
    if len(hit) < int(coverage_min_cells):
        warnings.append(
            f"角点覆盖不足：只命中 {len(hit)}/{int(coverage_cells_n) ** 2} 个网格，"
            "建议补拍画面四角与边缘的倾斜视图"
        )
    worst = max(per_view) if per_view else 0.0
    if worst > 1.5:
        warnings.append(f"最差视图重投影误差 {worst:.2f}px 偏大，建议重拍该角度")

    calibration = CameraCalibration(
        camera_matrix=np.asarray(camera_matrix, dtype=np.float64),
        dist_coeffs=np.asarray(dist_coeffs, dtype=np.float64),
        image_size=(width, height),
        rms_px=float(rms),
        per_view_rms_px=[float(v) for v in per_view],
        num_views=len(views),
        coverage_cells_hit=len(hit),
        board=spec,
    )
    return calibration, warnings


def backup_path(path: Path) -> Path:
    """生成备份路径：<name>.<时间戳>.bak<suffix>。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}")


def save_calibration(calibration: CameraCalibration, path: Any) -> Path:
    """保存标定文件（JSON）；覆盖前自动备份。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = backup_path(target)
        shutil.copy2(target, backup)
        LOGGER.info("已备份旧标定文件：%s", backup)
    payload = calibration.to_dict()
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return target


def load_calibration(path: Any) -> CameraCalibration:
    """读取标定文件；版本/结构非法时抛出中文错误。"""
    target = Path(path)
    if not target.is_file():
        raise CalibrationError(f"找不到摄像头标定文件：{target}，请先运行 --calibrate-camera")
    with open(target, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise CalibrationError("摄像头标定文件必须是 JSON 对象")
    version = int(raw.get("schema_version", -1))
    if version != SCHEMA_VERSION:
        raise CalibrationError(
            f"摄像头标定文件版本 {version} 与当前版本 {SCHEMA_VERSION} 不兼容，请重新标定"
        )
    try:
        image_size = (int(raw["image_size"][0]), int(raw["image_size"][1]))
        camera_matrix = np.asarray(raw["camera_matrix"], dtype=np.float64).reshape(3, 3)
        dist_coeffs = np.asarray(raw["dist_coeffs"], dtype=np.float64).reshape(1, -1)
        board_raw = raw.get("board") or {}
        metrics = raw.get("metrics") or {}
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationError(f"摄像头标定文件结构非法：{exc}") from exc
    if not np.all(np.isfinite(camera_matrix)) or not np.all(np.isfinite(dist_coeffs)):
        raise CalibrationError("摄像头标定文件包含非有限值")
    board = CharucoBoardSpec(
        dictionary=str(board_raw.get("dictionary", "DICT_5X5_50")),
        squares_x=int(board_raw.get("squares_x", 8)),
        squares_y=int(board_raw.get("squares_y", 6)),
        square_length_m=float(board_raw.get("square_length_m", 0.025)),
        marker_length_m=float(board_raw.get("marker_length_m", 0.018)),
    )
    return CameraCalibration(
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=image_size,
        rms_px=float(metrics.get("rms_px", 0.0)),
        per_view_rms_px=[float(v) for v in (metrics.get("per_view_rms_px") or [])],
        num_views=int(metrics.get("num_views", 0)),
        coverage_cells_hit=int(metrics.get("coverage_cells_hit", 0)),
        board=board,
        schema_version=version,
        saved_at=str(raw.get("saved_at", "")),
    )


def image_size_matches(calibration: CameraCalibration, image_size: Tuple[int, int]) -> bool:
    """标定分辨率是否与当前画面一致（必须一致才能使用）。"""
    return (int(calibration.image_size[0]), int(calibration.image_size[1])) == (
        int(image_size[0]),
        int(image_size[1]),
    )


def write_board_image(
    spec: CharucoBoardSpec, path: Any, pixels_per_meter: float = 4000.0
) -> Path:
    """导出可打印的标定板 PNG：**严格按物理尺寸渲染**，标注文字放在板外的留白里。

    方格像素边长 = ``square_length_m * pixels_per_meter``（默认 4000 px/m，即 0.25 mm/px），
    因此用户用直尺核验整板尺寸即可确认打印比例是否正确。若 Pillow 可用，还会写入 PNG 的
    物理分辨率元数据，使打印机的“实际大小 / 100%”更接近真实尺寸。
    """
    image, px_per_meter_x, px_per_meter_y = render_board_image(spec, pixels_per_meter)
    expected = spec.square_length_m * pixels_per_meter
    measured = measure_rendered_square_px(image, spec)
    if measured is not None and abs(measured - expected) > 0.5:
        raise CalibrationError(
            f"标定板渲染自检失败：实测方格 {measured:.2f}px，期望 {expected:.2f}px，已拒绝导出"
        )
    board_width_mm = spec.squares_x * spec.square_length_m * 1000.0
    board_height_mm = spec.squares_y * spec.square_length_m * 1000.0
    lines = [
        f"ChArUco {spec.squares_x}x{spec.squares_y}  square={spec.square_length_m * 1000:.2f}mm"
        f"  marker={spec.marker_length_m * 1000:.2f}mm  dict={spec.dictionary}",
        f"Board size on paper: {board_width_mm:.1f} mm x {board_height_mm:.1f} mm"
        f"  (1 pixel = {1000.0 / float(pixels_per_meter):.3f} mm)",
        "PRINT AT 100% SCALE (ACTUAL SIZE) - DO NOT USE FIT TO PAGE",
        "After printing, measure several squares with a ruler; they MUST match the value above.",
    ]
    pad = max(int(round(0.004 * pixels_per_meter)), 8)
    line_height = max(int(round(0.0075 * pixels_per_meter)), 12)
    band = line_height * len(lines) + pad
    canvas = cv2.copyMakeBorder(image, pad, band, pad, pad, cv2.BORDER_CONSTANT, value=255)
    canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    for index, text in enumerate(lines):
        cv2.putText(
            canvas,
            text,
            (pad, canvas.shape[0] - band + pad + line_height * (index + 1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_png(target, canvas, px_per_meter_x, px_per_meter_y)
    return target


def render_board_image(
    spec: CharucoBoardSpec, pixels_per_meter: float = 4000.0
) -> Tuple[np.ndarray, float, float]:
    """渲染标定板灰度图；返回 ``(image, 横向 px/m, 纵向 px/m)``。

    必须先确认渲染出的方格像素尺寸与物理尺寸严格一致：OpenCV 的
    ``generateImage(outSize, marginSize)`` 会在给定外框内**缩掉**留白，若直接把留白
    算进外框，打印出来的方格就不是配置里的物理边长，标定会静默失真。
    """
    if pixels_per_meter <= 0:
        raise CalibrationError("pixels_per_meter 必须为正数")
    board = make_charuco_board(spec)
    width = int(round(spec.squares_x * spec.square_length_m * pixels_per_meter))
    height = int(round(spec.squares_y * spec.square_length_m * pixels_per_meter))
    if width <= 0 or height <= 0:
        raise CalibrationError("标定板渲染尺寸非法，请检查方格边长与 squares_x/squares_y")
    image = board.generateImage((width, height), marginSize=0, borderBits=1)
    if image.shape[0] != height or image.shape[1] != width:
        raise CalibrationError(
            f"标定板渲染尺寸异常：得到 {image.shape[1]}x{image.shape[0]}，期望 {width}x{height}"
        )
    actual_x = width / float(spec.squares_x)
    actual_y = height / float(spec.squares_y)
    if abs(actual_x - spec.square_length_m * pixels_per_meter) > 0.5 or abs(
        actual_y - spec.square_length_m * pixels_per_meter
    ) > 0.5:
        raise CalibrationError(
            f"标定板渲染比例异常：横向 {actual_x:.2f}px/格，纵向 {actual_y:.2f}px/格"
        )
    return image, width / (spec.squares_x * spec.square_length_m), height / (
        spec.squares_y * spec.square_length_m
    )


def measure_rendered_square_px(image: np.ndarray, spec: CharucoBoardSpec) -> Optional[float]:
    """在渲染出的标定板图上实测相邻角点间距（像素），用于自检渲染比例；无法测量时返回 None。"""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    view = detect_view(gray, spec)
    if view is None or view.count < 2:
        return None
    ids = np.asarray(view.ids, dtype=np.int64).ravel()
    points = np.asarray(view.corners, dtype=np.float64).reshape(-1, 2)
    lookup = {int(marker_id): points[index] for index, marker_id in enumerate(ids)}
    if 0 in lookup and 1 in lookup:
        return float(np.linalg.norm(lookup[1] - lookup[0]))
    return None


def _write_png(target: Path, image: np.ndarray, px_per_meter_x: float, px_per_meter_y: float) -> None:
    """写 PNG；Pillow 可用时附带物理分辨率元数据，否则退回 OpenCV（像素尺寸不受影响）。"""
    try:
        from PIL import Image  # 可选依赖：仅用于写入物理分辨率
    except Exception:
        Image = None
    if Image is not None:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        dpi_x = float(px_per_meter_x) / 39.37007874015748
        dpi_y = float(px_per_meter_y) / 39.37007874015748
        Image.fromarray(rgb).save(str(target), format="PNG", dpi=(dpi_x, dpi_y))
        return
    if not cv2.imwrite(str(target), image):
        raise CalibrationError(f"无法写入标定板图片：{target}")
