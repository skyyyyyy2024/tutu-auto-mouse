"""特征提取测试：EAR 数值、虹膜比例、14 维特征向量与 NaN 处理。"""

from __future__ import annotations

import numpy as np
import pytest

from eyemouse.features import build_feature_vector, compute_ear, compute_iris_ratio
from eyemouse.landmarks import (
    CHIN,
    EYE_A_DOWN,
    EYE_A_INNER,
    EYE_A_OUTER,
    EYE_A_UP,
    EYE_B_DOWN,
    EYE_B_INNER,
    EYE_B_OUTER,
    EYE_B_UP,
    FACE_POINT_COUNT,
    IRIS_A_CENTER,
    IRIS_B_CENTER,
    MOUTH_A,
    MOUTH_B,
    NOSE_TIP,
    FaceLandmarks,
)


def make_face(points_px: dict) -> FaceLandmarks:
    """由 {索引: (x, y)} 构造假 FaceLandmarks（像素坐标即给定值）。"""
    count = FACE_POINT_COUNT
    px = np.zeros((count, 2), dtype=np.float64)
    norm = np.zeros((count, 2), dtype=np.float64)
    three = np.zeros((count, 3), dtype=np.float64)
    for index, (x, y) in points_px.items():
        px[index] = (float(x), float(y))
        norm[index] = (float(x) / 1000.0, float(y) / 1000.0)
    return FaceLandmarks(pts_norm=norm, pts_px=px, pts_3d=three, img_w=1000, img_h=1000)


def frontal_face_points() -> dict:
    """构造一个近似正面的人脸关键点集合（覆盖 EAR/虹膜/头姿所需索引）。"""
    return {
        NOSE_TIP: (500, 500),
        CHIN: (500, 560),
        MOUTH_A: (460, 545),
        MOUTH_B: (540, 545),
        EYE_A_OUTER: (420, 470),
        EYE_A_INNER: (460, 470),
        EYE_A_UP: (440, 455),
        EYE_A_DOWN: (440, 485),
        IRIS_A_CENTER: (440, 470),
        EYE_B_INNER: (540, 470),
        EYE_B_OUTER: (580, 470),
        EYE_B_UP: (560, 455),
        EYE_B_DOWN: (560, 485),
        IRIS_B_CENTER: (560, 470),
        # EAR 专用点（160/158/153/144 与 385/387/373/380）
        160: (430, 458),
        158: (450, 458),
        153: (430, 482),
        144: (450, 482),
        385: (550, 458),
        387: (570, 458),
        373: (550, 482),
        380: (570, 482),
    }


def test_compute_ear_matches_formula():
    face = make_face(
        {
            33: (0, 50),
            160: (40, 30),
            158: (60, 30),
            133: (100, 50),
            153: (40, 70),
            144: (60, 70),
            362: (200, 50),
            385: (240, 30),
            387: (260, 30),
            263: (300, 50),
            373: (240, 70),
            380: (260, 70),
        }
    )
    ear_a, ear_b = compute_ear(face)
    vertical = np.hypot(20.0, 40.0) + np.hypot(20.0, 40.0)
    expected = vertical / (2.0 * 100.0)
    assert ear_a == pytest.approx(expected, rel=1e-6)
    assert ear_b == pytest.approx(expected, rel=1e-6)


def test_compute_ear_eyes_closed_is_smaller():
    open_face = make_face(frontal_face_points())
    closed_points = frontal_face_points()
    closed_points[160] = (430, 470)
    closed_points[158] = (450, 470)
    closed_points[153] = (430, 470)
    closed_points[144] = (450, 470)
    closed_face = make_face(closed_points)
    open_ear, _ = compute_ear(open_face)
    closed_ear, _ = compute_ear(closed_face)
    assert closed_ear < open_ear


def test_compute_iris_ratio_known_projection():
    face = make_face(
        {
            33: (0, 50),
            133: (100, 50),
            159: (0, 0),
            145: (0, 100),
            468: (25, 30),
            362: (200, 50),
            263: (300, 50),
            386: (0, 0),
            374: (0, 100),
            473: (225, 60),
        }
    )
    ratios = compute_iris_ratio(face)
    assert ratios.shape == (4,)
    assert ratios[0] == pytest.approx(0.25, abs=1e-6)
    assert ratios[1] == pytest.approx(0.30, abs=1e-6)
    assert ratios[2] == pytest.approx(0.25, abs=1e-6)
    assert ratios[3] == pytest.approx(0.60, abs=1e-6)


def test_x_ratio_is_left_to_right_for_both_eyes():
    face = make_face(
        {
            33: (0, 0),
            133: (100, 0),
            468: (100, 0),  # 虹膜在最右
            362: (200, 0),
            263: (300, 0),
            473: (300, 0),  # 虹膜在最右
        }
    )
    ratios = compute_iris_ratio(face)
    assert ratios[0] == pytest.approx(1.0, abs=1e-4)
    assert ratios[2] == pytest.approx(1.0, abs=1e-4)


def test_feature_vector_shape_and_finite():
    face = make_face(frontal_face_points())
    vector = build_feature_vector(face)
    assert vector is not None
    assert vector.shape == (14,)
    assert np.all(np.isfinite(vector))
    assert vector[4] == pytest.approx((vector[0] + vector[2]) / 2.0, abs=1e-9)
    assert vector[5] == pytest.approx((vector[1] + vector[3]) / 2.0, abs=1e-9)
    assert vector[9] == pytest.approx(0.5, abs=1e-9)
    assert vector[10] == pytest.approx(0.5, abs=1e-9)
    # 头部尺度 = 两外眼角像素距离 / 图像宽度 = (580-420)/1000
    assert vector[11] == pytest.approx(0.16, abs=1e-9)


def test_feature_vector_nan_returns_none():
    face = make_face(frontal_face_points())
    face.pts_px[IRIS_A_CENTER] = np.nan
    assert build_feature_vector(face) is None


def test_landmark_detector_enables_refine_landmarks():
    import inspect

    from eyemouse.landmarks import LandmarkDetector

    signature = inspect.signature(LandmarkDetector.__init__)
    assert signature.parameters["refine_landmarks"].default is True
