"""오디오 스파이크 + 모션 스파이크를 결합해 골 장면 후보를 찾고,
ffmpeg로 하이라이트 클립을 잘라내는 CLI 도구.

사용법:
    python -m highlight.highlight_extractor 경기영상.mp4 --output-dir out/

주의: 이 도구는 딥러닝 기반 골 인식이 아니라 "골이 나면 관중 소리와
움직임이 함께 튄다"는 가정에 기반한 신호 처리 휴리스틱이다. 완벽한
정확도를 기대하면 안 되며, 오탐/누락이 있을 수 있다. 실제 영상으로
--audio-z-threshold / --motion-z-threshold / --min-gap-sec 값을
튜닝해가며 써야 한다.
"""
import argparse
import os
import subprocess
from dataclasses import dataclass, field

from .audio_analysis import detect_audio_spikes, load_audio
from .motion_analysis import detect_motion_spikes
from .spike_event import SpikeEvent

# 단일 신호(오디오 또는 모션)만 잡힌 후보는 교차 검증된 후보보다 신뢰도를 낮춘다.
SINGLE_SIGNAL_CONFIDENCE_SCALE = 0.55
CORROBORATION_BONUS = 1.0


@dataclass
class HighlightCandidate:
    time_sec: float
    confidence: float
    sources: list[str] = field(default_factory=list)


def merge_events(
    audio_events: list[SpikeEvent],
    motion_events: list[SpikeEvent],
    corroboration_window_sec: float = 4.0,
) -> list[HighlightCandidate]:
    """오디오/모션 후보를 시간대로 대조해, 두 신호가 겹치면 신뢰도를 높인다."""
    candidates: list[HighlightCandidate] = []
    used_motion_idx: set[int] = set()

    for audio_event in audio_events:
        matches = [
            (i, m)
            for i, m in enumerate(motion_events)
            if i not in used_motion_idx
            and abs(m.time_sec - audio_event.time_sec) <= corroboration_window_sec
        ]
        if matches:
            best_idx, best_motion = max(matches, key=lambda pair: pair[1].score)
            used_motion_idx.add(best_idx)
            candidates.append(
                HighlightCandidate(
                    time_sec=(audio_event.time_sec + best_motion.time_sec) / 2,
                    confidence=audio_event.score + best_motion.score + CORROBORATION_BONUS,
                    sources=["audio", "motion"],
                )
            )
        else:
            candidates.append(
                HighlightCandidate(
                    time_sec=audio_event.time_sec,
                    confidence=audio_event.score * SINGLE_SIGNAL_CONFIDENCE_SCALE,
                    sources=["audio"],
                )
            )

    for i, motion_event in enumerate(motion_events):
        if i not in used_motion_idx:
            candidates.append(
                HighlightCandidate(
                    time_sec=motion_event.time_sec,
                    confidence=motion_event.score * SINGLE_SIGNAL_CONFIDENCE_SCALE,
                    sources=["motion"],
                )
            )

    candidates.sort(key=lambda c: c.time_sec)
    return candidates


def extract_clip(
    video_path: str,
    center_time_sec: float,
    pre_seconds: float,
    post_seconds: float,
    output_path: str,
) -> None:
    start = max(0.0, center_time_sec - pre_seconds)
    duration = pre_seconds + post_seconds
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.2f}",
        "-i",
        video_path,
        "-t",
        f"{duration:.2f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        output_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="오디오+모션 스파이크 기반으로 골 장면 후보를 찾아 클립으로 추출합니다."
    )
    parser.add_argument("video", help="입력 영상 파일 경로")
    parser.add_argument("--output-dir", default="highlights_out", help="클립 저장 폴더")
    parser.add_argument("--pre-seconds", type=float, default=8.0, help="후보 시점 이전 몇 초부터 자를지")
    parser.add_argument("--post-seconds", type=float, default=5.0, help="후보 시점 이후 몇 초까지 자를지")
    parser.add_argument("--audio-z-threshold", type=float, default=2.0)
    parser.add_argument("--motion-z-threshold", type=float, default=2.0)
    parser.add_argument("--min-gap-sec", type=float, default=10.0, help="같은 장면이 중복 검출되지 않도록 하는 최소 간격")
    parser.add_argument("--corroboration-window-sec", type=float, default=4.0)
    parser.add_argument("--min-confidence", type=float, default=0.0, help="이 값 미만인 후보는 버림")
    parser.add_argument("--max-clips", type=int, default=None, help="최대 몇 개 클립까지 추출할지")
    return parser


def run(args: argparse.Namespace) -> list[HighlightCandidate]:
    print("[1/3] 오디오 트랙 분석 중...")
    y, sr = load_audio(args.video)
    audio_events = detect_audio_spikes(
        y, sr, z_threshold=args.audio_z_threshold, min_gap_sec=args.min_gap_sec
    )
    print(f"      오디오 후보 {len(audio_events)}개 발견")

    print("[2/3] 영상 모션 분석 중 (시간이 걸릴 수 있습니다)...")
    motion_events = detect_motion_spikes(
        args.video, z_threshold=args.motion_z_threshold, min_gap_sec=args.min_gap_sec
    )
    print(f"      모션 후보 {len(motion_events)}개 발견")

    candidates = merge_events(audio_events, motion_events, args.corroboration_window_sec)
    candidates = [c for c in candidates if c.confidence >= args.min_confidence]
    candidates.sort(key=lambda c: -c.confidence)
    if args.max_clips is not None:
        candidates = candidates[: args.max_clips]
    candidates.sort(key=lambda c: c.time_sec)

    if not candidates:
        print("하이라이트 후보를 찾지 못했습니다. --audio-z-threshold / --motion-z-threshold 를 낮춰보세요.")
        return []

    print(f"[3/3] 후보 {len(candidates)}개 클립 추출 중...")
    os.makedirs(args.output_dir, exist_ok=True)
    for i, candidate in enumerate(candidates, start=1):
        output_path = os.path.join(
            args.output_dir, f"highlight_{i:02d}_{int(candidate.time_sec)}s.mp4"
        )
        extract_clip(args.video, candidate.time_sec, args.pre_seconds, args.post_seconds, output_path)
        sources = "+".join(candidate.sources)
        print(
            f"  [{i}] {format_timestamp(candidate.time_sec)} "
            f"신뢰도={candidate.confidence:.2f} 근거={sources} -> {output_path}"
        )

    return candidates


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
