from ..events import ShotCandidate, detect_shot_candidates, detect_touch_events
from ..tracking import FrameDetections


def make_frame(time_sec, ball, persons, diagonal=1000.0):
    return FrameDetections(time_sec=time_sec, ball_center=ball, person_centers=persons, frame_diagonal=diagonal)


def test_no_touch_event_when_ball_stays_with_same_owner():
    detections = [
        make_frame(0.0, (100.0, 100.0), [(100.0, 100.0), (800.0, 800.0)]),
        make_frame(0.5, (105.0, 100.0), [(105.0, 100.0), (800.0, 800.0)]),
        make_frame(1.0, (110.0, 100.0), [(110.0, 100.0), (800.0, 800.0)]),
    ]

    events = detect_touch_events(detections, min_owner_jump_ratio=0.15)

    assert events == []


def test_touch_event_detected_when_owner_position_jumps():
    detections = [
        make_frame(0.0, (100.0, 100.0), [(100.0, 100.0), (800.0, 800.0)]),
        make_frame(0.5, (105.0, 100.0), [(105.0, 100.0), (800.0, 800.0)]),
        # 공이 반대쪽 사람 근처로 크게 이동 (패스/탈취 후보)
        make_frame(1.0, (790.0, 790.0), [(105.0, 100.0), (790.0, 790.0)]),
    ]

    events = detect_touch_events(detections, min_owner_jump_ratio=0.15, min_gap_sec=0.1)

    assert len(events) == 1
    assert events[0].time_sec == 1.0


def test_touch_events_respect_min_gap_sec():
    detections = [
        make_frame(0.0, (0.0, 0.0), [(0.0, 0.0), (900.0, 900.0)]),
        make_frame(0.5, (900.0, 900.0), [(0.0, 0.0), (900.0, 900.0)]),
        make_frame(1.0, (0.0, 0.0), [(0.0, 0.0), (900.0, 900.0)]),
    ]

    events = detect_touch_events(detections, min_owner_jump_ratio=0.15, min_gap_sec=10.0)

    # 두 번째, 세 번째 프레임 모두 큰 점프지만 min_gap_sec 때문에 하나만 잡혀야 한다
    assert len(events) == 1


def test_frames_without_ball_or_persons_are_skipped():
    detections = [
        make_frame(0.0, None, []),
        make_frame(0.5, (100.0, 100.0), []),  # 사람이 없으면 owner를 정할 수 없음
        make_frame(1.0, (100.0, 100.0), [(100.0, 100.0)]),
    ]

    events = detect_touch_events(detections, min_owner_jump_ratio=0.01, min_gap_sec=0.0)

    assert events == []


def test_shot_candidate_carries_ball_position_near_spike_time():
    rng_positions = [
        (0.0, (0.0, 0.0)),
        (0.2, (1.0, 0.0)),
        (0.4, (2.0, 0.0)),
        (0.6, (3.0, 0.0)),
        (0.8, (4.0, 0.0)),
        (1.0, (5.0, 0.0)),
        (1.2, (100.0, 100.0)),  # 급가속
        (1.4, (101.0, 100.0)),
        (1.6, (102.0, 100.0)),
    ]
    detections = [make_frame(t, pos, [(500.0, 500.0)]) for t, pos in rng_positions]

    candidates = detect_shot_candidates(
        detections, sample_fps=5.0, window_sec=2.0, z_threshold=1.5, min_gap_sec=0.5
    )

    assert len(candidates) >= 1
    assert isinstance(candidates[0], ShotCandidate)
    closest = min(candidates, key=lambda c: abs(c.time_sec - 1.2))
    assert abs(closest.time_sec - 1.2) < 0.5
    assert closest.ball_position is not None
