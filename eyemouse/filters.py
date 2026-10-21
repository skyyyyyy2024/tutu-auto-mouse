"""One Euro Filter：平滑视线坐标，兼顾低延迟与抖动抑制。"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional, Sequence, Tuple

import numpy as np


class OneEuroFilter:
    """标准 One Euro Filter（Casiez et al. 2012），单通道实现。

    时间戳由调用者传入，便于单元测试；dt<=0 时返回上一次输出。
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev: Optional[float] = None
        self._dx_prev: float = 0.0
        self._t_prev: Optional[float] = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        """由截止频率与时间步长计算指数平滑系数。"""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        value = float(x)
        timestamp = float(t)
        if self._t_prev is None:
            self._t_prev = timestamp
            self._x_prev = value
            self._dx_prev = 0.0
            return value
        dt = timestamp - self._t_prev
        if dt <= 0.0:
            return float(self._x_prev)
        dx = (value - self._x_prev) / dt
        alpha_d = self._alpha(self.d_cutoff, dt)
        dx_hat = alpha_d * dx + (1.0 - alpha_d) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        alpha = self._alpha(cutoff, dt)
        x_hat = alpha * value + (1.0 - alpha) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = timestamp
        return x_hat

    def reset(self) -> None:
        """清空内部状态，使下一次调用等同于首次调用。"""
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    @property
    def value(self) -> Optional[float]:
        """最近一次的输出值，尚未调用过时为 None。"""
        return self._x_prev


class OneEuroFilter2D:
    """对 (x, y) 两个通道分别做 One Euro 滤波。"""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0) -> None:
        self.x_filter = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.y_filter = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def __call__(self, x: float, y: float, t: float) -> Tuple[float, float]:
        return self.x_filter(x, t), self.y_filter(y, t)

    def reset(self) -> None:
        """同时重置两个通道。"""
        self.x_filter.reset()
        self.y_filter.reset()

class FeatureSmoother:
    """特征层平滑：先做小窗口中值，再做 EMA。

    ``median_window<=1`` 关闭中值级，``ema_alpha>=1`` 关闭 EMA 级，
    因此可单独或同时关闭；输出维度与输入一致。
    """

    def __init__(self, median_window: int = 3, ema_alpha: float = 0.5) -> None:
        self.median_window = max(int(median_window), 1)
        self.ema_alpha = float(min(max(ema_alpha, 1e-3), 1.0))
        self._window: Deque[np.ndarray] = deque(maxlen=self.median_window)
        self._ema: Optional[np.ndarray] = None

    def __call__(self, features: Sequence[float]) -> np.ndarray:
        vector = np.asarray(features, dtype=np.float64)
        self._window.append(vector.copy())
        if self.median_window > 1 and len(self._window) > 1:
            stacked = np.vstack(self._window)
            smoothed = np.median(stacked, axis=0)
        else:
            smoothed = vector
        if self._ema is None:
            self._ema = smoothed.copy()
        else:
            self._ema = self.ema_alpha * smoothed + (1.0 - self.ema_alpha) * self._ema
        return self._ema.copy()

    def reset(self) -> None:
        """清空窗口与 EMA 状态。"""
        self._window.clear()
        self._ema = None

    @property
    def value(self) -> Optional[np.ndarray]:
        """最近一次输出（尚未调用过时为 None）。"""
        return None if self._ema is None else self._ema.copy()


class GazeStabilityTracker:
    """统计最近 ``window`` 秒的注视位置抖动，并判定是否已稳定（可锁定光标）。

    ``std()`` 返回水平/垂直标准差的欧氏合量（像素）；``locked()`` 在样本足够
    且抖动小于 ``std_threshold_px`` 时为真。
    """

    def __init__(
        self,
        window: float = 0.3,
        std_threshold_px: float = 1.5,
        min_samples: int = 3,
    ) -> None:
        self.window = float(window)
        self.std_threshold_px = float(std_threshold_px)
        self.min_samples = max(int(min_samples), 2)
        self._samples: Deque[Tuple[float, float, float]] = deque()

    def _prune(self, now: float) -> None:
        while self._samples and now - self._samples[0][0] > self.window:
            self._samples.popleft()

    def push(self, t: float, x: float, y: float) -> None:
        """记录一个采样点并淘汰过期样本。"""
        self._samples.append((float(t), float(x), float(y)))
        self._prune(float(t))

    def reset(self) -> None:
        """清空历史样本。"""
        self._samples.clear()

    @property
    def count(self) -> int:
        """当前窗口内的样本数。"""
        return len(self._samples)

    def std(self) -> float:
        """当前窗口内位置的欧氏抖动（像素）；样本不足返回 0.0。"""
        if len(self._samples) < 2:
            return 0.0
        values = np.array([[s[1], s[2]] for s in self._samples], dtype=np.float64)
        variance = float(np.var(values[:, 0]) + np.var(values[:, 1]))
        if variance <= 0.0:
            return 0.0
        return float(math.sqrt(variance))

    def locked(self) -> bool:
        """样本足够且抖动低于阈值时判定为稳定。"""
        if len(self._samples) < self.min_samples:
            return False
        return self.std() <= self.std_threshold_px
