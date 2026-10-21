"""配置读取与校验：把 config.yaml 解析为带默认值的 dataclass，并做中文化合法性检查。"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

# 合法动作名（click.actions 的值只允许取这些）
_DICT_NAME_RE = __import__("re").compile(r"^DICT_[A-Z0-9_]+$")

VALID_ACTIONS = (
    "none",
    "left_click",
    "right_click",
    "double_click",
    "middle_click",
    "toggle_drag",
    "toggle_pause",
)
# 合法点击模式
VALID_MODES = ("blink_sequence", "dwell", "both", "none")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

DEFAULT_ACTIONS = {
    1: "none",
    2: "left_click",
    3: "right_click",
    4: "double_click",
    5: "toggle_drag",
    6: "none",
}


def default_root() -> Path:
    """由本文件位置推断工作区根目录（eyemouse/ 的上一级）。"""
    return Path(__file__).resolve().parent.parent


@dataclass
class CameraConfig:
    """摄像头参数。"""

    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    mirror: bool = True


@dataclass
class TrackingConfig:
    """视线滤波、特征平滑、注视稳定与丢脸处理参数。"""

    min_cutoff: float = 0.5
    beta: float = 0.002
    d_cutoff: float = 1.0
    lost_face_timeout: float = 0.5
    deadzone_px: float = 30.0
    feature_median_window: int = 3
    feature_ema_alpha: float = 0.5
    stability_window: float = 0.3
    stability_std_px: float = 1.5


@dataclass
class ClickConfig:
    """连续眨眼点击与注视停留参数。"""

    mode: str = "blink_sequence"
    close_ratio: float = 0.60
    open_ratio: float = 0.75
    blink_min_duration: float = 0.06
    blink_max_duration: float = 0.50
    group_gap: float = 0.50
    max_blinks: int = 6
    freeze_lookback: float = 0.30
    cooldown: float = 0.6
    actions: dict = field(default_factory=lambda: dict(DEFAULT_ACTIONS))
    dwell_time: float = 1.2
    dwell_radius: float = 40.0


@dataclass
class CalibrationConfig:
    """校准流程与回归模型参数。"""

    grid: int = 3
    margin: float = 0.08
    settle_time: float = 1.0
    sample_time: float = 1.5
    poly_degree: int = 2
    ridge_alpha: float = 1.0
    file: str = "data/calibration.json"
    practice_blinks: bool = True


@dataclass
class HeadMotionCalibrationConfig:
    """头动补偿校准：是否启用、采样节奏、头姿合理范围与超范围限幅。"""

    enabled: bool = True
    points: int = 5
    per_point_seconds: float = 8.0
    settle_time: float = 1.0
    max_yaw_deg: float = 35.0
    max_pitch_deg: float = 30.0
    max_roll_deg: float = 30.0
    pose_margin_deg: float = 5.0
    out_of_range_step_px: float = 25.0
    ridge_alphas: list = field(default_factory=lambda: [0.1, 0.3, 1.0, 3.0, 10.0])
    cv_folds: int = 5


@dataclass
class FaceProfileConfig:
    """个人面部标定与几何视线估计参数。"""

    enabled: bool = True
    samples: int = 150
    eyeball_offset: float = 0.5
    focal_scale: float = 1.0
    reprojection_error_px: float = 8.0
    smoothing_alpha: float = 0.6
    file: str = "data/face_profile.json"


@dataclass
class HeadControlConfig:
    """面部朝向（头姿）控制光标：与眼控并存，可运行时切换。"""

    enabled: bool = True
    default_source: str = "eye"  # eye | head（默认沿用眼控）
    mode: str = "velocity"  # velocity（摇杆）| absolute（角度直映射位置）
    deadzone_deg: float = 4.0
    max_yaw_deg: float = 22.0
    max_pitch_deg: float = 16.0
    speed_px_s: float = 900.0
    response: float = 1.6
    smoothing_alpha: float = 0.6
    invert_x: bool = False
    invert_y: bool = False
    diagonal_boost: float = 0.5  # 对角（左下/右下等）方向额外增益
    translation_weight: float = 0.5  # 脸部左右平移计入水平方向的比例（可为负以翻转）
    translation_range: float = 0.25  # 平移满量程（归一化画面宽度）


@dataclass
class HandControlConfig:
    """右手控制光标移动：与眼控/头控并存，眼睛仍负责点击。"""

    enabled: bool = True
    pointer_source: str = "hand"  # eye | hand | hybrid
    mirror_handedness: bool = False  # 是否互换左右手标签（camera.mirror=true 时无需互换）
    open_ratio: float = 1.1  # 张开判定比例（指尖/指节到手腕距离）
    finger_spread_min: float = 0.25  # 相邻指尖最小间距（相对掌宽）
    enter_frames: int = 5  # 连续满足进入 OPEN 的帧数
    exit_frames: int = 5  # 连续不满足退出 OPEN 的帧数
    lost_timeout: float = 0.3  # 手丢失多久立即退出（秒）
    mapping: str = "relative"  # relative | absolute
    gain: float = 2.4  # 手位移 -> 光标位移增益
    active_region: float = 0.6  # absolute 满量程区域（画面比例）
    min_cutoff: float = 0.8  # 手部 One Euro min_cutoff
    beta: float = 0.01  # 手部 One Euro beta
    deadzone_px: float = 12.0  # 手控死区（像素）
    hand_every_n_frames: int = 1  # 每 N 帧检测一次手
    suspend_blink_while_hand: bool = False  # gate 打开时暂停眨眼点击
    tracking_point: str = "thumb_tip"  # thumb_tip | palm | wrist | index_tip
    require_thumb: bool = True  # 张开判定是否必须拇指伸出


@dataclass
class CameraCalibrationConfig:
    """摄像头内参标定（ChArUco）：板参数、采集门槛与保存路径。长度单位一律为米。"""

    dictionary: str = "DICT_5X5_50"
    squares_x: int = 8
    squares_y: int = 6
    square_length_m: float = 0.025
    marker_length_m: float = 0.018
    min_views: int = 15  # 建议 15~20；数量不是唯一质量标准
    min_corners_per_view: int = 12  # 单视图最少角点数
    coverage_cells: int = 3  # 覆盖度网格（NxN）
    coverage_min_cells: int = 6  # 至少覆盖多少个格子才不警告
    duplicate_distance: float = 0.02  # 归一化角点均方距离小于该值视为重复视角
    file: str = "data/camera_calibration.json"


@dataclass
class GlassesTrackingConfig:
    """眼镜 ArUco 标记追踪（阶段一默认关闭，不影响现有行为）。"""

    enabled: bool = False  # 阶段一默认关闭
    marker_id: int = 0
    dictionary: str = "DICT_5X5_50"
    marker_size_m: float = 0.030  # 必须由用户实测
    subpixel_win: int = 5  # 亚像素精化窗口（奇数）
    min_marker_area_px: float = 400.0
    max_reprojection_error_px: float = 3.0
    ambiguity_reproj_margin_px: float = 0.5
    ambiguity_angle_deg: float = 12.0
    ambiguity_evidence_px: float = 0.15
    acquisition_frames: int = 20
    ambiguity_branch_angle_deg: float = 25.0
    max_linear_speed_m_s: float = 1.5
    max_angular_speed_deg_s: float = 400.0
    gap_reset_s: float = 0.5
    slerp_alpha: float = 0.35
    translation_alpha: float = 0.35
    stabilize_frames: int = 5
    stale_timeout_s: float = 0.5
    stats_period_s: float = 2.0
    stability_window_s: float = 10.0
    compare_facemesh: bool = False


@dataclass
class SafetyConfig:
    """全局热键配置。"""

    pause_key: str = "f9"
    quit_key: str = "f10"
    recalibrate_key: str = "f8"
    toggle_click_key: str = "f7"
    cycle_mode_key: str = "f6"
    cursor_key: str = "f5"
    baseline_key: str = "f4"


@dataclass
class DebugConfig:
    """调试窗口与日志配置。"""

    show_window: bool = True
    log_level: str = "INFO"
    log_file: str = "data/run.log"


@dataclass
class AppConfig:
    """完整配置。root 为工作区绝对路径，config_path 为实际读取的配置文件绝对路径。"""

    camera: CameraConfig
    tracking: TrackingConfig
    click: ClickConfig
    calibration: CalibrationConfig
    safety: SafetyConfig
    debug: DebugConfig
    head_motion: HeadMotionCalibrationConfig = field(default_factory=HeadMotionCalibrationConfig)
    face_profile: FaceProfileConfig = field(default_factory=FaceProfileConfig)
    head_control: HeadControlConfig = field(default_factory=HeadControlConfig)
    hand_control: HandControlConfig = field(default_factory=HandControlConfig)
    camera_calibration: CameraCalibrationConfig = field(default_factory=CameraCalibrationConfig)
    glasses_tracking: GlassesTrackingConfig = field(default_factory=GlassesTrackingConfig)
    root: str = ""
    config_path: str = ""


def _require_number(name: str, value: Any, allow_zero: bool = False) -> None:
    """校验数值为正数（allow_zero 时允许 0），否则抛中文 ValueError。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"配置项 {name} 必须是数字，当前为 {value!r}")
    if allow_zero:
        if value < 0:
            raise ValueError(f"配置项 {name} 不能为负数，当前为 {value!r}")
    elif value <= 0:
        raise ValueError(f"配置项 {name} 必须为正数，当前为 {value!r}")


