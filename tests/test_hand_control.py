"""手控测试：张开手掌判定、gate 滞回、手控映射与配置校验（合成关键点，不开摄像头）。"""

from __future__ import annotations

import math

import numpy as np
import pytest

from eyemouse.app import resolve_cursor_driver, should_suspend_blink
from eyemouse.click_detector import ClickDetector
from eyemouse.config import config_from_dict
from eyemouse.hand_gesture import OpenPalmGate, is_open_palm
from eyemouse.hand_pointer import HandPointer, palm_center, tracking_point
from eyemouse.hand_tracker import HandTracker

SCREEN = (1001, 801)


# ---------------- 合成手部关键点 ----------------

def open_hand_points():
    """张开且五指分开的右手（2D 合成，单位任意）。"""
    return [
        (0.00, 0.00), (-0.12, 0.10), (-0.22, 0.16), (-0.40, 0.15), (-0.62, 0.28),
        (-0.25, 0.30), (-0.30, 0.55), (-0.33, 0.72), (-0.35, 0.85),
        (-0.08, 0.32), (-0.08, 0.58), (-0.09, 0.76), (-0.10, 0.90),
        (0.10, 0.32), (0.12, 0.56), (0.14, 0.73), (0.15, 0.86),
        (0.25, 0.30), (0.28, 0.50), (0.31, 0.64), (0.33, 0.75),
    ]


def fist_points():
    """握拳：四指与拇指都蜷起。"""
    points = list(open_hand_points())
    points[7] = (-0.28, 0.40)
    points[8] = (-0.20, 0.30)
    points[11] = (-0.07, 0.42)
    points[12] = (-0.06, 0.33)
    points[15] = (0.11, 0.42)
    points[16] = (0.08, 0.34)
    points[19] = (0.26, 0.42)
    points[20] = (0.22, 0.33)
    points[4] = (-0.20, 0.25)
    return points


def rotate(points, degrees):
    """整手绕原点旋转（判定应保持不变）。"""
    angle = math.radians(degrees)
    cos_v, sin_v = math.cos(angle), math.sin(angle)
    matrix = np.array([[cos_v, -sin_v], [sin_v, cos_v]])
    return (np.asarray(points, dtype=np.float64) @ matrix.T)


# ---------------- is_open_palm ----------------

def test_open_palm_true_for_spread_hand():
    assert is_open_palm(open_hand_points()) is True


def test_open_palm_false_for_fist_index_only_together_and_thumb_in():
    fist = fist_points()
    assert is_open_palm(fist) is False

    index_only = list(fist)
    index_only[7] = (-0.33, 0.72)
    index_only[8] = (-0.35, 0.85)
    assert is_open_palm(index_only) is False

    together = list(open_hand_points())
    together[8] = (-0.12, 0.85)
    together[12] = (-0.10, 0.90)
    together[16] = (-0.08, 0.86)
    together[20] = (-0.06, 0.75)
    assert is_open_palm(together) is False

    thumb_in = list(open_hand_points())
    thumb_in[3] = (-0.40, 0.15)
    thumb_in[4] = (-0.20, 0.25)
    assert is_open_palm(thumb_in) is False


@pytest.mark.parametrize("degrees", [90, 180, 270, 45])
def test_open_palm_is_rotation_invariant(degrees):
    assert is_open_palm(rotate(open_hand_points(), degrees)) is True
    assert is_open_palm(rotate(fist_points(), degrees)) is False


def test_open_palm_rejects_bad_input():
    assert is_open_palm([(0.0, 0.0)]) is False
    bad = list(open_hand_points())
    bad[3] = (float("nan"), 0.0)
    assert is_open_palm(bad) is False


def test_palm_center_is_mean_of_wrist_and_mcps():
    points = np.zeros((21, 2), dtype=np.float64)
    for index, value in ((0, 1.0), (5, 2.0), (9, 3.0), (13, 4.0), (17, 5.0)):
        points[index] = (value, value)
    center = palm_center(points)
    assert center == pytest.approx((3.0, 3.0))
    assert palm_center([(0.0, 0.0)]) is None


# ---------------- OpenPalmGate ----------------

def test_gate_enter_and_exit_hysteresis():
    gate = OpenPalmGate(enter_frames=3, exit_frames=2, lost_timeout=0.3)
    assert gate.update(0.0, True, True) is False
    assert gate.update(0.1, True, True) is False
    assert gate.update(0.2, True, True) is True
    # 单帧不满足不退出
    assert gate.update(0.3, True, False) is True
    assert gate.update(0.4, True, False) is False


