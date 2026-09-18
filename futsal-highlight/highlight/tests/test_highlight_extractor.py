from ..highlight_extractor import merge_events
from ..spike_event import SpikeEvent


def test_corroborated_signals_get_confidence_boost_over_either_alone():
    audio_events = [SpikeEvent(time_sec=30.0, score=3.0)]
    motion_events = [SpikeEvent(time_sec=31.0, score=2.5)]

    candidates = merge_events(audio_events, motion_events, corroboration_window_sec=4.0)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert set(candidate.sources) == {"audio", "motion"}
    assert candidate.confidence > max(audio_events[0].score, motion_events[0].score)


def test_uncorroborated_signals_kept_separate_with_reduced_confidence():
    audio_events = [SpikeEvent(time_sec=10.0, score=3.0)]
    motion_events = [SpikeEvent(time_sec=50.0, score=3.0)]

    candidates = merge_events(audio_events, motion_events, corroboration_window_sec=4.0)

    assert len(candidates) == 2
    for candidate in candidates:
        assert len(candidate.sources) == 1
        assert candidate.confidence < 3.0


def test_candidates_sorted_by_time():
    audio_events = [SpikeEvent(time_sec=50.0, score=2.0), SpikeEvent(time_sec=5.0, score=2.0)]
    motion_events = []

    candidates = merge_events(audio_events, motion_events)

    assert [c.time_sec for c in candidates] == [5.0, 50.0]


def test_each_motion_event_matched_to_at_most_one_audio_event():
    audio_events = [SpikeEvent(time_sec=30.0, score=3.0), SpikeEvent(time_sec=30.5, score=2.0)]
    motion_events = [SpikeEvent(time_sec=30.2, score=2.5)]

    candidates = merge_events(audio_events, motion_events, corroboration_window_sec=4.0)

    corroborated = [c for c in candidates if len(c.sources) == 2]
    assert len(corroborated) == 1
