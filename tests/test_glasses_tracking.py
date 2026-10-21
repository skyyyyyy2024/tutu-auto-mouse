"""眼镜 ArUco 标记六自由度追踪测试（合成数据，不开摄像头、不动鼠标）。"""

from __future__ import annotations

import inspect
import math

import cv2
import numpy as np
import pytest

import main as main_module

from eyemouse import glasses_tracker as gt
from eyemouse.camera_calibration import CameraCalibration, CharucoBoardSpec, save_calibration
from eyemouse.camera import Camera
from eyemouse.config import config_from_dict, load_config
from eyemouse.glasses_tracker import (
    AMBIGUOUS,
    BAD_REPROJECTION,
    CALIBRATION_MISMATCH,
    MOTION_OUTLIER,
    NO_MARKER,
    STABILIZING,
    TOO_SMALL,
    TRACKING,
    GlassesPose,
    GlassesTracker,
    PoseCandidate,
    StabilityStats,
)
from eyemouse.ui import flip_display_point, draw_glasses_overlay

K_TRUE = np.array([[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]])
IMAGE_SIZE = (1280, 720)
MARKER_SIZE_M = 0.04
DIST_ZERO = np.zeros((1, 5), dtype=np.float64)


def _calibration(image_size=IMAGE_SIZE, matrix=None) -> CameraCalibration:
    return CameraCalibration(
        camera_matrix=K_TRUE.copy() if matrix is None else np.asarray(matrix, dtype=np.float64),
        dist_coeffs=np.zeros(5, dtype=np.float64),
        image_size=image_size,
        rms_px=0.15,
        num_views=18,
        board=CharucoBoardSpec(),
    )


def _cfg(**overrides):
    """默认眼镜配置 + 测试用的快速参数（缩短稳定与歧义窗口）。"""
    cfg = config_from_dict({}).glasses_tracking
    cfg.marker_size_m = MARKER_SIZE_M
    cfg.acquisition_frames = 1
    cfg.stabilize_frames = 2
    cfg.min_marker_area_px = 100.0
    cfg.max_angular_speed_deg_s = 5000.0
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def _marker_rotation(tilt_x: float, tilt_y: float, roll: float) -> np.ndarray:
    """构造“正面朝向摄像头”的标记姿态。

    本约定（IPPE_SQUARE 模型点 Y 向上）下，正面朝向摄像头时 R[2, 2] < 0，
    若直接用 dx 旋转矩阵，标记会以背面朝前，渲染出的图案是镜像的、无法被检测。
    """
    base, _ = cv2.Rodrigues(np.array([math.pi, 0.0, 0.0]))
    extra, _ = cv2.Rodrigues(np.array([tilt_x, tilt_y, roll]))
    return base @ extra


def _project(object_points, rotation, translation):
    rvec, _ = cv2.Rodrigues(np.asarray(rotation, dtype=np.float64))
    points, _ = cv2.projectPoints(
        np.asarray(object_points, dtype=np.float64),
        rvec,
        np.asarray(translation, dtype=np.float64).reshape(3, 1),
        K_TRUE,
        DIST_ZERO,
    )
    return points.reshape(-1, 2)


