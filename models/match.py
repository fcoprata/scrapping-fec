from dataclasses import dataclass
from typing import Optional


@dataclass
class Match:
    date: Optional[str]
    opponent: str
    score: Optional[str]
    home_away: str  # "H" or "A"
    competition: str
    status: str = "played"  # "played" or "upcoming"
    match_url: Optional[str] = None
