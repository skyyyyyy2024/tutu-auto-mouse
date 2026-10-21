"""校准模型测试：合成数据拟合、保存/加载、分辨率校验、备份与 JSON 安全。"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from eyemouse.calibration import (
    CalibrationModel,
    Calibrator,
    ModelVersionMismatchError,
    ScreenSizeMismatchError,
)
from eyemouse.config import config_from_dict


def make_synthetic(screen=(1920, 1080), grid=3, per_point=20, noise=1.0, seed=0):
    """已知线性映射（特征 0/1 -> 屏幕坐标）+ 目标噪声的合成数据。"""
    rng = np.random.default_rng(seed)
    width, height = screen
    xs = [width * 0.1 + (width * 0.8) * index / (grid - 1) for index in range(grid)]
    ys = [height * 0.1 + (height * 0.8) * index / (grid - 1) for index in range(grid)]
    features = []
    targets = []
    point_ids = []
    point_id = 0
    for y in ys:
        for x in xs:
            for _ in range(per_point):
                vector = np.zeros(14, dtype=np.float64)
                vector[0] = x / width
                vector[1] = y / height
                features.append(vector)
                targets.append((x + rng.normal(0.0, noise), y + rng.normal(0.0, noise)))
                point_ids.append(point_id)
            point_id += 1
    return np.array(features), np.array(targets), np.array(point_ids)


def train_model(screen=(1920, 1080), **kwargs):
    """训练一个合成数据模型，返回 (model, features, targets, point_ids)。"""
    features, targets, point_ids = make_synthetic(screen=screen, **kwargs)
    model = CalibrationModel(
        poly_degree=2, ridge_alpha=1.0, screen_size=screen, ear_baseline=0.3
    )
    model.fit(
        features,
        targets,
        point_ids=point_ids,
        ear_baseline=0.3,
        screen_size=screen,
    )
    return model, features, targets, point_ids


def test_predict_error_is_small():
    model, features, targets, _ = train_model()
    predictions = np.array([model.predict(row) for row in features])
    error = float(np.mean(np.linalg.norm(predictions - targets, axis=1)))
    assert error < 30.0


def test_evaluate_leave_one_point_out():
    model, _, _, _ = train_model()
    error = model.evaluate()
    assert error < 120.0
    assert model.mean_error == pytest.approx(error)


def test_predict_is_clipped_to_screen():
    model, _, _, _ = train_model()
    extreme = np.zeros(14, dtype=np.float64)
    extreme[0] = 100.0
    extreme[1] = 100.0
    x, y = model.predict(extreme)
    assert 0.0 <= x <= 1919.0
    assert 0.0 <= y <= 1079.0


def test_save_load_roundtrip(tmp_path):
    model, features, _, _ = train_model()
    path = tmp_path / "data" / "calibration.json"
    saved = model.save(path, root=tmp_path)
    assert saved == path.resolve()
    assert path.is_file()
    loaded = CalibrationModel.load(path, expected_screen=(1920, 1080), root=tmp_path)
    assert loaded.screen_size == (1920, 1080)
    assert loaded.ear_baseline == pytest.approx(model.ear_baseline)
    for row in features[:20]:
        assert loaded.predict(row) == pytest.approx(model.predict(row), abs=1e-6)


def test_saved_file_is_json_not_pickle(tmp_path):
    model, _, _, _ = train_model()
    path = tmp_path / "data" / "calibration.json"
    model.save(path, root=tmp_path)
    raw = path.read_bytes()
    assert not raw.startswith(b"\x80")  # pickle 协议魔数
    assert b"pickle" not in raw.lower()
    data = json.loads(raw.decode("utf-8"))
    assert data["version"] == 3
    assert "kinds" in data
    assert "head_pose_range" in data
    assert data["feature_dim"] == 14
    assert data["screen_width"] == 1920
    assert data["screen_height"] == 1080
    assert len(data["features"]) == len(data["targets"]) == len(data["point_ids"])


def test_screen_size_mismatch_raises(tmp_path):
    model, _, _, _ = train_model()
    path = tmp_path / "data" / "calibration.json"
    model.save(path, root=tmp_path)
    with pytest.raises(ScreenSizeMismatchError) as excinfo:
        CalibrationModel.load(path, expected_screen=(1280, 720), root=tmp_path)
    assert "重新校准" in str(excinfo.value)


def test_overwrite_creates_backup_without_deleting(tmp_path):
    model, _, _, _ = train_model()
    path = tmp_path / "data" / "calibration.json"
    model.save(path, root=tmp_path)
    first_content = path.read_text(encoding="utf-8")
    second, _, _, _ = train_model(seed=1)
    second.save(path, root=tmp_path)
    assert path.is_file()
    backups = list((tmp_path / "data").glob("calibration.*.bak.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == first_content


def test_save_outside_data_is_rejected(tmp_path):
    model, _, _, _ = train_model()
    with pytest.raises(ValueError):
        model.save(tmp_path / "calibration.json", root=tmp_path)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        CalibrationModel.load(tmp_path / "data" / "calibration.json", root=tmp_path)


def test_grid_points_layout():
    calibrator = Calibrator(config_from_dict({}))
    points = calibrator.grid_points(1000, 800)
    assert len(points) == 9
    assert points[0] == pytest.approx((80.0, 64.0))
    assert points[4] == pytest.approx((500.0, 400.0))
    assert points[-1] == pytest.approx((920.0, 736.0))


def make_pose_pair(screen=(1920, 1080), per_point=25, seed=0):
    """一致的静止/头动合成数据。

    生成模型：真实注视比例 -> 屏幕坐标；头动时虹膜测量值被头姿污染
    （= 真实注视 + 0.15 * 头姿），头姿特征可用于补偿；鼻尖与头部尺度固定。
    返回 ((静止特征, 静止目标, 静止点号), (头动特征, 头动目标, 头动点号))。
    """
    rng = np.random.default_rng(seed)
    width, height = screen
    grid = [
        (width * 0.1 + width * 0.8 * i / 2, height * 0.1 + height * 0.8 * j / 2)
        for j in range(3)
        for i in range(3)
    ]
    head_points = [
        (width * 0.08, height * 0.08),
        (width * 0.92, height * 0.08),
        (width * 0.5, height * 0.5),
        (width * 0.08, height * 0.92),
        (width * 0.92, height * 0.92),
    ]

    def build(points, moving, base_id):
        features = []
        targets = []
        point_ids = []
        for offset, (x, y) in enumerate(points):
            for _ in range(per_point):
                if moving:
                    yaw = rng.uniform(-0.6, 0.6)
                    pitch = rng.uniform(-0.5, 0.5)
                    roll = rng.uniform(-0.3, 0.3)
                else:
                    yaw = pitch = roll = 0.0
                vector = np.zeros(14, dtype=np.float64)
                vector[0] = x / width + 0.15 * yaw
                vector[1] = y / height + 0.15 * pitch
                vector[2] = vector[0]
                vector[3] = vector[1]
                vector[4] = vector[0]
                vector[5] = vector[1]
                vector[6] = yaw
                vector[7] = pitch
                vector[8] = roll
                vector[9] = 0.5
                vector[10] = 0.5
                vector[11] = 0.16
                features.append(vector)
                targets.append((x, y))
                point_ids.append(base_id + offset)
        return np.array(features), np.array(targets), np.array(point_ids)

    return build(grid, False, 0), build(head_points, True, 100)


def _head_error(model, features, targets):
    predictions = np.array([model.predict(row) for row in features])
    return float(np.mean(np.linalg.norm(predictions - targets, axis=1)))


def test_head_motion_compensation_reduces_error():
    static, head = make_pose_pair(per_point=25, seed=4)
    static_features, static_targets, static_ids = static
    head_features, head_targets, head_ids = head

    static_only = CalibrationModel(poly_degree=2, ridge_alpha=1.0)
    static_only.fit(static_features, static_targets, point_ids=static_ids)

    merged = CalibrationModel(poly_degree=2, ridge_alpha=1.0)
    merged.fit(
        np.vstack([static_features, head_features]),
        np.concatenate([static_targets, head_targets], axis=0),
        point_ids=np.concatenate([static_ids, head_ids]),
        kinds=["static"] * len(static_features) + ["head"] * len(head_features),
    )

    error_before = _head_error(static_only, head_features, head_targets)
    error_after = _head_error(merged, head_features, head_targets)
    assert error_before > 40.0
    assert error_after < error_before * 0.5
    assert error_after < 20.0


def test_subset_errors_are_recorded():
    static, head = make_pose_pair(per_point=20, seed=6)
    static_features, static_targets, static_ids = static
    head_features, head_targets, head_ids = head
    model = CalibrationModel(poly_degree=2, ridge_alpha=1.0)
    model.fit(
        np.vstack([static_features, head_features]),
        np.concatenate([static_targets, head_targets], axis=0),
        point_ids=np.concatenate([static_ids, head_ids]),
        kinds=["static"] * len(static_features) + ["head"] * len(head_features),
    )
    error = model.evaluate()
    assert model.mean_error == pytest.approx(error)
    assert model.static_error is not None
    assert model.head_motion_error is not None
    assert model.head_motion_error < 20.0
    assert model.kinds.count("head") == len(head_features)


def test_alpha_cv_selects_candidate():
    features, targets, point_ids = make_synthetic(per_point=15, noise=25.0, seed=8)
    model = CalibrationModel(
        poly_degree=2, ridge_alpha=1.0, alphas=[0.01, 1.0, 100.0], cv_folds=5
    )
    model.fit(features, targets, point_ids=point_ids)
    assert model.alpha_cv_used is True
    assert model.ridge_alpha in (0.01, 1.0, 100.0)


def test_pose_range_and_clamp():
    screen = (1920, 1080)
    _, head = make_pose_pair(per_point=20, seed=7)
    head_features, head_targets, head_ids = head
    pose_range = Calibrator.head_pose_range_from_features(head_features)
    assert pose_range is not None
    model = CalibrationModel(poly_degree=2, ridge_alpha=1.0, pose_margin_deg=1.0)
    model.fit(
        head_features,
        head_targets,
        point_ids=head_ids,
        kinds=["head"] * len(head_features),
        head_pose_range=pose_range,
    )
    assert model.pose_in_range(head_features[0])
    outside = head_features[0].copy()
    outside[6] = 5.0  # yaw = 225 度，远超校准范围
    assert not model.pose_in_range(outside)
    x, y, in_range = model.predict_clamped(outside, (100.0, 100.0), 25.0)
    assert in_range is False
    assert math.hypot(x - 100.0, y - 100.0) <= 25.0 + 1e-6


def test_save_and_load_head_motion_metadata(tmp_path):
    _, head = make_pose_pair(per_point=20, seed=9)
    head_features, head_targets, head_ids = head
    pose_range = Calibrator.head_pose_range_from_features(head_features)
    model = CalibrationModel(
        poly_degree=2, ridge_alpha=1.0, alphas=[0.1, 1.0, 10.0], pose_margin_deg=4.0
    )
    model.fit(
        head_features,
        head_targets,
        point_ids=head_ids,
        kinds=["head"] * len(head_features),
        head_pose_range=pose_range,
        pose_margin_deg=4.0,
    )
    model.evaluate()
    path = tmp_path / "data" / "calibration.json"
    model.save(path, root=tmp_path)
    loaded = CalibrationModel.load(path, expected_screen=(1920, 1080), root=tmp_path)
    assert loaded.head_pose_range is not None
    assert loaded.pose_margin_deg == pytest.approx(4.0)
    assert loaded.head_motion_error == pytest.approx(model.head_motion_error)
    assert loaded.kinds.count("head") == len(head_features)
    for row in head_features[:10]:
        assert loaded.predict(row) == pytest.approx(model.predict(row), abs=1e-6)


def test_head_motion_points_layout():
    calibrator = Calibrator(config_from_dict({}))
    points = calibrator.head_motion_points(1000, 800)
    assert len(points) == 5
    assert points[0] == pytest.approx((500.0, 400.0))
    assert points[1] == pytest.approx((80.0, 64.0))
    assert points[4] == pytest.approx((920.0, 736.0))


def test_head_motion_points_respects_count():
    cfg = config_from_dict({"head_motion_calibration": {"points": 3}})
    calibrator = Calibrator(cfg)
    assert len(calibrator.head_motion_points(1000, 800)) == 3


def _fake_face():
    """构造一个正面人脸（覆盖虹膜/头姿/EAR 所需索引）。"""
    from eyemouse.landmarks import CHIN, EYE_A_DOWN, EYE_A_INNER, EYE_A_OUTER, EYE_A_UP
    from eyemouse.landmarks import EYE_B_DOWN, EYE_B_INNER, EYE_B_OUTER, EYE_B_UP
    from eyemouse.landmarks import FACE_POINT_COUNT, FaceLandmarks, IRIS_A_CENTER, IRIS_B_CENTER
    from eyemouse.landmarks import MOUTH_A, MOUTH_B, NOSE_TIP

    points = {
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
        160: (430, 458),
        158: (450, 458),
        153: (430, 482),
        144: (450, 482),
        385: (550, 458),
        387: (570, 458),
        373: (550, 482),
        380: (570, 482),
    }
    count = FACE_POINT_COUNT
    px = np.zeros((count, 2), dtype=np.float64)
    norm = np.zeros((count, 2), dtype=np.float64)
    three = np.zeros((count, 3), dtype=np.float64)
    for index, (x, y) in points.items():
        px[index] = (float(x), float(y))
        norm[index] = (float(x) / 1000.0, float(y) / 1000.0)
    return FaceLandmarks(pts_norm=norm, pts_px=px, pts_3d=three, img_w=1000, img_h=1000)


class _FakeCamera:
    """固定返回同一帧的假摄像头。"""

    def __init__(self) -> None:
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def read(self):
        return self.frame


class _FakeDetector:
    """始终返回同一张人脸的假检测器。"""

    def __init__(self, face) -> None:
        self.face = face

    def detect(self, frame):
        return self.face


def test_sample_head_motion_collects_samples():
    cfg = config_from_dict(
        {
            "calibration": {"practice_blinks": False},
            "head_motion_calibration": {
                "points": 2,
                "per_point_seconds": 0.05,
                "settle_time": 0.01,
                "max_yaw_deg": 180,
                "max_pitch_deg": 180,
                "max_roll_deg": 180,
            },
        }
    )
    calibrator = Calibrator(cfg)
    points = calibrator.head_motion_points(1000, 800)
    features, targets, point_ids = calibrator._sample_head_motion(
        _FakeCamera(), _FakeDetector(_fake_face()), object(), points, 0.3, []
    )
    assert features.ndim == 2 and features.shape[1] == 14
    assert features.shape[0] >= 5
    assert targets.shape == (features.shape[0], 2)
    assert set(point_ids.tolist()) <= {100, 101}
    pose_range = Calibrator.head_pose_range_from_features(features)
    assert pose_range is not None and "yaw" in pose_range


def test_pose_within_limits_rejects_extreme_pose():
    cfg = config_from_dict({"head_motion_calibration": {"max_yaw_deg": 10.0}})
    calibrator = Calibrator(cfg)
    vector = np.zeros(14, dtype=np.float64)
    assert calibrator._pose_within_limits(vector)
    vector[6] = 1.0  # yaw = 45 度，超过 10 度上限
    assert not calibrator._pose_within_limits(vector)
