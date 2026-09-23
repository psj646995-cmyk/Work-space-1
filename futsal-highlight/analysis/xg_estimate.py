"""거리·각도 기반 "참고용" xG(득점 기대값) 근사치.

정밀한 xG는 다중 카메라로 보정된 실제 좌표계와 대량의 실제 슈팅 데이터로
학습한 모델이 필요하다 — 폰 한 대로 찍은, 카메라도 움직이는 영상에서는
애초에 정확한 계산이 불가능하다. 여기서는 "골대에 가깝고 각도가 넓을수록
득점 확률이 높다"는 일반적인 경향만 반영한 단순 로지스틱 근사치를 제공한다.

**실제 확률이 아니라 상대적 참고 지표로만 써야 한다.** 아래 계수는 검증된
데이터로 학습한 값이 아니라 그 경향만 만족하도록 손으로 정한 예시 값이다.
또한 골대의 화면상 좌표를 알아야 계산할 수 있으므로, 카메라가 고정되어
있고 골대 위치를 사람이 지정해준 경우에만 사용할 수 있다 (카메라가 계속
움직이는 영상에는 적용할 수 없다).
"""
import math

DISTANCE_COEF = -1.0  # 화면 대각선 대비 정규화된 거리가 멀어질수록 감소
ANGLE_COEF = 2.0  # 골대를 보는 각도(라디안)가 넓을수록 증가
INTERCEPT = 0.5

CAVEAT = "참고용 근사치입니다 (카메라 보정 없음, 실제 확률과 다를 수 있음)"


def estimate_shot_xg(
    shot_position: tuple[float, float],
    goal_post_a: tuple[float, float],
    goal_post_b: tuple[float, float],
    frame_diagonal: float,
) -> float:
    """슈팅 지점과 골대 양쪽 기둥 좌표로 참고용 xG(0~1)를 근사한다."""
    goal_center = (
        (goal_post_a[0] + goal_post_b[0]) / 2,
        (goal_post_a[1] + goal_post_b[1]) / 2,
    )
    distance = math.hypot(shot_position[0] - goal_center[0], shot_position[1] - goal_center[1])
    normalized_distance = distance / frame_diagonal if frame_diagonal else 0.0

    v1 = (goal_post_a[0] - shot_position[0], goal_post_a[1] - shot_position[1])
    v2 = (goal_post_b[0] - shot_position[0], goal_post_b[1] - shot_position[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        angle = 0.0
    else:
        cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)
        angle = math.acos(max(-1.0, min(1.0, cos_angle)))

    z = INTERCEPT + DISTANCE_COEF * normalized_distance + ANGLE_COEF * angle
    return 1 / (1 + math.exp(-z))
