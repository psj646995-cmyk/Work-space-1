import numpy as np
import pytest

from ..object_detection import (
    BallDetection,
    compute_ball_speed_series,
    detect_ball_speed_spikes_from_series,
)


def test_speed_computed_between_two_consecutive_detections():
    detections = [
        BallDetection(time_sec=0.0, ball_center=(100.0, 100.0), frame_diagonal=1000.0),
        BallDetection(time_sec=1.0, ball_center=(400.0, 500.0), frame_diagonal=1000.0),
    ]

    speeds, times = compute_ball_speed_series(detections)

    assert len(speeds) == 1
    assert speeds[0] == pytest.approx(0.5)  # 거리 500 / 대각선 1000 / 1초
    assert times[0] == 1.0


def test_lost_ball_breaks_the_speed_chain():
    detections = [
        BallDetection(time_sec=0.0, ball_center=(0.0, 0.0), frame_diagonal=1000.0),
        BallDetection(time_sec=0.1, ball_center=None, frame_diagonal=1000.0),
        BallDetection(time_sec=0.2, ball_center=(0.0, 0.0), frame_diagonal=1000.0),
        BallDetection(time_sec=0.3, ball_center=(100.0, 0.0), frame_diagonal=1000.0),
    ]

    speeds, times = compute_ball_speed_series(detections)

    # 공을 놓친 프레임(0.1s) 전후는 연결되지 않고, 0.2s -> 0.3s만 속도로 계산된다
    assert len(speeds) == 1
    assert times[0] == 0.3


def test_no_detections_returns_empty_series():
    detections = [
        BallDetection(time_sec=0.0, ball_center=None, frame_diagonal=1000.0),
        BallDetection(time_sec=0.1, ball_center=None, frame_diagonal=1000.0),
    ]

    speeds, times = compute_ball_speed_series(detections)

    assert len(speeds) == 0
    assert len(times) == 0


def _synthetic_ball_detections_with_speed_jump(
    jump_time_sec: float = 3.0,
    sample_fps: float = 10.0,
    duration_sec: float = 6.0,
    seed: int = 0,
) -> list[BallDetection]:
    rng = np.random.default_rng(seed)
    n = int(duration_sec * sample_fps)
    x, y = 0.0, 0.0
    detections = []
    jump_idx = int(jump_time_sec * sample_fps)
    for i in range(n):
        if i == jump_idx:
            x += 200.0
            y += 200.0
        else:
            x += rng.normal(0.0, 1.0)
            y += rng.normal(0.0, 1.0)
        detections.append(
            BallDetection(time_sec=i / sample_fps, ball_center=(x, y), frame_diagonal=1000.0)
        )
    return detections


def test_detects_injected_ball_speed_spike_near_expected_time():
    detections = _synthetic_ball_detections_with_speed_jump(jump_time_sec=3.0)

    speeds, times = compute_ball_speed_series(detections)
    events = detect_ball_speed_spikes_from_series(
        speeds, times, sample_fps=10.0, z_threshold=2.0, min_gap_sec=1.0
    )

    assert len(events) >= 1
    closest = min(events, key=lambda e: abs(e.time_sec - 3.0))
    assert abs(closest.time_sec - 3.0) < 0.5


def test_steady_ball_movement_produces_no_spikes():
    rng = np.random.default_rng(1)
    n = 60
    x, y = 0.0, 0.0
    detections = []
    for i in range(n):
        x += rng.normal(0.0, 1.0)
        y += rng.normal(0.0, 1.0)
        detections.append(
            BallDetection(time_sec=i / 10.0, ball_center=(x, y), frame_diagonal=1000.0)
        )

    speeds, times = compute_ball_speed_series(detections)
    events = detect_ball_speed_spikes_from_series(
        speeds, times, sample_fps=10.0, z_threshold=4.0, min_gap_sec=1.0
    )

    assert events == []