def _require_int(name: str, value: Any, minimum: int) -> None:
    """校验整数字段下限，否则抛中文 ValueError。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"配置项 {name} 必须是整数，当前为 {value!r}")
    if value < minimum:
        raise ValueError(f"配置项 {name} 必须不小于 {minimum}，当前为 {value}")


def _require_bool(name: str, value: Any) -> None:
    """校验布尔字段，否则抛中文 ValueError。"""
    if not isinstance(value, bool):
        raise ValueError(f"配置项 {name} 必须是布尔值 true/false，当前为 {value!r}")


def _coerce_actions(raw: Any) -> dict:
    """把 actions 映射统一成 {int: str}，键不是整数时抛中文 ValueError。"""
    if raw is None:
        return dict(DEFAULT_ACTIONS)
    if not isinstance(raw, dict):
        raise ValueError("配置项 click.actions 必须是「次数: 动作名」的映射")
    actions: dict = {}
    for key, value in raw.items():
        try:
            count = int(key)
        except (TypeError, ValueError):
            raise ValueError(f"配置项 click.actions 的键必须是整数，当前为 {key!r}") from None
        actions[count] = str(value)
    return actions


def _build_section(name: str, section: Any, cls: type) -> Any:
    """把 YAML 的一个配置节构造成对应 dataclass，缺失取默认值，未知字段报错。"""
    if section is None:
        return cls()
    if not isinstance(section, dict):
        raise ValueError(f"配置节 {name} 必须是映射")
    valid = {item.name for item in dataclasses.fields(cls)}
    unknown = sorted(set(section) - valid)
    if unknown:
        raise ValueError(f"配置节 {name} 含未知字段：{unknown}")
    try:
        return cls(**section)
    except TypeError as exc:  # pragma: no cover - 理论上被上面的检查拦住
        raise ValueError(f"配置节 {name} 字段不合法：{exc}") from exc


def _validate_data_path(name: str, value: Any, root: Path) -> None:
    """要求给定路径解析后位于 <root>/data/ 之内，否则抛中文 ValueError。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"配置项 {name} 必须是非空字符串路径")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    data_dir = (root / "data").resolve()
    if resolved == data_dir or data_dir not in resolved.parents:
        raise ValueError(f"配置项 {name} 必须位于工作区 data/ 目录内，当前为 {resolved}")


