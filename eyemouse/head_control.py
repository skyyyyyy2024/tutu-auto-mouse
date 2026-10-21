"""面部朝向控制光标：把头姿 yaw/pitch（外加脸部左右平移）映射为光标位置。

两种模式：

- ``velocity``（摇杆式）：头部偏离中性区越远，光标移动越快；回到中性区即停止。
- ``absolute``（默认，最「跟手」）：角度直接线性映射为屏幕位置，角度与位置一一对应，
  头回正光标也回正。

三个可选增强：

- ``diagonal_boost``：对角方向（左下/右下/左上/右上）额外增益，|u|、|v| 都非零时按
  ``1 + boost * 2*min/(|u|+|v|)`` 放大，纯单轴不受影响，用来补偿「自然对角转头幅度偏小」。
- ``translation_weight`` / ``translation_range``：把脸在画面中的左右平移也计入水平方向
  （相对基准点的偏移 / range，再乘 weight 加到水平比例上），提供更细的横向控制。
- ``invert_x`` / ``invert_y``：方向反了置 true。

按 ``safety.baseline_key``（默认 F4）可把当前头姿与脸位设为零点基准（一键基准点校准）：
基准点对应屏幕中心。本模块只在光标来源为 ``head`` 时使用；眼控（虹膜 + 回归模型）完全保留。
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

CURSOR_SOURCES = ("eye", "head")
HEAD_MODES = ("velocity", "absolute")
MAX_DT = 0.2  # 秒；防止卡顿后位置跳变


def clamp(value: float, low: float, high: float) -> float:
    """把数值限制到 [low, high]。"""
    return min(max(float(value), float(low)), float(high))


def shaped_ratio(angle: float, deadzone_deg: float, max_deg: float) -> float:
    """把角度转成 [-1, 1] 比例：中性区为 0，到 max_deg 时饱和为 ±1。"""
    magnitude = abs(float(angle))
    deadzone = max(float(deadzone_deg), 0.0)
    if not math.isfinite(magnitude) or magnitude <= deadzone:
        return 0.0
    span = max(float(max_deg) - deadzone, 1e-6)
    return math.copysign(min((magnitude - deadzone) / span, 1.0), float(angle))


def apply_diagonal_boost(x_ratio: float, y_ratio: float, boost: float) -> Tuple[float, float]:
    """对角增益：两个轴都非零时按对角程度放大，单轴保持不变。"""
    amount = float(boost)
    if not math.isfinite(amount) or amount <= 0.0:
        return (x_ratio, y_ratio)
    magnitude_x = abs(x_ratio)
    magnitude_y = abs(y_ratio)
    total = magnitude_x + magnitude_y
    if total <= 1e-9:
        return (x_ratio, y_ratio)
    factor = 1.0 + amount * (2.0 * min(magnitude_x, magnitude_y) / total)
    return (x_ratio * factor, y_ratio * factor)


def axis_velocity(
    angle: float,
    deadzone_deg: float,
    max_deg: float,
    speed_px_s: float,
    response: float,
) -> float:
    """把单个轴向角度映射为带符号速度（像素/秒）。

    中性区（|angle| <= deadzone）内速度为 0；到 ``max_deg`` 时达到 ``speed_px_s``，
    ``response`` 为速度曲线指数（越大越「细腻」，小幅偏离移动更慢）。
    """
    ratio = shaped_ratio(angle, deadzone_deg, max_deg)
    shaped = math.copysign(abs(ratio) ** max(float(response), 1e-6), ratio)
    return float(speed_px_s) * shaped


def velocity_from_ratio(ratio: float, speed_px_s: float, response: float) -> float:
    """把 [-1,1] 比例转成带符号速度（像素/秒），保留 response 曲线。"""
    bounded = clamp(ratio, -1.0, 1.0)
    shaped = math.copysign(abs(bounded) ** max(float(response), 1e-6), bounded)
    return float(speed_px_s) * shaped


class HeadCursorMapper:
    """按配置把 (yaw, pitch, face_x) 转成屏幕坐标，内部维护速度与位置状态。"""

    def __init__(self, cfg: object, screen_size: Tuple[int, int]) -> None:
        self.cfg = cfg
        self.screen_size = (int(screen_size[0]), int(screen_size[1]))
        self._x = 0.0
        self._y = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._last_time: Optional[float] = None
        self._center_yaw = 0.0
        self._center_pitch = 0.0
        self._center_face_x: Optional[float] = None  # None=尚未建立，首帧自动采用
        self.reset()

    def reset(self) -> None:
        """回到屏幕中心并清空速度、时间与基准点状态。"""
        width, height = self.screen_size
        self._x = (width - 1.0) / 2.0
        self._y = (height - 1.0) / 2.0
        self._vx = 0.0
        self._vy = 0.0
        self._last_time = None
        self._center_yaw = 0.0
        self._center_pitch = 0.0
        self._center_face_x = None

    def recenter(self, yaw: float, pitch: float, face_x: Optional[float] = None) -> bool:
        """一键基准点校准：把当前头姿与脸位设为零点。

        之后 (yaw, pitch) 与脸部左右偏移都相对该零点计算；absolute 模式下基准点即屏幕中心。
        角度非有限值时忽略并返回 False。
        """
        yaw_value = float(yaw)
        pitch_value = float(pitch)
        if not (math.isfinite(yaw_value) and math.isfinite(pitch_value)):
            return False
        self._center_yaw = yaw_value
        self._center_pitch = pitch_value
        if face_x is not None:
            face_value = float(face_x)
            if math.isfinite(face_value):
                self._center_face_x = face_value
        self._vx = 0.0
        self._vy = 0.0
        if self.cfg.mode == "absolute":
            width, height = self.screen_size
            self._x = (width - 1.0) / 2.0
            self._y = (height - 1.0) / 2.0
        return True

    @property
    def center(self) -> Tuple[float, float]:
        """当前角度基准点 (yaw, pitch)。"""
        return (self._center_yaw, self._center_pitch)

    @property
    def center_face_x(self) -> float:
        """当前脸部水平基准（归一化画面 x）；尚未建立时按画面中心 0.5。"""
        if self._center_face_x is None:
            return 0.5
        return self._center_face_x

    @property
    def position(self) -> Tuple[float, float]:
        """当前映射出的屏幕坐标。"""
        return (self._x, self._y)

    @property
    def velocity(self) -> Tuple[float, float]:
        """当前平滑后的速度（像素/秒）。"""
        return (self._vx, self._vy)

    def _translation_ratio(self, face_x: Optional[float]) -> float:
        """脸部左右平移折算到水平比例，超范围被裁剪。

        尚未建立基准（未按 F4）时，用第一个有效脸位自动建立基准并返回 0，
        避免启动瞬间把居中的脸当成大偏移。
        """
        if face_x is None:
            return 0.0
        try:
            value = float(face_x)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(value):
            return 0.0
        if self._center_face_x is None:
            self._center_face_x = value
            return 0.0
        span = float(self.cfg.translation_range)
        if span <= 0.0:
            return 0.0
        return clamp((value - self._center_face_x) / span, -1.0, 1.0)

    def _ratios(self, yaw: float, pitch: float, face_x: Optional[float]) -> Tuple[float, float]:
        """计算含平移、对角增益并裁剪到 [-1,1] 的水平/垂直比例。"""
        x_ratio = shaped_ratio(yaw, self.cfg.deadzone_deg, self.cfg.max_yaw_deg)
        y_ratio = shaped_ratio(pitch, self.cfg.deadzone_deg, self.cfg.max_pitch_deg)
        weight = float(self.cfg.translation_weight)
        if weight != 0.0:
            x_ratio += weight * self._translation_ratio(face_x)
        x_ratio, y_ratio = apply_diagonal_boost(x_ratio, y_ratio, self.cfg.diagonal_boost)
        return (clamp(x_ratio, -1.0, 1.0), clamp(y_ratio, -1.0, 1.0))

    def _absolute(self, x_ratio: float, y_ratio: float) -> Tuple[float, float]:
        width, height = self.screen_size
        if self.cfg.invert_x:
            x_ratio = -x_ratio
        if self.cfg.invert_y:
            y_ratio = -y_ratio
        x = (x_ratio + 1.0) / 2.0 * (width - 1.0)
        y = (1.0 - y_ratio) / 2.0 * (height - 1.0)  # 抬头(pitch>0) -> 光标上移
        return (x, y)

    def update(
        self,
        yaw: float,
        pitch: float,
        now: float,
        face_x: Optional[float] = None,
    ) -> Tuple[float, float]:
        """用当前头姿角度、脸位与时间戳更新并返回光标坐标（自动扣除基准点）。"""
        rel_yaw = float(yaw) - self._center_yaw
        rel_pitch = float(pitch) - self._center_pitch
        x_ratio, y_ratio = self._ratios(rel_yaw, rel_pitch, face_x)

        if self.cfg.mode == "absolute":
            self._x, self._y = self._absolute(x_ratio, y_ratio)
            self._last_time = float(now)
            return (self._x, self._y)

        if self._last_time is None:
            dt = 0.0
        else:
            dt = min(max(float(now) - self._last_time, 0.0), MAX_DT)
        self._last_time = float(now)

        vx = velocity_from_ratio(x_ratio, self.cfg.speed_px_s, self.cfg.response)
        vy = velocity_from_ratio(y_ratio, self.cfg.speed_px_s, self.cfg.response)
        if self.cfg.invert_x:
            vx = -vx
        vy = -vy  # 抬头 -> 屏幕 y 减小
        if self.cfg.invert_y:
            vy = -vy

        alpha = clamp(self.cfg.smoothing_alpha, 0.0, 1.0)
        self._vx = alpha * vx + (1.0 - alpha) * self._vx
        self._vy = alpha * vy + (1.0 - alpha) * self._vy

        width, height = self.screen_size
        self._x = clamp(self._x + self._vx * dt, 0.0, width - 1.0)
        self._y = clamp(self._y + self._vy * dt, 0.0, height - 1.0)
        return (self._x, self._y)


def next_source(current: str) -> str:
    """在 eye 与 head 之间循环切换光标来源。"""
    normalized = str(current).strip().lower()
    if normalized not in CURSOR_SOURCES:
        return CURSOR_SOURCES[0]
    index = CURSOR_SOURCES.index(normalized)
    return CURSOR_SOURCES[(index + 1) % len(CURSOR_SOURCES)]