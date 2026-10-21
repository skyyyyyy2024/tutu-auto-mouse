"""手部控制光标映射：手掌中心 -> 屏幕坐标（relative / absolute），带独立滤波与死区。

- 追踪点：手腕(0) 与四个 MCP(5/9/13/17) 的均值，即手掌中心（归一化坐标）。
- ``relative``（默认）：gate 进入时记录手部锚点与当前光标位置，之后按位移增量移动，
  退出再进入不会跳变。
- ``absolute``：把手在画面中的位置线性映射到屏幕，只取中间 ``active_region`` 为满量程。
- One Euro 参数与死区都独立于眼控滤波器，互不共享状态。
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

import numpy as np

from .filters import OneEuroFilter2D
from .hand_gesture import (
    INDEX_MCP,
    INDEX_TIP,
    MIDDLE_MCP,
    PINKY_MCP,
    RING_MCP,
    THUMB_TIP,
    WRIST,
    normalize_points,
)

HAND_MAPPINGS = ("relative", "absolute")
PALM_POINT_INDEXES = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)

# 光标以哪个关键点为基准：手掌中心 / 手腕 / 食指指尖 / 拇指指尖
TRACKING_POINTS = ("palm", "wrist", "index_tip", "thumb_tip")
_TRACKING_INDEXES = {
    "wrist": (WRIST,),
    "index_tip": (INDEX_TIP,),
    "thumb_tip": (THUMB_TIP,),
}


def clamp(value: float, low: float, high: float) -> float:
    """把数值限制到 [low, high]。"""
    return min(max(float(value), float(low)), float(high))


def tracking_point(
    points_norm: Sequence[Sequence[float]], mode: str = "palm"
) -> Optional[Tuple[float, float]]:
    """按 ``mode`` 取追踪点（归一化坐标）。

    palm（默认）= 手腕与四个 MCP 的均值；wrist / index_tip / thumb_tip 分别取
    手腕 0 / 食指指尖 8 / 拇指指尖 4；未知取值回退为 palm。
    """
    array = normalize_points(points_norm)
    if array is None:
        return None
    key = str(mode).strip().lower()
    indexes = _TRACKING_INDEXES.get(key, PALM_POINT_INDEXES)
    point = array[list(indexes)].mean(axis=0)
    if not np.all(np.isfinite(point)):
        return None
    return (float(point[0]), float(point[1]))


def palm_center(points_norm: Sequence[Sequence[float]]) -> Optional[Tuple[float, float]]:
    """手掌中心：手腕与四个 MCP 的均值（归一化坐标）。"""
    return tracking_point(points_norm, "palm")


class HandPointer:
    """把手掌中心映射为屏幕坐标，维护锚点/参考与滤波状态。"""

    def __init__(self, cfg: object, screen_size: Tuple[int, int]) -> None:
        self.cfg = cfg
        self.screen_size = (int(screen_size[0]), int(screen_size[1]))
        self.filter = OneEuroFilter2D(float(cfg.min_cutoff), float(cfg.beta), 1.0)
        self._anchor: Optional[Tuple[float, float]] = None
        self._reference: Optional[Tuple[float, float]] = None
        self._last_output: Optional[Tuple[float, float]] = None

    @property
    def active(self) -> bool:
        """当前是否已锁定参考（gate 打开中）。"""
        return self._anchor is not None and self._reference is not None

    @property
    def last_output(self) -> Optional[Tuple[float, float]]:
        """最近一次输出的屏幕坐标。"""
        return self._last_output

    def activate(self, tracking_point: Tuple[float, float], cursor_xy: Tuple[float, float]) -> None:
        """gate 进入：锁定手部锚点与当前光标参考位置。"""
        self._anchor = (float(tracking_point[0]), float(tracking_point[1]))
        self._reference = (float(cursor_xy[0]), float(cursor_xy[1]))
        self._last_output = self._reference
        self.filter.reset()

    def deactivate(self) -> None:
        """gate 退出：清除锚点与参考，下次进入重新锁定。"""
        self._anchor = None
        self._reference = None
        self.filter.reset()

    def reset(self) -> None:
        """重置全部状态（暂停/重校准/切换来源时调用）。"""
        self.deactivate()
        self._last_output = None

    def _relative(self, point: Tuple[float, float]) -> Tuple[float, float]:
        assert self._anchor is not None and self._reference is not None
        width, height = self.screen_size
        gain = float(self.cfg.gain)
        x = self._reference[0] + (point[0] - self._anchor[0]) * gain * width
        y = self._reference[1] + (point[1] - self._anchor[1]) * gain * height
        return (x, y)

    def _absolute(self, point: Tuple[float, float]) -> Tuple[float, float]:
        width, height = self.screen_size
        half = max(float(self.cfg.active_region) / 2.0, 1e-3)
        gain = float(self.cfg.gain)
        ratio_x = clamp((point[0] - 0.5) / half, -1.0, 1.0) * gain
        ratio_y = clamp((point[1] - 0.5) / half, -1.0, 1.0) * gain
        x = (clamp(ratio_x, -1.0, 1.0) + 1.0) / 2.0 * (width - 1.0)
        y = (clamp(ratio_y, -1.0, 1.0) + 1.0) / 2.0 * (height - 1.0)
        return (x, y)

    def update(self, tracking_point: Tuple[float, float], now: float) -> Optional[Tuple[float, float]]:
        """用手掌中心更新并返回屏幕坐标；未锁定时返回 None。"""
        if not self.active:
            return None
        point = (float(tracking_point[0]), float(tracking_point[1]))
        if not (math.isfinite(point[0]) and math.isfinite(point[1])):
            return self._last_output
        if str(self.cfg.mapping) == "absolute":
            raw_x, raw_y = self._absolute(point)
        else:
            raw_x, raw_y = self._relative(point)
        width, height = self.screen_size
        filtered_x, filtered_y = self.filter(raw_x, raw_y, float(now))
        target = (clamp(filtered_x, 0.0, width - 1.0), clamp(filtered_y, 0.0, height - 1.0))
        if self._last_output is not None:
            distance = math.hypot(target[0] - self._last_output[0], target[1] - self._last_output[1])
            if distance < float(self.cfg.deadzone_px):
                return self._last_output
        self._last_output = target
        return target