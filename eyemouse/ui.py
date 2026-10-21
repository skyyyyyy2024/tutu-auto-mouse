"""OpenCV 界面：校准界面、眨眼练习界面与调试叠加层（叠加层文字一律英文，避免中文乱码）。"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from .config import AppConfig
from .hand_gesture import HAND_CONNECTIONS
from .landmarks import (
    EYE_A_DOWN,
    EYE_A_INNER,
    EYE_A_OUTER,
    EYE_A_UP,
    EYE_B_DOWN,
    EYE_B_INNER,
    EYE_B_OUTER,
    EYE_B_UP,
    IRIS_A_CENTER,
    IRIS_B_CENTER,
)

LOGGER = logging.getLogger(__name__)

FONT = cv2.FONT_HERSHEY_SIMPLEX
ACTION_DISPLAY_SECONDS = 0.8
DEBUG_WINDOW_SIZE = (480, 360)
KEYPOINT_INDEXES = [
    EYE_A_OUTER,
    EYE_A_INNER,
    EYE_A_UP,
    EYE_A_DOWN,
    IRIS_A_CENTER,
    EYE_B_OUTER,
    EYE_B_INNER,
    EYE_B_UP,
    EYE_B_DOWN,
    IRIS_B_CENTER,
]


def map_point_to_canvas(
    px: float,
    py: float,
    frame_width: int,
    frame_height: int,
    canvas_width: int,
    canvas_height: int,
) -> Tuple[float, float]:
    """把摄像头帧像素坐标映射到叠加层画布坐标。

    只依据摄像头帧的实际 ``(width, height)`` 与画布的 ``(width, height)``，
    x / y 各自独立缩放；不使用屏幕坐标，也不涉及任何头姿补偿值。
    """
    if frame_width <= 0 or frame_height <= 0:
        return float(px), float(py)
    scale_x = float(canvas_width) / float(frame_width)
    scale_y = float(canvas_height) / float(frame_height)
    return float(px) * scale_x, float(py) * scale_y


def flip_display_point(px: float, py: float, frame_width: int, mirrored: bool) -> Tuple[float, float]:
    """把**未镜像**画面坐标换算到左右镜像后的显示坐标。

    几何计算一律用未镜像原始画面；自拍镜像只影响显示，因此绘制检测结果时必须
    在这一步换算，否则标记边框与坐标轴会左右颠倒。
    """
    if not mirrored:
        return float(px), float(py)
    return float(int(frame_width) - 1) - float(px), float(py)


def draw_glasses_overlay(
    frame: np.ndarray,
    pose: Any,
    *,
    camera_matrix: Any = None,
    dist_coeffs: Any = None,
    mirrored: bool = False,
    axis_length_m: float = 0.03,
    stats: Any = None,
    stability: Any = None,
    extra_lines: Optional[Tuple[str, ...]] = None,
) -> None:
    """在**待显示**的 BGR 帧上绘制眼镜标记位姿叠加层（文字一律英文，避免中文乱码）。

    ``pose.corners_px`` 与坐标轴都用未镜像原始画面坐标计算；``mirrored=True`` 时
    本函数负责换算到镜像显示坐标。映射只使用摄像头帧的实际宽高，不使用屏幕坐标，
    也不使用任何头姿补偿值。
    """
    height, width = frame.shape[:2]
    status = str(getattr(pose, "status", ""))
    valid = bool(getattr(pose, "valid", False))
    stale = bool(getattr(pose, "stale", False))
    if valid and not stale:
        color = (0, 255, 0)
    elif stale:
        color = (0, 255, 255)
    else:
        color = (160, 160, 160)

    corners = getattr(pose, "corners_px", None)
    if corners is not None:
        mapped = [
            tuple(
                int(round(value))
                for value in flip_display_point(float(px), float(py), width, mirrored)
            )
            for px, py in np.asarray(corners, dtype=np.float64).reshape(-1, 2)
        ]
        if len(mapped) == 4:
            for index in range(4):
                cv2.line(frame, mapped[index], mapped[(index + 1) % 4], color, 2)
        for point in mapped:
            cv2.circle(frame, point, 3, (0, 0, 255), -1)
        label = f"id={int(getattr(pose, 'marker_id', -1))}"
        cv2.putText(frame, label, (mapped[0][0] + 6, mapped[0][1] - 6), FONT, 0.55, color, 2)

    rotation = getattr(pose, "rotation_matrix", None)
    translation = getattr(pose, "translation_m", None)
    if camera_matrix is not None and rotation is not None and translation is not None:
        _draw_glasses_axes(
            frame,
            np.asarray(rotation, dtype=np.float64),
            np.asarray(translation, dtype=np.float64),
            np.asarray(camera_matrix, dtype=np.float64),
            dist_coeffs,
            mirrored=mirrored,
            axis_length_m=axis_length_m,
        )

    angles = pose.angles_deg() if hasattr(pose, "angles_deg") else None
    translation_mm = pose.translation_mm() if hasattr(pose, "translation_mm") else None
    reprojection = getattr(pose, "reprojection_error_px", None)
    area = getattr(pose, "marker_area_px", None)
    lines = [f"Status: {status}" + (" (STALE)" if stale else "")]
    if reprojection is not None:
        lines.append(f"Reproj {float(reprojection):.2f}px")
    if area is not None:
        lines.append(f"Marker {float(area):.0f}px2")
    if translation_mm is not None:
        lines.append(
            f"Trans {translation_mm[0]:+.0f},{translation_mm[1]:+.0f},{translation_mm[2]:+.0f} mm"
        )
    if angles is not None:
        lines.append(f"Yaw/Pitch/Roll {angles[0]:+.1f}/{angles[1]:+.1f}/{angles[2]:+.1f}")
    if stats is not None:
        lines.append(f"TrackingFPS {float(stats.tracking_fps()):.1f}")
        lines.append(f"Valid {float(stats.valid_ratio()) * 100.0:.0f}% ({int(stats.frames)} frames)")
    if stability is not None:
        summary = stability.summary()
        lines.append(
            "Stability dPos %.1fmm dRot %.2fdeg (n=%d)"
            % (
                float(summary["position_std_mm"]),
                float(summary["rotation_std_deg"]),
                int(summary["samples"]),
            )
        )
    note = str(getattr(pose, "resolve_note", "") or getattr(pose, "reason", ""))
    if note:
        lines.append(f"Note: {note}")
    if extra_lines:
        lines.extend(str(item) for item in extra_lines)
    for index, line in enumerate(lines):
        cv2.putText(frame, line, (8, 24 + index * 20), FONT, 0.55, color, 1, cv2.LINE_AA)


def _draw_glasses_axes(
    frame: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: Any,
    *,
    mirrored: bool,
    axis_length_m: float,
) -> None:
    """把标记坐标轴投影到帧并绘制（X=红 Y=绿 Z=蓝，BGR）。"""
    length = float(axis_length_m)
    if not np.isfinite(length) or length <= 0.0:
        return
    height, width = frame.shape[:2]
    axis = np.array(
        [
            [0.0, 0.0, 0.0],
            [length, 0.0, 0.0],
            [0.0, length, 0.0],
            [0.0, 0.0, length],
        ],
        dtype=np.float64,
    )
    try:
        rvec, _ = cv2.Rodrigues(np.asarray(rotation, dtype=np.float64).reshape(3, 3))
        projected, _ = cv2.projectPoints(
            axis,
            rvec,
            np.asarray(translation, dtype=np.float64).reshape(3, 1),
            camera_matrix,
            np.zeros((1, 1), dtype=np.float64) if dist_coeffs is None else dist_coeffs,
        )
    except cv2.error:
        return
    points = np.asarray(projected, dtype=np.float64).reshape(-1, 2)
    if not np.all(np.isfinite(points)):
        return
    mapped = [
        tuple(int(round(value)) for value in flip_display_point(float(px), float(py), width, mirrored))
        for px, py in points
    ]
    colors = ((0, 0, 255), (0, 255, 0), (255, 0, 0))
    for index, color in enumerate(colors, start=1):
        cv2.line(frame, mapped[0], mapped[index], color, 2)


class UI:
    """封装校准窗口、眨眼练习窗口与调试叠加层。

    校准流程通过鸭子类型调用以下方法：``show_text``、``draw_target``、
    ``show_progress``、``pump``、``show_blink_practice``。
    """

    def __init__(
        self,
        cfg: AppConfig,
        screen_size: Tuple[int, int],
        show_window: bool = True,
    ) -> None:
        self.cfg = cfg
        self.screen_size = (int(screen_size[0]), int(screen_size[1]))
        self.enabled = bool(show_window) and bool(cfg.debug.show_window)
        self._calib_window = "EyeMouse Calibration"
        self._debug_window = "EyeMouse Debug"
        self._calib_created = False
        self._debug_created = False
        self._calibrating = False
        self._text = ""
        self._progress: Tuple[int, int] = (0, 0)
        self._target: Optional[Tuple[float, float, float]] = None
        self._practice: Optional[Tuple[int, int, str]] = None
        self._head: Optional[Tuple[int, int, float, str]] = None
        self._action_text = ""
        self._action_until = 0.0

    # ---------------- 校准界面 ----------------
    def open_calibration(self) -> None:
        """进入校准：隐藏调试窗口并创建全屏黑底校准窗口。"""
        self._calibrating = True
        self._hide_debug_window()
        if not self.enabled:
            return
        try:
            cv2.namedWindow(self._calib_window, cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty(
                self._calib_window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
            )
            self._calib_created = True
            self._render_calibration()
        except cv2.error:
            LOGGER.warning("无法创建校准窗口，改为无界面校准", exc_info=True)
            self.enabled = False

    def close_calibration(self) -> None:
        """退出校准：销毁校准窗口。"""
        self._calibrating = False
        self._target = None
        self._practice = None
        self._head = None
        self._text = ""
        if self._calib_created:
            try:
                cv2.destroyWindow(self._calib_window)
            except cv2.error:
                LOGGER.debug("销毁校准窗口失败", exc_info=True)
            self._calib_created = False

    def show_text(self, text: str) -> None:
        """显示校准提示文字（英文）。"""
        self._text = text
        self._render_calibration()

    def show_progress(self, current: int, total: int) -> None:
        """右上角进度 n/9。"""
        self._progress = (int(current), int(total))
        self._render_calibration()

    def draw_target(self, x: float, y: float, shrink: float) -> None:
        """绘制校准圆点，shrink 从 1 收缩到 0。"""
        self._target = (float(x), float(y), float(shrink))
        self._render_calibration()

    def show_head_motion(
        self, current: int, total: int, seconds_left: float, message: str = ""
    ) -> None:
        """显示头动校准提示：当前点编号、剩余秒数与操作说明。"""
        self._head = (int(current), int(total), float(seconds_left), str(message))
        self._render_calibration()

    def show_blink_practice(self, target: int, detected: int, action: str) -> None:
        """显示眨眼练习提示。"""
        self._practice = (int(target), int(detected), str(action))
        self._render_calibration()

    def _render_calibration(self) -> None:
        if not self.enabled or not self._calibrating or not self._calib_created:
            return
        width, height = self.screen_size
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(canvas, self._text or "Calibration", (40, 60), FONT, 1.0, (255, 255, 255), 2)
        current, total = self._progress
        if total > 0:
            label = f"{current}/{total}"
            cv2.putText(canvas, label, (width - 180, 60), FONT, 1.0, (200, 200, 200), 2)
        if self._head is not None:
            current, total, seconds_left, message = self._head
            head_lines = [message, f"Point {current}/{total}   {seconds_left:.1f}s"]
            for index, line in enumerate(head_lines):
                cv2.putText(
                    canvas,
                    line,
                    (60, height - 90 + index * 40),
                    FONT,
                    0.9,
                    (0, 255, 255),
                    2,
                )
        if self._practice is not None:
            required, detected, action = self._practice
            lines = [
                f"Please blink {required} times",
                f"Detected blinks: {detected}",
                f"Action: {action}",
                "Press ESC to skip practice",
            ]
            for index, line in enumerate(lines):
                cv2.putText(
                    canvas,
                    line,
                    (width // 2 - 300, height // 2 - 60 + index * 50),
                    FONT,
                    1.1,
                    (0, 255, 255),
                    2,
                )
        if self._target is not None:
            target_x, target_y, shrink = self._target
            clamped = min(max(shrink, 0.0), 1.0)
            radius = int(8 + 32 * clamped)
            color = (0, 255, 0) if clamped <= 0.01 else (0, 0, 255)
            cv2.circle(canvas, (int(target_x), int(target_y)), radius, color, -1)
        try:
            cv2.imshow(self._calib_window, canvas)
            cv2.waitKey(1)
        except cv2.error:
            LOGGER.warning("刷新校准窗口失败，改为无界面校准", exc_info=True)
            self.enabled = False

    def pump(self, delay_ms: int) -> int:
        """处理窗口事件并返回按键码（无按键返回 -1）；校准流程用 ESC=27 取消。"""
        if self._calibrating:
            self._render_calibration()
        if not self.enabled:
            time.sleep(min(max(delay_ms, 0), 5) / 1000.0)
            return -1
        try:
            key = cv2.waitKey(max(int(delay_ms), 1)) & 0xFF
        except cv2.error:
            self.enabled = False
            return -1
        return -1 if key == 255 else int(key)

    # ---------------- 调试窗口 ----------------
    def _hide_debug_window(self) -> None:
        if self._debug_created:
            try:
                cv2.destroyWindow(self._debug_window)
            except cv2.error:
                LOGGER.debug("隐藏调试窗口失败", exc_info=True)
            self._debug_created = False

    def show_action(self, action: str) -> None:
        """在调试窗口显示动作名 0.8 秒。"""
        self._action_text = action.upper()
        self._action_until = time.time() + ACTION_DISPLAY_SECONDS

    def draw_debug(
        self,
        frame: Optional[np.ndarray],
        *,
        face: Any = None,
        ear: Optional[float] = None,
        fps: float = 0.0,
        status: str = "",
        blinks: int = 0,
        settle_ratio: float = 0.0,
        mode: str = "",
        dwell_progress: float = 0.0,
        dragging: bool = False,
        raw_xy: Optional[Tuple[float, float]] = None,
        filtered_xy: Optional[Tuple[float, float]] = None,
        jitter_px: Optional[float] = None,
        pose_warning: bool = False,
        head_pose: Optional[Tuple[float, float, float]] = None,
        gaze: Optional[Tuple[float, float]] = None,
        reprojection_error: Optional[float] = None,
        head_rvec: Optional[np.ndarray] = None,
        head_tvec: Optional[np.ndarray] = None,
        head_axis_length: float = 40.0,
        head_focal_scale: float = 1.0,
        face_x: Optional[float] = None,
        cursor_source: str = "",
        hand: Any = None,
        hand_gate: str = "",
        pointer_source: str = "",
        hand_fps: float = 0.0,
        hand_point: Any = None,
    ) -> None:
        """组合并显示调试小窗（校准时隐藏）。"""
        if not self.enabled or self._calibrating:
            return
        width, height = DEBUG_WINDOW_SIZE
        frame_width = frame_height = 0
        if frame is None:
            canvas = np.zeros((height, width, 3), dtype=np.uint8)
        else:
            frame_height, frame_width = frame.shape[:2]
            canvas = cv2.resize(frame, (width, height))
        if face is not None and frame_width > 0 and frame_height > 0:
            self._draw_face_points(canvas, face, frame_width, frame_height)
            if head_rvec is not None and head_tvec is not None:
                self._draw_head_axis(
                    canvas,
                    head_rvec,
                    head_tvec,
                    frame_width,
                    frame_height,
                    head_axis_length,
                    head_focal_scale,
                )
        if hand is not None and frame_width > 0 and frame_height > 0:
            self._draw_hand_points(canvas, hand, frame_width, frame_height, hand_point)
        raw_text = (
            f"Raw  {raw_xy[0]:.0f},{raw_xy[1]:.0f}" if raw_xy is not None else "Raw  --"
        )
        filtered_text = (
            f"Filt {filtered_xy[0]:.0f},{filtered_xy[1]:.0f}"
            if filtered_xy is not None
            else "Filt --"
        )
        jitter_text = f"Jitter 1s: {jitter_px:.1f} px" if jitter_px is not None else "Jitter 1s: --"
        head_text = (
            f"Head {head_pose[0]:.1f}/{head_pose[1]:.1f}/{head_pose[2]:.1f}"
            if head_pose is not None
            else "Head --/--/--"
        )
        gaze_text = (
            f"Gaze {gaze[0]:.1f}/{gaze[1]:.1f}" if gaze is not None else "Gaze --/--"
        )
        reproj_text = (
            f"Reproj {reprojection_error:.1f}px"
            if reprojection_error is not None
            else "Reproj --"
        )
        face_text = f"FaceX {face_x:.3f}" if face_x is not None else "FaceX --"
        lines = [
            f"EAR {ear:.3f}" if ear is not None else "EAR --",
            f"FPS {fps:.1f}",
            f"Status: {status}",
            f"Mode: {mode}",
            f"Blinks: {blinks}",
            raw_text,
            filtered_text,
            jitter_text,
            head_text,
            gaze_text,
            reproj_text,
            face_text,
        ]
        if hand_gate:
            lines.append(f"Hand: {hand_gate}")
        if hand_fps > 0.0:
            lines.append(f"HandFPS {hand_fps:.1f}")
        if pointer_source:
            lines.append(f"Ptr: {pointer_source}")
        if cursor_source:
            lines.append(f"Source: {cursor_source}")
        for index, line in enumerate(lines):
            cv2.putText(canvas, line, (8, 20 + index * 18), FONT, 0.5, (0, 255, 0), 1)
        if pose_warning:
            cv2.putText(
                canvas,
                "HEAD OUT OF RANGE",
                (8, 20 + len(lines) * 18 + 4),
                FONT,
                0.55,
                (0, 0, 255),
                2,
            )
        bar_width = int(width * min(max(settle_ratio, 0.0), 1.0))
        cv2.rectangle(canvas, (0, height - 6), (bar_width, height - 1), (0, 200, 255), -1)
        center = (width - 34, height - 34)
        cv2.circle(canvas, center, 22, (80, 80, 80), 2)
        if dwell_progress > 0:
            cv2.ellipse(
                canvas,
                center,
                (22, 22),
                -90,
                0,
                int(360 * min(max(dwell_progress, 0.0), 1.0)),
                (0, 255, 255),
                3,
            )
        if dragging:
            cv2.putText(canvas, "DRAGGING", (8, height - 40), FONT, 0.7, (0, 0, 255), 2)
        if self._action_text and time.time() < self._action_until:
            cv2.putText(
                canvas,
                self._action_text,
                (width // 2 - 90, height // 2),
                FONT,
                0.9,
                (0, 255, 255),
                2,
            )
        cv2.putText(
            canvas,
            "F9 pause  F10 quit  F8 recal  F7 click  F6 mode",
            (8, height - 22),
            FONT,
            0.4,
            (200, 200, 200),
            1,
        )
        try:
            if not self._debug_created:
                cv2.namedWindow(self._debug_window, cv2.WINDOW_AUTOSIZE)
                screen_width, screen_height = self.screen_size
                cv2.moveWindow(
                    self._debug_window,
                    max(0, screen_width - width - 10),
                    max(0, screen_height - height - 40),
                )
                self._debug_created = True
            cv2.imshow(self._debug_window, canvas)
            cv2.waitKey(1)
        except cv2.error:
            LOGGER.warning("刷新调试窗口失败，关闭窗口显示", exc_info=True)
            self.enabled = False

    @staticmethod
    def _draw_face_points(
        canvas: np.ndarray,
        face: Any,
        frame_width: int,
        frame_height: int,
    ) -> None:
        """把 ``face.pts_px``（摄像头帧像素坐标）映射到 canvas 上绘制。

        映射只使用摄像头帧的实际 (width, height) 与 canvas 的 (width, height)，
        x / y 各自缩放；不使用屏幕坐标或头姿补偿值。
        """
        points = getattr(face, "pts_px", None)
        if points is None:
            return
        canvas_height, canvas_width = canvas.shape[:2]
        for index in KEYPOINT_INDEXES:
            if index >= len(points):
                continue
            px, py = points[index]
            if not (np.isfinite(px) and np.isfinite(py)):
                continue
            x, y = map_point_to_canvas(
                px, py, frame_width, frame_height, canvas_width, canvas_height
            )
            cv2.circle(canvas, (int(x), int(y)), 2, (0, 255, 255), -1)

    @staticmethod
    def _draw_hand_points(
        canvas: np.ndarray,
        hand: Any,
        frame_width: int,
        frame_height: int,
        hand_point: Any = None,
    ) -> None:
        """把手部 21 点（摄像头帧像素坐标）映射到 canvas 并绘制骨架，并标出实际追踪点。"""
        points = getattr(hand, "pts_px", None)
        if points is None:
            return
        canvas_height, canvas_width = canvas.shape[:2]
        mapped = []
        for px, py in np.asarray(points, dtype=np.float64):
            if not (np.isfinite(px) and np.isfinite(py)):
                mapped.append(None)
                continue
            mapped.append(
                map_point_to_canvas(px, py, frame_width, frame_height, canvas_width, canvas_height)
            )
        for start, end in HAND_CONNECTIONS:
            if start >= len(mapped) or end >= len(mapped):
                continue
            if mapped[start] is None or mapped[end] is None:
                continue
            cv2.line(
                canvas,
                (int(mapped[start][0]), int(mapped[start][1])),
                (int(mapped[end][0]), int(mapped[end][1])),
                (0, 200, 255),
                1,
            )
        for point in mapped:
            if point is None:
                continue
            cv2.circle(canvas, (int(point[0]), int(point[1])), 2, (255, 128, 0), -1)
        if hand_point is None:
            return
        point_px = (
            float(hand_point[0]) * float(frame_width),
            float(hand_point[1]) * float(frame_height),
        )
        if not (np.isfinite(point_px[0]) and np.isfinite(point_px[1])):
            return
        marker = map_point_to_canvas(
            point_px[0], point_px[1], frame_width, frame_height, canvas_width, canvas_height
        )
        cv2.circle(canvas, (int(round(marker[0])), int(round(marker[1]))), 6, (255, 0, 255), 2)

    @staticmethod
    def _draw_head_axis(
        canvas: np.ndarray,
        rvec: np.ndarray,
        tvec: np.ndarray,
        frame_width: int,
        frame_height: int,
        axis_length: float,
        focal_scale: float,
    ) -> None:
        """用 solvePnP 位姿把头部三轴投影到帧，再经 map_point_to_canvas 画到画布。"""
        length = float(axis_length)
        if not np.isfinite(length) or length <= 0.0:
            return
        rotation = np.asarray(rvec, dtype=np.float64).reshape(3, 1)
        translation = np.asarray(tvec, dtype=np.float64).reshape(3, 1)
        axis = np.array(
            [[0.0, 0.0, 0.0], [length, 0.0, 0.0], [0.0, length, 0.0], [0.0, 0.0, length]],
            dtype=np.float64,
        )
        focal = float(frame_width) * float(focal_scale)
        camera = np.array(
            [
                [focal, 0.0, frame_width / 2.0],
                [0.0, focal, frame_height / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        try:
            projected, _ = cv2.projectPoints(
                axis, rotation, translation, camera, np.zeros((4, 1), dtype=np.float64)
            )
        except cv2.error:
            return
        points = projected.reshape(-1, 2)
        if not np.all(np.isfinite(points)):
            return
        canvas_height, canvas_width = canvas.shape[:2]
        origin = map_point_to_canvas(
            float(points[0][0]), float(points[0][1]), frame_width, frame_height, canvas_width, canvas_height
        )
        colors = ((0, 0, 255), (0, 255, 0), (255, 0, 0))  # X=红 Y=绿 Z=蓝（BGR）
        for index, color in enumerate(colors, start=1):
            end = map_point_to_canvas(
                float(points[index][0]),
                float(points[index][1]),
                frame_width,
                frame_height,
                canvas_width,
                canvas_height,
            )
            cv2.line(
                canvas,
                (int(origin[0]), int(origin[1])),
                (int(end[0]), int(end[1])),
                color,
                2,
            )

    def close(self) -> None:
        """关闭所有窗口。"""
        if not self.enabled:
            return
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            LOGGER.debug("关闭窗口失败", exc_info=True)
        self._calib_created = False
        self._debug_created = False
