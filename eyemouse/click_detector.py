"""连续眨眼计数状态机与注视停留点击检测（纯逻辑，不依赖摄像头和鼠标）。"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple

from .config import ClickConfig

# 位置历史保留时长（秒），用于序列开头的点击位置快照
HISTORY_SECONDS = 2.0


@dataclass
class ClickEvent:
    """一次被触发的点击/拖拽/暂停事件。"""

    action: str
    blink_count: int
    position: Tuple[float, float]


class ClickDetector:
    """基于 EAR 迟滞与分组结算的连续眨眼检测器，附带注视停留点击。"""

    def __init__(self, cfg: ClickConfig) -> None:
        self.cfg = cfg
        self.mode = cfg.mode
        self._history: Deque[Tuple[float, float, float]] = deque()
        self._now = 0.0
        self._last_action_time: Optional[float] = None
        self._dwell_center: Optional[Tuple[float, float]] = None
        self._dwell_start: Optional[float] = None
        self._dwell_armed = True
        self._reset_sequence()

    # ---------------- 内部状态 ----------------
    def _reset_sequence(self) -> None:
        """清空当前眨眼序列（含位置快照）。"""
        self._state = "OPEN"
        self._blink_count = 0
        self._first_close_time: Optional[float] = None
        self._last_open_time: Optional[float] = None
        self._close_start: Optional[float] = None
        self._snapshot_pos: Optional[Tuple[float, float]] = None

    def _reset_dwell(self) -> None:
        """重置注视停留计时与去重标记。"""
        self._dwell_center = None
        self._dwell_start = None
        self._dwell_armed = True

    # ---------------- 对外只读状态 ----------------
    def in_sequence(self) -> bool:
        """序列进行中（CLOSED 或已累计至少一次眨眼）。"""
        return self._state == "CLOSED" or self._blink_count > 0

    def pending_count(self) -> int:
        """当前序列已累计的有效眨眼次数。"""
        return self._blink_count

    def settle_remaining(self) -> float:
        """距离结算还剩多少秒（限制在 0..group_gap），供 UI 倒计时条。"""
        if self._state != "OPEN" or self._blink_count <= 0 or self._last_open_time is None:
            return 0.0
        remaining = self.cfg.group_gap - (self._now - self._last_open_time)
        return float(min(max(remaining, 0.0), self.cfg.group_gap))

    def dwell_progress(self) -> float:
        """注视停留进度 0~1。"""
        if self._dwell_start is None or self.cfg.dwell_time <= 0:
            return 0.0
        return float(min(max((self._now - self._dwell_start) / self.cfg.dwell_time, 0.0), 1.0))

    # ---------------- 位置历史与快照 ----------------
    def push_position(self, t: float, x: float, y: float) -> None:
        """记录光标位置；只保留最近 HISTORY_SECONDS 秒。"""
        self._history.append((float(t), float(x), float(y)))
        cutoff = float(t) - HISTORY_SECONDS
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

    def _take_snapshot(self, close_start: float, gaze_xy: Tuple[float, float]) -> None:
        """取「第一次闭眼开始前 freeze_lookback 秒」那一刻的光标位置作为点击位置。"""
        target = close_start - self.cfg.freeze_lookback
        candidate: Optional[Tuple[float, float]] = None
        for hist_t, hist_x, hist_y in self._history:
            if hist_t <= target:
                candidate = (hist_x, hist_y)
        if candidate is None:
            if self._history:
                candidate = (self._history[0][1], self._history[0][2])
            else:
                candidate = (float(gaze_xy[0]), float(gaze_xy[1]))
        self._snapshot_pos = candidate

    # ---------------- 冷却 ----------------
    def _cooldown_ok(self, t: float) -> bool:
        if self._last_action_time is None:
            return True
        return (t - self._last_action_time) >= self.cfg.cooldown

    # ---------------- 眨眼序列 ----------------
    def _settle(self, t: float) -> Optional[ClickEvent]:
        """结算当前序列并（可能）返回事件。"""
        count = self._blink_count
        position: Tuple[float, float] = self._snapshot_pos if self._snapshot_pos is not None else (0.0, 0.0)
        action = self.cfg.actions.get(count, "none")
        event: Optional[ClickEvent] = None
        if 1 <= count <= self.cfg.max_blinks and action != "none" and self._cooldown_ok(t):
            event = ClickEvent(action=action, blink_count=count, position=position)
            self._last_action_time = t
        self._reset_sequence()
        return event

    def _update_blink(
        self,
        t: float,
        avg_ear: float,
        ear_baseline: float,
        gaze_xy: Tuple[float, float],
    ) -> None:
        """推进眨眼迟滞状态机（不做结算）。"""
        if ear_baseline <= 0:
            return
        close_threshold = ear_baseline * self.cfg.close_ratio
        open_threshold = ear_baseline * self.cfg.open_ratio
        if self._state == "OPEN":
            if avg_ear < close_threshold:
                self._state = "CLOSED"
                self._close_start = t
                if self._blink_count == 0:
                    self._take_snapshot(t, gaze_xy)
        else:
            if avg_ear > open_threshold:
                duration = t - float(self._close_start)
                self._state = "OPEN"
                if duration < self.cfg.blink_min_duration:
                    if self._blink_count == 0:
                        # 序列开头的噪声：丢弃刚取的快照
                        self._snapshot_pos = None
                        self._first_close_time = None
                        self._last_open_time = None
                elif duration <= self.cfg.blink_max_duration:
                    self._blink_count += 1
                    self._last_open_time = t
                    if self._blink_count == 1:
                        self._first_close_time = self._close_start
                else:
                    # 闭眼过长：视为有意休息，作废整个序列
                    self._reset_sequence()

    # ---------------- 注视停留 ----------------
    def _update_dwell(self, t: float, gaze_xy: Tuple[float, float]) -> Optional[ClickEvent]:
        """推进注视停留检测；眨眼序列进行中不累计停留时间。"""
        if self.in_sequence():
            self._dwell_start = None
            self._dwell_center = None
            return None
        x, y = float(gaze_xy[0]), float(gaze_xy[1])
        if self._dwell_center is None:
            self._dwell_center = (x, y)
            self._dwell_start = t
            self._dwell_armed = True
            return None
        center_x, center_y = self._dwell_center
        if math.hypot(x - center_x, y - center_y) > self.cfg.dwell_radius:
            self._dwell_center = (x, y)
            self._dwell_start = t
            self._dwell_armed = True
            return None
        if not self._dwell_armed or self._dwell_start is None:
            return None
        if (t - self._dwell_start) >= self.cfg.dwell_time and self._cooldown_ok(t):
            self._last_action_time = t
            self._dwell_armed = False
            self._dwell_start = None
            return ClickEvent(action="left_click", blink_count=0, position=(x, y))
        return None

    # ---------------- 主入口 ----------------
    def update(
        self,
        t: float,
        avg_ear: float,
        ear_baseline: float,
        gaze_xy: Tuple[float, float],
        face_ok: bool,
    ) -> Optional[ClickEvent]:
        """推进一帧状态；返回本帧触发的事件（无则为 None）。"""
        timestamp = float(t)
        self._now = timestamp
        if not face_ok:
            self._reset_sequence()
            self._reset_dwell()
            return None
        if self.mode == "none":
            return None

        event: Optional[ClickEvent] = None
        if self.mode in ("blink_sequence", "both"):
            if (
                self._state == "OPEN"
                and self._blink_count > 0
                and self._last_open_time is not None
                and (timestamp - self._last_open_time) > self.cfg.group_gap
            ):
                event = self._settle(timestamp)
            self._update_blink(timestamp, avg_ear, ear_baseline, gaze_xy)
        if event is None and self.mode in ("dwell", "both"):
            event = self._update_dwell(timestamp, gaze_xy)
        return event

    # ---------------- 控制 ----------------
    def set_mode(self, mode: str) -> None:
        """切换点击模式并重置状态。"""
        if mode not in ("blink_sequence", "dwell", "both", "none"):
            raise ValueError(f"非法点击模式：{mode!r}")
        self.mode = mode
        self.reset()

    def reset(self) -> None:
        """清空序列、停留计时与位置历史。"""
        self._reset_sequence()
        self._reset_dwell()
        self._history.clear()
