from dataclasses import dataclass
from typing import Optional


@dataclass
class Player:
    player_id: str
    slug: str
    name: str
    position: str  # "Goleiro", "Defensor", "Meia", "Atacante" (as grouped by OGol)
    jersey_number: Optional[str]
    age: Optional[int]
    nationality: Optional[str]
    market_value_eur: Optional[int]
    photo_url: Optional[str]
    profile_url: str
    active: bool = True
    position_detail: Optional[str] = None  # finer-grained position from Transfermarkt (e.g. "Lateral Esq.")
    contract_until: Optional[str] = None
