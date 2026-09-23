"""하이라이트 모드 / 경기 분석 모드를 한 곳에서 고르는 진입점.

사용법:
    python run.py --mode highlight 경기영상.mp4 --output-dir out/
    python run.py --mode analyze 경기영상.mp4 --output-dir out/

각 모드의 나머지 옵션은 그 모드 CLI(highlight.highlight_extractor /
analysis.cli)와 동일하다. --mode 뒤에 오는 인자는 그대로 해당 모드로 전달된다.
"""
import argparse

from analysis.cli import build_arg_parser as build_analyze_parser
from analysis.cli import run as run_analyze
from highlight.highlight_extractor import build_arg_parser as build_highlight_parser
from highlight.highlight_extractor import run as run_highlight


def main() -> None:
    parser = argparse.ArgumentParser(description="풋살 하이라이트/경기 분석 도구", add_help=False)
    parser.add_argument("--mode", choices=["highlight", "analyze"], required=True)
    args, remaining = parser.parse_known_args()

    if args.mode == "highlight":
        sub_args = build_highlight_parser().parse_args(remaining)
        run_highlight(sub_args)
    else:
        sub_args = build_analyze_parser().parse_args(remaining)
        run_analyze(sub_args)


if __name__ == "__main__":
    main()
