import pytest

from ..models import MatchStat, Position
from ..mom_selector import select_mom


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


def test_select_mom_raises_on_empty_list():
    with pytest.raises(ValueError):
        select_mom([])


def test_select_mom_picks_highest_rating():
    hero = make_stat(player_id="p1", player_name="Hero", goals=3, shots_on_target=3)
    average = make_stat(player_id="p2", player_name="Average")
    villain = make_stat(player_id="p3", player_name="Villain", own_goals=1)

    result = select_mom([average, villain, hero])
    assert result.player_id == "p1"
    assert result.player_name == "Hero"


def test_select_mom_multigoal_striker_beats_keeper_with_no_saves():
    striker = make_stat(
        player_id="s1", player_name="Striker", goals=2, assists=1, shots_on_target=2
    )
    keeper = make_stat(player_id="k1", player_name="Keeper", position=Position.GOALKEEPER)
    result = select_mom([striker, keeper])
    assert result.player_id == "s1"


def test_select_mom_busy_keeper_can_beat_field_player():
    keeper = make_stat(player_id="k1", player_name="Keeper", position=Position.GOALKEEPER, saves=6)
    quiet_field_player = make_stat(player_id="f1", player_name="Quiet")
    result = select_mom([keeper, quiet_field_player])
    assert result.player_id == "k1"


def test_tiebreak_prefers_higher_attacking_points_when_rating_ties():
    # 6.0 + 1*goal(1.8) = 7.8
    goal_scorer = make_stat(player_id="a", player_name="Alice", goals=1, shots_on_target=1)
    # 6.0 + 6*non_scoring_shot_on_target(0.3) = 7.8 (반올림 후 동일)
    volume_shooter = make_stat(player_id="b", player_name="Bob", shots_on_target=6)

    result = select_mom([goal_scorer, volume_shooter])
    assert result.player_id == "a"
    assert result.attacking_points == 1


def test_tiebreak_falls_back_to_name_when_everything_ties():
    alice = make_stat(player_id="a", player_name="Alice")
    bob = make_stat(player_id="b", player_name="Bob")

    result = select_mom([bob, alice])
    assert result.player_name == "Alice"
