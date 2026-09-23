"""터치/슈팅 후보들을 클립으로 잘라 하나의 영상으로 이어붙인다."""
import os

from highlight.video_utils import concat_clips, extract_clip

from .events import ShotCandidate, TouchEvent


def build_combined_video(
    video_path: str,
    touch_events: list[TouchEvent],
    shot_events: list[ShotCandidate],
    output_dir: str,
    pre_seconds: float = 4.0,
    post_seconds: float = 4.0,
    combined_name: str = "analysis_highlights.mp4",
) -> str | None:
    """탐지된 이벤트 시점마다 짧은 클립을 잘라 시간 순으로 이어붙인다.

    이벤트가 하나도 없으면 None을 반환한다. 전체 길이는 이벤트 개수 x
    (pre_seconds+post_seconds)로 자연스럽게 정해진다 — 감지된 장면이
    많을수록 결과 영상도 길어진다.
    """
    all_times = sorted(
        [e.time_sec for e in touch_events] + [e.time_sec for e in shot_events]
    )
    if not all_times:
        return None

    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    clip_paths: list[str] = []
    for i, time_sec in enumerate(all_times, start=1):
        clip_path = os.path.join(clips_dir, f"event_{i:03d}_{int(time_sec)}s.mp4")
        extract_clip(video_path, time_sec, pre_seconds, post_seconds, clip_path)
        clip_paths.append(clip_path)

    combined_path = os.path.join(output_dir, combined_name)
    concat_clips(clip_paths, combined_path)
    return combined_path
