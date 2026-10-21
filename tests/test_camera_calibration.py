"""摄像头内参标定测试：板参数、渲染比例、检测角点顺序、标定恢复、存读与版本。

全部使用合成图像与数值，不开真实摄像头、不动真实鼠标。
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from eyemouse.camera_calibration import (
    SCHEMA_VERSION,
    CalibrationError,
    CameraCalibration,
    CharucoBoardSpec,
    DetectedView,
    calibrate_from_views,
    coverage_cells,
    detect_view,
    image_size_matches,
    is_duplicate_view,
    load_calibration,
    make_charuco_board,
    measure_rendered_square_px,
    normalize_corners,
    render_board_image,
    resolve_dictionary,
    save_calibration,
    view_reprojection_rms,
    write_board_image,
)

K_TRUE = np.array([[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]])
IMAGE_SIZE = (1280, 720)
DIST_ZERO = np.zeros((1, 5), dtype=np.float64)


def _spec() -> CharucoBoardSpec:
    return CharucoBoardSpec(dictionary="DICT_5X5_50", squares_x=8, squares_y=6)


def _calibration() -> CameraCalibration:
    return CameraCalibration(
        camera_matrix=K_TRUE.copy(),
        dist_coeffs=np.zeros(5, dtype=np.float64),
        image_size=IMAGE_SIZE,
        rms_px=0.42,
        per_view_rms_px=[0.3, 0.5],
        num_views=12,
        coverage_cells_hit=9,
        board=_spec(),
    )


def _synthetic_views(count: int = 10, noise: float = 0.0) -> list:
    """用已知内参投影 ChArUco 角点，合成标定视图（不渲染图像）。"""
    board = make_charuco_board(_spec())
    object_points = np.asarray(board.getChessboardCorners(), dtype=np.float64)
    rng = np.random.default_rng(7)
    tilts = [(25, -15), (-20, 20), (15, -25), (-25, 15), (30, -20),
             (-15, 25), (20, -10), (-30, 10), (10, -30), (-10, 30)]
    views = []
    for index in range(count):
        tilt_x, tilt_y = tilts[index % len(tilts)]
        rvec = np.array([np.deg2rad(tilt_x), np.deg2rad(tilt_y), np.deg2rad(5.0 * index)])
        tvec = np.array([0.01 * (index % 3), 0.01 * (index % 2), 0.35 + 0.01 * (index % 5)])
        projected, _ = cv2.projectPoints(object_points, rvec, tvec, K_TRUE, DIST_ZERO)
        points = projected.reshape(-1, 2).astype(np.float64)
        if noise > 0.0:
            points = points + rng.normal(0.0, noise, points.shape)
        ids = np.arange(object_points.shape[0], dtype=np.int32).reshape(-1, 1)
        views.append(DetectedView(corners=points.astype(np.float32).reshape(-1, 1, 2), ids=ids))
    return views


# ---------------- 板参数与字典 ----------------
def test_board_spec_corner_count_and_dict_roundtrip():
    spec = _spec()
    assert spec.corner_count == 35
    payload = spec.to_dict()
    assert payload["unit"] == "meter"
    assert payload["square_length_m"] == pytest.approx(0.025)
    restored = CharucoBoardSpec.from_config(spec)
    assert restored == spec


def test_resolve_dictionary_rejects_unknown_and_empty():
    assert resolve_dictionary("DICT_5X5_50") is not None
    with pytest.raises(CalibrationError):
        resolve_dictionary("NOT_A_DICT")
    with pytest.raises(CalibrationError):
        resolve_dictionary("  ")


def test_make_charuco_board_rejects_invalid_geometry():
    with pytest.raises(CalibrationError):
        make_charuco_board(CharucoBoardSpec(squares_x=7, squares_y=5))
    with pytest.raises(CalibrationError):
        make_charuco_board(CharucoBoardSpec(square_length_m=0.02, marker_length_m=0.02))


# ---------------- 渲染与打印比例 ----------------
def test_render_board_image_has_exact_physical_scale():
    image, px_per_meter_x, px_per_meter_y = render_board_image(_spec(), pixels_per_meter=4000.0)
    assert image.shape == (600, 800)
    assert px_per_meter_x == pytest.approx(4000.0)
    assert px_per_meter_y == pytest.approx(4000.0)
    # 一格 25 mm @ 4000 px/m 必须正好 100 px（缩掉留白会导致打印尺寸错误）
    measured = measure_rendered_square_px(image, _spec())
    assert measured == pytest.approx(100.0, abs=0.5)


def test_render_board_image_rejects_bad_scale():
    with pytest.raises(CalibrationError):
        render_board_image(_spec(), pixels_per_meter=0.0)


def test_write_board_image_roundtrips_and_measures(tmp_path):
    target = write_board_image(_spec(), tmp_path / "board.png")
    assert target.is_file()
    image = cv2.imread(str(target))
    assert image is not None
    assert measure_rendered_square_px(image, _spec()) == pytest.approx(100.0, abs=0.5)


def test_write_board_image_sets_physical_dpi(tmp_path):
    pillow = pytest.importorskip("PIL.Image")
    target = write_board_image(_spec(), tmp_path / "board.png")
    info = pillow.open(str(target)).info
    dpi = info.get("dpi")
    assert dpi is not None
    assert dpi[0] == pytest.approx(4000.0 / 39.37007874015748, rel=1e-3)


# ---------------- 检测与角点顺序 ----------------
def test_detect_view_returns_all_corners_with_consistent_order():
    image, _, _ = render_board_image(_spec(), pixels_per_meter=2000.0)
    view = detect_view(image, _spec())
    assert view is not None
    assert view.count == 35
    ids = np.asarray(view.ids).ravel()
    points = np.asarray(view.corners).reshape(-1, 2)
    lookup = {int(marker_id): points[index] for index, marker_id in enumerate(ids)}
    board = make_charuco_board(_spec())
    object_points = np.asarray(board.getChessboardCorners(), dtype=np.float64)
    # 角点 id 与棋盘角点一一对应：id 0 是最上一行最左侧，id 1 在其右侧。
    assert lookup[0][0] < lookup[1][0]
    assert lookup[0][1] == pytest.approx(lookup[1][1], abs=2.0)
    # 下一行的第一个角点（id = squares_x - 1）应在 id 0 下方。
    below = lookup[_spec().squares_x - 1]
    assert below[1] > lookup[0][1]
    # id 顺序必须与 getChessboardCorners 的行优先顺序一致：同一列，下一行。
    assert below[0] == pytest.approx(lookup[0][0], abs=2.0)
    assert object_points[0][1] < object_points[_spec().squares_x - 1][1]


def test_detect_view_returns_none_on_blank_image():
    blank = np.full((480, 640), 255, dtype=np.uint8)
    assert detect_view(blank, _spec()) is None


def test_coverage_and_duplicate_helpers():
    corners = np.array([[[0.0, 0.0]], [[1279.0, 0.0]], [[0.0, 719.0]], [[1279.0, 719.0]]])
    hit = coverage_cells(corners, IMAGE_SIZE, 3)
    assert len(hit) == 4
    assert np.allclose(normalize_corners(corners, IMAGE_SIZE)[0], [0.0, 0.0])
    assert is_duplicate_view(corners, [corners], IMAGE_SIZE, 0.02) is True
    moved = corners + 400.0
    assert is_duplicate_view(moved, [corners], IMAGE_SIZE, 0.02) is False
    assert is_duplicate_view(corners, [], IMAGE_SIZE, 0.02) is False


# ---------------- 标定恢复 ----------------
def test_calibrate_from_views_recovers_intrinsics():
    views = _synthetic_views(count=12)
    calibration, warnings = calibrate_from_views(views, IMAGE_SIZE, _spec(), min_views=10)
    matrix = calibration.camera_matrix
    assert matrix[0, 0] == pytest.approx(900.0, rel=0.02)
    assert matrix[1, 1] == pytest.approx(900.0, rel=0.02)
    assert matrix[0, 2] == pytest.approx(640.0, abs=10.0)
    assert matrix[1, 2] == pytest.approx(360.0, abs=10.0)
    assert calibration.rms_px < 1.0
    assert calibration.num_views == 12
    assert calibration.image_size == IMAGE_SIZE
    assert isinstance(warnings, list)
    assert len(calibration.per_view_rms_px) == 12


def test_calibrate_from_views_rejects_too_few_views():
    views = _synthetic_views(count=4)
    with pytest.raises(CalibrationError):
        calibrate_from_views(views, IMAGE_SIZE, _spec(), min_views=15)


def test_calibrate_from_views_rejects_non_finite_and_bad_ids():
    views = _synthetic_views(count=12)
    broken = list(views)
    bad_corners = np.array(broken[0].corners, dtype=np.float32).copy()
    bad_corners[0, 0, 0] = np.nan
    broken[0] = DetectedView(corners=bad_corners, ids=broken[0].ids)
    with pytest.raises(CalibrationError):
        calibrate_from_views(broken, IMAGE_SIZE, _spec(), min_views=10)
    wrong_ids = list(views)
    wrong_ids[0] = DetectedView(corners=wrong_ids[0].corners, ids=np.full_like(views[0].ids, 999))
    with pytest.raises(CalibrationError):
        calibrate_from_views(wrong_ids, IMAGE_SIZE, _spec(), min_views=10)


def test_view_reprojection_rms_is_zero_for_exact_projection():
    board = make_charuco_board(_spec())
    object_points = np.asarray(board.getChessboardCorners(), dtype=np.float64)
    rvec = np.array([0.2, -0.1, 0.05])
    tvec = np.array([0.0, 0.0, 0.4])
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, K_TRUE, DIST_ZERO)
    rms = view_reprojection_rms(
        object_points, projected.reshape(-1, 2), rvec, tvec, K_TRUE, DIST_ZERO
    )
    assert rms == pytest.approx(0.0, abs=1e-6)


# ---------------- 存读、版本、备份、分辨率 ----------------
def test_save_load_roundtrip(tmp_path):
    target = tmp_path / "camera_calibration.json"
    save_calibration(_calibration(), target)
    loaded = load_calibration(target)
    assert loaded.schema_version == SCHEMA_VERSION
    assert np.allclose(loaded.camera_matrix, K_TRUE)
    assert loaded.image_size == IMAGE_SIZE
    assert loaded.board == _spec()
    assert loaded.saved_at
    assert image_size_matches(loaded, IMAGE_SIZE) is True
    assert image_size_matches(loaded, (640, 480)) is False


def test_save_backs_up_existing_file(tmp_path):
    target = tmp_path / "camera_calibration.json"
    save_calibration(_calibration(), target)
    save_calibration(_calibration(), target)
    backups = list(tmp_path.glob("camera_calibration.*.bak.json"))
    assert len(backups) == 1


def test_load_missing_file_raises_chinese_error(tmp_path):
    with pytest.raises(CalibrationError) as excinfo:
        load_calibration(tmp_path / "missing.json")
    assert "camera_calibration" in str(excinfo.value) or "标定" in str(excinfo.value)


def test_load_rejects_wrong_version_and_structure(tmp_path):
    target = tmp_path / "camera_calibration.json"
    save_calibration(_calibration(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = SCHEMA_VERSION + 1
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_calibration(target)

    payload["schema_version"] = SCHEMA_VERSION
    payload.pop("camera_matrix")
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_calibration(target)


def test_load_rejects_non_finite_values(tmp_path):
    target = tmp_path / "camera_calibration.json"
    save_calibration(_calibration(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["camera_matrix"][0][0] = float("nan")
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_calibration(target)


def test_load_rejects_non_object_json(tmp_path):
    target = tmp_path / "camera_calibration.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(CalibrationError):
        load_calibration(target)
