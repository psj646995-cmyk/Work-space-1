from ..highlight_extractor import merge_events
from ..spike_event import SpikeEvent


def test_corroborated_signals_get_confidence_boost_over_either_alone():
    audio_events = [SpikeEvent(time_sec=30.0, score=3.0)]
    motion_events = [SpikeEvent(time_sec=31.0, score=2.5)]

    candidates = merge_events(
        [("audio", audio_events), ("motion", motion_events)], corroboration_window_sec=4.0
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert set(candidate.sources) == {"audio", "motion"}
    assert candidate.confidence > max(audio_events[0].score, motion_events[0].score)


def test_uncorroborated_signals_kept_separate_with_reduced_confidence():
    audio_events = [SpikeEvent(time_sec=10.0, score=3.0)]
    motion_events = [SpikeEvent(time_sec=50.0, score=3.0)]

    candidates = merge_events(
        [("audio", audio_events), ("motion", motion_events)], corroboration_window_sec=4.0
    )

    assert len(candidates) == 2
    for candidate in candidates:
        assert len(candidate.sources) == 1
        assert candidate.confidence < 3.0


def test_candidates_sorted_by_time():
    audio_events = [SpikeEvent(time_sec=50.0, score=2.0), SpikeEvent(time_sec=5.0, score=2.0)]

    candidates = merge_events([("audio", audio_events)])

    assert [c.time_sec for c in candidates] == [5.0, 50.0]


def test_each_motion_event_matched_to_at_most_one_audio_event():
    audio_events = [SpikeEvent(time_sec=30.0, score=3.0), SpikeEvent(time_sec=30.5, score=2.0)]
    motion_events = [SpikeEvent(time_sec=30.2, score=2.5)]

    candidates = merge_events(
        [("audio", audio_events), ("motion", motion_events)], corroboration_window_sec=4.0
    )

    corroborated = [c for c in candidates if len(c.sources) == 2]
    assert len(corroborated) == 1


def test_three_signals_agreeing_get_bigger_boost_than_two():
    two_signal_candidates = merge_events(
        [
            ("audio", [SpikeEvent(time_sec=10.0, score=2.0)]),
            ("motion", [SpikeEvent(time_sec=10.2, score=2.0)]),
        ],
        corroboration_window_sec=4.0,
    )
    three_signal_candidates = merge_events(
        [
            ("audio", [SpikeEvent(time_sec=10.0, score=2.0)]),
            ("motion", [SpikeEvent(time_sec=10.2, score=2.0)]),
            ("ball_speed", [SpikeEvent(time_sec=10.1, score=2.0)]),
        ],
        corroboration_window_sec=4.0,
    )

    assert len(two_signal_candidates) == 1
    assert len(three_signal_candidates) == 1
    assert three_signal_candidates[0].confidence > two_signal_candidates[0].confidence
    assert set(three_signal_candidates[0].sources) == {"audio", "motion", "ball_speed"}


def test_events_from_same_source_never_grouped_together():
    audio_events = [
        SpikeEvent(time_sec=10.0, score=3.0),
        SpikeEvent(time_sec=10.1, score=2.9),
    ]

    candidates = merge_events([("audio", audio_events)], corroboration_window_sec=4.0)

    assert len(candidates) == 2
    for candidate in candidates:
        assert candidate.sources == ["audio"]
