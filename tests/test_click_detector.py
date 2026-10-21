"""连续眨眼检测与注视停留测试（合成 EAR 序列，显式时间戳，不使用 sleep）。"""

from __future__ import annotations

import pytest

from eyemouse.click_detector import ClickDetector
from eyemouse.config import ClickConfig, config_from_dict

DT = 1.0 / 30.0
BASELINE = 0.30
OPEN = 0.30
CLOSED = 0.05


def make_frames(segments, start: float = 0.0):
    """把 (EAR, 时长秒) 序列展开为逐帧 (t, ear) 列表，帧间隔 DT。"""
    frames = []
    t = start
    for ear, duration in segments:
        count = max(1, int(round(duration / DT)))
        for _ in range(count):
            frames.append((t, float(ear)))
            t += DT
    return frames


def blink_frames(
    count: int,
    gap: float = 0.2,
    blink: float = 0.15,
    start: float = 0.0,
    tail: float = 0.8,
):
    """构造 count 次连续眨眼，前导 0.1s 睁眼、末尾 0.8s 睁眼用于结算。"""
    segments = [(OPEN, 0.1)]
    for index in range(count):
        segments.append((CLOSED, blink))
        segments.append((OPEN, tail if index == count - 1 else gap))
    return make_frames(segments, start=start)


def drive(detector, frames, gaze=(100.0, 100.0), baseline=BASELINE, push=True, face_ok=True):
    """依次喂帧，返回触发的事件列表。"""
    events = []
    for t, ear in frames:
        if push:
            detector.push_position(t, gaze[0], gaze[1])
        event = detector.update(t, ear, baseline, gaze, face_ok)
        if event is not None:
            events.append(event)
    return events


def default_click_config() -> ClickConfig:
    return config_from_dict({}).click


def test_single_blink_triggers_nothing():
    detector = ClickDetector(default_click_config())
    assert drive(detector, blink_frames(1)) == []


@pytest.mark.parametrize(
    "count,action",
    [(2, "left_click"), (3, "right_click"), (4, "double_click"), (5, "toggle_drag")],
)
def test_blink_counts_map_to_actions(count, action):
    detector = ClickDetector(default_click_config())
    events = drive(detector, blink_frames(count))
    assert len(events) == 1
    assert events[0].action == action
    assert events[0].blink_count == count


def test_large_gap_splits_into_two_sequences():
    detector = ClickDetector(default_click_config())
    assert drive(detector, blink_frames(2, gap=0.8)) == []


def test_long_close_voids_sequence():
    detector = ClickDetector(default_click_config())
    frames = make_frames(
        [(OPEN, 0.1), (CLOSED, 0.15), (OPEN, 0.2), (CLOSED, 0.9), (OPEN, 0.8)]
    )
    assert drive(detector, frames) == []


def test_noise_blink_is_ignored():
    detector = ClickDetector(default_click_config())
    frames = make_frames(
        [
            (CLOSED, 0.02),
            (OPEN, 0.033),
            (CLOSED, 0.15),
            (OPEN, 0.2),
            (CLOSED, 0.15),
            (OPEN, 0.8),
        ]
    )
    events = drive(detector, frames)
    assert len(events) == 1
    assert events[0].blink_count == 2
    assert events[0].action == "left_click"


def test_too_many_blinks_triggers_nothing():
    detector = ClickDetector(default_click_config())
    assert drive(detector, blink_frames(7)) == []


def test_cooldown_drops_second_group_but_allows_later():
    cfg = default_click_config()
    cfg.cooldown = 2.0
    detector = ClickDetector(cfg)
    segments = [(OPEN, 0.1)]
    for _ in range(3):
        segments += [(CLOSED, 0.15), (OPEN, 0.2), (CLOSED, 0.15), (OPEN, 0.8)]
    events = drive(detector, make_frames(segments))
    assert len(events) == 2
    assert all(event.action == "left_click" for event in events)


def test_snapshot_uses_position_before_first_close():
    cfg = default_click_config()
    detector = ClickDetector(cfg)
    history = []
    t = 0.0
    while t < 1.0:
        detector.push_position(t, t * 100.0, 50.0)
        history.append((t, t * 100.0, 50.0))
        t += DT
    start = t
    segments = [(OPEN, 0.05)]
    for _ in range(5):
        segments += [(CLOSED, 0.15), (OPEN, 0.2)]
    segments += [(OPEN, 0.8)]
    frames = make_frames(segments, start=start)
    first_closed_t = next(ft for ft, ear in frames if ear == CLOSED)
    expected_x = None
    for hist_t, hist_x, _ in history:
        if hist_t <= first_closed_t - cfg.freeze_lookback:
            expected_x = hist_x
    events = drive(detector, frames, push=False)
    assert len(events) == 1
    assert events[0].blink_count == 5
    assert abs(events[0].position[0] - expected_x) < 1e-9
    assert abs(events[0].position[1] - 50.0) < 1e-9


def test_snapshot_falls_back_to_earliest_history():
    cfg = default_click_config()
    detector = ClickDetector(cfg)
    for index in range(3):
        detector.push_position(index * DT, float(index), 7.0)
    frames = make_frames(
        [(OPEN, 0.05), (CLOSED, 0.15), (OPEN, 0.2), (CLOSED, 0.15), (OPEN, 0.8)],
        start=0.1,
    )
    events = drive(detector, frames, push=False)
    assert events[0].position == (0.0, 7.0)


