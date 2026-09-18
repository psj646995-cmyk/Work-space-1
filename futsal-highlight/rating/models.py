"""경기 스탯 데이터 모델."""
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Position(str, Enum):
    FIELD = "field"
    GOALKEEPER = "goalkeeper"


class MatchStat(BaseModel):
    """한 선수의 한 경기 스탯. 값이 없는 항목은 0으로 둔다."""

    player_id: str
    player_name: str
    team_id: str
    position: Position
    minutes_played: float = Field(ge=0, le=120)

    # +요인
    goals: int = 0
    assists: int = 0
    shots_on_target: int = 0  # 유효슈팅 (골로 연결된 슈팅 포함)
    key_passes: int = 0
    passes_completed: int = 0
    passes_attempted: int = 0
    dribbles_successful: int = 0
    tackles_successful: int = 0
    aerial_duels_won: int = 0
    saves: int = 0  # 키퍼 선방 (골키퍼 전용)

    # -요인
    turnovers: int = 0
    dribbles_conceded: int = 0
    fouls_committed: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    big_chances_missed: int = 0
    own_goals: int = 0
    errors_leading_to_goal: int = 0  # 실점 빌미 제공

    @model_validator(mode="after")
    def _validate_passes(self) -> "MatchStat":
        if self.passes_completed > self.passes_attempted:
            raise ValueError("passes_completed는 passes_attempted를 넘을 수 없습니다")
        if self.goals > self.shots_on_target:
            raise ValueError("goals는 shots_on_target을 넘을 수 없습니다 (골은 유효슈팅에 포함)")
        return self

    @property
    def pass_success_rate(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted

    @property
    def passes_missed(self) -> int:
        return self.passes_attempted - self.passes_completed

    @property
    def non_scoring_shots_on_target(self) -> int:
        """골로 연결되지 않은 유효슈팅 (골 가중치와 중복 반영 방지용)."""
        return self.shots_on_target - self.goals
