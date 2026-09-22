"""Aggregate per-match SofaScore stats into per-player season totals."""

from collections import Counter
from typing import Dict, Iterable, List

from models.player_match_stats import MatchAdvancedStats, PlayerMatchStats
from models.player_stats import PlayerAdvancedSeason

# SofaScore usa letra única por posição; times sem cobertura OGol (a maioria da
# liga) dependem só disso para agrupar percentis por posição.
_POSITION_LABELS = {
    "G": "Goleiro",
    "D": "Defensor",
    "M": "Meia",
    "F": "Atacante",
}

# PlayerMatchStats attr -> PlayerAdvancedSeason attr (summed)
_SUM_FIELDS = {
    "minutes_played": "minutes",
    "xg": "xg",
    "xa": "xa",
    "goals": "goals",
    "assists": "assists",
    "shots_total": "shots",
    "touches": "touches",
    "passes_total": "passes",
    "passes_accurate": "passes_accurate",
    "opp_half_passes_total": "opp_half_passes",
    "own_half_passes_total": "own_half_passes",
    "key_passes": "key_passes",
    "long_balls_total": "long_balls",
    "long_balls_accurate": "long_balls_accurate",
    "crosses_total": "crosses",
    "crosses_accurate": "crosses_accurate",
    "possession_lost": "possession_lost",
    "ball_recovery": "ball_recovery",
    "ball_carries": "ball_carries",
    "progressive_carries": "progressive_carries",
    "duels_won": "duels_won",
    "duels_lost": "duels_lost",
    "aerials_won": "aerials_won",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "fouls": "fouls",
}


def aggregate_player_season(
    matches: Iterable[MatchAdvancedStats], team_name_contains: str
) -> List[PlayerAdvancedSeason]:
    """Sum per-match rows for players whose team name matches the target club."""
    key = team_name_contains.lower()
    acc: Dict[str, PlayerAdvancedSeason] = {}
    positions: Dict[str, Counter] = {}
    for match in matches:
        for p in match.players:
            if key not in (p.team_name or "").lower():
                continue
            row = acc.get(p.player_id)
            if row is None:
                row = PlayerAdvancedSeason(player_id=p.player_id, name=p.name)
                acc[p.player_id] = row
            if p.is_starter or (p.minutes_played or 0) > 0:
                row.matches += 1
            row.name = p.name or row.name
            for src, dst in _SUM_FIELDS.items():
                setattr(row, dst, _round(getattr(row, dst) + (getattr(p, src) or 0)))
            if p.position:
                positions.setdefault(p.player_id, Counter())[p.position] += 1

    for player_id, row in acc.items():
        counts = positions.get(player_id)
        if counts:
            most_common = counts.most_common(1)[0][0]
            row.position_group = _POSITION_LABELS.get(most_common, most_common)

    return sorted(acc.values(), key=lambda r: r.minutes, reverse=True)


def _round(v):
    return round(v, 4) if isinstance(v, float) else v
