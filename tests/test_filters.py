"""One Euro Filter 测试：静止稳定、阶跃收敛、reset、dt<=0 行为。"""

from __future__ import annotations

from eyemouse.filters import OneEuroFilter, OneEuroFilter2D

DT = 1.0 / 60.0


def _feed(filter_, values, dt=DT):
    """按固定时间步长依次喂入数值，返回最后一次输出。"""
    t = 0.0
    out = 0.0
    for value in values:
        out = filter_(value, t)
        t += dt
    return out


def test_first_call_returns_input():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    assert filt(0.25, 0.0) == 0.25


def test_static_input_is_stable():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    out = _feed(filt, [0.5] * 300)
    assert abs(out - 0.5) < 1e-9


def test_step_input_converges():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    out = _feed(filt, [0.0] * 30 + [1.0] * 400)
    assert abs(out - 1.0) < 1e-3


def test_reset_restores_first_call_behavior():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    _feed(filt, [0.3] * 50)
    filt.reset()
    assert filt(0.9, 100.0) == 0.9


def test_dt_zero_returns_last_output():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    first = filt(0.2, 0.0)
    assert filt(0.8, 0.0) == first


def test_dt_negative_returns_last_output():
    filt = OneEuroFilter(1.0, 0.02, 1.0)
    first = filt(0.2, 5.0)
    assert filt(0.8, 4.0) == first
    assert filt.value == first


def test_filter2d_channels_independent():
    filt = OneEuroFilter2D(1.0, 0.02, 1.0)
    t = 0.0
    out = (0.0, 0.0)
    for _ in range(300):
        out = filt(1.0, -1.0, t)
        t += DT
    assert abs(out[0] - 1.0) < 1e-3
    assert abs(out[1] + 1.0) < 1e-3


def test_filter2d_reset():
    filt = OneEuroFilter2D(1.0, 0.02, 1.0)
    t = 0.0
    for _ in range(50):
        filt(1.0, 1.0, t)
        t += DT
    filt.reset()
    assert filt(0.0, 0.0, 200.0) == (0.0, 0.0)
