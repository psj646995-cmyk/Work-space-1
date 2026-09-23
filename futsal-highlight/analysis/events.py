"""프레임별 공/선수 위치로부터 터치(패스 후보)·슈팅 후보 이벤트를 추출한다.

여기서 나오는 이벤트는 모두 "무슨 일이 일어난 것 같다"는 기하학적 신호일
뿐, "그 패스가 좋았다/나빴다" 같은 가치 판단은 하지 않는다. 그런 판단은
실제 전술 맥락(상대 위치, 의도, 다음 장면)을 이해해야 하는데 지금 파이프라인은
공/사람의 픽셀 좌표만 보기 때문이다. 사람이 리포트를 보고 최종 판단하는
것을 전제로 한다.
"""
from dataclasses import dataclass
from math import hypot

from highlight.object_detection import BallDetection, compute_ball_speed_series
from highlight.signal_utils import z_score_spikes

from .tracking import FrameDetections


@dataclass
class TouchEvent:
    time_sec: float
    ball_position: tuple[float, float]


@dataclass
class ShotCandidate:
    time_sec: float
    score: float
    ball_position: tuple[float, float]


def _nearest_person_index(ball: tuple[float, float], persons: list[tuple[float, float]]) -> int | None:
    if not persons:
        return None
    return min(range(len(persons)), key=lambda i: hypot(persons[i][0] - ball[0], persons[i][1] - ball[1]))


def detect_touch_events(
    detections: list[FrameDetections],
    min_owner_jump_ratio: float = 0.15,
    min_gap_sec: float = 1.0,
) -> list[TouchEvent]:
    """공을 가진 것으로 보이는 위치가 유의미하게 바뀌는(=패스/탈취 후보) 시점을 찾는다.

    선수 개인 식별은 하지 않으므로 "누가 잡았는지"가 아니라 "공에 가장
    가까운 사람의 위치가 화면 대각선 대비 min_owner_jump_ratio 이상
    이동했는지"만 본다.
    """
    events: list[TouchEvent] = []
    last_owner_pos: tuple[float, float] | None = None
    last_event_time = float("-inf")

    for d in detections:
        if d.ball_center is None:
            continue
        owner_idx = _nearest_person_index(d.ball_center, d.person_centers)
        if owner_idx is None:
            continue
        owner_pos = d.person_centers[owner_idx]

        if last_owner_pos is not None and d.frame_diagonal > 0:
            jump = hypot(owner_pos[0] - last_owner_pos[0], owner_pos[1] - last_owner_pos[1])
            if (
                jump / d.frame_diagonal >= min_owner_jump_ratio
                and (d.time_sec - last_event_time) >= min_gap_sec
            ):
                events.append(TouchEvent(time_sec=d.time_sec, ball_position=d.ball_center))
                last_event_time = d.time_sec

        last_owner_pos = owner_pos

    return events


def detect_shot_candidates(
    detections: list[FrameDetections],
    sample_fps: float = 5.0,
    window_sec: float = 6.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 3.0,
) -> list[ShotCandidate]:
    """공이 급가속하는 구간을 강슛/강킥 후보로 반환한다 (하이라이트 모드와 같은 로직 재사용)."""
    ball_detections = [
        BallDetection(time_sec=d.time_sec, ball_center=d.ball_center, frame_diagonal=d.frame_diagonal)
        for d in detections
    ]
    speeds, times = compute_ball_speed_series(ball_detections)
    if len(speeds) == 0:
        return []

    window = max(3, int(window_sec * sample_fps))
    spikes = z_score_spikes(speeds, times, window, z_threshold, min_gap_sec)

    position_by_time = {d.time_sec: d.ball_center for d in detections if d.ball_center is not None}
    candidates: list[ShotCandidate] = []
    for spike in spikes:
        closest_time = min(position_by_time, key=lambda t: abs(t - spike.time_sec))
        candidates.append(
            ShotCandidate(
                time_sec=spike.time_sec,
                score=spike.score,
                ball_position=position_by_time[closest_time],
            )
        )
    return candidates