def _require_dict_name(name: str, value: Any) -> None:
    """ArUco 字典名必须是形如 DICT_5X5_50 的非空字符串。"""
    if not isinstance(value, str) or not _DICT_NAME_RE.match(value):
        raise ValueError(f"配置项 {name} 必须是形如 DICT_5X5_50 的 ArUco 字典名，当前为 {value!r}")


def _validate_camera_calibration_config(cfg: CameraCalibrationConfig) -> None:
    """校验摄像头标定节。"""
    _require_dict_name("camera_calibration.dictionary", cfg.dictionary)
    _require_int("camera_calibration.squares_x", cfg.squares_x, 2)
    _require_int("camera_calibration.squares_y", cfg.squares_y, 2)
    if (cfg.squares_x * cfg.squares_y) % 2 != 0:
        raise ValueError(
            f"配置项 camera_calibration 的 squares_x*squares_y 必须为偶数（否则标记数不是整数），当前为 {cfg.squares_x}x{cfg.squares_y}"
        )
    _require_number("camera_calibration.square_length_m", cfg.square_length_m)
    _require_number("camera_calibration.marker_length_m", cfg.marker_length_m)
    if cfg.marker_length_m >= cfg.square_length_m:
        raise ValueError(
            f"配置项 camera_calibration.marker_length_m 必须小于 square_length_m，当前为 {cfg.marker_length_m} >= {cfg.square_length_m}"
        )
    _require_int("camera_calibration.min_views", cfg.min_views, 3)
    _require_int("camera_calibration.min_corners_per_view", cfg.min_corners_per_view, 4)
    _require_int("camera_calibration.coverage_cells", cfg.coverage_cells, 1)
    max_cells = cfg.coverage_cells * cfg.coverage_cells
    _require_int("camera_calibration.coverage_min_cells", cfg.coverage_min_cells, 1)
    if cfg.coverage_min_cells > max_cells:
        raise ValueError(
            f"配置项 camera_calibration.coverage_min_cells 不能大于 {max_cells}，当前为 {cfg.coverage_min_cells}"
        )
    _require_number("camera_calibration.duplicate_distance", cfg.duplicate_distance, allow_zero=True)
    if cfg.duplicate_distance > 1.0:
        raise ValueError(
            f"配置项 camera_calibration.duplicate_distance 不能大于 1，当前为 {cfg.duplicate_distance}"
        )


