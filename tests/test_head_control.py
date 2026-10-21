"""面部朝向控制光标测试：摇杆速度、绝对映射、方向反转、来源切换与配置校验。"""

from __future__ import annotations

import math

import pytest

from eyemouse.config import config_from_dict
from eyemouse.head_control import HeadCursorMapper, axis_velocity, next_source

SCREEN = (1001, 801)  # (w-1, h-1) = (1000, 800)，中心方便断言为 (500, 400)


def _cfg(**overrides):
    data = {
        "mode": "velocity",
        "deadzone_deg": 4.0,
        "max_yaw_deg": 20.0,
        "max_pitch_deg": 20.0,
        "speed_px_s": 1000.0,
        "response": 1.0,
        "smoothing_alpha": 1.0,
        "invert_x": False,
        "invert_y": False,
    }
    data.update(overrides)
    return config_from_dict({"head_control": data}).head_control


def test_axis_velocity_deadzone_and_saturation():
    assert axis_velocity(0.0, 4.0, 20.0, 1000.0, 1.0) == 0.0
    assert axis_velocity(3.9, 4.0, 20.0, 1000.0, 1.0) == 0.0
    assert axis_velocity(4.0, 4.0, 20.0, 1000.0, 1.0) == 0.0
    # 单调且饱和
    mid = axis_velocity(12.0, 4.0, 20.0, 1000.0, 1.0)
    assert 0.0 < mid < 1000.0
    assert axis_velocity(20.0, 4.0, 20.0, 1000.0, 1.0) == pytest.approx(1000.0)
    assert axis_velocity(200.0, 4.0, 20.0, 1000.0, 1.0) == pytest.approx(1000.0)
    assert axis_velocity(-20.0, 4.0, 20.0, 1000.0, 1.0) == pytest.approx(-1000.0)
    assert math.isnan(axis_velocity(float("nan"), 4.0, 20.0, 1000.0, 1.0)) is False
    assert axis_velocity(float("nan"), 4.0, 20.0, 1000.0, 1.0) == 0.0


def test_axis_velocity_response_is_monotonic():
    low = axis_velocity(8.0, 4.0, 20.0, 1000.0, 2.0)
    high = axis_velocity(16.0, 4.0, 20.0, 1000.0, 2.0)
    assert 0.0 < low < high < 1000.0


def test_velocity_moves_toward_face_direction():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)  # 第一帧只记录时间
    assert mapper.position == (500.0, 400.0)
    mapper.update(0.0, 0.0, 0.1)
    assert mapper.position == (500.0, 400.0)  # 中性区不动

    x, y = mapper.update(20.0, 0.0, 0.2)  # 向右看 -> 光标右移
    assert x == pytest.approx(600.0)
    assert y == pytest.approx(400.0)

    x, y = mapper.update(0.0, 20.0, 0.3)  # 抬头 -> 光标上移
    assert x == pytest.approx(600.0)
    assert y == pytest.approx(300.0)


def test_velocity_deadzone_holds_position():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    mapper.update(15.0, 15.0, 0.1)
    before = mapper.position
    mapper.update(3.0, -3.0, 0.2)  # 回到中性区，仍在死区内
    assert mapper.position == before


def test_velocity_respects_invert_flags():
    mapper = HeadCursorMapper(_cfg(invert_x=True, invert_y=True), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    x, y = mapper.update(20.0, 20.0, 0.1)
    assert x < 500.0  # 默认右移，反转后左移
    assert y > 400.0  # 默认上移，反转后下移


def test_velocity_clamps_to_screen():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    for index in range(1, 30):
        mapper.update(20.0, 20.0, index * 0.1)  # 右转 + 抬头
    x, y = mapper.position
    assert 0.0 <= x <= 1000.0
    assert 0.0 <= y <= 800.0
    assert x == pytest.approx(1000.0)
    assert y == pytest.approx(0.0)


def test_velocity_dt_is_capped_after_long_stall():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    x, _ = mapper.update(20.0, 0.0, 100.0)  # 100 秒卡顿
    assert x == pytest.approx(500.0 + 1000.0 * 0.2)  # 单帧最多 0.2 秒


def test_absolute_maps_angle_to_screen():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    assert mapper.update(0.0, 0.0, 0.0) == (500.0, 400.0)
    assert mapper.update(20.0, 20.0, 0.1) == (1000.0, 0.0)
    assert mapper.update(-20.0, -20.0, 0.2) == (0.0, 800.0)
    # 超出范围被裁剪
    assert mapper.update(80.0, -80.0, 0.3) == (1000.0, 800.0)


def test_absolute_respects_invert_y():
    mapper = HeadCursorMapper(_cfg(mode="absolute", invert_y=True), SCREEN)
    assert mapper.update(0.0, 20.0, 0.0) == (500.0, 800.0)


def test_reset_returns_to_center():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    mapper.update(20.0, 0.0, 0.1)
    assert mapper.position != (500.0, 400.0)
    mapper.reset()
    assert mapper.position == (500.0, 400.0)


def test_next_source_cycles_between_eye_and_head():
    assert next_source("eye") == "head"
    assert next_source("head") == "eye"
    assert next_source("unknown") == "eye"


def test_config_defaults_keep_eye_source():
    cfg = config_from_dict({})
    assert cfg.head_control.enabled is True
    assert cfg.head_control.default_source == "eye"
    assert cfg.head_control.mode == "velocity"
    assert cfg.safety.cursor_key == "f5"


def test_config_rejects_invalid_head_control():
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"default_source": "mouse"}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"mode": "warp"}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"max_yaw_deg": 2.0, "deadzone_deg": 4.0}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"smoothing_alpha": 1.5}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"unknown": 1}})


