"""오디오/모션/공-속도 스파이크를 결합해 골 장면 후보를 찾고,
ffmpeg로 하이라이트 클립을 잘라내는 CLI 도구.

사용법:
    python -m highlight.highlight_extractor 경기영상.mp4 --output-dir out/

주의: 이 도구는 딥러닝 기반 골 인식이 아니라 "골이 나면 관중 소리·움직임이
튀고 공이 빠르게 움직인다"는 가정에 기반한 신호 처리/객체검출 휴리스틱이다.
완벽한 정확도를 기대하면 안 되며, 오탐/누락이 있을 수 있다. 실제 영상으로
--audio-z-threshold / --motion-z-threshold / --ball-z-threshold / --min-gap-sec
값을 튜닝해가며 써야 한다.
"""
import argparse
import os
from dataclasses import dataclass, field

from .audio_analysis import detect_audio_spikes, load_audio
from .motion_analysis import detect_motion_spikes
from .object_detection import detect_ball_speed_spikes
from .spike_event import SpikeEvent
from .video_utils import concat_clips, extract_clip

# 단일 신호만 잡힌 후보는 여러 신호가 겹친 후보보다 신뢰도를 낮춘다.
SINGLE_SIGNAL_CONFIDENCE_SCALE = 0.55
CORROBORATION_BONUS = 1.0


@dataclass
class HighlightCandidate:
    time_sec: float
    confidence: float
    sources: list[str] = field(default_factory=list)


def merge_events(
    signals: list[tuple[str, list[SpikeEvent]]],
    corroboration_window_sec: float = 4.0,
) -> list[HighlightCandidate]:
    """여러 신호(오디오/모션/공-속도 등)의 후보를 시간대로 대조해 결합한다.

    비슷한 시간대에 서로 다른 신호가 함께 튀면 "교차 검증됨"으로 보고
    신뢰도를 크게 높이고, 한 신호만 잡히면 신뢰도를 낮춰서 후보로 남긴다.
    같은 신호에서 나온 두 이벤트가 한 후보에 같이 묶이는 일은 없다.
    """
    tagged_events = [
        (source, event) for source, events in signals for event in events
    ]
    tagged_events.sort(key=lambda pair: -pair[1].score)

    used = [False] * len(tagged_events)
    candidates: list[HighlightCandidate] = []

    for seed_idx, (seed_source, seed_event) in enumerate(tagged_events):
        if used[seed_idx]:
            continue

        group = [(seed_idx, seed_source, seed_event)]
        used[seed_idx] = True
        sources_in_group = {seed_source}

        for other_idx, (other_source, other_event) in enumerate(tagged_events):
            if used[other_idx] or other_source in sources_in_group:
                continue
            if abs(other_event.time_sec - seed_event.time_sec) <= corroboration_window_sec:
                group.append((other_idx, other_source, other_event))
                used[other_idx] = True
                sources_in_group.add(other_source)

        total_score = sum(event.score for _, _, event in group)
        # 점수가 큰 신호가 대표 시각을 더 많이 끌어오도록 가중평균 사용
        # (단순 평균이면 약한 신호가 강한 신호의 정확한 시점을 흐리게 만듦)
        avg_time = sum(event.time_sec * event.score for _, _, event in group) / total_score

        if len(group) == 1:
            confidence = total_score * SINGLE_SIGNAL_CONFIDENCE_SCALE
        else:
            confidence = total_score + (len(group) - 1) * CORROBORATION_BONUS

        candidates.append(
            HighlightCandidate(
                time_sec=avg_time,
                confidence=confidence,
                sources=sorted(sources_in_group),
            )
        )

    candidates.sort(key=lambda c: c.time_sec)
    return candidates


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="오디오+모션+공속도 스파이크 기반으로 골 장면 후보를 찾아 클립으로 추출합니다."
    )
    parser.add_argument("video", help="입력 영상 파일 경로")
    parser.add_argument("--output-dir", default="highlights_out", help="클립 저장 폴더")
    parser.add_argument("--pre-seconds", type=float, default=8.0, help="후보 시점 이전 몇 초부터 자를지")
    parser.add_argument("--post-seconds", type=float, default=5.0, help="후보 시점 이후 몇 초까지 자를지")
    parser.add_argument("--audio-z-threshold", type=float, default=2.0)
    parser.add_argument("--motion-z-threshold", type=float, default=2.0)
    parser.add_argument("--ball-z-threshold", type=float, default=2.0)
    parser.add_argument(
        "--use-ball-detection",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="YOLO로 공을 검출해 공 속도 급증 신호를 추가로 사용할지 (모델 로딩 시간이 있음)",
    )
    parser.add_argument("--min-gap-sec", type=float, default=10.0, help="같은 장면이 중복 검출되지 않도록 하는 최소 간격")
    parser.add_argument("--corroboration-window-sec", type=float, default=4.0)
    parser.add_argument("--min-confidence", type=float, default=0.0, help="이 값 미만인 후보는 버림")
    parser.add_argument("--max-clips", type=int, default=None, help="최대 몇 개 클립까지 추출할지")
    parser.add_argument(
        "--combined-name",
        default="highlights_combined.mp4",
        help="개별 클립을 이어붙인 하나의 하이라이트 영상 파일명",
    )
    parser.add_argument(
        "--no-combined",
        action="store_true",
        help="개별 클립만 만들고 하나로 이어붙인 영상은 만들지 않음",
    )
    return parser


