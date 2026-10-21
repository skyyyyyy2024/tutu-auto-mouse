"""平滑与稳定判定测试：特征层中值/EMA 平滑、抖动统计与注视锁定。"""

from __future__ import annotations

import numpy as np
import pytest

from eyemouse.filters import FeatureSmoother, GazeStabilityTracker


def test_median_window_rejects_single_spike():
    smoother = FeatureSmoother(median_window=3, ema_alpha=1.0)
    smoother(np.zeros(4))
    smoother(np.zeros(4))
    output = smoother(np.array([100.0, 0.0, 0.0, 0.0]))
    assert output[0] == pytest.approx(0.0)


def test_ema_smooths_a_step():
    smoother = FeatureSmoother(median_window=1, ema_alpha=0.5)
    smoother(np.zeros(2))
    output = smoother(np.array([1.0, 1.0]))
    assert output[0] == pytest.approx(0.5)
    assert output[1] == pytest.approx(0.5)


def test_smoother_reset_clears_state():
    smoother = FeatureSmoother()
    smoother(np.ones(3))
    assert smoother.value is not None
    smoother.reset()
    assert smoother.value is None


def test_stability_tracker_locks_when_still():
    tracker = GazeStabilityTracker(window=0.3, std_threshold_px=1.0, min_samples=3)
    for index in range(5):
        tracker.push(index * 0.05, 100.0, 200.0)
    assert tracker.locked() is True
    assert tracker.std() == pytest.approx(0.0)


def test_stability_tracker_unlocks_when_moving():
    tracker = GazeStabilityTracker(window=0.3, std_threshold_px=1.0, min_samples=3)
    for index in range(5):
        tracker.push(index * 0.05, 100.0 + index * 40.0, 200.0)
    assert tracker.locked() is False
    assert tracker.std() > 1.0


def test_stability_tracker_prunes_old_samples():
    tracker = GazeStabilityTracker(window=0.3, std_threshold_px=100.0, min_samples=2)
    tracker.push(0.0, 0.0, 0.0)
    tracker.push(0.05, 0.0, 0.0)
    tracker.push(1.0, 500.0, 500.0)
    assert tracker.count == 1
    assert tracker.std() == pytest.approx(0.0)


def test_stability_tracker_needs_min_samples():
    tracker = GazeStabilityTracker(window=0.3, std_threshold_px=100.0, min_samples=3)
    tracker.push(0.0, 10.0, 10.0)
    tracker.push(0.05, 10.0, 10.0)
    assert tracker.locked() is False
