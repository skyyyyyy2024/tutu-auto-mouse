"""主循环：状态机整合摄像头、关键点、特征、校准、点击检测、鼠标、热键与界面。"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .calibration import (
    CalibrationCancelled,
    CalibrationModel,
    Calibrator,
    ModelVersionMismatchError,
    ScreenSizeMismatchError,
)
from .camera import Camera, CameraError
from .click_detector import ClickDetector, ClickEvent
from .config import AppConfig
from .face_profile import FaceProfile
from .features import build_feature_vector, compute_ear
from .gaze_geometry import estimate_gaze
from .hand_gesture import OpenPalmGate, is_open_palm
from .hand_pointer import HandPointer, tracking_point as hand_tracking_point
from .hand_tracker import HandLandmarks, HandTracker
from .head_control import HeadCursorMapper, next_source
from .head_pose import HeadPoseEstimator
from .filters import FeatureSmoother, GazeStabilityTracker, OneEuroFilter2D
from .hotkeys import HotkeyManager, HotkeyRequests
from .landmarks import EYE_A_OUTER, EYE_B_OUTER, LandmarkDetector
from .mouse import DryRunMouse, MouseController, PyAutoGuiMouse
from .ui import UI

LOGGER = logging.getLogger(__name__)

CLICK_MODES = ("blink_sequence", "dwell", "both", "none")
CURSOR_DRIVERS = ("hand", "eye", "head", "none")


def resolve_cursor_driver(pointer_source: str, hand_active: bool, cursor_source: str) -> str:
    """决定本帧由谁驱动光标：hand / eye / head / none（none=不移动光标）。"""
    if hand_active:
        return "hand"
    if str(pointer_source) == "hand":
        return "none"
    if str(cursor_source) == "head":
        return "head"
    return "eye"


def should_suspend_blink(suspend_flag: bool, hand_active: bool) -> bool:
    """是否暂停眨眼点击：仅在开关为真且手控正在接管时。"""
    return bool(suspend_flag and hand_active)
FALLBACK_EAR_BASELINE = 0.3
ACTION_LABELS = {
    "left_click": "LEFT CLICK",
    "right_click": "RIGHT CLICK",
    "middle_click": "MIDDLE CLICK",
    "double_click": "DOUBLE CLICK",
    "toggle_drag": "DRAG",
    "toggle_pause": "PAUSE",
}


def is_in_venv() -> bool:
    """当前解释器是否运行在虚拟环境中。"""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def face_center_x(face: object) -> Optional[float]:
    """脸部水平中心（两外眼角中点 x / 画面宽），作为头控的平移输入。"""
    width = float(getattr(face, "img_w", 0) or 0)
    points = getattr(face, "pts_px", None)
    if width <= 0.0 or points is None:
        return None
    try:
        left = float(points[EYE_A_OUTER][0])
        right = float(points[EYE_B_OUTER][0])
    except (IndexError, TypeError, ValueError):
        return None
    center = (left + right) / 2.0
    if not math.isfinite(center):
        return None
    return center / width


def get_screen_size() -> Tuple[int, int]:
    """用 pyautogui 获取主显示器分辨率。"""
    try:
        import pyautogui

        size = pyautogui.size()
        return int(size[0]), int(size[1])
    except Exception as exc:
        raise RuntimeError(
            f"无法获取屏幕分辨率，请在带图形界面的桌面环境运行（{exc}）"
        ) from exc


def configure_logging(cfg: AppConfig) -> Path:
    """同时输出到终端与 data/run.log（追加模式，不删除旧日志）。"""
    log_path = Path(cfg.debug.log_file)
    if not log_path.is_absolute():
        log_path = Path(cfg.root) / log_path
    log_path = log_path.resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, str(cfg.debug.log_level).upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    return log_path


def describe_environment(cfg: AppConfig, log_path: Path) -> List[str]:
    """返回启动时需要打印/写入的一次性环境信息。"""
    calibration_path = Path(cfg.calibration.file)
    if not calibration_path.is_absolute():
        calibration_path = Path(cfg.root) / calibration_path
    audit_dir = Path(cfg.root) / "audit_logs"
    return [
        f"项目根目录（工作区）：{cfg.root}",
        f"配置文件：{cfg.config_path or (Path(cfg.root) / 'config.yaml')}",
        f"校准文件：{calibration_path.resolve()}",
        f"日志文件：{log_path}",
        f"审计日志目录：{audit_dir.resolve()}",
        f"Python 解释器：{sys.executable}",
        f"是否处于虚拟环境：{'是' if is_in_venv() else '否'}",
    ]


class EyeMouseApp:
    """EyeMouse 应用主体，状态机为 INIT -> CALIBRATING -> TRACKING <-> PAUSED -> EXIT。"""

    def __init__(
        self,
        cfg: AppConfig,
        dry_run: bool = False,
        show_window: bool = True,
        force_recalibrate: bool = False,
        force_recalibrate_face: bool = False,
    ) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self.force_recalibrate = force_recalibrate
        self.force_recalibrate_face = force_recalibrate_face
        self.log_path = configure_logging(cfg)
        self.screen_size = get_screen_size()
        self.landmark_detector = LandmarkDetector()
        self.camera = Camera(cfg.camera)
        self.mouse: MouseController = DryRunMouse() if dry_run else PyAutoGuiMouse()
        self.ui = UI(cfg, self.screen_size, show_window=show_window)
        self.hotkeys = HotkeyManager(cfg.safety)
        self.filter = OneEuroFilter2D(
            cfg.tracking.min_cutoff, cfg.tracking.beta, cfg.tracking.d_cutoff
        )
        self.feature_smoother = FeatureSmoother(
            cfg.tracking.feature_median_window, cfg.tracking.feature_ema_alpha
        )
        self.stability = GazeStabilityTracker(
            cfg.tracking.stability_window, cfg.tracking.stability_std_px
        )
        self.jitter_tracker = GazeStabilityTracker(1.0, float("inf"))
        self.face_profile: Optional[FaceProfile] = self._load_face_profile()
        self.head_estimator = HeadPoseEstimator(
            profile=self.face_profile,
            focal_scale=cfg.face_profile.focal_scale,
            reprojection_error_px=cfg.face_profile.reprojection_error_px,
            smoothing_alpha=cfg.face_profile.smoothing_alpha,
        )
        self.head_pose = None
        self.gaze: Optional[Tuple[float, float]] = None
        source = str(cfg.head_control.default_source).strip().lower()
        if not cfg.head_control.enabled or source not in ("eye", "head"):
            source = "eye"
        self.cursor_source = source
        self.head_mapper = HeadCursorMapper(cfg.head_control, self.screen_size)
        self.pointer_source = self._resolve_pointer_source(cfg)
        self.hand_gate = OpenPalmGate(
            cfg.hand_control.enter_frames,
            cfg.hand_control.exit_frames,
            cfg.hand_control.lost_timeout,
        )
        self.hand_pointer = HandPointer(cfg.hand_control, self.screen_size)
        self.hand: Optional[HandLandmarks] = None
        self.hand_point: Optional[Tuple[float, float]] = None
        self.hand_gate_open = False
        self.hand_fps = 0.0
        self._hand_frame_counter = 0
        self._hand_last_time: Optional[float] = None
        self._blink_suspended = False
        self.hand_tracker: Optional[HandTracker] = None
        if self.pointer_source in ("hand", "hybrid"):
            try:
                self.hand_tracker = HandTracker(mirror_handedness=cfg.hand_control.mirror_handedness)
            except Exception:
                LOGGER.warning("手部检测初始化失败，回退为眼控", exc_info=True)
                self.pointer_source = "eye"
        self.raw_xy: Optional[Tuple[float, float]] = None
        self.filtered_xy: Optional[Tuple[float, float]] = None
        self.face_x: Optional[float] = None
        self.pose_warning = False
        self.detector = ClickDetector(cfg.click)
        self.model: Optional[CalibrationModel] = None
        self.state = "INIT"
        self.paused = False
        self.click_enabled = True
        self.dragging = False
        self.last_mouse: Tuple[float, float] = (0.0, 0.0)
        self.last_face_time = time.perf_counter()
        self.fps = 0.0
        self._last_frame_time = time.perf_counter()
        self._running = True

    # ---------------- 生命周期 ----------------
    def run(self) -> int:
        """启动并运行主循环，返回进程退出码。"""
        for line in describe_environment(self.cfg, self.log_path):
            LOGGER.info("%s", line)
        LOGGER.info("鼠标模式：%s", "dry-run（不真正控制鼠标）" if self.dry_run else "真实控制")
        self.hotkeys.start()
        try:
            self.camera.open()
        except CameraError:
            self.hotkeys.stop()
            self.ui.close()
            raise
        try:
            if self.force_recalibrate_face:
                self._recalibrate_face()
            self._enter_tracking_or_calibrate()
            self._main_loop()
        except CalibrationCancelled:
            LOGGER.warning("校准被取消，程序退出")
            return 1
        except Exception:
            LOGGER.exception("运行过程中发生未捕获异常，正在安全退出")
            return 1
        finally:
            self._release_drag()
            self.camera.release()
            self.landmark_detector.close()
            if self.hand_tracker is not None:
                self.hand_tracker.close()
            self.hotkeys.stop()
            self.ui.close()
        return 0

    def _calibration_path(self) -> Path:
        path = Path(self.cfg.calibration.file)
        if not path.is_absolute():
            path = Path(self.cfg.root) / path
        return path.resolve()

    def _face_profile_path(self) -> Path:
        path = Path(self.cfg.face_profile.file)
        if not path.is_absolute():
            path = Path(self.cfg.root) / path
        return path.resolve()

    def _load_face_profile(self) -> Optional[FaceProfile]:
        """载入个人面部模板；不存在或无效时返回 None（不影响启动）。"""
        if not self.cfg.face_profile.enabled:
            return None
        path = self._face_profile_path()
        try:
            return FaceProfile.load(path, root=self.cfg.root)
        except FileNotFoundError:
            LOGGER.info("未找到面部模板：%s", path)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            LOGGER.warning("面部模板无效（%s），将重新标定", exc)
        return None

    def _enter_tracking_or_calibrate(self) -> None:
        """存在有效校准文件则直接跟踪，否则进入校准。"""
        calibration_path = self._calibration_path()
        model: Optional[CalibrationModel] = None
        if not self.force_recalibrate:
            try:
                model = CalibrationModel.load(
                    calibration_path, expected_screen=self.screen_size, root=self.cfg.root
                )
                LOGGER.info("已加载有效校准文件：%s", calibration_path)
            except FileNotFoundError:
                LOGGER.info("未找到校准文件，进入校准流程：%s", calibration_path)
            except ScreenSizeMismatchError as exc:
                LOGGER.warning("%s", exc)
            except ModelVersionMismatchError as exc:
                LOGGER.warning("%s（旧版本校准文件将重新校准）", exc)
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                LOGGER.warning("校准文件无效（%s），重新校准", exc)
        if model is None:
            model = self._calibrate()
        self.model = model
        self.state = "TRACKING"
        LOGGER.info("进入 TRACKING 状态")

    def _save_created_profile(self, calibrator: Calibrator) -> None:
        """若本轮生成了新的面部模板，则保存并切换头姿估计器。"""
        profile = getattr(calibrator, "created_profile", None)
        if profile is None:
            return
        saved = profile.save(self._face_profile_path(), root=self.cfg.root)
        self.face_profile = profile
        self.head_estimator.set_profile(profile)
        LOGGER.info("面部模板绝对路径：%s", saved)

    def _calibrate(self) -> CalibrationModel:
        """执行校准并保存结果。"""
        self.state = "CALIBRATING"
        self.ui.open_calibration()
        try:
            calibrator = Calibrator(self.cfg, profile=self.face_profile)
            model = calibrator.run(
                self.camera, self.landmark_detector, self.ui, self.screen_size
            )
        finally:
            self.ui.close_calibration()
        self._save_created_profile(calibrator)
        saved_path = model.save(self._calibration_path(), root=self.cfg.root)
        LOGGER.info("校准文件绝对路径：%s", saved_path)
        return model

    def _recalibrate_face(self) -> None:
        """只重做面部标定；已有屏幕校准模型则继续沿用。"""
        LOGGER.info("开始重做面部标定（--recalibrate-face）")
        self._release_drag()
        self.detector.reset()
        self._reset_smoothing()
        self.state = "CALIBRATING"
        self.ui.open_calibration()
        try:
            calibrator = Calibrator(self.cfg, profile=None)
            profile = calibrator.calibrate_face(
                self.camera, self.landmark_detector, self.ui
            )
        finally:
            self.ui.close_calibration()
        if profile is None:
            raise CalibrationCancelled("用户取消了面部标定")
        self._save_created_profile(calibrator)
        LOGGER.info("面部标定完成（样本 %d 帧）", profile.sample_frames)

    # ---------------- 热键与状态 ----------------
    def _handle_requests(self, requests: HotkeyRequests) -> None:
        if requests.quit:
            LOGGER.info("收到退出请求（F10）")
            self.state = "EXIT"
            return
        if requests.recalibrate:
            self._recalibrate()
            return
        if requests.toggle_click:
            self.click_enabled = not self.click_enabled
            LOGGER.info("点击功能已%s", "开启" if self.click_enabled else "关闭")
        if requests.cycle_mode:
            self._cycle_mode()
        if requests.cycle_cursor:
            self._cycle_cursor()
        if requests.recenter:
            self._recenter_baseline()
        if requests.toggle_pause:
            self._toggle_pause()

    @staticmethod
    def _resolve_pointer_source(cfg: AppConfig) -> str:
        """解析手控来源；未启用手控或取值非法时回退眼控。"""
        source = str(cfg.hand_control.pointer_source).strip().lower()
        if not cfg.hand_control.enabled or source not in ("eye", "hand", "hybrid"):
            return "eye"
        return source

    def _hand_debug(self) -> dict:
        """手控相关调试字段。"""
        return {
            "hand": self.hand,
            "hand_point": self.hand_point,
            "hand_gate": "OPEN" if self.hand_gate_open else "CLOSED",
            "pointer_source": self.pointer_source,
            "hand_fps": self.hand_fps,
        }

    def _toggle_pause(self) -> None:
        if self.state == "PAUSED":
            self.state = "TRACKING"
            self._reset_smoothing()
            LOGGER.info("已恢复跟踪（F9）")
        else:
            self.state = "PAUSED"
            self._release_drag()
            self.detector.reset()
            self._reset_smoothing()
            LOGGER.info("已暂停（F9），程序不再移动鼠标")

    def _cycle_cursor(self) -> None:
        """在眼控与面部朝向控制之间循环切换光标来源。"""
        if not self.cfg.head_control.enabled:
            LOGGER.info("面部朝向控制已禁用（head_control.enabled=false），保持眼控")
            return
        self.cursor_source = next_source(self.cursor_source)
        self._reset_smoothing()
        self.head_mapper.reset()
        LOGGER.info(
            "光标来源已切换为：%s",
            "面部朝向(head)" if self.cursor_source == "head" else "眼睛(eye)",
        )

    def _recenter_baseline(self) -> None:
        """一键基准点校准（F4）：把头控零点设为当前头姿。

        头控模式下当前头姿即屏幕中心；眼控模式没有中性基准，改为重置平滑与注视稳定。
        """
        if self.cursor_source == "head":
            pose = self.head_pose
            if pose is None:
                LOGGER.warning("基准点校准：尚未获取头姿，请正对镜头后重试")
                return
            yaw, pitch, _roll = pose.angles()
            if not self.head_mapper.recenter(yaw, pitch, self.face_x):
                LOGGER.warning("基准点校准：头姿角度无效，已忽略")
                return
            self._reset_smoothing()
            LOGGER.info("头控基准点已重设：yaw=%.1f° pitch=%.1f°", yaw, pitch)
        else:
            self._reset_smoothing()
            LOGGER.info("眼控模式无中性基准，已重置平滑与注视稳定（F4）")
        self.ui.show_action("基准点校准")

    def _cycle_mode(self) -> None:
        index = CLICK_MODES.index(self.cfg.click.mode) if self.cfg.click.mode in CLICK_MODES else 0
        next_mode = CLICK_MODES[(index + 1) % len(CLICK_MODES)]
        self.cfg.click.mode = next_mode
        self.detector.set_mode(next_mode)
        LOGGER.info("点击模式已切换为：%s", next_mode)

    def _recalibrate(self) -> None:
        LOGGER.info("收到重新校准请求（F8）")
        self._release_drag()
        self.detector.reset()
        self._reset_smoothing()
        try:
            self.model = self._calibrate()
        except CalibrationCancelled:
            LOGGER.warning("重新校准被取消，程序退出")
            self.state = "EXIT"
            return
        self.state = "TRACKING"
        LOGGER.info("重新校准完成，恢复跟踪")

    def _reset_smoothing(self) -> None:
        """重置特征平滑、屏幕滤波、注视稳定与抖动统计。"""
        self.filter.reset()
        self.feature_smoother.reset()
        self.stability.reset()
        self.jitter_tracker.reset()
        self.head_estimator.reset()
        self.head_pose = None
        self.gaze = None
        self.face_x = None
        self.pose_warning = False
        self.hand = None
        self.hand_point = None
        self.hand_gate.reset()
        self.hand_pointer.reset()
        self.hand_gate_open = False
        self._blink_suspended = False
        self._hand_last_time = None

    def _debug_extra(self) -> dict:
        """调试叠加层需要的坐标/抖动/超范围信息。"""
        pose = self.head_pose
        return {
            "raw_xy": self.raw_xy,
            "filtered_xy": self.filtered_xy,
            "jitter_px": self.jitter_tracker.std(),
            "pose_warning": self.pose_warning,
            "head_pose": None if pose is None else pose.angles(),
            "gaze": self.gaze,
            "reprojection_error": None if pose is None else pose.reprojection_error,
            "head_rvec": None if pose is None else pose.rvec,
            "head_tvec": None if pose is None else pose.tvec,
            "head_axis_length": 40.0 if pose is None else pose.axis_length,
            "head_focal_scale": self.cfg.face_profile.focal_scale,
            "cursor_source": self.cursor_source,
            "face_x": self.face_x,
            **self._hand_debug(),
        }

    def _release_drag(self) -> None:
        if self.dragging:
            self.mouse.release("left")
            self.dragging = False
            LOGGER.info("已释放拖拽左键")

    # ---------------- 帧循环 ----------------
    def _main_loop(self) -> None:
        while self._running and self.state != "EXIT":
            requests = self.hotkeys.poll()
            if requests.any():
                self._handle_requests(requests)
                if self.state == "EXIT":
                    break
            if self.state == "PAUSED":
                self._paused_frame()
            else:
                self._tracking_frame()

    def _update_fps(self, now: float) -> None:
        delta = now - self._last_frame_time
        self._last_frame_time = now
        if delta > 0:
            instant = 1.0 / delta
            self.fps = instant if self.fps <= 0 else 0.9 * self.fps + 0.1 * instant
            if self.fps < 15.0:
                LOGGER.warning("帧率偏低：%.1f FPS", self.fps)

    def _baseline(self) -> float:
        if self.model is not None and self.model.ear_baseline > 0:
            return float(self.model.ear_baseline)
        return FALLBACK_EAR_BASELINE

    def _paused_frame(self) -> None:
        frame = self.camera.read()
        face = self.landmark_detector.detect(frame) if frame is not None else None
        self.ui.draw_debug(
            frame,
            face=face,
            ear=None,
            fps=self.fps,
            status="PAUSED",
            blinks=0,
            settle_ratio=0.0,
            mode=self.cfg.click.mode,
            dwell_progress=0.0,
            dragging=False,
            jitter_px=self.jitter_tracker.std(),
            **self._hand_debug(),
        )

    def _tracking_frame(self) -> None:
        now = time.perf_counter()
        self._update_fps(now)
        frame = self.camera.read()
        if frame is None:
            LOGGER.debug("读帧失败，跳过本帧")
            return
        self._process_hands(now, frame)
        face = self.landmark_detector.detect(frame)
        if face is None:
            if now - self.last_face_time > self.cfg.tracking.lost_face_timeout:
                self._release_drag()
                self.detector.update(now, 0.0, self._baseline(), self.last_mouse, False)
                self.ui.draw_debug(
                    frame,
                    face=None,
                    ear=None,
                    fps=self.fps,
                    status="NO FACE",
                    blinks=0,
                    settle_ratio=0.0,
                    mode=self.cfg.click.mode,
                    dwell_progress=0.0,
                    dragging=self.dragging,
                    jitter_px=self.jitter_tracker.std(),
                    **self._hand_debug(),
                )
            else:
                self.ui.draw_debug(
                    frame,
                    face=None,
                    ear=None,
                    fps=self.fps,
                    status="TRACKING",
                    blinks=self.detector.pending_count(),
                    settle_ratio=0.0,
                    mode=self.cfg.click.mode,
                    dwell_progress=0.0,
                    dragging=self.dragging,
                    jitter_px=self.jitter_tracker.std(),
                    **self._hand_debug(),
                )
            return

        self.last_face_time = now
        self.face_x = face_center_x(face)
        ear_a, ear_b = compute_ear(face)
        mean_ear = (ear_a + ear_b) / 2.0
        baseline = self._baseline()
        close_threshold = baseline * self.cfg.click.close_ratio
        frozen = self.detector.in_sequence() or mean_ear < close_threshold
        self.pose_warning = False
        hand_active = (
            self.hand_gate_open
            and self.hand_tracker is not None
            and self.pointer_source in ("hand", "hybrid")
        )
        driver = resolve_cursor_driver(self.pointer_source, hand_active, self.cursor_source)
        if driver == "hand":
            self._drive_hand_cursor(now)
        if not frozen:
            pose = self.head_estimator.estimate(face)
            self.head_pose = pose
            self.gaze = estimate_gaze(
                face,
                rotation=pose.rotation if pose.trustworthy else None,
                eyeball_offset=self.cfg.face_profile.eyeball_offset,
            )
            if driver == "eye":
                self._drive_eye_cursor(face, pose, now)
            elif driver == "head":
                self._drive_head_cursor(pose, now)
            elif driver == "none":
                # 手控模式且 gate 关闭：特征/头姿继续算，但光标不动
                self._drive_eye_cursor(face, pose, now, move_cursor=False)

        if should_suspend_blink(self.cfg.hand_control.suspend_blink_while_hand, hand_active):
            if not self._blink_suspended:
                self.detector.reset()
                self._blink_suspended = True
        else:
            self._blink_suspended = False
            event = self.detector.update(now, mean_ear, baseline, self.last_mouse, True)
            if event is not None:
                self._handle_event(event)

        self.ui.draw_debug(
            frame,
            face=face,
            ear=mean_ear,
            fps=self.fps,
            status="TRACKING",
            blinks=self.detector.pending_count(),
            settle_ratio=self.detector.settle_remaining() / max(self.cfg.click.group_gap, 1e-6),
            mode=self.cfg.click.mode,
            dwell_progress=self.detector.dwell_progress(),
            dragging=self.dragging,
            **self._debug_extra(),
        )

    def _process_hands(self, now: float, frame) -> None:
        """按 hand_every_n_frames 检测右手并推进 gate，必要时锁定/释放手控参考。"""
        tracker = self.hand_tracker
        if tracker is None:
            return
        cfg = self.cfg.hand_control
        self._hand_frame_counter += 1
        if self._hand_frame_counter % max(cfg.hand_every_n_frames, 1) == 0:
            self.hand = tracker.detect(frame, want="Right")
            if self._hand_last_time is None:
                self._hand_last_time = now
            else:
                delta = now - self._hand_last_time
                self._hand_last_time = now
                if delta > 0:
                    instant = 1.0 / delta
                    self.hand_fps = (
                        instant if self.hand_fps <= 0 else 0.9 * self.hand_fps + 0.1 * instant
                    )
        hand = self.hand
        present = hand is not None
        self.hand_point = (
            hand_tracking_point(hand.pts_norm, cfg.tracking_point) if present else None
        )
        palm_open = bool(
            present
            and is_open_palm(
                hand.pts_norm, cfg.open_ratio, cfg.finger_spread_min, cfg.require_thumb
            )
        )
        was_open = self.hand_gate.is_open
        self.hand_gate_open = self.hand_gate.update(now, present, palm_open)
        if self.hand_gate_open and not was_open:
            center = self.hand_point
            if center is None:
                self.hand_gate_open = False
            else:
                self.hand_pointer.activate(center, self.last_mouse)
                LOGGER.info("手控已激活（张开手掌）")
        elif was_open and not self.hand_gate_open:
            self.hand_pointer.deactivate()
            LOGGER.info("手控已释放（手掌闭合或手丢失）")

    def _drive_eye_cursor(self, face, pose, now: float, move_cursor: bool = True) -> None:
        """眼控路径：特征 -> 回归模型 -> One Euro + 死区 + 注视稳定。

        ``move_cursor=False`` 时只更新特征/预测与调试信息，不移动鼠标（手控模式使用）。
        """
        vector = build_feature_vector(
            face,
            pose=pose,
            profile=self.face_profile,
            eyeball_offset=self.cfg.face_profile.eyeball_offset,
        )
        if vector is not None and self.model is not None:
            smooth_vector = self.feature_smoother(vector)
            predicted_x, predicted_y, in_range = self.model.predict_clamped(
                smooth_vector,
                self.last_mouse,
                self.cfg.head_motion.out_of_range_step_px,
            )
            self.pose_warning = not in_range
            self.raw_xy = (predicted_x, predicted_y)
            filtered_x, filtered_y = self.filter(predicted_x, predicted_y, now)
            self.filtered_xy = (filtered_x, filtered_y)
            self.stability.push(now, filtered_x, filtered_y)
            self.jitter_tracker.push(now, filtered_x, filtered_y)
            if move_cursor:
                if not self.stability.locked():
                    last_x, last_y = self.last_mouse
                    if (
                        math.hypot(filtered_x - last_x, filtered_y - last_y)
                        >= self.cfg.tracking.deadzone_px
                    ):
                        self.mouse.move(filtered_x, filtered_y)
                        self.last_mouse = (filtered_x, filtered_y)
                self.detector.push_position(now, filtered_x, filtered_y)

    def _drive_head_cursor(self, pose, now: float) -> None:
        """面部朝向控制：yaw/pitch -> 光标（velocity 积分或 absolute 直映射），不经回归模型。"""
        yaw, pitch, _roll = pose.angles()
        target_x, target_y = self.head_mapper.update(yaw, pitch, now, self.face_x)
        self.pose_warning = not pose.trustworthy
        self.raw_xy = (target_x, target_y)
        filtered_x, filtered_y = self.filter(target_x, target_y, now)
        self.filtered_xy = (filtered_x, filtered_y)
        self.jitter_tracker.push(now, filtered_x, filtered_y)
        self.mouse.move(filtered_x, filtered_y)
        self.last_mouse = (filtered_x, filtered_y)
        self.detector.push_position(now, filtered_x, filtered_y)

    def _drive_hand_cursor(self, now: float) -> None:
        """手控光标：手掌中心 -> 屏幕坐标（HandPointer 已含独立滤波与死区）。"""
        hand = self.hand
        center = self.hand_point
        if hand is None or center is None:
            return
        target = self.hand_pointer.update(center, now)
        if target is None:
            return
        self.raw_xy = target
        self.filtered_xy = target
        self.jitter_tracker.push(now, target[0], target[1])
        self.mouse.move(target[0], target[1])
        self.last_mouse = target
        self.detector.push_position(now, target[0], target[1])

    def _handle_event(self, event: ClickEvent) -> None:
        action = event.action
        if action == "toggle_pause":
            self._toggle_pause()
            return
        if not self.click_enabled:
            LOGGER.info("点击功能已关闭，忽略动作：%s", action)
            return
        position = event.position
        self.mouse.move(position[0], position[1])
        if action == "left_click":
            self.mouse.click("left")
        elif action == "right_click":
            self.mouse.click("right")
        elif action == "middle_click":
            self.mouse.click("middle")
        elif action == "double_click":
            self.mouse.double_click()
        elif action == "toggle_drag":
            if self.dragging:
                self.mouse.release("left")
                self.dragging = False
            else:
                self.mouse.press("left")
                self.dragging = True
        else:
            LOGGER.warning("未知动作：%s", action)
            return
        self.ui.show_action(ACTION_LABELS.get(action, action))
        LOGGER.info(
            "执行动作 %s（连续眨眼 %d 次，位置 %.0f,%.0f）",
            action,
            event.blink_count,
            position[0],
            position[1],
        )

