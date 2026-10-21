"""手部手势判定：张开手掌检测与滞回状态机（纯逻辑，便于合成关键点测试）。

MediaPipe Hands 关键点索引：

- 0 手腕；1–4 拇指（CMC/MCP/IP/TIP）；5–8 食指；9–12 中指；13–16 无名指；17–20 小指。

判定全部基于距离比较，因此对整手旋转（90°/180°）保持不变。
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

WRIST = 0
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# (PIP, TIP) 四指：食指/中指/无名指/小指
FINGER_JOINTS = ((INDEX_PIP, INDEX_TIP), (MIDDLE_PIP, MIDDLE_TIP), (RING_PIP, RING_TIP), (PINKY_PIP, PINKY_TIP))
FINGERTIPS = (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

DEFAULT_OPEN_RATIO = 1.1
DEFAULT_FINGER_SPREAD_MIN = 0.25


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))


def normalize_points(points: Sequence[Sequence[float]]) -> Optional[np.ndarray]:
    """把输入转成 (21, 2) 的有限值数组；形状/数值不合法时返回 None。"""
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape != (21, 2):
        return None
    if not np.all(np.isfinite(array)):
        return None
    return array


def is_open_palm(
    points: Sequence[Sequence[float]],
    open_ratio: float = DEFAULT_OPEN_RATIO,
    finger_spread_min: float = DEFAULT_FINGER_SPREAD_MIN,
    require_thumb: bool = True,
) -> bool:
    """判断是否为「张开手掌」：四指伸直 +（可选）拇指张开 + 指尖不并拢。

    ``require_thumb=False`` 时忽略拇指条件，手掌开合不再被大拇指牵制。
    """
    array = normalize_points(points)
    if array is None:
        return False
    ratio = float(open_ratio)
    wrist = array[WRIST]
    palm_width = _distance(array[INDEX_MCP], array[PINKY_MCP])
    if not math.isfinite(palm_width) or palm_width <= 1e-6:
        return False

    for pip, tip in FINGER_JOINTS:
        if _distance(array[tip], wrist) <= _distance(array[pip], wrist) * ratio:
            return False

    if require_thumb:
        thumb_reference = array[PINKY_MCP]
        if (
            _distance(array[THUMB_TIP], thumb_reference)
            <= _distance(array[THUMB_IP], thumb_reference) * ratio
        ):
            return False

    spread = min(
        _distance(array[FINGERTIPS[i]], array[FINGERTIPS[i + 1]]) for i in range(len(FINGERTIPS) - 1)
    )
    if spread / palm_width < float(finger_spread_min):
        return False
    return True


class OpenPalmGate:
    """张开手掌的滞回状态机：连续满足才进入，连续不满足才退出，手丢失超时立即退出。"""

    def __init__(self, enter_frames: int = 5, exit_frames: int = 5, lost_timeout: float = 0.3) -> None:
        self.enter_frames = max(int(enter_frames), 1)
        self.exit_frames = max(int(exit_frames), 1)
        self.lost_timeout = max(float(lost_timeout), 0.0)
        self.reset()

    def reset(self) -> None:
        """清空全部状态，回到 CLOSED。"""
        self._open = False
        self._enter_streak = 0
        self._exit_streak = 0
        self._last_seen: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """当前 gate 是否打开。"""
        return self._open

    def update(self, now: float, hand_present: bool, palm_open: bool) -> bool:
        """推进一帧并返回 gate 是否打开。"""
        timestamp = float(now)
        if not hand_present:
            self._enter_streak = 0
            self._exit_streak = 0
            if self._open and (self._last_seen is None or timestamp - self._last_seen > self.lost_timeout):
                self._open = False
            return self._open

        self._last_seen = timestamp
        if palm_open:
            self._enter_streak += 1
            self._exit_streak = 0
        else:
            self._exit_streak += 1
            self._enter_streak = 0

        if not self._open and self._enter_streak >= self.enter_frames:
            self._open = True
        elif self._open and self._exit_streak >= self.exit_frames:
            self._open = False
        return self._open