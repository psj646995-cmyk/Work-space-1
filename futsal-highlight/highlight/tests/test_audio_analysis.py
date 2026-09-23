import numpy as np

from ..audio_analysis import detect_audio_spikes


def _synthetic_audio_with_spike(
    duration_sec: float = 60.0,
    sr: int = 8000,
    spike_time_sec: float = 30.0,
    spike_duration_sec: float = 1.0,
    baseline_amplitude: float = 0.01,
    spike_amplitude: float = 0.3,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_samples = int(duration_sec * sr)
    audio = rng.normal(0.0, baseline_amplitude, n_samples)

    spike_start = int(spike_time_sec * sr)
    spike_end = int((spike_time_sec + spike_duration_sec) * sr)
    audio[spike_start:spike_end] += rng.normal(0.0, spike_amplitude, spike_end - spike_start)
    return audio


def test_detects_injected_loudness_spike_near_expected_time():
    sr = 8000
    audio = _synthetic_audio_with_spike(spike_time_sec=30.0, sr=sr)

    events = detect_audio_spikes(audio, sr, z_threshold=2.0, min_gap_sec=5.0)

    assert len(events) >= 1
    closest = min(events, key=lambda e: abs(e.time_sec - 30.0))
    assert abs(closest.time_sec - 30.0) < 2.0


def test_quiet_uniform_audio_produces_no_spikes():
    sr = 8000
    rng = np.random.default_rng(1)
    quiet_audio = rng.normal(0.0, 0.01, int(30 * sr))

    events = detect_audio_spikes(quiet_audio, sr, z_threshold=3.0, min_gap_sec=5.0)

    assert events == []


def test_min_gap_sec_suppresses_duplicate_detections_of_same_event():
    sr = 8000
    audio = _synthetic_audio_with_spike(
        spike_time_sec=20.0, spike_duration_sec=2.0, sr=sr
    )

    events = detect_audio_spikes(audio, sr, z_threshold=2.0, min_gap_sec=10.0)

    # 하나의 긴 스파이크 구간이 여러 개의 후보로 쪼개지지 않아야 한다
    assert len(events) == 1
