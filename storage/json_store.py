import json
import os
import time
from dataclasses import asdict
from typing import List
from models.match import Match
from models.match_stats import MatchStats
from models.player import Player
from models.player_stats import PlayerAdvancedSeason, PlayerSeasonStats
from models.player_match_stats import MatchAdvancedStats
from storage import db as _db


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Pastas dentro de ~/Documents costumam ser sincronizadas (iCloud Drive), então
# um arquivo que acabamos de salvar pode ser lido de volta truncado enquanto o
# sync ainda está materializando o conteúdo em disco. Isso já derrubou builds
# do pipeline em lote (JSONDecodeError logo após um save bem-sucedido). Como
# sempre lemos algo que este mesmo processo escreveu por completo segundos
# antes, um retry curto resolve — não é um dado realmente corrompido.
_READ_RETRIES = 3
_READ_RETRY_DELAY_S = 0.4


def _read_json(path: str):
    last_err = None
    for attempt in range(_READ_RETRIES):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            last_err = e
            if attempt < _READ_RETRIES - 1:
                time.sleep(_READ_RETRY_DELAY_S)
    raise last_err


class JsonStore:
    def __init__(self):
        os.makedirs(_DATA_DIR, exist_ok=True)

    def save(self, team: str, matches: List[Match]) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches.json"))
        rows = [asdict(m) for m in matches]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        _db.upsert_raw_snapshot("matches", team, "matches", rows)
        return path

    def save_stats(self, team: str, stats: List[MatchStats]) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_stats.json"))
        rows = [asdict(s) for s in stats]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        _db.upsert_raw_snapshot("stats", team, "stats", rows)
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
        _db.upsert_raw_snapshot("squad", team, "squad", payload)
        return path

    def save_player_stats(self, team: str, stats: List[PlayerSeasonStats], season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_stats.json"))
        payload = {
            "season_year": season_year,
            "players": [asdict(s) for s in stats],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _db.upsert_raw_snapshot("player_stats", team, "player_stats", payload)
        return path

    def load_squad(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_squad.json"))
        if not os.path.exists(path):
            return {"season_year": "", "epoca_id": "", "players": []}
        return _read_json(path)

    def load(self, team: str) -> List[dict]:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches.json"))
        if not os.path.exists(path):
            return []
        return _read_json(path)

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
        _db.upsert_raw_snapshot("sofascore", team, "advanced_matches", payload)
        return path

    def load_match_advanced(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_matches.json"))
        if not os.path.exists(path):
            return {"season_year": "", "matches": []}
        return _read_json(path)

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
        _db.upsert_raw_snapshot("sofascore", team, "advanced_season", payload)
        return path

    def load_advanced_season(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_advanced_season.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        return _read_json(path)

    # ---- raw source loaders (resolve layer) -------------------------
    def load_ogol_matches(self, team: str) -> list:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_ogol_matches.json"))
        if not os.path.exists(path):
            return []
        return _read_json(path)

    def load_ogol_stats(self, team: str) -> list:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_ogol_stats.json"))
        if not os.path.exists(path):
            return []
        return _read_json(path)

    def load_player_stats(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_stats.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        return _read_json(path)

    # ---- resolve layer: players_master / matches_master ------------
    def save_players_master(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_players_master.json"))
        payload = {"season_year": season_year, "players": rows}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _db.upsert_players_master(team, season_year, rows)
        return path

    def load_players_master(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_players_master.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        return _read_json(path)

    def save_matches_master(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches_master.json"))
        payload = {"season_year": season_year, "matches": rows}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _db.upsert_matches_master(team, season_year, rows)
        return path

    def load_matches_master(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_matches_master.json"))
        if not os.path.exists(path):
            return {"season_year": "", "matches": []}
        return _read_json(path)

    # ---- derive layer: player_metrics / team_metrics / match_reports ----
    def save_player_metrics(self, team: str, rows: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_metrics.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, "players": rows}, f, ensure_ascii=False, indent=2)

        in_squad_keys = {p["key"] for p in self.load_players_master(team).get("players", []) if p.get("in_squad")}
        db_rows = [{**r, "in_current_squad": r.get("key") in in_squad_keys} for r in rows]
        _db.upsert_player_season_stats(team, season_year, db_rows)
        return path

    def load_player_metrics(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_player_metrics.json"))
        if not os.path.exists(path):
            return {"season_year": "", "players": []}
        return _read_json(path)

    def save_team_metrics(self, team: str, data: dict, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_team_metrics.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, **data}, f, ensure_ascii=False, indent=2)
        _db.upsert_team_metrics(team, season_year, data)
        return path

    def load_team_metrics(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_team_metrics.json"))
        if not os.path.exists(path):
            return {}
        return _read_json(path)

    def save_match_reports(self, team: str, reports: list, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_match_reports.json"))
        payload = {"season_year": season_year, "reports": reports}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _db.upsert_match_reports(team, season_year, payload)
        return path

    def load_match_reports(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_match_reports.json"))
        if not os.path.exists(path):
            return {"season_year": "", "reports": []}
        return _read_json(path)

    def save_analysis(self, team: str, data: dict, season_year: str) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_analysis.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"season_year": season_year, **data}, f, ensure_ascii=False, indent=2)
        _db.upsert_team_analysis(team, season_year, data)
        return path

    def load_analysis(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_analysis.json"))
        if not os.path.exists(path):
            return {}
        return _read_json(path)

    # ---- fixtures / standings ---------------------------------------
    def save_fixtures(self, team: str, rows: list) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_fixtures.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fixtures": rows}, f, ensure_ascii=False, indent=2)
        _db.upsert_raw_snapshot("sofascore", team, "fixtures", rows)
        return path

    def load_fixtures(self, team: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"{team}_fixtures.json"))
        if not os.path.exists(path):
            return {"fixtures": []}
        return _read_json(path)

    def save_standings(self, key: str, rows: list) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"standings_{key}.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"standings": rows}, f, ensure_ascii=False, indent=2)
        season_label = key.replace("_", "-")
        comp_key = season_label.rsplit("-", 1)[0]
        from config import TEAMS
        team_key_by_sofascore_id = {
            (v.get("sofascore") or {}).get("team_id"): k
            for k, v in TEAMS.items() if (v.get("sofascore") or {}).get("team_id")
        }
        _db.upsert_standings(comp_key, season_label, rows, team_key_by_sofascore_id)
        return path

    def load_standings(self, key: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"standings_{key}.json"))
        if not os.path.exists(path):
            return {"standings": []}
        return _read_json(path)

    # ---- league-wide (todos os clubes) --------------------------------
    def save_league_player_metrics(self, data: dict) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, "league_player_metrics.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _db.upsert_league_player_metrics(data)
        return path

    def load_league_player_metrics(self) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, "league_player_metrics.json"))
        if not os.path.exists(path):
            return {"generated_at": "", "players": []}
        return _read_json(path)

    # ---- UFMG statistical & probabilistic data ----------------------
    def save_ufmg_data(self, key: str, data: dict) -> str:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"ufmg_{key}.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _db.upsert_ufmg(key, data)
        return path

    def load_ufmg_data(self, key: str) -> dict:
        path = os.path.abspath(os.path.join(_DATA_DIR, f"ufmg_{key}.json"))
        if not os.path.exists(path):
            return {}
        return _read_json(path)


def _advanced_row_dict(row: PlayerAdvancedSeason) -> dict:
    d = asdict(row)
    # surface computed helpers so the dashboard doesn't recompute them
    d["pass_accuracy"] = row.pass_accuracy
    d["touches_per90"] = row.touches_per90
    d["xg_per90"] = row.xg_per90
    return d