def test_absolute_treats_recenter_as_center():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    assert mapper.recenter(10.0, -5.0) is True
    assert mapper.center == (10.0, -5.0)
    assert mapper.position == (500.0, 400.0)  # 立刻落到基点对应的屏幕中心
    assert mapper.update(10.0, -5.0, 0.0) == (500.0, 400.0)
    assert mapper.update(30.0, -25.0, 0.1) == (1000.0, 800.0)  # 相对基点 ±20°


def test_absolute_deadzone_keeps_cursor_at_center():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    assert mapper.update(3.0, -3.0, 0.0) == (500.0, 400.0)  # 死区内回到中心
    x, y = mapper.update(12.0, 0.0, 0.1)
    assert 500.0 < x < 1000.0
    assert y == pytest.approx(400.0)


def test_velocity_recenter_stops_movement():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    mapper.update(0.0, 0.0, 0.0)
    mapper.update(20.0, 0.0, 0.1)
    moved = mapper.position
    assert moved != (500.0, 400.0)
    assert mapper.recenter(20.0, 0.0) is True
    mapper.update(20.0, 0.0, 0.2)  # 当前头姿变为中性
    assert mapper.position == moved


def test_recenter_rejects_non_finite():
    mapper = HeadCursorMapper(_cfg(), SCREEN)
    assert mapper.recenter(float("nan"), 0.0) is False
    assert mapper.center == (0.0, 0.0)


def test_reset_clears_baseline():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    mapper.recenter(15.0, 15.0)
    mapper.reset()
    assert mapper.center == (0.0, 0.0)
    assert mapper.update(0.0, 0.0, 0.0) == (500.0, 400.0)


def test_config_defaults_include_baseline_key():
    cfg = config_from_dict({})
    assert cfg.safety.baseline_key == "f4"
    assert cfg.head_control.mode == "velocity"  # 代码默认仍是摇杆，config.yaml 可覆盖


def test_diagonal_boost_amplifies_diagonal_only():
    plain = HeadCursorMapper(_cfg(mode="absolute", diagonal_boost=0.0), SCREEN)
    boosted = HeadCursorMapper(_cfg(mode="absolute", diagonal_boost=0.5), SCREEN)
    x_plain, y_plain = plain.update(15.0, -15.0, 0.0)
    x_boost, y_boost = boosted.update(15.0, -15.0, 0.0)
    assert x_boost > x_plain
    assert y_boost > y_plain  # 负 pitch 更负 -> 更靠下
    # 单轴不受对角增益影响
    assert plain.update(15.0, 0.0, 0.1) == boosted.update(15.0, 0.0, 0.1)


def test_default_diagonal_boost_reaches_corner_at_75_percent_turn():
    """按「自然对角转头只到各轴 75%」反推默认增益，并验证足以到达角点。"""
    cfg = config_from_dict({"head_control": {"mode": "absolute"}}).head_control
    yaw = 0.75 * cfg.max_yaw_deg
    pitch = -0.75 * cfg.max_pitch_deg  # 负 pitch = 向下
    plain = HeadCursorMapper(
        config_from_dict({"head_control": {"mode": "absolute", "diagonal_boost": 0.0}}).head_control,
        SCREEN,
    )
    x_plain, y_plain = plain.update(yaw, pitch, 0.0)
    plain_coverage = (y_plain - 400.0) / 400.0
    assert plain_coverage < 0.8  # 无增益时明显到不了右下角
    mapper = HeadCursorMapper(cfg, SCREEN)
    x, y = mapper.update(yaw, pitch, 0.0)
    boosted_coverage = (y - 400.0) / 400.0
    assert x == pytest.approx(1000.0)  # 水平已压满
    assert boosted_coverage >= 0.99  # 垂直也基本压满（对角增益按对角程度加权）


def test_translation_shifts_horizontal_output():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    mapper.recenter(0.0, 0.0, face_x=0.5)
    assert mapper.center_face_x == 0.5
    assert mapper.update(0.0, 0.0, 0.0, 0.5) == (500.0, 400.0)
    # 脸右移 0.125 = range 的一半 -> 比例 +0.5*0.5，再映射到屏幕
    x, y = mapper.update(0.0, 0.0, 0.1, 0.625)
    assert x == pytest.approx(625.0)
    assert y == pytest.approx(400.0)


def test_translation_can_be_disabled():
    mapper = HeadCursorMapper(_cfg(mode="absolute", translation_weight=0.0), SCREEN)
    assert mapper.update(0.0, 0.0, 0.0, 0.9) == (500.0, 400.0)


def test_translation_weight_can_flip_direction():
    mapper = HeadCursorMapper(_cfg(mode="absolute", translation_weight=-0.5), SCREEN)
    mapper.recenter(0.0, 0.0, face_x=0.0)
    x, _ = mapper.update(0.0, 0.0, 0.0, 0.25)
    assert x < 500.0


def test_translation_auto_baseline_avoids_startup_jump():
    mapper = HeadCursorMapper(_cfg(mode="absolute"), SCREEN)
    # 首帧脸居中：自动建立基准，不产生偏移（F4 之前也不会跳）
    assert mapper.update(0.0, 0.0, 0.0, 0.5) == (500.0, 400.0)
    assert mapper.center_face_x == 0.5
    x, _ = mapper.update(0.0, 0.0, 0.1, 0.5625)
    assert x > 500.0


def test_config_defaults_include_motion_enhancements():
    cfg = config_from_dict({}).head_control
    assert cfg.diagonal_boost == 0.5
    assert cfg.translation_weight == 0.5
    assert cfg.translation_range == 0.25


def test_config_rejects_bad_motion_enhancements():
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"diagonal_boost": -1.0}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"translation_weight": 1.5}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"translation_range": 0.0}})
    with pytest.raises(ValueError):
        config_from_dict({"head_control": {"translation_range": 2.0}})