"""打印用眼镜 ArUco 单标记图纸测试：全部合成数据，不开摄像头、不控制鼠标。

重点锁死三件事：黑框物理边长与配置一致、PNG 物理分辨率元数据可还原真实尺寸、
白边（quiet zone）在图上确实留白。
"""

from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from eyemouse.camera_calibration import CalibrationError, resolve_dictionary
from eyemouse.marker_sheet import (
    MarkerSheetSpec,
    detect_marker_ids,
    marker_cell_count,
    marker_geometry,
    measure_marker_bbox_px,
    render_marker_patch,
    render_marker_sheet,
    ruler_band_height,
    ruler_line_thickness,
    sheet_annotation_lines,
    write_marker_sheet,
)


def _spec(**overrides) -> MarkerSheetSpec:
    values = {
        "dictionary": "DICT_5X5_50",
        "marker_id": 0,
        "marker_size_m": 0.030,
        "quiet_margin_m": 0.010,
        "ruler_mm": 100.0,
    }
    values.update(overrides)
    return MarkerSheetSpec(**values)


def _gray(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _png_phys_px_per_meter(path: Path) -> int:
    data = Path(path).read_bytes()
    index = data.index(b"pHYs")
    x_ppu, _y_ppu, _unit = struct.unpack(">LLB", data[index + 4 : index + 13])
    return int(x_ppu)


def test_marker_cell_count_follows_dictionary_bits():
    assert marker_cell_count(_spec()) == 7
    assert marker_cell_count(_spec(dictionary="DICT_4X4_50")) == 6
    assert marker_cell_count(_spec(border_bits=2)) == 9


def test_marker_cell_count_rejects_bad_border_bits():
    with pytest.raises(CalibrationError):
        marker_cell_count(_spec(border_bits=0))


def test_geometry_snaps_to_integer_cells():
    geometry = marker_geometry(_spec())
    assert geometry.cells == 7
    assert geometry.cell_px == 51
    assert geometry.marker_px == 357
    assert geometry.pixels_per_meter == pytest.approx(11900.0, rel=1e-9)
    assert geometry.pixels_per_meter_int == 11900
    assert geometry.patch_px == 357 + 2 * 119
    assert geometry.dpi == pytest.approx(302.26, abs=0.01)


def test_geometry_physical_size_is_exact():
    geometry = marker_geometry(_spec())
    assert geometry.marker_size_mm == pytest.approx(30.0, abs=1e-6)
    assert geometry.quiet_margin_mm == pytest.approx(10.0, abs=1e-6)
    assert geometry.ruler_mm == pytest.approx(100.0, abs=1e-6)
    assert geometry.marker_px / geometry.pixels_per_meter == pytest.approx(0.030, rel=1e-9)
    other = marker_geometry(_spec(marker_size_m=0.05))
    assert other.marker_size_mm == pytest.approx(50.0, abs=1e-6)
    assert other.marker_size_mm / 1000.0 == pytest.approx(0.05, rel=1e-9)


@pytest.mark.parametrize(
    "overrides",
    [
        {"marker_size_m": 0.0},
        {"marker_size_m": -0.01},
        {"pixels_per_meter": 0.0},
        {"pixels_per_meter": -1.0},
        {"quiet_margin_m": -0.001},
        {"ruler_mm": 0.0},
    ],
)
def test_geometry_rejects_invalid_values(overrides):
    with pytest.raises(CalibrationError):
        marker_geometry(_spec(**overrides))


def test_geometry_rejects_unknown_dictionary():
    with pytest.raises(CalibrationError):
        marker_geometry(_spec(dictionary="NOT_A_DICT"))


def test_quiet_margin_is_at_least_one_cell():
    geometry = marker_geometry(_spec(quiet_margin_m=0.0))
    assert geometry.quiet_px == geometry.cell_px


def test_render_patch_has_exact_black_square_and_quiet_zone():
    patch, geometry = render_marker_patch(_spec())
    assert patch.shape == (geometry.patch_px, geometry.patch_px)
    assert measure_marker_bbox_px(patch) == (
        geometry.quiet_px,
        geometry.quiet_px,
        geometry.marker_px,
    )
    ring = geometry.quiet_px
    assert bool((patch[:ring] == 255).all())
    assert bool((patch[-ring:] == 255).all())
    assert bool((patch[:, :ring] == 255).all())
    assert bool((patch[:, -ring:] == 255).all())


def test_rendered_marker_is_detectable_with_expected_id():
    patch, _geometry = render_marker_patch(_spec())
    assert detect_marker_ids(patch, "DICT_5X5_50") == [0]
    other, _geometry2 = render_marker_patch(_spec(marker_id=7))
    assert detect_marker_ids(other, "DICT_5X5_50") == [7]


def test_render_rejects_out_of_range_marker_id():
    with pytest.raises(CalibrationError):
        render_marker_patch(_spec(marker_id=99))


def test_sheet_annotation_lines_are_ascii_only():
    geometry = marker_geometry(_spec())
    lines = sheet_annotation_lines(_spec(), geometry)
    assert lines
    for line in lines:
        assert line.isascii(), line


def test_sheet_keeps_marker_centred_and_quiet_zone_white():
    image, geometry = render_marker_sheet(_spec())
    gray = _gray(image)
    measured = measure_marker_bbox_px(gray)
    assert measured is not None
    left, top, side = measured
    assert side == geometry.marker_px
    assert abs((left + side / 2.0) - gray.shape[1] / 2.0) <= 1.0
    assert top >= geometry.quiet_px
    assert bool((gray[top - geometry.quiet_px : top, left : left + side] == 255).all())
    assert bool((gray[top : top + side, left - geometry.quiet_px : left] == 255).all())


def test_sheet_ruler_bar_is_exact_length():
    image, geometry = render_marker_sheet(_spec())
    gray = _gray(image)
    dark = gray < 128
    row_index = int(np.argmax(dark.sum(axis=1)))
    columns = np.where(dark[row_index])[0]
    span = int(columns.max()) - int(columns.min()) + 1
    assert span == geometry.ruler_px + ruler_line_thickness(geometry)
    assert geometry.ruler_px == round(geometry.ruler_mm / 1000.0 * geometry.pixels_per_meter)


def test_sheet_fits_a4_with_margin():
    image, geometry = render_marker_sheet(_spec())
    width_mm = image.shape[1] / geometry.pixels_per_meter * 1000.0
    height_mm = image.shape[0] / geometry.pixels_per_meter * 1000.0
    assert width_mm <= 190.0
    assert height_mm <= 280.0


def test_ruler_band_height_covers_ticks_and_labels():
    geometry = marker_geometry(_spec())
    band = ruler_band_height(geometry, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 1)
    assert band > 0


def test_write_marker_sheet_sets_physical_resolution(tmp_path):
    target = write_marker_sheet(_spec(), tmp_path / "marker.png")
    assert target.exists()
    geometry = marker_geometry(_spec())
    assert _png_phys_px_per_meter(target) == geometry.pixels_per_meter_int
    image = cv2.imread(str(target), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    assert measure_marker_bbox_px(image)[2] == geometry.marker_px


def test_write_marker_sheet_physical_size_from_metadata(tmp_path):
    target = write_marker_sheet(_spec(), tmp_path / "marker.png")
    ppm = _png_phys_px_per_meter(target)
    geometry = marker_geometry(_spec())
    printed_mm = geometry.marker_px / ppm * 1000.0
    assert printed_mm == pytest.approx(30.0, abs=0.01)


def test_write_marker_sheet_accepts_prerendered_image(tmp_path):
    image, geometry = render_marker_sheet(_spec())
    target = write_marker_sheet(_spec(), tmp_path / "marker.png", image=image)
    assert target.exists()
    written = cv2.imread(str(target), cv2.IMREAD_GRAYSCALE)
    assert written.shape == _gray(image).shape
    assert _png_phys_px_per_meter(target) == geometry.pixels_per_meter_int


def test_spec_from_config_reads_glasses_tracking():
    cfg = SimpleNamespace(
        glasses_tracking=SimpleNamespace(
            dictionary="DICT_5X5_50", marker_id=3, marker_size_m=0.042
        )
    )
    spec = MarkerSheetSpec.from_config(cfg)
    assert spec.dictionary == "DICT_5X5_50"
    assert spec.marker_id == 3
    assert spec.marker_size_m == pytest.approx(0.042)
    assert marker_geometry(spec).marker_size_mm == pytest.approx(42.0, abs=1e-6)


def test_spec_from_config_rejects_missing_section():
    with pytest.raises(CalibrationError):
        MarkerSheetSpec.from_config(SimpleNamespace())


def test_printed_marker_size_matches_tracker_convention():
    """合成投影：按图纸黑框边长渲染后，PnP 反推距离应与真值一致（正负 5%）。

    这条测试锁死跨模块契约：图纸上 30 mm 的黑框，与追踪模块 ``marker_size_m``
    指的是同一个量（黑框外缘到外缘），否则平移量会整体按比例错。
    """
    from eyemouse.glasses_tracker import marker_object_points

    spec = _spec()
    patch, geometry = render_marker_patch(spec)
    fx = 1000.0
    distance_m = 0.5
    expected_px = fx * spec.marker_size_m / distance_m
    scale = expected_px / geometry.marker_px
    resized = cv2.resize(patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    size = 400
    canvas = np.full((size, size), 255, dtype=np.uint8)
    top = (size - resized.shape[0]) // 2
    left = (size - resized.shape[1]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    detector = cv2.aruco.ArucoDetector(
        resolve_dictionary(spec.dictionary), cv2.aruco.DetectorParameters()
    )
    corners, ids, _rejected = detector.detectMarkers(canvas)
    assert ids is not None
    assert int(np.asarray(ids).ravel()[0]) == spec.marker_id
    image_points = np.asarray(corners[0], dtype=np.float64).reshape(4, 1, 2)
    camera_matrix = np.array(
        [[fx, 0.0, size / 2.0], [0.0, fx, size / 2.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    solved = cv2.solvePnP(
        marker_object_points(spec.marker_size_m),
        image_points,
        camera_matrix,
        np.zeros((1, 5), dtype=np.float64),
        flags=cv2.SOLVEPNP_IPPE_SQUARE,
    )
    assert solved[0]
    estimated_m = float(np.asarray(solved[2]).ravel()[2])
    assert estimated_m == pytest.approx(distance_m, rel=0.05)