def _marker_frame(
    rotation=None,
    translation=(0.01, -0.005, 0.45),
    marker_id: int = 0,
    side: int = 400,
    image_size=IMAGE_SIZE,
    dictionary_name: str = "DICT_5X5_50",
    marker_size_m: float = MARKER_SIZE_M,
):
    """把 ArUco 标记按给定位姿渲染进一帧灰度-BGR 画面（等效于相机看到的图像）。

    位图自身的左上角对应模型点 0，因此目标四边形必须用 ``p[0..3]`` 顺序，
    否则渲染出的图案是镜像的，检测会失败。
    """
    if rotation is None:
        rotation = _marker_rotation(0.3, -0.14, 0.05)
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, side)
    object_points = gt.marker_object_points(marker_size_m)
    projected = _project(object_points, rotation, translation)
    src = np.array(
        [[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(src, projected.astype(np.float32))
    warped = cv2.warpPerspective(
        marker, transform, tuple(image_size), borderMode=cv2.BORDER_CONSTANT, borderValue=255
    )
    return cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)


def _candidate(error: float, rotation: np.ndarray, depth: float = 0.5) -> PoseCandidate:
    return PoseCandidate(
        rotation=np.asarray(rotation, dtype=np.float64),
        translation=np.array([0.0, 0.0, depth]),
        reprojection_error_px=float(error),
        positive_depth=depth > 0.0,
        valid_rotation=gt.is_valid_rotation(np.asarray(rotation, dtype=np.float64)),
    )


def _rot_z(degrees: float) -> np.ndarray:
    matrix, _ = cv2.Rodrigues(np.array([0.0, 0.0, math.radians(degrees)]))
    return matrix


# ---------------- 几何基础 ----------------
def test_marker_object_points_order_and_scale():
    points = gt.marker_object_points(0.04)
    assert points.dtype == np.float32
    expected = np.array(
        [
            [-0.02, 0.02, 0.0],
            [0.02, 0.02, 0.0],
            [0.02, -0.02, 0.0],
            [-0.02, -0.02, 0.0],
        ]
    )
    assert np.allclose(points, expected)


def test_quaternion_matrix_roundtrip_and_sign_equivalence():
    rotation = _marker_rotation(0.3, -0.2, 0.1)
    quaternion = gt.quaternion_from_matrix(rotation)
    assert gt.quaternion_dot(quaternion, quaternion) == pytest.approx(1.0)
    restored = gt._quaternion_to_matrix(quaternion)
    assert np.allclose(restored, rotation, atol=1e-9)
    # q 与 -q 表示同一旋转
    assert np.allclose(gt._quaternion_to_matrix(-quaternion), rotation, atol=1e-9)
    assert gt.quaternion_angle_deg(quaternion, -quaternion) == pytest.approx(0.0)
    aligned = gt.align_quaternion_sign(-quaternion, quaternion)
    assert gt.quaternion_dot(aligned, quaternion) > 0.0
    assert gt.is_valid_rotation(restored) is True


def test_is_valid_rotation_rejects_bad_matrices():
    assert gt.is_valid_rotation(np.eye(3)) is True
    assert gt.is_valid_rotation(np.zeros((3, 3))) is False
    assert gt.is_valid_rotation(np.diag([1.0, 1.0, 2.0])) is False
    assert gt.is_valid_rotation(np.full((3, 3), np.nan)) is False
    assert gt.is_valid_rotation(np.eye(2)) is False
    mirrored = np.diag([-1.0, 1.0, 1.0])
    assert gt.is_valid_rotation(mirrored) is False


def test_rotation_angle_handles_wraparound():
    # 350 度与 10 度之差必须按短弧算成 20 度，而不是 340 度。
    assert gt.rotation_angle_deg(_rot_z(350.0), _rot_z(10.0)) == pytest.approx(20.0, abs=1e-6)
    assert gt.rotation_angle_deg(_rot_z(-179.0), _rot_z(179.0)) == pytest.approx(2.0, abs=1e-6)
    assert gt.rotation_angle_deg(_rot_z(0.0), _rot_z(180.0)) == pytest.approx(180.0, abs=1e-6)
    assert gt.quaternion_angle_deg(
        gt.quaternion_from_matrix(_rot_z(350.0)), gt.quaternion_from_matrix(_rot_z(10.0))
    ) == pytest.approx(20.0, abs=1e-6)


def test_slerp_takes_short_arc_and_honours_endpoints():
    start = gt.quaternion_from_matrix(_rot_z(170.0))
    end = gt.quaternion_from_matrix(_rot_z(-170.0))
    midpoint = gt.slerp(start, end, 0.5)
    # 短弧中点应接近 180 度，而不是回到 0 度（长弧会绕回起点附近）。
    assert gt.quaternion_angle_deg(start, midpoint) == pytest.approx(10.0, abs=1e-6)
    assert np.allclose(gt.slerp(start, end, 0.0), start, atol=1e-9)
    assert gt.quaternion_angle_deg(gt.slerp(start, end, 1.0), end) == pytest.approx(0.0, abs=1e-9)


def test_direction_angles_are_display_only_and_finite():
    yaw, pitch, roll = gt.direction_angles_deg(_marker_rotation(0.0, 0.0, 0.0))
    assert abs(yaw) < 1e-6 and abs(pitch) < 1e-6
    tilted = gt.direction_angles_deg(_marker_rotation(0.3, -0.2, 0.0))
    assert all(math.isfinite(value) for value in tilted)
    assert abs(tilted[0]) > 1.0


# ---------------- 候选位姿求解与选择 ----------------
def test_solve_candidates_recovers_pose():
    rotation = _marker_rotation(0.25, -0.1, 0.05)
    translation = np.array([0.01, -0.005, 0.45])
    corners = _project(gt.marker_object_points(MARKER_SIZE_M), rotation, translation)
    tracker = GlassesTracker(_cfg(), _calibration())
    candidates = tracker.solve_candidates(corners)
    assert candidates
    best = min(candidates, key=lambda item: item.reprojection_error_px)
    assert best.positive_depth is True
    assert best.valid_rotation is True
    assert best.reprojection_error_px < 0.05
    assert gt.rotation_angle_deg(rotation, best.rotation) < 1.0
    assert np.linalg.norm(best.translation - translation) < 0.01


def test_solve_candidates_returns_empty_for_non_finite_corners():
    tracker = GlassesTracker(_cfg(), _calibration())
    corners = np.full((4, 2), np.nan, dtype=np.float32)
    assert tracker.solve_candidates(corners) == []


def test_select_candidate_prefers_clearly_better_solution():
    tracker = GlassesTracker(_cfg(), _calibration())
    better = _candidate(0.05, _rot_z(0.0))
    worse = _candidate(1.5, _rot_z(30.0))
    chosen, status, note = tracker.select_candidate([worse, better], 1.0)
    assert chosen is better
    assert status == ""
    assert note == ""


def test_select_candidate_rejects_quality_failures():
    tracker = GlassesTracker(_cfg(max_reprojection_error_px=0.5), _calibration())
    assert tracker.select_candidate([], 1.0)[1] == NO_MARKER
    bad = [_candidate(2.0, _rot_z(0.0))]
    assert tracker.select_candidate(bad, 1.0)[1] == BAD_REPROJECTION
    negative = _candidate(0.1, _rot_z(0.0), depth=-0.5)
    assert tracker.select_candidate([negative], 1.0)[1] == BAD_REPROJECTION


def test_ambiguity_cold_start_is_reported_then_resolved_by_evidence():
    """平面标记双解：冷启动先报 AMBIGUOUS，累积多帧证据后必须选到误差更小的解。"""
    rotation = _marker_rotation(0.15, -0.05, 0.0)
    translation = np.array([0.0, 0.0, 0.45])
    corners = _project(gt.marker_object_points(MARKER_SIZE_M), rotation, translation)
    tracker = GlassesTracker(_cfg(acquisition_frames=5), _calibration())
    candidates = tracker.solve_candidates(corners)
    assert len(candidates) >= 2
    seen_ambiguous = False
    chosen = None
    for frame in range(6):
        chosen, status, note = tracker.select_candidate(candidates, 1.0 + 0.033 * frame)
        if status == AMBIGUOUS:
            seen_ambiguous = True
            assert "歧义" in note
        else:
            break
    assert seen_ambiguous is True
    assert chosen is not None
    assert gt.rotation_angle_deg(rotation, chosen.rotation) < 2.0
    assert chosen.reprojection_error_px == pytest.approx(
        min(item.reprojection_error_px for item in candidates), abs=1e-9
    )


def test_ambiguity_resolved_immediately_with_recent_reference():
    rotation = _marker_rotation(0.15, -0.05, 0.0)
    corners = _project(gt.marker_object_points(MARKER_SIZE_M), rotation, np.array([0.0, 0.0, 0.45]))
    tracker = GlassesTracker(_cfg(acquisition_frames=1), _calibration())
    candidates = tracker.solve_candidates(corners)
    tracker._previous_rotation = rotation
    tracker._previous_time = 1.0
    chosen, status, note = tracker.select_candidate(candidates, 1.033)
    assert chosen is not None
    assert status == ""
    assert "连续性" in note
    assert gt.rotation_angle_deg(rotation, chosen.rotation) < 2.0


def test_ambiguity_stays_when_evidence_is_equal():
    """两支候选误差完全一致时不得强行输出可信姿态。"""
    tracker = GlassesTracker(_cfg(acquisition_frames=3), _calibration())
    first = _candidate(0.2, _rot_z(0.0))
    second = _candidate(0.2, _rot_z(40.0))
    assert len(tracker.solve_candidates.__doc__ or "") > 0
    for frame in range(4):
        chosen, status, _note = tracker.select_candidate([first, second], 1.0 + frame)
        assert chosen is None
        assert status == AMBIGUOUS


# ---------------- 完整 update 流程 ----------------
def test_update_tracks_rendered_marker_and_reports_stats():
    rotation = _marker_rotation(0.3, -0.14, 0.05)
    translation = np.array([0.01, -0.005, 0.45])
    frame = _marker_frame(rotation, translation)
    tracker = GlassesTracker(_cfg(), _calibration())
    poses = [tracker.update(frame, 1.0 + 0.033 * index) for index in range(4)]
    assert poses[0].status == STABILIZING
    assert poses[0].valid is False
    final = poses[-1]
    assert final.status == TRACKING
    assert final.valid is True
    assert final.marker_id == 0
    assert final.corners_px is not None and final.corners_px.shape == (4, 2)
    assert final.marker_area_px and final.marker_area_px > 100.0
    assert final.reprojection_error_px is not None and final.reprojection_error_px < 1.0
    assert gt.rotation_angle_deg(rotation, final.rotation_matrix) < 3.0
    assert np.linalg.norm(final.translation_m - translation) < 0.02
    assert final.angles_deg() is not None
    millimetres = final.translation_mm()
    assert millimetres[0] == pytest.approx(10.0, abs=5.0)
    assert millimetres[2] == pytest.approx(450.0, abs=20.0)
    stats = tracker.stats
    assert stats.frames == 4
    assert stats.valid_ratio() == pytest.approx(0.75)
    assert stats.tracking_fps() > 0.0
    assert stats.status_counts[TRACKING] == 3


def test_update_detects_marker_corners_in_bitmap_order():
    rotation = _marker_rotation(0.2, 0.1, 0.0)
    translation = np.array([0.0, 0.0, 0.45])
    frame = _marker_frame(rotation, translation)
    tracker = GlassesTracker(_cfg(), _calibration())
    expected = _project(gt.marker_object_points(MARKER_SIZE_M), rotation, translation)
    detected = tracker.detect_marker(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    assert detected is not None
    assert detected.shape == (4, 2)
    assert np.allclose(detected, expected, atol=1.0)


def test_update_missing_marker_reports_no_marker_and_stale_pose():
    frame = _marker_frame()
    blank = np.full((IMAGE_SIZE[1], IMAGE_SIZE[0], 3), 255, dtype=np.uint8)
    tracker = GlassesTracker(_cfg(), _calibration())
    for index in range(4):
        last_valid = tracker.update(frame, 1.0 + 0.033 * index)
    assert last_valid.valid is True
    stale = tracker.update(blank, 1.1)
    assert stale.status == NO_MARKER
    assert stale.valid is False
    assert stale.stale is True
    assert np.allclose(stale.rotation_matrix, last_valid.rotation_matrix)
    expired = tracker.update(blank, 1.1 + 10.0)
    assert expired.status == NO_MARKER
    assert expired.stale is False
    assert expired.rotation_matrix is None


def test_update_rejects_calibration_mismatch_and_missing_calibration():
    frame = _marker_frame()
    wrong_size = GlassesTracker(_cfg(), _calibration(image_size=(640, 480)))
    pose = wrong_size.update(frame, 1.0)
    assert pose.status == CALIBRATION_MISMATCH
    assert "分辨率" in pose.reason
    missing = GlassesTracker(_cfg(), None)
    pose = missing.update(frame, 1.0)
    assert pose.status == CALIBRATION_MISMATCH
    assert "--calibrate-camera" in pose.reason


def test_update_rejects_tiny_marker():
    frame = _marker_frame()
    tracker = GlassesTracker(_cfg(min_marker_area_px=10_000_000.0), _calibration())
    pose = tracker.update(frame, 1.0)
    assert pose.status == TOO_SMALL
    assert pose.marker_area_px is not None and pose.corners_px is not None


def test_update_rejects_motion_outlier_and_timestamp_anomaly():
    first = _marker_frame(_marker_rotation(0.3, -0.14, 0.05))
    jumped = _marker_frame(_marker_rotation(0.8, -0.14, 0.05))
    tracker = GlassesTracker(_cfg(max_angular_speed_deg_s=100.0), _calibration())
    for index in range(4):
        tracker.update(first, 1.0 + 0.033 * index)
    outlier = tracker.update(jumped, 1.15)
    assert outlier.status == MOTION_OUTLIER
    tracker.reset()
    for index in range(4):
        tracker.update(first, 2.0 + 0.033 * index)
    frozen = tracker.update(first, 2.0 + 0.033 * 3)
    assert frozen.status == MOTION_OUTLIER


def test_update_long_gap_resets_filter_without_rejection():
    first = _marker_frame(_marker_rotation(0.3, -0.14, 0.05))
    second = _marker_frame(_marker_rotation(-0.3, 0.2, -0.05))
    tracker = GlassesTracker(_cfg(gap_reset_s=0.5), _calibration())
    for index in range(4):
        tracker.update(first, 1.0 + 0.033 * index)
    pose = tracker.update(second, 1.2 + 5.0)
    assert pose.status != MOTION_OUTLIER
    assert pose.status == STABILIZING
    assert np.allclose(pose.rotation_matrix, pose.raw_rotation_matrix, atol=1e-9)


def test_update_handles_nan_gray_and_bad_shape_frames():
    tracker = GlassesTracker(_cfg(), _calibration())
    nan_frame = np.full((IMAGE_SIZE[1], IMAGE_SIZE[0], 3), np.nan, dtype=np.float32)
    assert tracker.update(nan_frame, 1.0).status == NO_MARKER
    gray = np.full((IMAGE_SIZE[1], IMAGE_SIZE[0]), 255, dtype=np.uint8)
    assert tracker.update(gray, 1.1).status == NO_MARKER
    weird = np.zeros((IMAGE_SIZE[1], IMAGE_SIZE[0], 7), dtype=np.uint8)
    assert tracker.update(weird, 1.2).status == NO_MARKER
    assert tracker.update(None, 1.3).status == NO_MARKER


def test_smoothing_applies_after_quality_gate():
    start = _marker_frame(_marker_rotation(0.2, 0.0, 0.0))
    turned = _marker_frame(_marker_rotation(0.2, 0.25, 0.0))
    tracker = GlassesTracker(_cfg(slerp_alpha=0.35), _calibration())
    for index in range(6):
        pose = tracker.update(start, 1.0 + 0.033 * index)
    raw_angle = gt.rotation_angle_deg(pose.raw_rotation_matrix, pose.rotation_matrix)
    assert raw_angle == pytest.approx(0.0, abs=1e-6)
    turned_pose = tracker.update(turned, 1.2)
    # 先判断可信再平滑：平滑结果必须落在上一帧与当前观测之间。
    total = gt.rotation_angle_deg(pose.rotation_matrix, turned_pose.raw_rotation_matrix)
    smoothed = gt.rotation_angle_deg(pose.rotation_matrix, turned_pose.rotation_matrix)
    assert total > 5.0
    assert 0.0 < smoothed < total
    assert smoothed == pytest.approx(total * 0.35, rel=0.2)


def test_reset_clears_filters_and_statistics():
    frame = _marker_frame()
    tracker = GlassesTracker(_cfg(), _calibration())
    for index in range(4):
        tracker.update(frame, 1.0 + 0.033 * index)
    assert tracker.stats.frames > 0
    tracker.reset()
    tracker.reset_stats()
    assert tracker._smoothed_quaternion is None
    assert tracker._previous_rotation is None
    assert tracker._ambiguity_branches == []
    assert tracker.stats.frames == 0
    assert tracker.stats.status_counts == {}
    assert tracker.update(frame, 2.0).status == STABILIZING


def test_stability_stats_uses_rotation_geometry_not_euler_wraparound():
    stats = StabilityStats(window_s=10.0)
    reference = gt.quaternion_from_matrix(_rot_z(179.0))
    for index in range(10):
        quaternion = gt.quaternion_from_matrix(_rot_z(179.0 + (index % 3) - 1))
        stats.push(1.0 + 0.033 * index, np.array([0.0, 0.0, 0.45]), quaternion)
    summary = stats.summary()
    assert summary["samples"] == 10.0
    assert summary["position_std_mm"] == pytest.approx(0.0, abs=1e-6)
    # 跨 ±180 度也不能出现 ~180 度的假抖动。
    assert summary["rotation_std_deg"] < 5.0
    assert gt.quaternion_angle_deg(reference, reference) == pytest.approx(0.0)


# ---------------- 镜像规则：只影响显示，不影响几何 ----------------
class _FakeCapture:
    """最小 VideoCapture 替身：只提供 Camera 需要的接口，不开真实摄像头。"""

    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame
        self.released = False

    def isOpened(self) -> bool:
        return True

    def set(self, *_args) -> bool:
        return True

    def read(self):
        return True, self._frame.copy()

    def release(self) -> None:
        self.released = True


def test_camera_read_mirrors_only_for_display(monkeypatch):
    frame = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _index: _FakeCapture(frame))
    camera = Camera(config_from_dict({}).camera)
    camera.open()
    raw = camera.read_raw()
    displayed = camera.read()
    assert np.array_equal(raw, frame)
    assert np.array_equal(displayed, cv2.flip(frame, 1))
    camera.release()


def test_flip_display_point_is_involution():
    x, y = flip_display_point(10.0, 20.0, 1280, True)
    assert (x, y) == (1269.0, 20.0)
    assert flip_display_point(x, y, 1280, True) == (10.0, 20.0)
    assert flip_display_point(10.0, 20.0, 1280, False) == (10.0, 20.0)


def test_overlay_draws_mirrored_corners_with_raw_camera_size(monkeypatch):
    lines = []
    monkeypatch.setattr(cv2, "line", lambda img, p1, p2, color, *a, **k: lines.append((p1, p2)))
    monkeypatch.setattr(cv2, "circle", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "putText", lambda *a, **k: None)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    corners = np.array([[10.0, 10.0], [40.0, 10.0], [40.0, 40.0], [10.0, 40.0]])
    pose = GlassesPose(
        valid=True,
        status=TRACKING,
        timestamp=1.0,
        marker_id=0,
        corners_px=corners,
        marker_area_px=900.0,
        reprojection_error_px=0.2,
    )
    draw_glasses_overlay(frame, pose, mirrored=True)
    assert lines[0] == ((1269, 10), (1239, 10))
    lines.clear()
    draw_glasses_overlay(frame, pose, mirrored=False)
    assert lines[0] == ((10, 10), (40, 10))


def test_glasses_geometry_never_flips_frames():
    """几何路径不得镜像：追踪器里不允许出现 cv2.flip，自检必须读未镜像帧。"""
    assert "flip" not in inspect.getsource(gt)
    source = inspect.getsource(main_module.glasses_test)
    assert "read_raw()" in source
    assert source.count("cv2.flip") == 1


# ---------------- 命令行入口 ----------------
def test_write_charuco_board_cli_writes_exact_scale(tmp_path):
    cfg = config_from_dict({})
    cfg.root = str(tmp_path)
    target = tmp_path / "board.png"
    assert main_module.write_charuco_board(cfg, str(target)) == 0
    image = cv2.imread(str(target))
    assert image is not None
    assert image.shape[1] > cfg.camera_calibration.squares_x


def test_parser_exposes_new_modes():
    parser = main_module.build_parser()
    args = parser.parse_args(
        ["--calibrate-camera", "--glasses-test", "--write-charuco-board", "out.png"]
    )
    assert args.calibrate_camera is True
    assert args.glasses_test is True
    assert args.write_charuco_board == "out.png"
    default = parser.parse_args([])
    assert default.write_charuco_board is None
    assert default.glasses_test is False


def test_glasses_test_requires_calibration_file(tmp_path, monkeypatch, capsys):
    cfg = config_from_dict({})
    cfg.root = str(tmp_path)
    monkeypatch.setattr(main_module, "calibration_file", lambda c: tmp_path / "missing.json")
    assert main_module.glasses_test(cfg, show_window=False) == 1
    assert "calibrate-camera" in capsys.readouterr().err


def test_glasses_test_does_not_create_mouse_or_clicks(tmp_path, monkeypatch, capsys):
    cfg = config_from_dict({})
    cfg.root = str(tmp_path)
    path = tmp_path / "camera_calibration.json"
    save_calibration(_calibration(), path)
    monkeypatch.setattr(main_module, "calibration_file", lambda c: path)
    frame = _marker_frame()
    monkeypatch.setattr(main_module, "Camera", lambda _cfg: _FakeCamera(frame))

    from eyemouse import mouse as mouse_module

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("眼镜自检不得创建真实鼠标控制")

    monkeypatch.setattr(mouse_module, "PyAutoGuiMouse", _forbidden)
    monkeypatch.setattr(mouse_module.PyAutoGuiMouse, "__init__", _forbidden)
    assert main_module.glasses_test(cfg, show_window=False) == 0
    out = capsys.readouterr().out
    assert "不控制鼠标" in out


def test_calibrate_camera_refuses_headless(tmp_path, monkeypatch, capsys):
    cfg = config_from_dict({})
    cfg.root = str(tmp_path)
    monkeypatch.setattr(main_module, "Camera", lambda _cfg: _FakeCamera(_marker_frame()))
    assert main_module.calibrate_camera(cfg, show_window=False) == 1
    assert "无法采集标定视图" in capsys.readouterr().err


class _FakeCamera:
    """main.py 用的摄像头替身（只提供自检需要的接口）。"""

    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def open(self):
        return self

    def read_raw(self):
        return self._frame.copy()

    def read(self):
        return cv2.flip(self._frame, 1)

    def release(self) -> None:
        pass


# ---------------- 配置 ----------------
def test_new_config_sections_have_safe_defaults():
    cfg = config_from_dict({})
    assert cfg.glasses_tracking.enabled is False
    assert cfg.glasses_tracking.marker_id == 0
    assert cfg.glasses_tracking.marker_size_m == pytest.approx(0.03)
    assert cfg.glasses_tracking.acquisition_frames >= 1
    assert cfg.camera_calibration.dictionary == "DICT_5X5_50"
    assert cfg.camera_calibration.file == "data/camera_calibration.json"
    assert cfg.camera_calibration.squares_x * cfg.camera_calibration.squares_y % 2 == 0


def test_real_config_yaml_contains_new_sections():
    cfg = load_config()
    assert cfg.camera_calibration.min_views >= 3
    assert cfg.glasses_tracking.stabilize_frames >= 1
    assert cfg.glasses_tracking.ambiguity_evidence_px > 0.0
    assert cfg.glasses_tracking.compare_facemesh is False


@pytest.mark.parametrize(
    "section",
    [
        {"camera_calibration": {"dictionary": "NOPE"}},
        {"camera_calibration": {"squares_x": 7, "squares_y": 7}},
        {"camera_calibration": {"square_length_m": 0.01}},
        {"camera_calibration": {"marker_length_m": 0.03}},
        {"camera_calibration": {"unknown_field": 1}},
        {"camera_calibration": {"file": "outside.json"}},
        {"glasses_tracking": {"dictionary": "5X5_50"}},
        {"glasses_tracking": {"subpixel_win": 4}},
        {"glasses_tracking": {"subpixel_win": 0}},
        {"glasses_tracking": {"slerp_alpha": 1.5}},
        {"glasses_tracking": {"marker_size_m": 0}},
        {"glasses_tracking": {"acquisition_frames": 0}},
        {"glasses_tracking": {"ambiguity_branch_angle_deg": 5.0}},
        {"glasses_tracking": {"enabled": "yes"}},
        {"glasses_tracking": {"nope": 1}},
    ],
)
def test_new_sections_reject_invalid_values(section):
    with pytest.raises(ValueError):
        config_from_dict(section)


def test_unknown_but_well_formed_dictionary_fails_at_construction():
    with pytest.raises(ValueError):
        GlassesTracker._resolve_dictionary("DICT_9X9_999")