def test_gate_ignores_flapping_and_requires_consecutive_enter():
    gate = OpenPalmGate(enter_frames=3, exit_frames=3, lost_timeout=1.0)
    for now, palm in ((0.0, True), (0.1, False), (0.2, True), (0.3, False), (0.4, True), (0.5, True)):
        assert gate.update(now, True, palm) is False


def test_gate_lost_timeout_exits_immediately():
    gate = OpenPalmGate(enter_frames=1, exit_frames=10, lost_timeout=0.3)
    assert gate.update(0.0, True, True) is True
    assert gate.update(0.1, False, False) is True  # 未超时
    assert gate.update(0.5, False, False) is False  # 超过 lost_timeout


def test_gate_reset_closes():
    gate = OpenPalmGate(enter_frames=1, exit_frames=1, lost_timeout=0.3)
    assert gate.update(0.0, True, True) is True
    gate.reset()
    assert gate.is_open is False


# ---------------- HandPointer ----------------

def hand_config(**overrides):
    data = {
        "pointer_source": "hand",
        "mapping": "relative",
        "gain": 1.0,
        "active_region": 0.6,
        "min_cutoff": 1000.0,
        "beta": 0.0,
        "deadzone_px": 0.0,
        "open_ratio": 1.1,
        "finger_spread_min": 0.25,
        "enter_frames": 1,
        "exit_frames": 1,
        "lost_timeout": 0.3,
        "hand_every_n_frames": 1,
        "suspend_blink_while_hand": False,
        "mirror_handedness": False,
    }
    data.update(overrides)
    return config_from_dict({"hand_control": data}).hand_control


def test_relative_mapping_moves_by_expected_delta():
    pointer = HandPointer(hand_config(gain=1.0), SCREEN)
    pointer.activate((0.5, 0.5), (500.0, 400.0))
    target = pointer.update((0.6, 0.5), 0.0)
    assert target == pytest.approx((600.1, 400.0))


def test_relative_reactivation_does_not_jump():
    pointer = HandPointer(hand_config(), SCREEN)
    pointer.activate((0.5, 0.5), (500.0, 400.0))
    moved = pointer.update((0.7, 0.6), 0.0)
    pointer.deactivate()
    # 在别处重新进入：以当前光标为参考，手位置即为新锚点 -> 不动
    pointer.activate((0.7, 0.6), moved)
    assert pointer.update((0.7, 0.6), 0.1) == pytest.approx(moved)


def test_relative_deadzone_holds_output():
    pointer = HandPointer(hand_config(gain=1.0, deadzone_px=50.0), SCREEN)
    pointer.activate((0.5, 0.5), (500.0, 400.0))
    assert pointer.update((0.501, 0.5), 0.0) == pytest.approx((500.0, 400.0))


def test_absolute_mapping_uses_active_region():
    pointer = HandPointer(hand_config(mapping="absolute", gain=1.0, active_region=0.6), SCREEN)
    pointer.activate((0.5, 0.5), (500.0, 400.0))
    assert pointer.update((0.5, 0.5), 0.0) == pytest.approx((500.0, 400.0))
    # 第二次调用会经过 One Euro（min_cutoff=1000 时 alpha≈1），允许极小平滑差
    assert pointer.update((0.8, 0.2), 0.1) == pytest.approx((1000.0, 0.0), abs=1.0)


def test_pointer_inactive_returns_none():
    pointer = HandPointer(hand_config(), SCREEN)
    assert pointer.update((0.5, 0.5), 0.0) is None


# ---------------- app 驱动决策 & 眨眼点击保持 ----------------

def test_hand_mode_does_not_move_cursor_when_gate_closed():
    assert resolve_cursor_driver("hand", False, "eye") == "none"
    assert resolve_cursor_driver("hand", True, "eye") == "hand"


def test_hybrid_and_eye_driver_selection():
    assert resolve_cursor_driver("hybrid", False, "eye") == "eye"
    assert resolve_cursor_driver("hybrid", False, "head") == "head"
    assert resolve_cursor_driver("hybrid", True, "head") == "hand"
    assert resolve_cursor_driver("eye", False, "head") == "head"


def test_suspend_blink_flag_logic():
    assert should_suspend_blink(False, True) is False
    assert should_suspend_blink(True, False) is False
    assert should_suspend_blink(True, True) is True


