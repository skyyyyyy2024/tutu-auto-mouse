"""调试叠加层关键点映射回归测试：校准前后同一帧绘制坐标必须一致。

背景：叠加层先把摄像头帧缩放到 480x360 画布再画关键点。原先只用
``scale = canvas_w / frame_w`` 同时缩放 x、y，当帧为 16:9、画布为 4:3 时
纵向会被压缩，关键点显示在眼睛上方。修复后用帧实际 (w, h) 与画布
(w, h) 各自缩放，且不使用屏幕坐标或头姿补偿值。
"""

from __future__ import annotations

import inspect

import cv2
import numpy as np
import pytest

from eyemouse.config import config_from_dict
from eyemouse.landmarks import FaceLandmarks
from eyemouse.ui import KEYPOINT_INDEXES, UI, map_point_to_canvas

FRAME_W, FRAME_H = 1280, 720
CANVAS_W, CANVAS_H = 480, 360


def _make_face(frame_w: int, frame_h: int, seed: int = 0) -> FaceLandmarks:
    rng = np.random.default_rng(seed)
    pts_norm = rng.random((478, 2))
    pts_px = pts_norm * np.array([frame_w, frame_h], dtype=np.float64)
    pts_3d = np.zeros((478, 3), dtype=np.float64)
    return FaceLandmarks(
        pts_norm=pts_norm, pts_px=pts_px, pts_3d=pts_3d, img_w=frame_w, img_h=frame_h
    )


def test_map_point_scales_axes_independently():
    x, y = map_point_to_canvas(640.0, 360.0, FRAME_W, FRAME_H, CANVAS_W, CANVAS_H)
    assert x == pytest.approx(240.0)
    assert y == pytest.approx(180.0)


def test_map_point_handles_degenerate_frame():
    assert map_point_to_canvas(10.0, 20.0, 0, 0, CANVAS_W, CANVAS_H) == (10.0, 20.0)


def test_mapping_fixes_legacy_single_scale_bias():
    # 归一化中心点 (0.5, 0.5) 映射后仍应落在画布中心。
    x, y = map_point_to_canvas(
        0.5 * FRAME_W, 0.5 * FRAME_H, FRAME_W, FRAME_H, CANVAS_W, CANVAS_H
    )
    assert y / CANVAS_H == pytest.approx(0.5, abs=0.01)
    # 旧的单一 scale 会得到相对 y=0.375（偏上 25%），确认回归点存在。
    legacy_y = (0.5 * FRAME_H) * (CANVAS_W / FRAME_W)
    assert legacy_y / CANVAS_H == pytest.approx(0.375, abs=0.01)


def test_draw_face_points_signature_has_no_screen_or_pose():
    params = list(inspect.signature(UI._draw_face_points).parameters)
    assert params == ["canvas", "face", "frame_width", "frame_height"]


def test_overlay_matches_camera_test_relative_positions(monkeypatch):
    face = _make_face(FRAME_W, FRAME_H)
    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)

    captured = []

    def fake_circle(img, center, radius, color, thickness=1, lineType=None, shift=None):
        captured.append(center)

    monkeypatch.setattr(cv2, "circle", fake_circle)

    UI._draw_face_points(canvas, face, FRAME_W, FRAME_H)

    assert len(captured) == len(KEYPOINT_INDEXES)
    for center, index in zip(captured, KEYPOINT_INDEXES):
        px, py = face.pts_px[index]
        # 校准前 (--camera-test) 直接画在帧上：相对位置 = px/frame_w, py/frame_h
        rel_before_x = px / FRAME_W
        rel_before_y = py / FRAME_H
        # 校准后叠加层画在画布上：相对位置必须与校准前一致。
        rel_after_x = center[0] / CANVAS_W
        rel_after_y = center[1] / CANVAS_H
        assert rel_after_x == pytest.approx(rel_before_x, abs=1.5 / CANVAS_W)
        assert rel_after_y == pytest.approx(rel_before_y, abs=1.5 / CANVAS_H)


def test_draw_head_axis_signature_has_no_self():
    """回归：_draw_head_axis 必须是 staticmethod，否则经实例调用会把 self 当 canvas 传入。"""
    params = list(inspect.signature(UI._draw_head_axis).parameters)
    assert params == [
        "canvas",
        "rvec",
        "tvec",
        "frame_width",
        "frame_height",
        "axis_length",
        "focal_scale",
    ]


def test_draw_head_axis_callable_via_instance(monkeypatch):
    """回归：按 draw_debug 的调用方式经实例调用，不得抛 TypeError。"""
    cfg = config_from_dict({})
    ui = UI(cfg, (1920, 1080), show_window=False)
    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)

    drawn = []
    monkeypatch.setattr(cv2, "line", lambda *args, **kwargs: drawn.append(args))

    rvec = np.zeros((3, 1), dtype=np.float64)
    tvec = np.array([[0.0], [0.0], [600.0]], dtype=np.float64)
    ui._draw_head_axis(canvas, rvec, tvec, FRAME_W, FRAME_H, 40.0, 1.0)

    assert len(drawn) == 3