def _validate_glasses_tracking_config(cfg: GlassesTrackingConfig) -> None:
    """校验眼镜追踪节。"""
    _require_bool("glasses_tracking.enabled", cfg.enabled)
    _require_int("glasses_tracking.marker_id", cfg.marker_id, 0)
    _require_dict_name("glasses_tracking.dictionary", cfg.dictionary)
    _require_number("glasses_tracking.marker_size_m", cfg.marker_size_m)
    if cfg.subpixel_win < 1 or cfg.subpixel_win % 2 == 0 or cfg.subpixel_win > 21:
        raise ValueError(
            f"配置项 glasses_tracking.subpixel_win 必须是 1~21 的奇数，当前为 {cfg.subpixel_win}"
        )
    _require_number("glasses_tracking.min_marker_area_px", cfg.min_marker_area_px)
    _require_number("glasses_tracking.max_reprojection_error_px", cfg.max_reprojection_error_px)
    _require_number(
        "glasses_tracking.ambiguity_reproj_margin_px", cfg.ambiguity_reproj_margin_px, allow_zero=True
    )
    _require_number("glasses_tracking.ambiguity_angle_deg", cfg.ambiguity_angle_deg, allow_zero=True)
    _require_number("glasses_tracking.ambiguity_evidence_px", cfg.ambiguity_evidence_px, allow_zero=True)
    _require_int("glasses_tracking.acquisition_frames", cfg.acquisition_frames, 1)
    _require_number(
        "glasses_tracking.ambiguity_branch_angle_deg", cfg.ambiguity_branch_angle_deg, allow_zero=True
    )
    if cfg.ambiguity_branch_angle_deg <= cfg.ambiguity_angle_deg:
        raise ValueError(
            "配置项 glasses_tracking.ambiguity_branch_angle_deg 必须大于 ambiguity_angle_deg，"
            f"当前为 {cfg.ambiguity_branch_angle_deg} <= {cfg.ambiguity_angle_deg}"
        )
    _require_number("glasses_tracking.max_linear_speed_m_s", cfg.max_linear_speed_m_s)
    _require_number("glasses_tracking.max_angular_speed_deg_s", cfg.max_angular_speed_deg_s)
    _require_number("glasses_tracking.gap_reset_s", cfg.gap_reset_s)
    for key in ("slerp_alpha", "translation_alpha"):
        value = getattr(cfg, key)
        _require_number(f"glasses_tracking.{key}", value)
        if value > 1.0:
            raise ValueError(f"配置项 glasses_tracking.{key} 不能大于 1，当前为 {value}")
    _require_int("glasses_tracking.stabilize_frames", cfg.stabilize_frames, 1)
    _require_number("glasses_tracking.stale_timeout_s", cfg.stale_timeout_s, allow_zero=True)
    _require_number("glasses_tracking.stats_period_s", cfg.stats_period_s)
    _require_number("glasses_tracking.stability_window_s", cfg.stability_window_s)
    _require_bool("glasses_tracking.compare_facemesh", cfg.compare_facemesh)


