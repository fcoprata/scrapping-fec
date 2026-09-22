import datetime as _dt
from typing import Dict, Iterable, List, Optional, Tuple

from scrapers.base import JsonApiScraper
from models.player_match_stats import (
    MatchAdvancedStats,
    PlayerMatchStats,
    Shot,
)

API = "https://api.sofascore.com/api/v1"

# SofaScore statistics key -> PlayerMatchStats attribute
_STAT_MAP = {
    "touches": "touches",
    "totalPass": "passes_total",
    "accuratePass": "passes_accurate",
    "keyPass": "key_passes",
    "totalLongBalls": "long_balls_total",
    "accurateLongBalls": "long_balls_accurate",
    "totalCross": "crosses_total",
    "accurateCross": "crosses_accurate",
    "totalOwnHalfPasses": "own_half_passes_total",
    "accurateOwnHalfPasses": "own_half_passes_accurate",
    "totalOppositionHalfPasses": "opp_half_passes_total",
    "accurateOppositionHalfPasses": "opp_half_passes_accurate",
    "possessionLostCtrl": "possession_lost",
    "ballRecovery": "ball_recovery",
    "ballCarriesCount": "ball_carries",
    "progressiveBallCarriesCount": "progressive_carries",
    "totalBallCarriesDistance": "carry_distance",
    "duelWon": "duels_won",
    "duelLost": "duels_lost",
    "aerialWon": "aerials_won",
    "interceptionWon": "interceptions",
    "totalClearance": "clearances",
    "fouls": "fouls",
    "totalShots": "shots_total",
    "goalAssist": "assists",
}


