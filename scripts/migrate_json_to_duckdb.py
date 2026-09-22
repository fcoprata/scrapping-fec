"""Backfill o DuckDB (storage/db.py) a partir dos data/*.json já coletados
pelos 40 clubes, sem precisar re-rodar scraping.

Idempotente — reaproveita os mesmos upserts que o pipeline ao vivo usa
(storage/json_store.py já chama db.py em todo save_* novo daqui pra frente;
este script cobre o histórico que já existia em disco antes da migração — e
serve de auto-bootstrap: o DuckDB vive fora do repo (~/.local/share, ver
storage/db.py), então não existe no deploy do Streamlit Community Cloud, que
só tem o que está no git. `views/scout.py` chama `migrate()` na primeira vez
que o banco estiver vazio lá, reconstruindo a partir do JSON commitado.

Uso via CLI: python scripts/migrate_json_to_duckdb.py
"""

import sys

from config import TEAMS, COMPETITIONS
from storage import db
from storage.json_store import JsonStore


def migrate(store: JsonStore = None, verbose: bool = True) -> dict:
    store = store or JsonStore()
    db.sync_config(TEAMS, COMPETITIONS)

    n_players_master = n_matches_master = n_player_metrics = 0
    n_team_metrics = n_match_reports = n_analysis = 0

    for team_key in TEAMS:
        pm = store.load_players_master(team_key)
        if pm.get("players"):
            db.upsert_players_master(team_key, pm.get("season_year", ""), pm["players"])
            n_players_master += 1

        mm = store.load_matches_master(team_key)
        if mm.get("matches"):
            db.upsert_matches_master(team_key, mm.get("season_year", ""), mm["matches"])
            n_matches_master += 1

        pmet = store.load_player_metrics(team_key)
        if pmet.get("players"):
            in_squad_keys = {p["key"] for p in pm.get("players", []) if p.get("in_squad")}
            db_rows = [{**r, "in_current_squad": r.get("key") in in_squad_keys} for r in pmet["players"]]
            db.upsert_player_season_stats(team_key, pmet.get("season_year", ""), db_rows)
            n_player_metrics += 1

        tmet = store.load_team_metrics(team_key)
        if tmet:
            db.upsert_team_metrics(team_key, tmet.get("season_year", ""), tmet)
            n_team_metrics += 1

        mrep = store.load_match_reports(team_key)
        if mrep.get("reports"):
            db.upsert_match_reports(team_key, mrep.get("season_year", ""), mrep)
            n_match_reports += 1

        an = store.load_analysis(team_key)
        if an:
            db.upsert_team_analysis(team_key, an.get("season_year", ""), an)
            n_analysis += 1

        # raw snapshots — squad/player_stats/advanced já viram raw_snapshots
        # automaticamente da próxima vez que forem salvos; aqui cobrimos o
        # que já está em disco pra não perder histórico.
        squad = store.load_squad(team_key)
        if squad.get("players"):
            db.upsert_raw_snapshot("squad", team_key, "squad", squad)
        pstats = store.load_player_stats(team_key)
        if pstats.get("players"):
            db.upsert_raw_snapshot("player_stats", team_key, "player_stats", pstats)
        adv_m = store.load_match_advanced(team_key)
        if adv_m.get("matches"):
            db.upsert_raw_snapshot("sofascore", team_key, "advanced_matches", adv_m)
        adv_s = store.load_advanced_season(team_key)
        if adv_s.get("players"):
            db.upsert_raw_snapshot("sofascore", team_key, "advanced_season", adv_s)

    for key in ("serie_a_2026", "serie_b_2026"):
        standings = store.load_standings(key)
        if standings.get("standings"):
            season_label = key.replace("_", "-")
            comp_key = season_label.rsplit("-", 1)[0]
            team_key_by_sofascore_id = {
                (v.get("sofascore") or {}).get("team_id"): k
                for k, v in TEAMS.items() if (v.get("sofascore") or {}).get("team_id")
            }
            db.upsert_standings(comp_key, season_label, standings["standings"], team_key_by_sofascore_id)

        ufmg = store.load_ufmg_data(key)
        if ufmg:
            db.upsert_ufmg(key, ufmg)

    league = store.load_league_player_metrics()
    if league.get("players"):
        db.upsert_league_player_metrics(league)

    stats = {
        "players_master": n_players_master, "matches_master": n_matches_master,
        "player_metrics": n_player_metrics, "team_metrics": n_team_metrics,
        "match_reports": n_match_reports, "analysis": n_analysis, "teams_total": len(TEAMS),
    }
    if verbose:
        for k, v in stats.items():
            if k != "teams_total":
                print(f"{k}: {v}/{len(TEAMS)} clubes")
        conn = db.get_conn()
        for t in ("teams", "competitions", "players", "matches", "standings", "raw_snapshots"):
            n = conn.execute(f"select count(*) from {t}").fetchone()[0]
            print(f"  {t}: {n} linhas no banco")
    return stats


if __name__ == "__main__":
    migrate()
    sys.exit(0)
