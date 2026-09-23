"""터치/슈팅 후보를 사람이 보기 좋은 HTML 리포트로 만든다.

경기 미팅에서 바로 열어볼 수 있도록, 각 이벤트 시점의 썸네일 프레임과
함께 정리한다. 여기 나오는 코멘트는 모두 기하학적으로 관측된 사실
("공을 가진 위치가 바뀜", "공이 급가속함")일 뿐이고, 그 장면이 전술적으로
좋았는지 나빴는지는 리포트를 보는 사람이 직접 판단해야 한다.
"""
import html
import os
import subprocess

from .events import ShotCandidate, TouchEvent
from .xg_estimate import CAVEAT, estimate_shot_xg


def _extract_thumbnail(video_path: str, time_sec: float, output_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(0.0, time_sec):.2f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-q:v",
        "3",
        output_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def generate_report(
    video_path: str,
    touch_events: list[TouchEvent],
    shot_events: list[ShotCandidate],
    output_dir: str,
    goal_posts: tuple[tuple[float, float], tuple[float, float]] | None = None,
    frame_diagonal: float | None = None,
) -> str:
    """이벤트들을 HTML 리포트로 만들어 output_dir/report.html 로 저장하고 그 경로를 반환한다."""
    thumbs_dir = os.path.join(output_dir, "thumbnails")
    os.makedirs(thumbs_dir, exist_ok=True)

    rows: list[tuple[float, str, str, str, str]] = []

    for i, touch in enumerate(touch_events, start=1):
        thumb_name = f"touch_{i:03d}.jpg"
        _extract_thumbnail(video_path, touch.time_sec, os.path.join(thumbs_dir, thumb_name))
        rows.append(
            (
                touch.time_sec,
                "터치/패스 후보",
                f"thumbnails/{thumb_name}",
                "이 시점에서 공을 가진 것으로 보이는 선수의 위치가 크게 바뀌었습니다 (패스 또는 볼 탈취 가능성).",
                "",
            )
        )

    can_estimate_xg = goal_posts is not None and frame_diagonal
    for i, shot in enumerate(shot_events, start=1):
        thumb_name = f"shot_{i:03d}.jpg"
        _extract_thumbnail(video_path, shot.time_sec, os.path.join(thumbs_dir, thumb_name))
        if can_estimate_xg:
            xg = estimate_shot_xg(shot.ball_position, goal_posts[0], goal_posts[1], frame_diagonal)
            xg_text = f"참고용 득점확률 근사치: {xg * 100:.0f}% ({CAVEAT})"
        else:
            xg_text = "골대 위치가 지정되지 않아 참고 수치를 생략합니다 (--goal-post-a/--goal-post-b 옵션 참고)"
        rows.append(
            (
                shot.time_sec,
                "슈팅/강킥 후보",
                f"thumbnails/{thumb_name}",
                "공이 급격히 빨라졌습니다 (강한 슈팅 또는 킥 후보).",
                xg_text,
            )
        )

    rows.sort(key=lambda r: r[0])

    row_html = []
    for time_sec, kind, thumb_rel, comment, extra in rows:
        row_html.append(
            f"""
      <div class="event">
        <img src="{html.escape(thumb_rel)}" alt="thumbnail">
        <div class="event-body">
          <div class="event-time">{_format_timestamp(time_sec)} &middot; {html.escape(kind)}</div>
          <div class="event-comment">{html.escape(comment)}</div>
          {f'<div class="event-extra">{html.escape(extra)}</div>' if extra else ""}
        </div>
      </div>"""
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>경기 분석 리포트</title>
<style>
  body {{ font-family: -apple-system, "Malgun Gothic", sans-serif; background: #111; color: #eee; margin: 0; padding: 24px; }}
  h1 {{ font-size: 20px; }}
  .caveat {{ background: #332b00; border: 1px solid #665500; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; line-height: 1.6; }}
  .event {{ display: flex; gap: 16px; background: #1c1c1c; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
  .event img {{ width: 240px; height: auto; border-radius: 6px; flex-shrink: 0; object-fit: cover; }}
  .event-time {{ font-weight: bold; margin-bottom: 6px; }}
  .event-comment {{ color: #ccc; }}
  .event-extra {{ color: #f0c040; margin-top: 6px; font-size: 14px; }}
</style>
</head>
<body>
  <h1>경기 분석 리포트</h1>
  <div class="caveat">
    이 리포트는 딥러닝 액션 인식이 아니라 공/사람 위치 검출(YOLO) 기반 기하학적
    신호로 만들어졌습니다. "터치/패스 후보"와 "슈팅/강킥 후보"는 무슨 일이
    일어난 것 같다는 신호일 뿐이며, 그 장면이 전술적으로 좋았는지 나빴는지는
    사람이 직접 보고 판단해야 합니다. 참고용 득점확률도 카메라 보정 없이 계산한
    근사치이므로 실제 확률과 다를 수 있습니다.
  </div>
  {"".join(row_html) if row_html else "<p>탐지된 이벤트가 없습니다. 임계값을 조정해보세요.</p>"}
</body>
</html>
"""

    report_path = os.path.join(output_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    return report_path
