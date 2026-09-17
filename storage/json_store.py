import json
import os
from dataclasses import asdict
from typing import List
from models.match import Match
from models.match_stats import MatchStats
from models.player import Player
from models.player_stats import PlayerAdvancedSeason, PlayerSeasonStats
from models.player_match_stats import MatchAdvancedStats


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class JsonStore:
    def __init__(self):
        os.makedirs(_DATA_DIR, exist_ok=True)

    def save(self, team: str, matches: List[Match]) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(m) for m in matches], f, ensure_ascii=False, indent=2)
        return path

    def save_stats(self, team: str, stats: List[MatchStats]) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_stats.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in stats], f, ensure_ascii=False, indent=2)
        return path

    def save_squad(self, team: str, players: List[Player], season_year: str, epoca_id: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_squad.json"))
        payload = {
            "season_year": season_year,
            "epoca_id": epoca_id,
            "players": [asdict(p) for p in players],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def save_player_stats(self, team: str, stats: List[PlayerSeasonStats], season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_stats.json"))
        payload = {
            "season_year": season_year,
            "players": [asdict(s) for s in stats],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def load_squad(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_squad.json"))
        if not os.path.exists(path):
            return {"season_year": "", "epoca_id": "", "players": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load(self, team: str) -> List[dict]:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches.json"))
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- SofaScore advanced stats ------------------------------------
    def save_match_advanced(
        self, team: str, matches: List[MatchAdvancedStats], season_year: str
    ) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_matches.json"))
        payload = {
            "season_year": season_year,
            "matches": [asdict(m) for m in matches],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def load_match_advanced(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_matches.json"))
        if not os.path.exists(path):
            return {"season_year": "", "matches": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_advanced_season(
        self, team: str, rows: List[PlayerAdvancedSeason], season_year: str
    ) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_season.json"))
        payload = {
            "season_year": season_year,
            "players": [_advanced_row_dict(r) for r in rows],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def load_advanced_season(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_season.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- raw source loaders (resolve layer) -------------------------
    def load_ogol_matches(self, team: str) -> list:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_ogol_matches.json"))
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_ogol_stats(self, team: str) -> list:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_ogol_stats.json"))
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_player_stats(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_stats.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- resolve layer: players_master / matches_master ------------
    def save_players_master(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_players_master.json"))
        payload = {"season_year": season_year, "players": rows}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def load_players_master(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_players_master.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_matches_master(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches_master.json"))
        payload = {"season_year": season_year, "matches": rows}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def load_matches_master(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches_master.json"))
        if not os.path.exists(path):
            return {"season_year": "", "matches": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- derive layer: player_metrics / team_metrics / match_reports ----
    def save_player_metrics(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_metrics.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, "players": rows}, f, ensure_ascii=False, indent=2)
        return path

    def load_player_metrics(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_metrics.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_team_metrics(self, team: str, data: dict, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_team_metrics.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, **data}, f, ensure_ascii=False, indent=2)
        return path

    def load_team_metrics(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_team_metrics.json"))
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_match_reports(self, team: str, reports: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_match_reports.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, "reports": reports}, f, ensure_ascii=False, indent=2)
        return path

    def load_match_reports(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_match_reports.json"))
        if not os.path.exists(path):
            return {"season_year": "", "reports": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_analysis(self, team: str, data: dict, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_analysis.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, **data}, f, ensure_ascii=False, indent=2)
        return path

    def load_analysis(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_analysis.json"))
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- fixtures / standings ---------------------------------------
    def save_fixtures(self, team: str, rows: list) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_fixtures.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fixtures": rows}, f, ensure_ascii=False, indent=2)
        return path

    def load_fixtures(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_fixtures.json"))
        if not os.path.exists(path):
            return {"fixtures": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_standings(self, key: str, rows: list) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"standings_{key}.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"standings": rows}, f, ensure_ascii=False, indent=2)
        return path

    def load_standings(self, key: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"standings_{key}.json"))
        if not os.path.exists(path):
            return {"standings": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- UFMG statistical & probabilistic data ----------------------
    def save_ufmg_data(self, key: str, data: dict) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"ufmg_{key}.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load_ufmg_data(self, key: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"ufmg_{key}.json"))
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)


def _advanced_row_dict(row: PlayerAdvancedSeason) -> dict:
    d = asdict(row)
    # surface computed helpers so the dashboard doesn't recompute them
    d["pass_accuracy"] = row.pass_accuracy
    d["touches_per90"] = row.touches_per90
    d["xg_per90"] = row.xg_per90
    return d
