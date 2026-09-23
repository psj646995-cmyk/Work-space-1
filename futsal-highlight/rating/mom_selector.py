"""경기 평점을 기반으로 MOM(Man of the Match)을 선정한다."""
from pydantic import BaseModel

from .models import MatchStat
from .rating_engine import compute_rating


class MomResult(BaseModel):
    player_id: str
    player_name: str
    team_id: str
    rating: float
    attacking_points: int  # 골 + 어시스트 (동점 타이브레이크용)


def _attacking_points(stat: MatchStat) -> int:
    return stat.goals + stat.assists


def select_mom(stats: list[MatchStat]) -> MomResult:
    """경기 참여 선수 스탯 목록에서 MOM을 한 명 선정한다.

    동점 처리 우선순위: 1) 평점 높은 순 2) 공격포인트(골+어시) 많은 순 3) 이름 오름차순
    """
    if not stats:
        raise ValueError("스탯이 비어 있어 MOM을 선정할 수 없습니다")

    ranked = sorted(
        stats,
        key=lambda s: (-compute_rating(s), -_attacking_points(s), s.player_name),
    )
    winner = ranked[0]
    return MomResult(
        player_id=winner.player_id,
        player_name=winner.player_name,
        team_id=winner.team_id,
        rating=compute_rating(winner),
        attacking_points=_attacking_points(winner),
    )
