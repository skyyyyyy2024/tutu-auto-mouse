"""个人面部标定：采集稳定点的 3D 中位数模板，按两外眼角距离归一化。

坐标说明：MediaPipe 的 ``pts_3d`` 是 ``(x/width, y/height, z/width)`` 的各向异性
归一化坐标，本模块先还原为各向同性像素尺度 ``(x*width, y*height, z*width)``，
再除以两外眼角距离得到无量纲模板。``z`` 只是相对深度估计，不是绝对真值。
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np

from .landmarks import EYE_A_OUTER, EYE_B_OUTER, STABLE_POINT_INDEXES, FaceLandmarks

LOGGER = logging.getLogger(__name__)

PROFILE_VERSION = 1
ESC_KEY = 27
MIN_PROFILE_FRAMES = 10


def _call_ui(ui: Any, name: str, *args: Any) -> Any:
    """调用 UI 上的可选方法；未实现时返回 None。"""
    callback = getattr(ui, name, None)
    if callback is None:
        return None
    return callback(*args)


def _resolve_data_file(path: Any, root: Path) -> Path:
    """把模板文件路径解析为绝对路径，并要求位于 <root>/data/ 之内。"""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    data_dir = (root / "data").resolve()
    if resolved == data_dir or data_dir not in resolved.parents:
        raise ValueError(f"面部模板文件必须位于工作区 data/ 目录内，当前为 {resolved}")
    return resolved


def metric_points(face: FaceLandmarks) -> np.ndarray:
    """把归一化 3D 关键点还原为各向同性像素尺度坐标 (478, 3)。"""
    width = float(face.img_w)
    height = float(face.img_h)
    raw = np.asarray(face.pts_3d, dtype=np.float64)
    metric = np.empty_like(raw[:, :3])
    metric[:, 0] = raw[:, 0] * width
    metric[:, 1] = raw[:, 1] * height
    metric[:, 2] = raw[:, 2] * width
    return metric


def scale_reference(metric: np.ndarray) -> float:
    """两外眼角（33 与 263）3D 距离，作为尺度参考。"""
    return float(np.linalg.norm(metric[EYE_B_OUTER] - metric[EYE_A_OUTER]))


def extract_normalized(face: FaceLandmarks) -> Optional[Tuple[np.ndarray, float]]:
    """返回稳定点各向同性坐标（按两外眼角距离归一化）与尺度参考。

    无效或非有限时返回 None。
    """
    if face.img_w <= 0 or face.img_h <= 0:
        return None
    metric = metric_points(face)
    scale = scale_reference(metric)
    if not np.isfinite(scale) or scale <= 0.0:
        return None
    points = metric[STABLE_POINT_INDEXES] / scale
    if not np.all(np.isfinite(points)):
        return None
    return points, scale


@dataclass
class FaceProfile:
    """个人面部 3D 模板（无量纲，单位为两外眼角距离）。"""

    points_3d: np.ndarray  # (N, 3)
    point_indexes: List[int] = field(default_factory=lambda: list(STABLE_POINT_INDEXES))
    sample_frames: int = 0
    quality: dict = field(default_factory=dict)
    version: int = PROFILE_VERSION
    created: str = ""

    def to_json(self) -> dict:
        """转换为可 JSON 序列化的字典。"""
        return {
            "version": int(self.version),
            "created": self.created or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "point_indexes": [int(value) for value in self.point_indexes],
            "points_3d": [[float(value) for value in row] for row in self.points_3d],
            "sample_frames": int(self.sample_frames),
            "quality": dict(self.quality),
        }

    @classmethod
    def from_json(cls, payload: dict) -> "FaceProfile":
        """由字典构造模板；缺字段抛中文 ValueError。"""
        points = np.asarray(payload["points_3d"], dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("面部模板 points_3d 必须是 (N, 3) 数组")
        indexes = [int(value) for value in payload.get("point_indexes", STABLE_POINT_INDEXES)]
        if len(indexes) != points.shape[0]:
            raise ValueError("面部模板 point_indexes 数量与 points_3d 不一致")
        return cls(
            points_3d=points,
            point_indexes=indexes,
            sample_frames=int(payload.get("sample_frames", 0)),
            quality=dict(payload.get("quality") or {}),
            version=int(payload.get("version", PROFILE_VERSION)),
            created=str(payload.get("created", "")),
        )

    def save(self, path: Any, root: Any = None) -> Path:
        """保存为 JSON；覆盖前先把旧文件复制为带时间戳的 .bak.json。"""
        root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
        target = _resolve_data_file(path, root_path)
        if target.exists():
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup = target.with_name(f"{target.stem}.{timestamp}.bak.json")
            shutil.copy2(target, backup)
            LOGGER.info("旧面部模板已备份到 %s", backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_json()
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        LOGGER.info("面部模板已保存到绝对路径 %s", target)
        return target

    @classmethod
    def load(cls, path: Any, root: Any = None) -> "FaceProfile":
        """从 JSON 载入模板；文件不存在抛 FileNotFoundError。"""
        root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
        target = _resolve_data_file(path, root_path)
        if not target.is_file():
            raise FileNotFoundError(f"面部模板文件不存在：{target}")
        with open(target, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        profile = cls.from_json(payload)
        LOGGER.info("已载入面部模板：%s（%d 帧）", target, profile.sample_frames)
        return profile


class FaceProfileCollector:
    """累积有效帧并取稳定点中位数，生成个人模板。"""

    def __init__(self, samples: int = 150) -> None:
        self.samples = max(int(samples), MIN_PROFILE_FRAMES)
        self._stack: List[np.ndarray] = []
        self._scales: List[float] = []

    def __len__(self) -> int:
        return len(self._stack)

    @property
    def count(self) -> int:
        """当前有效帧数。"""
        return len(self._stack)

    @property
    def full(self) -> bool:
        """是否已达目标帧数。"""
        return len(self._stack) >= self.samples

    def add(self, face: FaceLandmarks) -> bool:
        """加入一帧；无效帧（无脸/非有限）返回 False 且不计数。"""
        extracted = extract_normalized(face)
        if extracted is None:
            return False
        points, scale = extracted
        self._stack.append(points)
        self._scales.append(float(scale))
        return True

    def build(self) -> FaceProfile:
        """取逐点中位数生成模板，并计算跨帧稳定性质量指标。"""
        if len(self._stack) < MIN_PROFILE_FRAMES:
            raise RuntimeError(
                f"面部标定有效帧不足（{len(self._stack)}/{MIN_PROFILE_FRAMES}），请重试"
            )
        stacked = np.stack(self._stack, axis=0)
        template = np.median(stacked, axis=0)
        point_std = np.linalg.norm(np.std(stacked, axis=0), axis=1)
        quality = {
            "point_std": float(np.median(point_std)),
            "point_std_max": float(np.max(point_std)),
            "scale_reference_px": float(np.median(self._scales)),
        }
        return FaceProfile(
            points_3d=template,
            point_indexes=list(STABLE_POINT_INDEXES),
            sample_frames=int(len(self._stack)),
            quality=quality,
        )


class FaceProfiler:
    """驱动摄像头完成面部标定：正对镜头、中性表情，采集到目标帧数。"""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg

    def run(self, camera: Any, detector: Any, ui: Any) -> Optional[FaceProfile]:
        """执行面部标定；ESC 取消返回 None，有效帧不足抛 RuntimeError。"""
        target = int(getattr(self.cfg, "samples", 150))
        collector = FaceProfileCollector(target)
        _call_ui(
            ui,
            "show_text",
            "Face calibration: look straight at the camera, neutral expression",
        )
        start = time.perf_counter()
        timeout = max(20.0, target / 15.0)
        while not collector.full and time.perf_counter() - start < timeout:
            frame = camera.read()
            if frame is not None:
                face = detector.detect(frame)
                if face is not None and collector.add(face):
                    _call_ui(ui, "show_progress", collector.count, collector.samples)
            if _call_ui(ui, "pump", 1) == ESC_KEY:
                LOGGER.info("面部标定被 ESC 取消")
                return None
        if collector.count < MIN_PROFILE_FRAMES:
            raise RuntimeError("面部标定有效帧不足，请检查光线与摄像头后重试（可按 ESC 取消）")
        profile = collector.build()
        LOGGER.info(
            "面部标定完成：%d 帧，point_std=%.4f，scale=%.1fpx",
            profile.sample_frames,
            profile.quality.get("point_std", float("nan")),
            profile.quality.get("scale_reference_px", float("nan")),
        )
        return profile