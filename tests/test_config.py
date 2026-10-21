"""配置模块测试：默认值、加载真实 config.yaml，以及各类非法值的报错。"""

from __future__ import annotations

import pytest

from eyemouse.config import config_from_dict, load_config


def test_empty_dict_uses_defaults():
    cfg = config_from_dict({})
    assert cfg.camera.index == 0
    assert cfg.camera.width == 1280
    assert cfg.camera.height == 720
    assert cfg.camera.fps == 30
    assert cfg.camera.mirror is True
    assert cfg.click.mode == "blink_sequence"
    assert cfg.click.actions == {
        1: "none",
        2: "left_click",
        3: "right_click",
        4: "double_click",
        5: "toggle_drag",
        6: "none",
    }
    assert cfg.calibration.grid == 3
    assert cfg.calibration.file == "data/calibration.json"
    assert cfg.debug.log_file == "data/run.log"
    assert cfg.safety.pause_key == "f9"


def test_partial_section_keeps_defaults():
    cfg = config_from_dict({"camera": {"width": 640}})
    assert cfg.camera.width == 640
    assert cfg.camera.height == 720


def test_load_real_config_yaml():
    cfg = load_config()
    assert cfg.click.actions[2] == "left_click"
    assert cfg.click.actions[5] == "toggle_drag"
    assert cfg.calibration.poly_degree == 2
    assert cfg.calibration.ridge_alpha == 1.0


def test_invalid_action_name():
    with pytest.raises(ValueError):
        config_from_dict({"click": {"actions": {2: "fly"}}})


def test_action_key_out_of_range():
    with pytest.raises(ValueError):
        config_from_dict({"click": {"actions": {9: "left_click"}}})


def test_close_ratio_not_less_than_open_ratio():
    with pytest.raises(ValueError):
        config_from_dict({"click": {"close_ratio": 0.8, "open_ratio": 0.7}})


def test_blink_duration_order():
    with pytest.raises(ValueError):
        config_from_dict({"click": {"blink_min_duration": 0.6, "blink_max_duration": 0.5}})


def test_invalid_mode():
    with pytest.raises(ValueError):
        config_from_dict({"click": {"mode": "bogus"}})


def test_negative_camera_fps():
    with pytest.raises(ValueError):
        config_from_dict({"camera": {"fps": -1}})


def test_calibration_file_outside_data(tmp_path):
    with pytest.raises(ValueError):
        config_from_dict({"calibration": {"file": "logs/calibration.json"}}, root=tmp_path)


def test_log_file_outside_data(tmp_path):
    with pytest.raises(ValueError):
        config_from_dict({"debug": {"log_file": "run.log"}}, root=tmp_path)


def test_data_paths_inside_data(tmp_path):
    cfg = config_from_dict(
        {
            "calibration": {"file": "data/calibration.json"},
            "debug": {"log_file": "data/run.log"},
        },
        root=tmp_path,
    )
    assert cfg.calibration.file == "data/calibration.json"
    assert cfg.debug.log_file == "data/run.log"


def test_unknown_field_rejected():
    with pytest.raises(ValueError):
        config_from_dict({"camera": {"zoom": 2}})


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml", root=tmp_path)


def test_default_tracking_and_head_motion():
    cfg = config_from_dict({})
    assert cfg.tracking.min_cutoff == 0.5
    assert cfg.tracking.beta == 0.002
    assert cfg.tracking.deadzone_px == 30.0
    assert cfg.tracking.feature_median_window == 3
    assert cfg.tracking.feature_ema_alpha == 0.5
    assert cfg.tracking.stability_window == 0.3
    assert cfg.tracking.stability_std_px == 1.5
    assert cfg.head_motion.enabled is True
    assert cfg.head_motion.points == 5
    assert cfg.head_motion.per_point_seconds == 8.0


def test_head_motion_section_override():
    cfg = config_from_dict(
        {"head_motion_calibration": {"enabled": False, "points": 3, "per_point_seconds": 6.0}}
    )
    assert cfg.head_motion.enabled is False
    assert cfg.head_motion.points == 3
    assert cfg.head_motion.per_point_seconds == 6.0


def test_invalid_head_motion_points():
    with pytest.raises(ValueError):
        config_from_dict({"head_motion_calibration": {"points": 0}})


def test_invalid_head_motion_alphas():
    with pytest.raises(ValueError):
        config_from_dict({"head_motion_calibration": {"ridge_alphas": []}})


def test_unknown_head_motion_field_rejected():
    with pytest.raises(ValueError):
        config_from_dict({"head_motion_calibration": {"zoom": 2}})


def test_invalid_feature_ema_alpha():
    with pytest.raises(ValueError):
        config_from_dict({"tracking": {"feature_ema_alpha": 1.5}})
