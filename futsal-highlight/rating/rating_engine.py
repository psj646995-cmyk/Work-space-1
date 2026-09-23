"""경기 스탯 기반 평점 계산.

기본 평점 6.0에서 시작해 +요인/−요인을 가중치만큼 더하고 뺀다.
가중치 크기는 "경기 결과에 미치는 실제 영향도"를 기준으로 정했다:
골/자책골/레드카드처럼 승패에 직결되는 사건은 크게, 패스 성공률처럼
누적성 지표는 표본이 충분할 때만 작게 반영한다. 가중치는 아래 두
딕셔너리(WEIGHTS_FIELD, WEIGHTS_GOALKEEPER)로 분리해뒀으니 실제
데이터가 쌓이면 이 숫자만 조정하면 된다.
"""
import math

from .models import MatchStat, Position

BASE_RATING = 6.0
RATING_MIN = 0.0
RATING_MAX = 10.0

# 필드 플레이어 가중치 (평점 1점당 영향력 크기 순)
WEIGHTS_FIELD: dict[str, float] = {
    "own_goal": -2.2,
    "red_card": -2.0,
    "goal": 1.8,
    "error_leading_to_goal": -1.3,
    "assist": 1.2,
    "big_chance_missed": -0.6,
    "yellow_card": -0.4,
    "key_pass": 0.35,
    "non_scoring_shot_on_target": 0.3,
    "dribble_successful": 0.15,
    "tackle_successful": 0.15,
    "dribble_conceded": -0.15,
    "turnover": -0.12,
    "aerial_duel_won": 0.1,
    "foul_committed": -0.1,
}

# 골키퍼 가중치: 선방 비중을 높이고, 득점 관여성 지표(개인기/키패스 등)는
# 골키퍼 역할과 관련이 낮으므로 절반으로 줄인다. 카드/실점 관련 패널티는 동일하게 유지.
_DEEMPHASIZED_FOR_GK = {
    "key_pass",
    "non_scoring_shot_on_target",
    "dribble_successful",
    "tackle_successful",
    "aerial_duel_won",
}
WEIGHTS_GOALKEEPER: dict[str, float] = {
    **{
        k: (v * 0.5 if k in _DEEMPHASIZED_FOR_GK else v)
        for k, v in WEIGHTS_FIELD.items()
    },
    "save": 0.9,
}

# 패스 성공률 보너스/페널티 설정.
# 표본이 적으면(시도 횟수가 적으면) 노이즈를 줄이기 위해 보정 영향력을 sqrt(시도수)로 스케일한다.
PASS_SUCCESS_BASELINE = 0.75
PASS_SUCCESS_WEIGHT = 2.0
PASS_SUCCESS_MIN_ATTEMPTS = 3


def _pass_success_contribution(stat: MatchStat) -> float:
    if stat.passes_attempted < PASS_SUCCESS_MIN_ATTEMPTS:
        return 0.0
    rate_delta = stat.pass_success_rate - PASS_SUCCESS_BASELINE
    volume_scale = math.sqrt(stat.passes_attempted) / 10.0
    return PASS_SUCCESS_WEIGHT * rate_delta * volume_scale


def compute_rating_breakdown(stat: MatchStat) -> dict[str, float]:
    """평점을 구성하는 각 요인의 기여도를 반환한다 (base 포함, 합산하면 최종 평점 clamp 전 값)."""
    weights = WEIGHTS_GOALKEEPER if stat.position == Position.GOALKEEPER else WEIGHTS_FIELD

    breakdown = {"base": BASE_RATING}
    breakdown["goal"] = weights["goal"] * stat.goals
    breakdown["assist"] = weights["assist"] * stat.assists
    breakdown["non_scoring_shot_on_target"] = (
        weights["non_scoring_shot_on_target"] * stat.non_scoring_shots_on_target
    )
    breakdown["key_pass"] = weights["key_pass"] * stat.key_passes
    breakdown["pass_success"] = _pass_success_contribution(stat)
    breakdown["dribble_successful"] = weights["dribble_successful"] * stat.dribbles_successful
    breakdown["tackle_successful"] = weights["tackle_successful"] * stat.tackles_successful
    breakdown["aerial_duel_won"] = weights["aerial_duel_won"] * stat.aerial_duels_won
    breakdown["turnover"] = weights["turnover"] * stat.turnovers
    breakdown["dribble_conceded"] = weights["dribble_conceded"] * stat.dribbles_conceded
    breakdown["foul_committed"] = weights["foul_committed"] * stat.fouls_committed
    breakdown["yellow_card"] = weights["yellow_card"] * stat.yellow_cards
    breakdown["red_card"] = weights["red_card"] * stat.red_cards
    breakdown["big_chance_missed"] = weights["big_chance_missed"] * stat.big_chances_missed
    breakdown["own_goal"] = weights["own_goal"] * stat.own_goals
    breakdown["error_leading_to_goal"] = (
        weights["error_leading_to_goal"] * stat.errors_leading_to_goal
    )

    if stat.position == Position.GOALKEEPER:
        breakdown["save"] = weights["save"] * stat.saves

    return breakdown


def compute_rating(stat: MatchStat) -> float:
    """0.0~10.0 사이로 clamp된 최종 평점을 반환한다 (소수점 1자리 반올림)."""
    total = sum(compute_rating_breakdown(stat).values())
    clamped = max(RATING_MIN, min(RATING_MAX, total))
    return round(clamped, 1)
