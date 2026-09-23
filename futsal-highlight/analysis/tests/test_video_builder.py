from ..video_builder import build_combined_video


def test_returns_none_when_no_events(tmp_path):
    result = build_combined_video(
        video_path="unused.mp4",
        touch_events=[],
        shot_events=[],
        output_dir=str(tmp_path),
    )

    assert result is None
