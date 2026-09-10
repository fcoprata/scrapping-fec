from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GoalEvent:
    minute: Optional[str]
    cumulative_score: str
    scorer: str
    assist: Optional[str]
    team: str  # "home" or "away"


@dataclass
class CardEvent:
    minute: Optional[str]
    player: str
    card_type: str  # "yellow", "red", or "yellow_red"
    reason: Optional[str]
    team: str  # "home" or "away"


@dataclass
class SubEvent:
    minute: Optional[str]
    player_in: str
    player_out: str
    reason: Optional[str]
    team: str  # "home" or "away"


@dataclass
class MatchStats:
    match_url: str
    home_team: str
    away_team: str
    referee: Optional[str] = None
    stadium: Optional[str] = None
    attendance: Optional[int] = None
    round: Optional[str] = None
    # In-match stats (populated by OGol scraper)
    possession_home_pct: Optional[int] = None
    possession_away_pct: Optional[int] = None
    shots_home: Optional[int] = None
    shots_away: Optional[int] = None
    shots_on_target_home: Optional[int] = None
    shots_on_target_away: Optional[int] = None
    corners_home: Optional[int] = None
    corners_away: Optional[int] = None
    fouls_home: Optional[int] = None
    fouls_away: Optional[int] = None
    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    goals: List[GoalEvent] = field(default_factory=list)
    cards: List[CardEvent] = field(default_factory=list)
    substitutions: List[SubEvent] = field(default_factory=list)
