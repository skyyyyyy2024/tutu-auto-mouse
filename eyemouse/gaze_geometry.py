"""几何视线估计：由眼角中点后移得到眼球中心，在头坐标系求视线角度。

约定：MediaPipe 的 ``z`` 越小表示越靠近摄像头，因此眼球中心（在虹膜之后）取
眼角中点沿 ``+z``（远离摄像头）后移 ``eyeball_offset * scale``；视线前向为 ``-z``。
角度在头坐标系下计算：先用头部旋转矩阵的转置把相机系方向旋回头坐标系，
因此 ``gaze_yaw`` / ``gaze_pitch`` 表示「眼在头内」的角度，单位为度。
``scale`` 取两外眼角 3D 距离。所有量都是相对估计。
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional, Tuple

import numpy as np

from .face_profile import metric_points, scale_reference
from .landmarks import (
    EYE_A_INNER,
    EYE_A_OUTER,
    EYE_B_INNER,
    EYE_B_OUTER,
    IRIS_A_CENTER,
    IRIS_B_CENTER,
    FaceLandmarks,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_EYEBALL_OFFSET = 0.5

# (外眼角, 内眼角, 虹膜中心)，顺序保证 x 方向语义一致
_EYES = (
    (EYE_A_OUTER, EYE_A_INNER, IRIS_A_CENTER),
    (EYE_B_INNER, EYE_B_OUTER, IRIS_B_CENTER),
)


def _fallback_forward(scale: float, eyeball_offset: float) -> float:
    value = float(eyeball_offset) * float(scale)
    return value if value > 1e-6 else 0.0


def estimate_gaze(
    face: FaceLandmarks,
    rotation: Optional[np.ndarray] = None,
    eyeball_offset: float = DEFAULT_EYEBALL_OFFSET,
) -> Tuple[float, float]:
    """估计头坐标系下的双眼平均视线角度 (gaze_yaw, gaze_pitch)，单位度。

    ``rotation`` 为头部旋转矩阵（头坐标系 -> 相机坐标系，来自 solvePnP）；
    为 None 时按正面处理。任何异常或非有限值都回退到 (0.0, 0.0)。
    """
    try:
        raw = getattr(face, "pts_3d", None)
        if raw is None:
            return (0.0, 0.0)
        metric = metric_points(face)
        if not np.all(np.isfinite(metric)):
            return (0.0, 0.0)
        scale = scale_reference(metric)
        if not np.isfinite(scale) or scale <= 0.0:
            return (0.0, 0.0)
        fallback = _fallback_forward(scale, eyeball_offset)
        if fallback <= 0.0:
            return (0.0, 0.0)
        rot = None
        if rotation is not None:
            candidate = np.asarray(rotation, dtype=np.float64)
            if candidate.shape == (3, 3) and np.all(np.isfinite(candidate)):
                rot = candidate
        yaws = []
        pitches = []
        for outer, inner, iris in _EYES:
            midpoint = (metric[outer] + metric[inner]) / 2.0
            center = midpoint + np.array([0.0, 0.0, float(eyeball_offset) * scale])
            direction = metric[iris] - center
            forward = -float(direction[2])
            if not np.isfinite(forward) or forward <= 1e-6:
                forward = fallback
            if rot is not None:
                direction = rot.T @ direction
                forward = -float(direction[2])
                if not np.isfinite(forward) or forward <= 1e-6:
                    forward = fallback
            yaw = math.degrees(math.atan2(float(direction[0]), forward))
            pitch = math.degrees(math.atan2(float(direction[1]), forward))
            if math.isfinite(yaw) and math.isfinite(pitch):
                yaws.append(yaw)
                pitches.append(pitch)
        if not yaws:
            return (0.0, 0.0)
        return (float(np.mean(yaws)), float(np.mean(pitches)))
    except Exception:
        LOGGER.debug("几何视线估计失败，回退到 (0, 0)", exc_info=True)
        return (0.0, 0.0)