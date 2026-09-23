import pytest
from pydantic import ValidationError

from ..models import MatchStat, Position
from ..rating_engine import (
    BASE_RATING,
    RATING_MAX,
    RATING_MIN,
    WEIGHTS_FIELD,
    compute_rating,
)


def make_stat(**overrides) -> MatchStat:
    defaults = dict(
        player_id="p1",
        player_name="Player",
        team_id="team-a",
        position=Position.FIELD,
        minutes_played=60,
    )
    defaults.update(overrides)
    return MatchStat(**defaults)


def test_no_events_gives_base_rating():
    stat = make_stat()
    assert compute_rating(stat) == BASE_RATING


def test_goal_scorer_rated_higher_than_assist_only():
    scorer = make_stat(goals=2, shots_on_target=2)
    assister = make_stat(assists=2)
    assert compute_rating(scorer) > compute_rating(assister) > BASE_RATING


def test_own_goal_hurts_more_than_a_missed_big_chance():
    own_goal_player = make_stat(own_goals=1)
    wasteful_player = make_stat(big_chances_missed=1)
    assert compute_rating(own_goal_player) < compute_rating(wasteful_player) < BASE_RATING


def test_red_card_bigger_penalty_than_yellow_card():
    red = make_stat(red_cards=1)
    yellow = make_stat(yellow_cards=1)
    assert compute_rating(red) < compute_rating(yellow) < BASE_RATING


def test_decisive_factors_outweigh_accumulating_factors():
    """골/자책골/레드카드처럼 승패에 직결되는 요인이, 패스 성공률처럼
    누적되는 요인보다 절대값 기준으로 더 크게 반영되어야 한다."""
    decisive = ["own_goal", "red_card", "goal", "error_leading_to_goal", "assist"]
    accumulating = [
        "big_chance_missed",
        "yellow_card",
        "key_pass",
        "non_scoring_shot_on_target",
        "dribble_successful",
        "tackle_successful",
        "dribble_conceded",
        "turnover",
        "aerial_duel_won",
        "foul_committed",
    ]
    min_decisive_weight = min(abs(WEIGHTS_FIELD[k]) for k in decisive)
    max_accumulating_weight = max(abs(WEIGHTS_FIELD[k]) for k in accumulating)
    assert min_decisive_weight > max_accumulating_weight


def test_goalkeeper_saves_increase_rating():
    keeper_no_saves = make_stat(position=Position.GOALKEEPER)
    keeper_with_saves = make_stat(position=Position.GOALKEEPER, saves=5)
    assert compute_rating(keeper_with_saves) > compute_rating(keeper_no_saves)


def test_pass_success_bonus_needs_minimum_sample_size():
    tiny_sample_perfect = make_stat(passes_attempted=2, passes_completed=2)
    no_passes = make_stat()
    # 표본이 너무 적으면 완벽한 성공률이어도 보너스를 주지 않는다
    assert compute_rating(tiny_sample_perfect) == compute_rating(no_passes) == BASE_RATING


def test_pass_success_bonus_rewards_high_accuracy_high_volume():
    accurate = make_stat(passes_attempted=30, passes_completed=28)
    inaccurate = make_stat(passes_attempted=30, passes_completed=15)
    assert compute_rating(accurate) > BASE_RATING > compute_rating(inaccurate)


def test_rating_clamped_to_valid_range():
    superstar = make_stat(goals=10, shots_on_target=10, assists=10, key_passes=10)
    disaster = make_stat(own_goals=5, red_cards=3, errors_leading_to_goal=5)
    assert compute_rating(superstar) == RATING_MAX
    assert compute_rating(disaster) == RATING_MIN


def test_goals_cannot_exceed_shots_on_target():
    with pytest.raises(ValidationError):
        make_stat(goals=2, shots_on_target=1)


def test_passes_completed_cannot_exceed_attempted():
    with pytest.raises(ValidationError):
        make_stat(passes_completed=5, passes_attempted=3)
