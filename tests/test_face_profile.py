"""个人面部标定、PnP 头姿升级与几何视线测试（合成 3D 点，不开摄像头）。"""

from __future__ import annotations

import json
import math

import cv2
import numpy as np
import pytest

from eyemouse.calibration import CalibrationModel, ModelVersionMismatchError
from eyemouse.config import config_from_dict
from eyemouse.face_profile import (
    FaceProfile,
    FaceProfileCollector,
    FaceProfiler,
    extract_normalized,
    metric_points,
    scale_reference,
)
from eyemouse.features import FEATURE_DIM, build_feature_vector
from eyemouse.gaze_geometry import estimate_gaze
from eyemouse.head_pose import (
    MODEL_INDEXES,
    MODEL_POINTS,
    HeadPoseEstimator,
    smooth_angle,
    wrap_angle_delta,
)
from eyemouse.landmarks import (
    EYE_A_INNER,
    EYE_A_OUTER,
    EYE_B_INNER,
    EYE_B_OUTER,
    IRIS_A_CENTER,
    IRIS_B_CENTER,
    STABLE_POINT_INDEXES,
    FaceLandmarks,
)

FRAME_W, FRAME_H = 1280, 720

# 20 个稳定点的基准 3D 位置（归一化坐标，两外眼角在 x=0.40 / 0.60）
_STABLE_BASE = {
    10: (0.50, 0.18, -0.05),
    151: (0.50, 0.24, -0.03),
    9: (0.50, 0.30, -0.02),
    8: (0.50, 0.33, -0.04),
    168: (0.50, 0.38, -0.02),
    6: (0.50, 0.42, 0.00),
    197: (0.50, 0.46, 0.01),
    195: (0.50, 0.50, 0.02),
    1: (0.50, 0.56, 0.05),
    4: (0.50, 0.60, 0.05),
    129: (0.44, 0.55, 0.00),
    358: (0.56, 0.55, 0.00),
    33: (0.40, 0.46, -0.01),
    133: (0.46, 0.46, 0.00),
    362: (0.54, 0.46, 0.00),
    263: (0.60, 0.46, -0.01),
    61: (0.44, 0.68, -0.01),
    291: (0.56, 0.68, -0.01),
    152: (0.50, 0.80, -0.02),
    199: (0.50, 0.64, 0.01),
}


def _camera(width: int = FRAME_W, height: int = FRAME_H) -> np.ndarray:
    return np.array([[width, 0, width / 2], [0, width, height / 2], [0, 0, 1]], dtype=np.float64)