def validate_config(cfg: AppConfig) -> None:
    """校验配置合法性，任何非法值都抛带中文说明的 ValueError。"""
    root = Path(cfg.root).resolve() if cfg.root else default_root()

    _require_int("camera.index", cfg.camera.index, 0)
    _require_number("camera.width", cfg.camera.width)
    _require_number("camera.height", cfg.camera.height)
    _require_number("camera.fps", cfg.camera.fps)
    _require_bool("camera.mirror", cfg.camera.mirror)

    _require_number("tracking.min_cutoff", cfg.tracking.min_cutoff)
    _require_number("tracking.beta", cfg.tracking.beta, allow_zero=True)
    _require_number("tracking.d_cutoff", cfg.tracking.d_cutoff)
    _require_number("tracking.lost_face_timeout", cfg.tracking.lost_face_timeout)
    _require_number("tracking.deadzone_px", cfg.tracking.deadzone_px, allow_zero=True)
    _require_int("tracking.feature_median_window", cfg.tracking.feature_median_window, 1)
    _require_number("tracking.feature_ema_alpha", cfg.tracking.feature_ema_alpha)
    if cfg.tracking.feature_ema_alpha > 1.0:
        raise ValueError(
            f"配置项 tracking.feature_ema_alpha 必须不大于 1，当前为 {cfg.tracking.feature_ema_alpha}"
        )
    _require_number("tracking.stability_window", cfg.tracking.stability_window)
    _require_number("tracking.stability_std_px", cfg.tracking.stability_std_px, allow_zero=True)

    if cfg.click.mode not in VALID_MODES:
        raise ValueError(f"配置项 click.mode 只能是 {VALID_MODES} 之一，当前为 {cfg.click.mode!r}")
    _require_number("click.close_ratio", cfg.click.close_ratio)
    _require_number("click.open_ratio", cfg.click.open_ratio)
    if cfg.click.close_ratio >= cfg.click.open_ratio:
        raise ValueError(
            f"配置项 click.close_ratio({cfg.click.close_ratio}) 必须小于 "
            f"click.open_ratio({cfg.click.open_ratio})"
        )
    _require_number("click.blink_min_duration", cfg.click.blink_min_duration)
    _require_number("click.blink_max_duration", cfg.click.blink_max_duration)
    if cfg.click.blink_min_duration >= cfg.click.blink_max_duration:
        raise ValueError(
            f"配置项 click.blink_min_duration({cfg.click.blink_min_duration}) 必须小于 "
            f"click.blink_max_duration({cfg.click.blink_max_duration})"
        )
    _require_number("click.group_gap", cfg.click.group_gap)
    _require_int("click.max_blinks", cfg.click.max_blinks, 1)
    _require_number("click.freeze_lookback", cfg.click.freeze_lookback, allow_zero=True)
    _require_number("click.cooldown", cfg.click.cooldown, allow_zero=True)
    _require_number("click.dwell_time", cfg.click.dwell_time)
    _require_number("click.dwell_radius", cfg.click.dwell_radius)

    if not isinstance(cfg.click.actions, dict) or not cfg.click.actions:
        raise ValueError("配置项 click.actions 不能为空")
    for count, action in cfg.click.actions.items():
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError(f"配置项 click.actions 的键必须是整数，当前为 {count!r}")
        if count < 1 or count > cfg.click.max_blinks:
            raise ValueError(
                f"配置项 click.actions 的键必须在 1..{cfg.click.max_blinks} 之间，当前为 {count}"
            )
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"配置项 click.actions 含非法动作名 {action!r}，合法值为 {VALID_ACTIONS}"
            )

    _require_int("calibration.grid", cfg.calibration.grid, 2)
    margin = cfg.calibration.margin
    _require_number("calibration.margin", margin, allow_zero=True)
    if margin >= 0.5:
        raise ValueError(f"配置项 calibration.margin 必须小于 0.5，当前为 {margin}")
    _require_number("calibration.settle_time", cfg.calibration.settle_time)
    _require_number("calibration.sample_time", cfg.calibration.sample_time)
    _require_int("calibration.poly_degree", cfg.calibration.poly_degree, 1)
    _require_number("calibration.ridge_alpha", cfg.calibration.ridge_alpha)
    _require_bool("calibration.practice_blinks", cfg.calibration.practice_blinks)

    _require_bool("head_motion_calibration.enabled", cfg.head_motion.enabled)
    _require_int("head_motion_calibration.points", cfg.head_motion.points, 1)
    _require_number("head_motion_calibration.per_point_seconds", cfg.head_motion.per_point_seconds)
    _require_number("head_motion_calibration.settle_time", cfg.head_motion.settle_time, allow_zero=True)
    _require_number("head_motion_calibration.max_yaw_deg", cfg.head_motion.max_yaw_deg)
    _require_number("head_motion_calibration.max_pitch_deg", cfg.head_motion.max_pitch_deg)
    _require_number("head_motion_calibration.max_roll_deg", cfg.head_motion.max_roll_deg)
    _require_number("head_motion_calibration.pose_margin_deg", cfg.head_motion.pose_margin_deg, allow_zero=True)
    _require_number(
        "head_motion_calibration.out_of_range_step_px",
        cfg.head_motion.out_of_range_step_px,
        allow_zero=True,
    )
    _require_int("head_motion_calibration.cv_folds", cfg.head_motion.cv_folds, 2)
    alphas = cfg.head_motion.ridge_alphas
    if not isinstance(alphas, (list, tuple)) or not alphas:
        raise ValueError("配置项 head_motion_calibration.ridge_alphas 必须是非空数字列表")
    for value in alphas:
        _require_number("head_motion_calibration.ridge_alphas", value)

    _require_bool("face_profile.enabled", cfg.face_profile.enabled)
    _require_int("face_profile.samples", cfg.face_profile.samples, 1)
    _require_number("face_profile.eyeball_offset", cfg.face_profile.eyeball_offset, allow_zero=True)
    _require_number("face_profile.focal_scale", cfg.face_profile.focal_scale)
    _require_number(
        "face_profile.reprojection_error_px", cfg.face_profile.reprojection_error_px
    )
    _require_number("face_profile.smoothing_alpha", cfg.face_profile.smoothing_alpha, allow_zero=True)
    if cfg.face_profile.smoothing_alpha > 1.0:
        raise ValueError(
            f"配置项 face_profile.smoothing_alpha 必须不大于 1，当前为 {cfg.face_profile.smoothing_alpha}"
        )

    _require_bool("head_control.enabled", cfg.head_control.enabled)
    if cfg.head_control.default_source not in ("eye", "head"):
        raise ValueError(
            f"配置项 head_control.default_source 只能是 eye 或 head，当前为 {cfg.head_control.default_source!r}"
        )
    if cfg.head_control.mode not in ("velocity", "absolute"):
        raise ValueError(
            f"配置项 head_control.mode 只能是 velocity 或 absolute，当前为 {cfg.head_control.mode!r}"
        )
    _require_number("head_control.deadzone_deg", cfg.head_control.deadzone_deg, allow_zero=True)
    _require_number("head_control.max_yaw_deg", cfg.head_control.max_yaw_deg)
    _require_number("head_control.max_pitch_deg", cfg.head_control.max_pitch_deg)
    if cfg.head_control.max_yaw_deg <= cfg.head_control.deadzone_deg:
        raise ValueError("配置项 head_control.max_yaw_deg 必须大于 head_control.deadzone_deg")
    if cfg.head_control.max_pitch_deg <= cfg.head_control.deadzone_deg:
        raise ValueError("配置项 head_control.max_pitch_deg 必须大于 head_control.deadzone_deg")
    _require_number("head_control.speed_px_s", cfg.head_control.speed_px_s)
    _require_number("head_control.response", cfg.head_control.response)
    _require_number("head_control.smoothing_alpha", cfg.head_control.smoothing_alpha, allow_zero=True)
    if cfg.head_control.smoothing_alpha > 1.0:
        raise ValueError(
            f"配置项 head_control.smoothing_alpha 必须不大于 1，当前为 {cfg.head_control.smoothing_alpha}"
        )
    _require_bool("head_control.invert_x", cfg.head_control.invert_x)
    _require_bool("head_control.invert_y", cfg.head_control.invert_y)
    _require_number("head_control.diagonal_boost", cfg.head_control.diagonal_boost, allow_zero=True)
    weight = cfg.head_control.translation_weight
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise ValueError(f"配置项 head_control.translation_weight 必须是数字，当前为 {weight!r}")
    if abs(float(weight)) > 1.0:
        raise ValueError(f"配置项 head_control.translation_weight 绝对值不能大于 1，当前为 {weight}")
    _require_number("head_control.translation_range", cfg.head_control.translation_range)
    if cfg.head_control.translation_range > 1.0:
        raise ValueError(
            f"配置项 head_control.translation_range 不能大于 1（归一化画面宽度），当前为 {cfg.head_control.translation_range}"
        )

    _require_bool("hand_control.enabled", cfg.hand_control.enabled)
    if cfg.hand_control.pointer_source not in ("eye", "hand", "hybrid"):
        raise ValueError(
            f"配置项 hand_control.pointer_source 只能是 eye/hand/hybrid，当前为 {cfg.hand_control.pointer_source!r}"
        )
    _require_bool("hand_control.mirror_handedness", cfg.hand_control.mirror_handedness)
    _require_number("hand_control.open_ratio", cfg.hand_control.open_ratio)
    spread = cfg.hand_control.finger_spread_min
    _require_number("hand_control.finger_spread_min", spread, allow_zero=True)
    if spread > 1.0:
        raise ValueError(f"配置项 hand_control.finger_spread_min 不能大于 1，当前为 {spread}")
    _require_int("hand_control.enter_frames", cfg.hand_control.enter_frames, 1)
    _require_int("hand_control.exit_frames", cfg.hand_control.exit_frames, 1)
    _require_number("hand_control.lost_timeout", cfg.hand_control.lost_timeout, allow_zero=True)
    if cfg.hand_control.mapping not in ("relative", "absolute"):
        raise ValueError(
            f"配置项 hand_control.mapping 只能是 relative/absolute，当前为 {cfg.hand_control.mapping!r}"
        )
    _require_number("hand_control.gain", cfg.hand_control.gain)
    active = cfg.hand_control.active_region
    _require_number("hand_control.active_region", active)
    if active > 1.0:
        raise ValueError(f"配置项 hand_control.active_region 不能大于 1，当前为 {active}")
    _require_number("hand_control.min_cutoff", cfg.hand_control.min_cutoff)
    _require_number("hand_control.beta", cfg.hand_control.beta, allow_zero=True)
    _require_number("hand_control.deadzone_px", cfg.hand_control.deadzone_px, allow_zero=True)
    _require_int("hand_control.hand_every_n_frames", cfg.hand_control.hand_every_n_frames, 1)
    _require_bool("hand_control.suspend_blink_while_hand", cfg.hand_control.suspend_blink_while_hand)
    _require_bool("hand_control.require_thumb", cfg.hand_control.require_thumb)
    if cfg.hand_control.tracking_point not in ("palm", "wrist", "index_tip", "thumb_tip"):
        raise ValueError(
            f"配置项 hand_control.tracking_point 只能是 palm/wrist/index_tip/thumb_tip，当前为 {cfg.hand_control.tracking_point!r}"
        )

    _validate_camera_calibration_config(cfg.camera_calibration)
    _validate_glasses_tracking_config(cfg.glasses_tracking)

    for key in ("pause_key", "quit_key", "recalibrate_key", "toggle_click_key", "cycle_mode_key", "cursor_key", "baseline_key"):
        value = getattr(cfg.safety, key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"配置项 safety.{key} 必须是非空字符串")

    _require_bool("debug.show_window", cfg.debug.show_window)
    if cfg.debug.log_level not in VALID_LOG_LEVELS:
        raise ValueError(
            f"配置项 debug.log_level 只能是 {VALID_LOG_LEVELS} 之一，当前为 {cfg.debug.log_level!r}"
        )

    _validate_data_path("calibration.file", cfg.calibration.file, root)
    _validate_data_path("face_profile.file", cfg.face_profile.file, root)
    _validate_data_path("camera_calibration.file", cfg.camera_calibration.file, root)
    _validate_data_path("debug.log_file", cfg.debug.log_file, root)