def test_blink_click_still_works_in_hand_mode():
    """手模式下 gate 关闭不移动光标，但眨眼点击链路不受影响。"""
    assert resolve_cursor_driver("hand", False, "eye") == "none"
    detector = ClickDetector(config_from_dict({}).click)
    dt = 1.0 / 30.0
    frames = []
    now = 0.0
    for ear, duration in (
        (0.30, 0.10), (0.05, 0.15), (0.30, 0.20), (0.05, 0.15), (0.30, 0.80)
    ):
        for _ in range(max(1, int(round(duration / dt)))):
            frames.append((now, float(ear)))
            now += dt
    events = []
    for t, ear in frames:
        detector.push_position(t, 500.0, 400.0)
        event = detector.update(t, ear, 0.30, (500.0, 400.0), True)
        if event is not None:
            events.append(event)
    assert len(events) == 1
    assert events[0].action == "left_click"


# ---------------- 配置校验 ----------------

def test_hand_control_defaults():
    cfg = config_from_dict({}).hand_control
    assert cfg.enabled is True
    assert cfg.pointer_source == "hand"
    assert cfg.mapping == "relative"
    assert cfg.gain == 2.4
    assert cfg.active_region == 0.6
    assert cfg.open_ratio == 1.1
    assert cfg.finger_spread_min == 0.25
    assert cfg.enter_frames == 5
    assert cfg.exit_frames == 5
    assert cfg.lost_timeout == 0.3
    assert cfg.hand_every_n_frames == 1
    assert cfg.suspend_blink_while_hand is False
    assert cfg.mirror_handedness is False
    assert cfg.tracking_point == "thumb_tip"
    assert cfg.require_thumb is True


def test_hand_control_rejects_invalid_values():
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"pointer_source": "mouse"}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"mapping": "warp"}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"active_region": 1.5}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"active_region": 0.0}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"gain": 0.0}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"tracking_point": "nose"}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"enter_frames": 0}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"finger_spread_min": 2.0}})
    with pytest.raises(ValueError):
        config_from_dict({"hand_control": {"unknown": 1}})


# ---------------- 左右手标签（回归：camera.mirror=true 时不得再互换） ----------------

def _tracker_with(mirror_handedness: bool) -> HandTracker:
    """不加载 MediaPipe 模型，仅构造可测 `_correct` 的实例。"""
    tracker = HandTracker.__new__(HandTracker)
    tracker.mirror_handedness = mirror_handedness
    return tracker


def test_handedness_not_swapped_for_mirrored_camera_frame():
    """摄像头帧已镜像（camera.mirror=true）时 MediaPipe 标签即真实左右手。"""
    tracker = _tracker_with(False)
    assert tracker._correct("Right") == "Right"
    assert tracker._correct("Left") == "Left"


def test_handedness_swapped_for_unmirrored_camera_frame():
    """非镜像输入下需要互换标签才能得到真实左右手。"""
    tracker = _tracker_with(True)
    assert tracker._correct("Right") == "Left"
    assert tracker._correct("Left") == "Right"


def test_default_config_does_not_double_swap_handedness():
    """默认 camera.mirror=true 与 hand_control.mirror_handedness=false 必须一致，避免判反。"""
    cfg = config_from_dict({})
    assert cfg.camera.mirror is True
    assert cfg.hand_control.mirror_handedness is False


# ---------------- 追踪点选择与拇指条件 ----------------

def test_tracking_point_selects_configured_landmark():
    points = open_hand_points()
    array = np.asarray(points, dtype=np.float64)
    palm = tuple(array[[0, 5, 9, 13, 17]].mean(axis=0))

    assert tracking_point(points, "palm") == pytest.approx(palm)
    assert tracking_point(points, "wrist") == pytest.approx(tuple(array[0]))
    assert tracking_point(points, "index_tip") == pytest.approx(tuple(array[8]))
    assert tracking_point(points, "thumb_tip") == pytest.approx(tuple(array[4]))
    # 未知取值回退为手掌中心
    assert tracking_point(points, "nose") == pytest.approx(palm)
    assert tracking_point(points, "PALM") == pytest.approx(palm)
    assert tracking_point([(0.0, 0.0)]) is None


def test_tracking_point_changes_with_mode():
    points = open_hand_points()
    assert tracking_point(points, "palm") != pytest.approx(tracking_point(points, "thumb_tip"))


def test_require_thumb_toggles_thumb_condition():
    tucked = list(open_hand_points())
    tucked[3] = (0.12, 0.30)
    tucked[4] = (0.25, 0.30)  # 拇指尖收拢到小指 MCP 附近

    assert is_open_palm(tucked) is False
    assert is_open_palm(tucked, require_thumb=False) is True