def _euler_R(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """与构造一致的 Ry @ Rx @ Rz 旋转矩阵（角度制）。"""
    ry, rx, rz = (math.radians(value) for value in (yaw, pitch, roll))
    my = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    mx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    mz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return my @ mx @ mz


def _geodesic(R1: np.ndarray, R2: np.ndarray) -> float:
    cosine = (np.trace(R1.T @ R2) - 1.0) / 2.0
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _face_from_px(points: dict, width: int = FRAME_W, height: int = FRAME_H) -> FaceLandmarks:
    px = np.zeros((478, 2))
    norm = np.zeros((478, 2))
    p3 = np.zeros((478, 3))
    for index, (x, y) in points.items():
        px[index] = (x, y)
        norm[index] = (x / width, y / height)
    return FaceLandmarks(pts_norm=norm, pts_px=px, pts_3d=p3, img_w=width, img_h=height)


def _face_3d(points: dict, width: int = 1000, height: int = 1000) -> FaceLandmarks:
    """points: {index: (x_px, y_px, z_px)}，构造各向同性 3D 坐标。"""
    px = np.zeros((478, 2))
    norm = np.zeros((478, 2))
    p3 = np.zeros((478, 3))
    for index, (x, y, z) in points.items():
        px[index] = (x, y)
        norm[index] = (x / width, y / height)
        p3[index] = (x / width, y / height, z / width)
    return FaceLandmarks(pts_norm=norm, pts_px=px, pts_3d=p3, img_w=width, img_h=height)


def _make_stable_face(noise: float = 0.0, seed: int = 0) -> FaceLandmarks:
    rng = np.random.default_rng(seed)
    px = np.zeros((478, 2))
    norm = np.zeros((478, 2))
    p3 = np.zeros((478, 3))
    for index, (x, y, z) in _STABLE_BASE.items():
        nx = x + rng.normal(0.0, noise)
        ny = y + rng.normal(0.0, noise)
        nz = z + rng.normal(0.0, noise)
        p3[index] = (nx, ny, nz)
        norm[index] = (nx, ny)
        px[index] = (nx * FRAME_W, ny * FRAME_H)
    return FaceLandmarks(pts_norm=norm, pts_px=px, pts_3d=p3, img_w=FRAME_W, img_h=FRAME_H)


# ---------------- 1. PnP 角度恢复 ----------------
def test_pnp_recovers_known_rotation_within_one_degree():
    rotation = _euler_R(12.0, 8.0, -15.0)
    rvec, _ = cv2.Rodrigues(rotation)
    tvec = np.array([[0.0], [0.0], [620.0]])
    projected, _ = cv2.projectPoints(MODEL_POINTS, rvec, tvec, _camera(), np.zeros((4, 1)))
    face = _face_from_px(dict(zip(MODEL_INDEXES, projected.reshape(-1, 2))))

    estimator = HeadPoseEstimator(smoothing_alpha=1.0)
    pose = estimator.estimate(face)
    assert pose.rotation is not None
    assert _geodesic(rotation, pose.rotation) < 1.0
    assert pose.reprojection_error < 1.0
    assert pose.trustworthy

    # 第二次调用复用上一帧初值，仍应收敛到同一解。
    again = estimator.estimate(face)
    assert _geodesic(rotation, again.rotation) < 1.0
    assert again.trustworthy


def test_reprojection_error_flags_untrustworthy_when_template_mismatch():
    person = MODEL_POINTS.copy()
    person[:, 0] *= 1.4
    rvec, _ = cv2.Rodrigues(_euler_R(9.0, 5.0, -3.0))
    tvec = np.array([[0.0], [0.0], [600.0]])
    projected, _ = cv2.projectPoints(person, rvec, tvec, _camera(), np.zeros((4, 1)))
    face = _face_from_px(dict(zip(MODEL_INDEXES, projected.reshape(-1, 2))))
    estimator = HeadPoseEstimator(smoothing_alpha=1.0, reprojection_error_px=2.0)
    pose = estimator.estimate(face)
    assert pose.reprojection_error > 2.0
    assert pose.trustworthy is False


# ---------------- 2. 个人模板优于通用模板 ----------------
def test_personal_template_beats_generic_under_proportion_mismatch():
    person = MODEL_POINTS.copy()
    person[:, 0] *= 1.4
    person[:, 1] *= 0.9
    person[3, 2] -= 15.0
    rvec, _ = cv2.Rodrigues(_euler_R(10.0, 6.0, -4.0))
    tvec = np.array([[0.0], [0.0], [620.0]])
    projected, _ = cv2.projectPoints(person, rvec, tvec, _camera(), np.zeros((4, 1)))
    face = _face_from_px(dict(zip(MODEL_INDEXES, projected.reshape(-1, 2))))

    generic = HeadPoseEstimator(smoothing_alpha=1.0).estimate(face)
    scale = float(np.linalg.norm(person[3] - person[2]))
    profile = FaceProfile(
        points_3d=person / scale,
        point_indexes=list(MODEL_INDEXES),
        sample_frames=1,
    )
    personal = HeadPoseEstimator(profile=profile, smoothing_alpha=1.0).estimate(face)
    assert personal.reprojection_error < generic.reprojection_error
    assert personal.reprojection_error < 1e-6
    assert personal.trustworthy


# ---------------- 3. 角度 ±180° 回绕 ----------------
def test_angle_wrap_around_smoothing():
    result = smooth_angle(179.0, -179.0, 0.5)
    # 最短弧：179 -> 181(=-179)，走 2 度，一半后应距 -179 还差 1 度。
    assert abs(wrap_angle_delta(result - (-179.0))) == pytest.approx(1.0, abs=1e-6)
    assert abs(result) > 170.0  # 朴素平均会得到 0，这里必须仍然靠近 ±180
    assert smooth_angle(179.0, -179.0, 1.0) == pytest.approx(-179.0, abs=1e-9)
    assert wrap_angle_delta(190.0) == pytest.approx(-170.0)


# ---------------- 4. 旧模型版本降级 ----------------
def test_old_model_version_requires_recalibration(tmp_path):
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "calibration.json"
    payload = {
        "version": 2,
        "screen_width": 1920,
        "screen_height": 1080,
        "features": [[0.0] * 14, [0.0] * 14],
        "targets": [[0.0, 0.0], [1.0, 1.0]],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ModelVersionMismatchError):
        CalibrationModel.load(path, root=tmp_path)


# ---------------- 5. 面部模板采集/保存/加载 ----------------
def test_metric_points_are_isotropic_and_scale_reference():
    face = _make_stable_face()
    metric = metric_points(face)
    assert metric.shape == (478, 3)
    # 归一化 0.2 的眼角间距 * 图像宽度 1280 = 256 像素，与图像高度无关。
    assert scale_reference(metric) == pytest.approx(0.2 * FRAME_W, abs=1e-6)
    assert metric[EYE_A_OUTER][0] == pytest.approx(0.40 * FRAME_W, abs=1e-6)
    assert metric[EYE_A_OUTER][1] == pytest.approx(0.46 * FRAME_H, abs=1e-6)


def test_extract_normalized_rejects_degenerate_frame():
    face = _make_stable_face()
    face.img_w = 0
    assert extract_normalized(face) is None


def test_profile_collector_median_and_quality():
    collector = FaceProfileCollector(samples=12)
    for seed in range(12):
        assert collector.add(_make_stable_face(noise=0.002, seed=seed)) is True
    assert collector.full
    profile = collector.build()
    assert profile.sample_frames == 12
    assert profile.points_3d.shape == (20, 3)
    assert profile.point_indexes == list(STABLE_POINT_INDEXES)
    assert profile.quality["point_std"] >= 0.0
    # 中位数应接近「基准点 / 尺度」（模板已按两外眼角距离归一化）。
    scale = scale_reference(metric_points(_make_stable_face()))
    expected = np.array(
        [
            [_STABLE_BASE[index][0] * FRAME_W, _STABLE_BASE[index][1] * FRAME_H, _STABLE_BASE[index][2] * FRAME_W]
            for index in STABLE_POINT_INDEXES
        ]
    ) / scale
    assert np.allclose(profile.points_3d, expected, atol=0.05)


def test_profile_save_load_and_backup(tmp_path):
    collector = FaceProfileCollector(samples=12)
    for seed in range(12):
        collector.add(_make_stable_face(seed=seed))
    profile = collector.build()
    path = tmp_path / "data" / "face_profile.json"
    profile.save(path, root=tmp_path)
    assert path.is_file()
    loaded = FaceProfile.load(path, root=tmp_path)
    np.testing.assert_allclose(loaded.points_3d, profile.points_3d)
    assert loaded.sample_frames == profile.sample_frames

    profile.save(path, root=tmp_path)  # 覆盖应生成备份
    backups = list((tmp_path / "data").glob("face_profile.*.bak.json"))
    assert backups


class _FakeCamera:
    def __init__(self, frames):
        self._frames = iter(frames)

    def read(self):
        return next(self._frames, None)


class _FakeDetector:
    def __init__(self, faces):
        self._faces = iter(faces)

    def detect(self, frame):
        return next(self._faces, None)


def test_profiler_drops_lost_frames():
    cfg = config_from_dict({"face_profile": {"samples": 10}}).face_profile
    frames = [object()] * 15
    faces = [None, _make_stable_face(seed=1), None, _make_stable_face(seed=2), _make_stable_face(seed=3)]
    faces += [_make_stable_face(seed=index) for index in range(4, 12)]
    profile = FaceProfiler(cfg).run(_FakeCamera(frames), _FakeDetector(faces), object())
    assert profile is not None
    assert profile.sample_frames == 10  # 10 个有效帧，None 帧被丢弃


# ---------------- 6. 几何视线 ----------------
def test_gaze_geometry_center_and_offsets():
    base = {
        EYE_A_OUTER: (420.0, 470.0, 0.0),
        EYE_A_INNER: (460.0, 470.0, 0.0),
        EYE_B_INNER: (540.0, 470.0, 0.0),
        EYE_B_OUTER: (580.0, 470.0, 0.0),
    }

    def with_iris(dx, dy):
        points = dict(base)
        points[IRIS_A_CENTER] = (440.0 + dx, 470.0 + dy, 0.0)
        points[IRIS_B_CENTER] = (560.0 + dx, 470.0 + dy, 0.0)
        return _face_3d(points)

    centered = estimate_gaze(with_iris(0.0, 0.0))
    assert centered == pytest.approx((0.0, 0.0), abs=1e-6)
    right = estimate_gaze(with_iris(6.0, 0.0))
    assert right[0] > 0.0
    assert right[1] == pytest.approx(0.0, abs=1e-6)
    down = estimate_gaze(with_iris(0.0, 6.0))
    assert down[1] > 0.0
    assert down[0] == pytest.approx(0.0, abs=1e-6)


def test_gaze_geometry_falls_back_without_3d():
    face = _face_from_px({EYE_A_OUTER: (420.0, 470.0), EYE_B_OUTER: (580.0, 470.0)})
    assert estimate_gaze(face) == (0.0, 0.0)


# ---------------- 7. 特征维度 ----------------
def test_feature_dim_is_fourteen():
    assert FEATURE_DIM == 14
    vector = build_feature_vector(_make_stable_face())
    assert vector is not None
    assert vector.shape == (14,)
    assert np.all(np.isfinite(vector))