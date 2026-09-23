"""경기 분석 모드 CLI: 터치/슈팅 후보를 찾아 HTML 분석 리포트를 만든다.

사용법:
    python -m analysis.cli 경기영상.mp4 --output-dir out/
"""
import argparse
import os

from .events import detect_shot_candidates, detect_touch_events
from .report import generate_report
from .tracking import detect_frame_objects


def _parse_point(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    x_str, y_str = value.split(",")
    return (float(x_str), float(y_str))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="풀경기/편집된 경기 영상에서 터치·슈팅 후보를 찾아 HTML 분석 리포트를 만듭니다."
    )
    parser.add_argument("video", help="입력 영상 파일 경로")
    parser.add_argument("--output-dir", default="analysis_out", help="리포트 저장 폴더")
    parser.add_argument("--sample-fps", type=float, default=5.0, help="초당 몇 프레임을 분석할지")
    parser.add_argument("--touch-jump-ratio", type=float, default=0.15, help="터치/패스 후보로 볼 최소 위치 변화 비율")
    parser.add_argument("--shot-z-threshold", type=float, default=2.0, help="슈팅 후보로 볼 공 속도 급증 임계값")
    parser.add_argument("--min-gap-sec", type=float, default=3.0, help="같은 이벤트가 중복 검출되지 않게 하는 최소 간격")
    parser.add_argument(
        "--goal-post-a",
        default=None,
        help="골대 한쪽 기둥의 화면 좌표 'x,y' (카메라가 고정된 영상에서만 사용, 참고용 xG 계산에 필요)",
    )
    parser.add_argument("--goal-post-b", default=None, help="골대 반대쪽 기둥의 화면 좌표 'x,y'")
    return parser


def run(args: argparse.Namespace) -> str | None:
    print("[1/3] YOLO로 공/선수 위치 추적 중 (모델 로딩 포함, 시간이 걸릴 수 있습니다)...")
    detections = detect_frame_objects(args.video, sample_fps=args.sample_fps)
    print(f"      {len(detections)}개 프레임 분석 완료")

    print("[2/3] 터치/슈팅 후보 탐지 중...")
    touch_events = detect_touch_events(
        detections, min_owner_jump_ratio=args.touch_jump_ratio, min_gap_sec=args.min_gap_sec
    )
    shot_events = detect_shot_candidates(
        detections,
        sample_fps=args.sample_fps,
        z_threshold=args.shot_z_threshold,
        min_gap_sec=args.min_gap_sec,
    )
    print(f"      터치 후보 {len(touch_events)}개, 슈팅 후보 {len(shot_events)}개 발견")

    goal_a = _parse_point(args.goal_post_a)
    goal_b = _parse_point(args.goal_post_b)
    frame_diagonal = detections[0].frame_diagonal if detections else None

    print("[3/3] HTML 리포트 생성 중...")
    os.makedirs(args.output_dir, exist_ok=True)
    report_path = generate_report(
        args.video,
        touch_events,
        shot_events,
        args.output_dir,
        goal_posts=(goal_a, goal_b) if goal_a and goal_b else None,
        frame_diagonal=frame_diagonal,
    )
    print(f"완료: {report_path}")
    return report_path


def main() -> None:
    args = build_arg_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
