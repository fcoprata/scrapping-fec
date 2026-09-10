from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CompetitionStats:
    competition: str
    appearances: int
    minutes: int
    goals: int
    assists: int
    goals_conceded: Optional[int] = None  # goalkeepers only ("GC" column on OGol)


@dataclass
class PlayerSeasonStats:
    player_id: str
    name: str
    profile_url: str
    position: str
    total_appearances: int
    total_minutes: int
    total_goals: int
    total_assists: int
    total_goals_conceded: Optional[int] = None  # goalkeepers only
    starts: Optional[int] = None
    substitute_appearances: Optional[int] = None
    avg_rating: Optional[float] = None
    competitions: List[CompetitionStats] = field(default_factory=list)
    # Advanced season aggregates (SofaScore, summed over per-match data)
    advanced: Optional["PlayerAdvancedSeason"] = None


@dataclass
class PlayerAdvancedSeason:
    """Season totals/averages of SofaScore per-match advanced metrics."""
    player_id: str
    name: str
    matches: int = 0
    minutes: int = 0
    xg: float = 0.0
    xa: float = 0.0
    goals: int = 0
    assists: int = 0
    shots: int = 0
    touches: int = 0
    passes: int = 0
    passes_accurate: int = 0
    opp_half_passes: int = 0
    own_half_passes: int = 0
    key_passes: int = 0
    long_balls: int = 0
    long_balls_accurate: int = 0
    crosses: int = 0
    crosses_accurate: int = 0
    possession_lost: int = 0
    ball_recovery: int = 0
    ball_carries: int = 0
    progressive_carries: int = 0
    duels_won: int = 0
    duels_lost: int = 0
    aerials_won: int = 0
    interceptions: int = 0
    clearances: int = 0
    fouls: int = 0

    @property
    def pass_accuracy(self) -> Optional[float]:
        return round(self.passes_accurate / self.passes * 100, 1) if self.passes else None

    @property
    def touches_per90(self) -> Optional[float]:
        return round(self.touches / self.minutes * 90, 1) if self.minutes else None

    @property
    def xg_per90(self) -> Optional[float]:
        return round(self.xg / self.minutes * 90, 2) if self.minutes else None
