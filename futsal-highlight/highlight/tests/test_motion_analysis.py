import numpy as np

from ..motion_analysis import detect_motion_spikes_from_series


def _synthetic_motion_series(
    duration_sec: float = 60.0,
    sample_fps: float = 5.0,
    spike_time_sec: float = 30.0,
    spike_width_samples: int = 4,
    baseline_std: float = 0.05,
    spike_amount: float = 2.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = int(duration_sec * sample_fps)
    times = np.arange(n) / sample_fps
    magnitudes = rng.normal(1.0, baseline_std, n)

    spike_idx = int(spike_time_sec * sample_fps)
    lo = max(0, spike_idx - spike_width_samples // 2)
    hi = min(n, spike_idx + spike_width_samples // 2)
    magnitudes[lo:hi] += spike_amount
    return magnitudes, times


def test_detects_injected_motion_spike_near_expected_time():
    magnitudes, times = _synthetic_motion_series(spike_time_sec=30.0)

    events = detect_motion_spikes_from_series(
        magnitudes, times, sample_fps=5.0, z_threshold=2.0, min_gap_sec=5.0
    )

    assert len(events) >= 1
    closest = min(events, key=lambda e: abs(e.time_sec - 30.0))
    assert abs(closest.time_sec - 30.0) < 2.0


def test_stable_motion_produces_no_spikes():
    rng = np.random.default_rng(2)
    n = 300
    times = np.arange(n) / 5.0
    stable_magnitudes = rng.normal(1.0, 0.02, n)

    events = detect_motion_spikes_from_series(
        stable_magnitudes, times, sample_fps=5.0, z_threshold=3.0, min_gap_sec=5.0
    )

    assert events == []


def test_two_distinct_spikes_both_detected():
    magnitudes, times = _synthetic_motion_series(spike_time_sec=10.0, seed=3)
    # 두 번째 스파이크를 추가로 주입
    second_idx = int(40.0 * 5.0)
    magnitudes[second_idx - 2 : second_idx + 2] += 2.0

    events = detect_motion_spikes_from_series(
        magnitudes, times, sample_fps=5.0, z_threshold=2.0, min_gap_sec=5.0
    )

    detected_times = sorted(e.time_sec for e in events)
    assert len(detected_times) == 2
    assert abs(detected_times[0] - 10.0) < 2.0
    assert abs(detected_times[1] - 40.0) < 2.0
