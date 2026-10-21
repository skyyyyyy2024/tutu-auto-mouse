"""用 solvePnP 从人脸关键点估计头部姿态 (yaw, pitch, roll)，单位度。

支持两种 3D 模板：

- 通用模板 ``MODEL_POINTS``（毫米级经验值，向后兼容）；
- 个人模板 ``FaceProfile``（无量纲，单位为两外眼角距离）。

旋转量与模板尺度无关，因此两种模板估计出的角度可直接比较；焦距默认取图像宽度，
可由 ``focal_scale`` 覆盖。``HeadPoseEstimator`` 用上一帧结果作为 solvePnP 初值，
并对角度做带 ±180° 回绕处理的时间平滑，同时输出重投影误差。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from .landmarks import (
    CHIN,
    EYE_A_OUTER,
    EYE_B_OUTER,
    MOUTH_A,
    MOUTH_B,
    NOSE_TIP,
    FaceLandmarks,
)

LOGGER = logging.getLogger(__name__)

# 通用 3D 人脸模型点（单位 mm），顺序与 MODEL_INDEXES 一一对应
MODEL_INDEXES = [NOSE_TIP, CHIN, EYE_A_OUTER, EYE_B_OUTER, MOUTH_A, MOUTH_B]
MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),  # 鼻尖
        (0.0, -63.6, -12.5),  # 下巴
        (-43.3, 32.7, -26.0),  # 眼角 A 外侧
        (43.3, 32.7, -26.0),  # 眼角 B 外侧
        (-28.9, -28.9, -24.1),  # 嘴角 A
        (28.9, -28.9, -24.1),  # 嘴角 B
    ],
    dtype=np.float64,
)

DEFAULT_REPROJECTION_ERROR_PX = 8.0
DEFAULT_SMOOTHING_ALPHA = 0.6


def wrap_angle_delta(delta: float) -> float:
    """把角度差归一到 [-180, 180)，用于处理 ±180° 回绕。"""
    return (float(delta) + 180.0) % 360.0 - 180.0


def normalize_angle(angle: float) -> float:
    """把角度归一到 [-180, 180)。"""
    return wrap_angle_delta(float(angle))


def smooth_angle(previous: float, target: float, alpha: float) -> float:
    """按最短弧方向对角度做 EMA 平滑，alpha 越大越贴近目标。"""
    ratio = float(min(max(alpha, 0.0), 1.0))
    return normalize_angle(float(previous) + ratio * wrap_angle_delta(float(target) - float(previous)))


def _normalize_angle(angle: float) -> float:
    """向后兼容的旧接口：把角度归一到 [-90, 90]。"""
    while angle > 90.0:
        angle -= 180.0
    while angle < -90.0:
        angle += 180.0
    return angle


@dataclass
class HeadPose:
    """一帧头姿结果：角度（度）、重投影误差、可信标记与位姿量。"""

    yaw: float
    pitch: float
    roll: float
    reprojection_error: float
    trustworthy: bool
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    rotation: Optional[np.ndarray] = None
    axis_length: float = 40.0

    def angles(self) -> Tuple[float, float, float]:
        """返回 (yaw, pitch, roll)。"""
        return (float(self.yaw), float(self.pitch), float(self.roll))


def _camera_matrix(face: FaceLandmarks, focal_scale: float) -> np.ndarray:
    focal = float(face.img_w) * float(focal_scale)
    return np.array(
        [
            [focal, 0.0, face.img_w / 2.0],
            [0.0, focal, face.img_h / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


class HeadPoseEstimator:
    """有状态头姿估计器：初值复用 + 角度时间平滑 + 重投影可信度。"""

    def __init__(
        self,
        profile: Any = None,
        focal_scale: float = 1.0,
        reprojection_error_px: float = DEFAULT_REPROJECTION_ERROR_PX,
        smoothing_alpha: float = DEFAULT_SMOOTHING_ALPHA,
    ) -> None:
        self.profile = profile
        self.focal_scale = float(focal_scale) if focal_scale else 1.0
        self.reprojection_error_px = float(reprojection_error_px)
        self.smoothing_alpha = float(min(max(smoothing_alpha, 0.0), 1.0))
        self._rvec: Optional[np.ndarray] = None
        self._tvec: Optional[np.ndarray] = None
        self._angles: Optional[Tuple[float, float, float]] = None
        self.last: Optional[HeadPose] = None

    def set_profile(self, profile: Any) -> None:
        """切换个人模板并重置初值（模板尺度变化后旧初值可能不适用）。"""
        self.profile = profile
        self.reset()

    def reset(self) -> None:
        """清空上一帧位姿与角度平滑状态。"""
        self._rvec = None
        self._tvec = None
        self._angles = None
        self.last = None

    def _template(self) -> Tuple[np.ndarray, Any]:
        profile = self.profile
        points = getattr(profile, "points_3d", None) if profile is not None else None
        indexes = getattr(profile, "point_indexes", None) if profile is not None else None
        if points is not None and indexes is not None and len(indexes) >= 4:
            array = np.asarray(points, dtype=np.float64)
            if array.ndim == 2 and array.shape[1] == 3 and array.shape[0] == len(indexes):
                return array, indexes
        return MODEL_POINTS, MODEL_INDEXES

    def estimate(self, face: FaceLandmarks) -> HeadPose:
        """估计头姿；失败时返回零姿态且 trustworthy=False。"""
        zero = HeadPose(0.0, 0.0, 0.0, float("inf"), False)
        if face.img_w <= 0 or face.img_h <= 0:
            return zero
        model_points, indexes = self._template()
        image_points = np.asarray(face.pts_px[indexes], dtype=np.float64)
        if not np.all(np.isfinite(image_points)):
            LOGGER.warning("头部姿态估计：关键点含非有限值，返回零姿态")
            return zero
        camera_matrix = _camera_matrix(face, self.focal_scale)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        use_guess = self._rvec is not None and self._tvec is not None
        rvec_in = self._rvec.copy() if use_guess else None
        tvec_in = self._tvec.copy() if use_guess else None
        try:
            success, rotation_vector, translation = cv2.solvePnP(
                model_points,
                image_points,
                camera_matrix,
                dist_coeffs,
                rvec_in,
                tvec_in,
                useExtrinsicGuess=use_guess,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
            if not success and use_guess:
                success, rotation_vector, translation = cv2.solvePnP(
                    model_points,
                    image_points,
                    camera_matrix,
                    dist_coeffs,
                    flags=cv2.SOLVEPNP_ITERATIVE,
                )
        except cv2.error as exc:
            LOGGER.warning("头部姿态估计：solvePnP 失败（%s），返回零姿态", exc)
            return zero
        if not success:
            LOGGER.warning("头部姿态估计：solvePnP 未收敛，返回零姿态")
            return zero

        try:
            projected, _ = cv2.projectPoints(
                model_points, rotation_vector, translation, camera_matrix, dist_coeffs
            )
            residuals = projected.reshape(-1, 2) - image_points
            reprojection_error = float(np.sqrt(np.mean(np.sum(residuals * residuals, axis=1))))
        except cv2.error:
            reprojection_error = float("inf")

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        euler_angles = cv2.RQDecomp3x3(rotation_matrix)[0]
        raw_pitch = normalize_angle(float(euler_angles[0]))
        raw_yaw = normalize_angle(float(euler_angles[1]))
        raw_roll = normalize_angle(float(euler_angles[2]))
        if not all(np.isfinite([raw_yaw, raw_pitch, raw_roll])):
            LOGGER.warning("头部姿态估计：欧拉角非有限值，返回零姿态")
            return zero

        if self._angles is None:
            smooth = (raw_yaw, raw_pitch, raw_roll)
        else:
            previous = self._angles
            smooth = (
                smooth_angle(previous[0], raw_yaw, self.smoothing_alpha),
                smooth_angle(previous[1], raw_pitch, self.smoothing_alpha),
                smooth_angle(previous[2], raw_roll, self.smoothing_alpha),
            )
        self._angles = smooth
        self._rvec = rotation_vector
        self._tvec = translation
        trustworthy = bool(np.isfinite(reprojection_error)) and (
            reprojection_error <= self.reprojection_error_px
        )
        pose = HeadPose(
            yaw=float(smooth[0]),
            pitch=float(smooth[1]),
            roll=float(smooth[2]),
            reprojection_error=float(reprojection_error),
            trustworthy=trustworthy,
            rvec=rotation_vector.reshape(3),
            tvec=translation.reshape(3),
            rotation=rotation_matrix,
            axis_length=40.0 if model_points is MODEL_POINTS else 0.5,
        )
        self.last = pose
        return pose


def estimate_head_pose(
    face: FaceLandmarks,
    profile: Any = None,
    focal_scale: float = 1.0,
) -> Tuple[float, float, float]:
    """无状态估计 (yaw, pitch, roll)；失败返回 (0.0, 0.0, 0.0)。"""
    estimator = HeadPoseEstimator(profile=profile, focal_scale=focal_scale)
    pose = estimator.estimate(face)
    return pose.angles()