def config_from_dict(
    data: Optional[dict],
    root: Any = None,
    config_path: str = "",
) -> AppConfig:
    """由字典构造并校验配置；缺失字段使用默认值。"""
    root_path = Path(root).resolve() if root is not None else default_root()
    raw = data or {}
    if not isinstance(raw, dict):
        raise ValueError("配置文件顶层必须是映射（键值对）")

    click_section = raw.get("click")
    if click_section is not None:
        if not isinstance(click_section, dict):
            raise ValueError("配置节 click 必须是映射")
        click_section = dict(click_section)
        click_section["actions"] = _coerce_actions(click_section.get("actions"))

    cfg = AppConfig(
        camera=_build_section("camera", raw.get("camera"), CameraConfig),
        tracking=_build_section("tracking", raw.get("tracking"), TrackingConfig),
        click=_build_section("click", click_section, ClickConfig),
        calibration=_build_section("calibration", raw.get("calibration"), CalibrationConfig),
        safety=_build_section("safety", raw.get("safety"), SafetyConfig),
        debug=_build_section("debug", raw.get("debug"), DebugConfig),
        head_motion=_build_section(
            "head_motion_calibration",
            raw.get("head_motion_calibration"),
            HeadMotionCalibrationConfig,
        ),
        face_profile=_build_section(
            "face_profile",
            raw.get("face_profile"),
            FaceProfileConfig,
        ),
        head_control=_build_section(
            "head_control",
            raw.get("head_control"),
            HeadControlConfig,
        ),
        hand_control=_build_section(
            "hand_control",
            raw.get("hand_control"),
            HandControlConfig,
        ),
        camera_calibration=_build_section(
            "camera_calibration",
            raw.get("camera_calibration"),
            CameraCalibrationConfig,
        ),
        glasses_tracking=_build_section(
            "glasses_tracking",
            raw.get("glasses_tracking"),
            GlassesTrackingConfig,
        ),
        root=str(root_path),
        config_path=str(config_path),
    )
    validate_config(cfg)
    return cfg


def load_config(path: Any = None, root: Any = None) -> AppConfig:
    """读取 YAML 配置文件并返回校验后的 AppConfig。"""
    root_path = Path(root).resolve() if root is not None else default_root()
    if path is None:
        config_path = root_path / "config.yaml"
    else:
        candidate = Path(path)
        config_path = candidate if candidate.is_absolute() else root_path / candidate
    config_path = config_path.resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"找不到配置文件：{config_path}")
    with open(config_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return config_from_dict(raw, root=root_path, config_path=str(config_path))
