from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Shot:
    """One shot from the SofaScore shotmap."""
    minute: Optional[int]
    player_id: str
    player_name: str
    is_home: bool
    xg: Optional[float]
    xgot: Optional[float]
    shot_type: Optional[str]      # goal / save / miss / block / post
    situation: Optional[str]      # regular-play / corner / fast-break / set-piece / penalty
    body_part: Optional[str]      # right-foot / left-foot / head / other
    is_goal: bool = False
    x: Optional[float] = None
    y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    assist_player_name: Optional[str] = None


@dataclass
class PlayerMatchStats:
    """Per-player per-match advanced stats from SofaScore."""
    event_id: int
    player_id: str
    name: str
    team: str                     # "home" or "away"
    team_name: str
    is_starter: bool
    position: Optional[str]
    minutes_played: int
    rating: Optional[float]

    touches: int = 0
    # Passing
    passes_total: int = 0
    passes_accurate: int = 0
    key_passes: int = 0
    long_balls_total: int = 0
    long_balls_accurate: int = 0
    crosses_total: int = 0
    crosses_accurate: int = 0
    own_half_passes_total: int = 0
    own_half_passes_accurate: int = 0
    opp_half_passes_total: int = 0
    opp_half_passes_accurate: int = 0
    # Ball retention / progression
    possession_lost: int = 0          # possessionLostCtrl
    ball_recovery: int = 0
    ball_carries: int = 0
    progressive_carries: int = 0
    carry_distance: float = 0.0
    # Duels / defence
    duels_won: int = 0
    duels_lost: int = 0
    aerials_won: int = 0
    interceptions: int = 0
    clearances: int = 0
    fouls: int = 0
    # Attacking output
    shots_total: int = 0
    goals: int = 0
    assists: int = 0
    xg: float = 0.0                   # summed from shotmap
    xa: float = 0.0                   # expectedAssists

    @property
    def pass_accuracy(self) -> Optional[float]:
        return round(self.passes_accurate / self.passes_total * 100, 1) if self.passes_total else None


@dataclass
class MatchAdvancedStats:
    """Team-level advanced stats + shots for one match (SofaScore)."""
    event_id: int
    home_team: str
    away_team: str
    competition: Optional[str] = None
    season: Optional[str] = None
    round: Optional[str] = None
    date: Optional[str] = None
    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    xgot_home: Optional[float] = None
    xgot_away: Optional[float] = None
    players: List[PlayerMatchStats] = field(default_factory=list)
    shots: List[Shot] = field(default_factory=list)