def test_snapshot_uses_gaze_when_history_empty():
    detector = ClickDetector(default_click_config())
    events = drive(detector, blink_frames(2), gaze=(11.0, 22.0), push=False)
    assert events[0].position == (11.0, 22.0)


def test_face_lost_clears_sequence_and_snapshot():
    detector = ClickDetector(default_click_config())
    frames = blink_frames(1, tail=0.1)
    drive(detector, frames, push=False)
    assert detector.pending_count() == 1
    last_t = frames[-1][0]
    detector.update(last_t + DT, OPEN, BASELINE, (1.0, 1.0), False)
    assert detector.pending_count() == 0
    assert not detector.in_sequence()
    new_frames = make_frames(
        [(OPEN, 0.05), (CLOSED, 0.15), (OPEN, 0.2), (CLOSED, 0.15), (OPEN, 0.8)],
        start=last_t + 2 * DT,
    )
    events = drive(detector, new_frames, gaze=(5.0, 6.0), push=False)
    assert len(events) == 1
    assert events[0].blink_count == 2
    assert events[0].position == (5.0, 6.0)


def test_hysteresis_between_thresholds_keeps_state():
    detector = ClickDetector(default_click_config())
    middle = (0.60 + 0.75) / 2 * BASELINE
    frames = make_frames([(OPEN, 0.05), (CLOSED, 0.02)] + [(middle, 0.02)] * 5 + [(OPEN, 0.8)])
    events = drive(detector, frames)
    assert events == []


def test_actions_mapping_is_configurable():
    cfg = config_from_dict(
        {
            "click": {
                "actions": {
                    1: "none",
                    2: "right_click",
                    3: "none",
                    4: "none",
                    5: "none",
                    6: "none",
                }
            }
        }
    ).click
    detector = ClickDetector(cfg)
    events = drive(detector, blink_frames(2))
    assert len(events) == 1
    assert events[0].action == "right_click"


def test_dwell_click_triggers_once_until_leaving_radius():
    detector = ClickDetector(default_click_config())
    detector.set_mode("dwell")
    frames = make_frames([(OPEN, 1.3)], start=0.0)
    events = drive(detector, frames, gaze=(500.0, 500.0), push=False)
    assert len(events) == 1
    assert events[0].action == "left_click"
    assert events[0].blink_count == 0
    more = make_frames([(OPEN, 2.0)], start=frames[-1][0] + DT)
    assert drive(detector, more, gaze=(500.0, 500.0), push=False) == []
    away = make_frames([(OPEN, 0.1)], start=more[-1][0] + DT)
    drive(detector, away, gaze=(700.0, 500.0), push=False)
    again = make_frames([(OPEN, 1.3)], start=away[-1][0] + DT)
    events2 = drive(detector, again, gaze=(700.0, 500.0), push=False)
    assert len(events2) == 1


def test_dwell_face_lost_resets_timer():
    detector = ClickDetector(default_click_config())
    detector.set_mode("dwell")
    frames = make_frames([(OPEN, 1.0)], start=0.0)
    for t, ear in frames:
        detector.update(t, ear, BASELINE, (300.0, 300.0), True)
    assert detector.dwell_progress() > 0.5
    last_t = frames[-1][0]
    detector.update(last_t + DT, OPEN, BASELINE, (300.0, 300.0), False)
    assert detector.dwell_progress() == 0.0
    rest = make_frames([(OPEN, 1.0)], start=last_t + 2 * DT)
    assert drive(detector, rest, gaze=(300.0, 300.0), push=False) == []


def test_mode_none_triggers_nothing():
    detector = ClickDetector(default_click_config())
    detector.set_mode("none")
    assert drive(detector, blink_frames(3)) == []
    assert drive(detector, make_frames([(OPEN, 2.0)]), push=False) == []


def test_mode_dwell_ignores_blinks():
    detector = ClickDetector(default_click_config())
    detector.set_mode("dwell")
    events = []
    for index, (t, ear) in enumerate(blink_frames(3)):
        gaze = (float(index * 100), 0.0)
        event = detector.update(t, ear, BASELINE, gaze, True)
        if event is not None:
            events.append(event)
    assert events == []


def test_sequence_status_accessors():
    cfg = default_click_config()
    detector = ClickDetector(cfg)
    detector.push_position(0.0, 0.0, 0.0)
    detector.update(0.0, OPEN, BASELINE, (0.0, 0.0), True)
    assert not detector.in_sequence()
    detector.update(DT, CLOSED, BASELINE, (0.0, 0.0), True)
    assert detector.in_sequence()
    assert detector.pending_count() == 0
    t = 2 * DT
    for _ in range(4):
        detector.update(t, CLOSED, BASELINE, (0.0, 0.0), True)
        t += DT
    detector.update(t, OPEN, BASELINE, (0.0, 0.0), True)
    assert detector.pending_count() == 1
    assert detector.in_sequence()
    remaining = detector.settle_remaining()
    assert 0.0 <= remaining <= cfg.group_gap


def test_reset_clears_everything():
    detector = ClickDetector(default_click_config())
    drive(detector, blink_frames(2, tail=0.1))
    detector.reset()
    assert not detector.in_sequence()
    assert detector.pending_count() == 0
    assert detector.settle_remaining() == 0.0
    assert detector.dwell_progress() == 0.0


def test_set_mode_rejects_invalid_value():
    detector = ClickDetector(default_click_config())
    with pytest.raises(ValueError):
        detector.set_mode("teleport")
