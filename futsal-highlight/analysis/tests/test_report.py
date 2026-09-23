import os

from ..report import generate_report


def test_report_generated_with_no_events(tmp_path):
    output_dir = str(tmp_path / "out")

    report_path = generate_report(
        video_path="unused.mp4",
        touch_events=[],
        shot_events=[],
        output_dir=output_dir,
    )

    assert os.path.isfile(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert "탐지된 이벤트가 없습니다" in content
