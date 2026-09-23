"""터미널에 진행률을 한 줄로 갱신해 보여주는 작은 유틸리티."""
import sys


def print_progress(current: int, total: int, prefix: str = "") -> None:
    """current/total 진행 상황을 같은 줄에 덮어써서 보여준다.

    total을 모르거나(0 이하) 신뢰할 수 없는 컨테이너(가변 프레임레이트 등)면
    퍼센트 대신 처리한 개수만 보여준다.
    """
    if total and total > 0:
        percent = min(100, int(current * 100 / total))
        bar_len = 20
        filled = int(bar_len * percent / 100)
        bar = "#" * filled + "-" * (bar_len - filled)
        line = f"\r{prefix}[{bar}] {percent}% ({current}/{total})"
    else:
        line = f"\r{prefix}처리 중... ({current}프레임)"

    sys.stdout.write(line.ljust(70))
    sys.stdout.flush()