class SofaScoreScraper(JsonApiScraper):
    # ---- discovery -------------------------------------------------------
    def search_team(self, name: str) -> List[dict]:
        data = self._get_json(f"{API}/search/all?q={name}")
        out = []
        for r in data.get("results", []):
            if r.get("type") == "team":
                e = r["entity"]
                out.append({
                    "id": e["id"],
                    "name": e["name"],
                    "slug": e.get("slug"),
                    "country": (e.get("country") or {}).get("name"),
                })
        return out

    def get_team_seasons(self, team_id: int) -> List[dict]:
        data = self._get_json(f"{API}/team/{team_id}/team-statistics/seasons")
        out = []
        for uts in data.get("uniqueTournamentSeasons", []):
            ut = uts["uniqueTournament"]
            for s in uts.get("seasons", []):
                out.append({
                    "tournament_id": ut["id"],
                    "tournament": ut["name"],
                    "season_id": s["id"],
                    "season": s["name"],
                    "year": s.get("year"),
                })
        return out

    def get_team_players(self, team_id: int) -> List["Player"]:
        """Elenco oficial do clube via SofaScore com posições, camisa, idade, contrato e valor de mercado."""
        from models.player import Player

        try:
            data = self._get_json(f"{API}/team/{team_id}/players")
        except Exception:
            return []

        raw_players = data.get("players", [])
        out: List[Player] = []
        pos_map = {
            "G": "Goleiro",
            "D": "Defensor",
            "M": "Meia",
            "F": "Atacante",
        }
        ref_date = _dt.date.today()
        for item in raw_players:
            p = item.get("player") or {}
            pid = p.get("id")
            if not pid or not p.get("name"):
                continue

            dob_ts = p.get("dateOfBirthTimestamp")
            age = None
            if dob_ts:
                try:
                    dob = _dt.datetime.fromtimestamp(dob_ts).date()
                    age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
                except Exception:
                    pass

            contract_ts = p.get("contractUntilTimestamp")
            contract_until = None
            if contract_ts:
                try:
                    contract_until = _dt.datetime.fromtimestamp(contract_ts).strftime("%d/%m/%Y")
                except Exception:
                    pass

            val = (p.get("proposedMarketValueRaw") or {}).get("value") or p.get("proposedMarketValue")
            market_val = int(val) if val is not None else None

            jersey = p.get("shirtNumber") or p.get("jerseyNumber")
            jersey_str = str(jersey) if jersey is not None else None

            pos_code = p.get("position")
            pos_group = pos_map.get(pos_code, "Meia")
            details = p.get("positionsDetailed")
            pos_detail = details[0] if details and isinstance(details, list) else None

            country_name = (p.get("country") or {}).get("name") or "Brasil"

            out.append(
                Player(
                    player_id=str(pid),
                    slug=p.get("slug") or p.get("name", "").lower().replace(" ", "-"),
                    name=p.get("name"),
                    position=pos_group,
                    jersey_number=jersey_str,
                    age=age,
                    nationality=country_name,
                    market_value_eur=market_val,
                    photo_url=None,
                    profile_url=f"https://www.sofascore.com/player/{p.get('slug')}/{pid}" if p.get("slug") else "",
                    active=True,
                    position_detail=pos_detail,
                    contract_until=contract_until,
                )
            )
        return out

    # ---- upcoming fixtures ----------------------------------------------
    def get_next_events(self, team_id: int, max_pages: int = 2) -> List[dict]:
        """Upcoming (not yet played) fixtures for a team, soonest first."""
        events: Dict[int, dict] = {}
        for page in range(max_pages):
            try:
                data = self._get_json(f"{API}/team/{team_id}/events/next/{page}")
            except Exception:
                break
            page_events = data.get("events", [])
            if not page_events:
                break
            for e in page_events:
                events[e["id"]] = self._event_meta(e)
        return sorted(events.values(), key=lambda m: m.get("date") or "")

    # ---- standings --------------------------------------------------------
    def get_standings(self, tournament_id: int, season_id: int) -> List[dict]:
        """League table for a tournament/season (total standings)."""
        data = self._get_json(
            f"{API}/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        )
        rows = []
        for group in data.get("standings", []):
            for row in group.get("rows", []):
                team = row.get("team") or {}
                rows.append({
                    "position": row.get("position"),
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "played": row.get("matches"),
                    "wins": row.get("wins"),
                    "draws": row.get("draws"),
                    "losses": row.get("losses"),
                    "goals_for": row.get("scoresFor"),
                    "goals_against": row.get("scoresAgainst"),
                    "goal_diff": row.get("scoreDiffFormatted"),
                    "points": row.get("points"),
                })
        return sorted(rows, key=lambda r: r.get("position") or 999)

    # ---- match list ----------------------------------------------------
    def get_season_events(
        self,
        team_id: int,
        season_ids: Iterable[int],
        max_pages: int = 12,
        finished_only: bool = True,
    ) -> List[dict]:
        """Team match list filtered to the given SofaScore season ids."""
        wanted = {int(s) for s in season_ids}
        events: Dict[int, dict] = {}
        for page in range(max_pages):
            data = self._get_json(f"{API}/team/{team_id}/events/last/{page}")
            page_events = data.get("events", [])
            if not page_events:
                break
            matched_on_page = False
            for e in page_events:
                if (e.get("season") or {}).get("id") not in wanted:
                    continue
                matched_on_page = True
                if finished_only and (e.get("status") or {}).get("type") != "finished":
                    continue
                events[e["id"]] = self._event_meta(e)
            # last/N returns older-and-older pages; stop once a whole page has
            # nothing from the wanted seasons (we've paged past them).
            if not matched_on_page and events:
                break
        return sorted(events.values(), key=lambda m: m.get("date") or "")

    @staticmethod
    def _event_meta(e: dict) -> dict:
        ts = e.get("startTimestamp")
        date = _dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else None
        rnd = (e.get("roundInfo") or {}).get("round")
        return {
            "event_id": e["id"],
            "date": date,
            "competition": (e.get("tournament") or {}).get("name"),
            "season": (e.get("season") or {}).get("name"),
            "season_id": (e.get("season") or {}).get("id"),
            "round": str(rnd) if rnd is not None else None,
            "home_team": e["homeTeam"]["name"],
            "away_team": e["awayTeam"]["name"],
            "home_id": e["homeTeam"]["id"],
            "away_id": e["awayTeam"]["id"],
        }

    # ---- per-match advanced stats ------------------------------------
    def get_match_advanced(self, meta: dict) -> Optional[MatchAdvancedStats]:
        event_id = meta["event_id"]
        try:
            lineups = self._get_json(f"{API}/event/{event_id}/lineups")
        except Exception:
            return None

        shots = self._get_shots(event_id)
        xg_by_player = _sum_xg_by_player(shots)
        goals_by_player = _count_goals_by_player(shots)

        players: List[PlayerMatchStats] = []
        for side in ("home", "away"):
            team_name = meta["home_team"] if side == "home" else meta["away_team"]
            for entry in (lineups.get(side) or {}).get("players", []):
                pms = self._parse_player(entry, event_id, side, team_name)
                if pms is None:
                    continue
                pms.xg = round(xg_by_player.get(pms.player_id, 0.0), 4)
                pms.goals = goals_by_player.get(pms.player_id, 0)
                players.append(pms)

        xg_home, xg_away, xgot_home, xgot_away = self._match_xg(event_id, shots)

        return MatchAdvancedStats(
            event_id=event_id,
            home_team=meta["home_team"],
            away_team=meta["away_team"],
            competition=meta.get("competition"),
            season=meta.get("season"),
            round=meta.get("round"),
            date=meta.get("date"),
            xg_home=xg_home,
            xg_away=xg_away,
            xgot_home=xgot_home,
            xgot_away=xgot_away,
            players=players,
            shots=shots,
        )

    def _parse_player(
        self, entry: dict, event_id: int, side: str, team_name: str
    ) -> Optional[PlayerMatchStats]:
        player = entry.get("player") or {}
        pid = player.get("id")
        if pid is None:
            return None
        stats = entry.get("statistics") or {}
        pms = PlayerMatchStats(
            event_id=event_id,
            player_id=str(pid),
            name=player.get("name", ""),
            team=side,
            team_name=team_name,
            is_starter=not entry.get("substitute", False),
            position=entry.get("position"),
            minutes_played=int(stats.get("minutesPlayed", 0) or 0),
            rating=_as_float(stats.get("rating")),
            xa=round(_as_float(stats.get("expectedAssists")) or 0.0, 4),
        )
        for key, attr in _STAT_MAP.items():
            if key in stats and stats[key] is not None:
                cur = getattr(pms, attr)
                setattr(pms, attr, type(cur)(stats[key]))
        return pms

    def _get_shots(self, event_id: int) -> List[Shot]:
        try:
            data = self._get_json(f"{API}/event/{event_id}/shotmap")
        except Exception:
            return []
        shots: List[Shot] = []
        for s in data.get("shotmap", []):
            p = s.get("player") or {}
            draw = s.get("draw") or {}
            start = draw.get("start") or {}
            end = draw.get("end") or {}
            pc = s.get("playerCoordinates") or {}

            # x = lateral width (0-100), y = distance from goal (0-100)
            sh_x = _as_float(start.get("x")) if start.get("x") is not None else _as_float(pc.get("y"))
            sh_y = _as_float(start.get("y")) if start.get("y") is not None else _as_float(pc.get("x"))
            end_x = _as_float(end.get("x"))
            end_y = _as_float(end.get("y"))

            shots.append(Shot(
                minute=s.get("time"),
                player_id=str(p.get("id", "")),
                player_name=p.get("name", ""),
                is_home=bool(s.get("isHome")),
                xg=_as_float(s.get("xg")),
                xgot=_as_float(s.get("xgot")),
                shot_type=s.get("shotType"),
                situation=s.get("situation"),
                body_part=s.get("bodyPart"),
                is_goal=s.get("shotType") == "goal",
                x=sh_x,
                y=sh_y,
                end_x=end_x,
                end_y=end_y,
            ))
        return shots

    def _match_xg(
        self, event_id: int, shots: List[Shot]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        # Prefer the official aggregate from the statistics endpoint.
        try:
            data = self._get_json(f"{API}/event/{event_id}/statistics")
        except Exception:
            data = {}
        xg_home = xg_away = xgot_home = xgot_away = None
        for period in data.get("statistics", []):
            if period.get("period") != "ALL":
                continue
            for group in period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    name = item.get("name")
                    if name == "Expected goals":
                        xg_home, xg_away = _as_float(item.get("home")), _as_float(item.get("away"))
                    elif name == "Expected goals on target":
                        xgot_home, xgot_away = _as_float(item.get("home")), _as_float(item.get("away"))
        if xg_home is None and shots:  # fallback: sum shotmap
            xg_home = round(sum(s.xg or 0 for s in shots if s.is_home), 2)
            xg_away = round(sum(s.xg or 0 for s in shots if not s.is_home), 2)
        return xg_home, xg_away, xgot_home, xgot_away


def _as_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sum_xg_by_player(shots: List[Shot]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for s in shots:
        if s.player_id and s.xg:
            out[s.player_id] = out.get(s.player_id, 0.0) + s.xg
    return out


def _count_goals_by_player(shots: List[Shot]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for s in shots:
        if s.is_goal and s.player_id:
            out[s.player_id] = out.get(s.player_id, 0) + 1
    return out
