"""特征提取：眼纵横比 EAR、虹膜比例，以及 14 维视线特征向量。"""

from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np

from .gaze_geometry import DEFAULT_EYEBALL_OFFSET, estimate_gaze
from .head_pose import HeadPose, HeadPoseEstimator, estimate_head_pose
from .landmarks import (
    EYE_A_DOWN,
    EYE_A_EAR,
    EYE_A_INNER,
    EYE_A_OUTER,
    EYE_A_UP,
    EYE_B_DOWN,
    EYE_B_EAR,
    EYE_B_INNER,
    EYE_B_OUTER,
    EYE_B_UP,
    IRIS_A_CENTER,
    IRIS_B_CENTER,
    NOSE_TIP,
    FaceLandmarks,
)

EPSILON = 1e-6

# 特征向量布局（14 维）：虹膜 4 + 均值 2 + 头姿 3 + 鼻尖平移 2 + 头部尺度 1 + 几何视线 2
FEATURE_DIM = 14
IRIS_SLICE = slice(0, 4)
# yaw/pitch/roll 三个分量（已除以 45，乘回 DEG_PER_UNIT 即得角度）
HEAD_POSE_SLICE = slice(6, 9)
HEAD_SCALE_INDEX = 11
# gaze_yaw/gaze_pitch 几何视线角度（同样已除以 DEG_PER_UNIT）
GAZE_SLICE = slice(12, 14)
DEG_PER_UNIT = 45.0


def _ear_for_eye(points: np.ndarray, indexes) -> float:
    """按 6 点公式计算单眼 EAR：(|p2-p6| + |p3-p5|) / (2*|p1-p4|)。"""
    p1, p2, p3, p4, p5, p6 = (points[index] for index in indexes)
    vertical = float(np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5))
    horizontal = float(np.linalg.norm(p1 - p4)) + EPSILON
    return vertical / (2.0 * horizontal)


def compute_ear(face: FaceLandmarks) -> Tuple[float, float]:
    """返回左右眼 EAR（图像左眼 A、图像右眼 B）。"""
    return (
        _ear_for_eye(face.pts_px, EYE_A_EAR),
        _ear_for_eye(face.pts_px, EYE_B_EAR),
    )


def _projection_ratio(start: np.ndarray, end: np.ndarray, point: np.ndarray) -> float:
    """点 point 在 start->end 有向线段上的投影比例（带防零除）。"""
    direction = end - start
    denominator = float(direction @ direction) + EPSILON
    return float((point - start) @ direction) / denominator


def compute_iris_ratio(face: FaceLandmarks) -> np.ndarray:
    """返回 [xA, yA, xB, yB]：虹膜在眼角连线/上下眼睑之间的比例。

    x 方向统一为「从图像左到图像右」，因此 A 眼取 33->133（outer->inner），
    B 眼取 362->263（inner->outer），两只眼语义一致。
    """
    points = face.pts_px
    x_a = _projection_ratio(points[EYE_A_OUTER], points[EYE_A_INNER], points[IRIS_A_CENTER])
    y_a = _projection_ratio(points[EYE_A_UP], points[EYE_A_DOWN], points[IRIS_A_CENTER])
    x_b = _projection_ratio(points[EYE_B_INNER], points[EYE_B_OUTER], points[IRIS_B_CENTER])
    y_b = _projection_ratio(points[EYE_B_UP], points[EYE_B_DOWN], points[IRIS_B_CENTER])
    return np.array([x_a, y_a, x_b, y_b], dtype=np.float64)


def compute_head_scale(face: FaceLandmarks) -> float:
    """头部尺度：两外眼角像素距离 / 图像宽度（无量纲），用于补偿前后移动。"""
    if face.img_w <= 0:
        return float("nan")
    outer_a = face.pts_px[EYE_A_OUTER]
    outer_b = face.pts_px[EYE_B_OUTER]
    return float(np.linalg.norm(outer_b - outer_a)) / float(face.img_w)


def build_feature_vector(
    face: FaceLandmarks,
    pose: Optional[HeadPose] = None,
    profile: Any = None,
    eyeball_offset: float = DEFAULT_EYEBALL_OFFSET,
    focal_scale: float = 1.0,
) -> Optional[np.ndarray]:
    """拼接 14 维特征向量。

    布局：虹膜 4 + 均值 2 + 头姿 3 + 鼻尖平移 2 + 头部尺度 1 + 几何视线 2。
    ``pose`` 可传入有状态估计器的结果（复用初值并做时间平滑）；为 None 时用
    无状态估计。任何异常或非有限值都返回 None。
    """
    try:
        x_a, y_a, x_b, y_b = compute_iris_ratio(face)
        if pose is None:
            pose = HeadPoseEstimator(profile=profile, focal_scale=focal_scale).estimate(face)
        yaw, pitch, roll = pose.angles()
        rotation = getattr(pose, "rotation", None)
        if not getattr(pose, "trustworthy", False):
            rotation = None  # 位姿不可信时不旋转，避免把误差放大到视线角度
        gaze_yaw, gaze_pitch = estimate_gaze(
            face, rotation=rotation, eyeball_offset=eyeball_offset
        )
        nose_x, nose_y = face.pts_norm[NOSE_TIP][:2]
        head_scale = compute_head_scale(face)
        features = np.array(
            [
                x_a,
                y_a,
                x_b,
                y_b,
                (x_a + x_b) / 2.0,
                (y_a + y_b) / 2.0,
                yaw / DEG_PER_UNIT,
                pitch / DEG_PER_UNIT,
                roll / DEG_PER_UNIT,
                nose_x,
                nose_y,
                head_scale,
                gaze_yaw / DEG_PER_UNIT,
                gaze_pitch / DEG_PER_UNIT,
            ],
            dtype=np.float64,
        )
    except Exception:
        return None
    if not np.all(np.isfinite(features)):
        return None
    return features


__all__ = [
    "FEATURE_DIM",
    "IRIS_SLICE",
    "HEAD_POSE_SLICE",
    "HEAD_SCALE_INDEX",
    "GAZE_SLICE",
    "DEG_PER_UNIT",
    "compute_ear",
    "compute_iris_ratio",
    "compute_head_scale",
    "build_feature_vector",
    "estimate_head_pose",
]