def run(args: argparse.Namespace) -> list[HighlightCandidate]:
    print("[1/4] 오디오 트랙 분석 중...")
    y, sr = load_audio(args.video)
    audio_events = detect_audio_spikes(
        y, sr, z_threshold=args.audio_z_threshold, min_gap_sec=args.min_gap_sec
    )
    print(f"      오디오 후보 {len(audio_events)}개 발견")

    print("[2/4] 영상 모션 분석 중...")
    motion_events = detect_motion_spikes(
        args.video, z_threshold=args.motion_z_threshold, min_gap_sec=args.min_gap_sec
    )
    print(f"      모션 후보 {len(motion_events)}개 발견")

    signals = [("audio", audio_events), ("motion", motion_events)]

    if args.use_ball_detection:
        print("[3/4] YOLO로 공 검출 및 속도 분석 중 (모델 로딩 포함, 시간이 걸릴 수 있습니다)...")
        ball_events = detect_ball_speed_spikes(
            args.video, z_threshold=args.ball_z_threshold, min_gap_sec=args.min_gap_sec
        )
        print(f"      공-속도 후보 {len(ball_events)}개 발견")
        signals.append(("ball_speed", ball_events))
    else:
        print("[3/4] 공 검출 건너뜀 (--no-use-ball-detection)")

    candidates = merge_events(signals, args.corroboration_window_sec)
    candidates = [c for c in candidates if c.confidence >= args.min_confidence]
    candidates.sort(key=lambda c: -c.confidence)
    if args.max_clips is not None:
        candidates = candidates[: args.max_clips]
    candidates.sort(key=lambda c: c.time_sec)

    if not candidates:
        print("하이라이트 후보를 찾지 못했습니다. --audio-z-threshold / --motion-z-threshold / --ball-z-threshold 를 낮춰보세요.")
        return []

    print(f"[4/4] 후보 {len(candidates)}개 클립 추출 중...")
    os.makedirs(args.output_dir, exist_ok=True)
    clip_paths: list[str] = []
    for i, candidate in enumerate(candidates, start=1):
        output_path = os.path.join(
            args.output_dir, f"highlight_{i:02d}_{int(candidate.time_sec)}s.mp4"
        )
        extract_clip(args.video, candidate.time_sec, args.pre_seconds, args.post_seconds, output_path)
        clip_paths.append(output_path)
        sources = "+".join(candidate.sources)
        print(
            f"  [{i}] {format_timestamp(candidate.time_sec)} "
            f"신뢰도={candidate.confidence:.2f} 근거={sources} -> {output_path}"
        )

    if not args.no_combined:
        combined_path = os.path.join(args.output_dir, args.combined_name)
        print(f"클립 {len(clip_paths)}개를 하나로 이어붙이는 중...")
        concat_clips(clip_paths, combined_path)
        print(f"완성된 하이라이트 영상: {combined_path}")

    return candidates


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
