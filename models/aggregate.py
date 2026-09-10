"""Aggregate per-match SofaScore stats into per-player season totals."""

from typing import Dict, Iterable, List

from models.player_match_stats import MatchAdvancedStats, PlayerMatchStats
from models.player_stats import PlayerAdvancedSeason

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
    for match in matches:
        for p in match.players:
            if key not in (p.team_name or "").lower():
                continue
            row = acc.get(p.player_id)
            if row is None:
                row = PlayerAdvancedSeason(player_id=p.player_id, name=p.name)
                acc[p.player_id] = row
            row.matches += 1
            row.name = p.name or row.name
            for src, dst in _SUM_FIELDS.items():
                setattr(row, dst, _round(getattr(row, dst) + (getattr(p, src) or 0)))
    return sorted(acc.values(), key=lambda r: r.minutes, reverse=True)


def _round(v):
    return round(v, 4) if isinstance(v, float) else v
