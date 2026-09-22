"""DuckDB storage layer — fonte de verdade normalizada, com constraint em vez
de fallback silencioso (a causa dos bugs de pontos/elenco corrigidos em
resolve/master.py e analysis/relegation.py).

`data/*.json` continua existindo como export gerado a partir daqui, pra não
quebrar as ~40 leituras em views/_common.py (load_json/load_team_json) que
esperam esse formato. storage/json_store.py chama as funções deste módulo logo
depois de escrever cada JSON (best-effort: falha de banco loga warning e não
derruba o pipeline — o JSON continua sendo a garantia mínima de disponibilidade
enquanto a migração amadurece).

Tabelas de identidade (teams/competitions/players/matches/standings) são
totalmente relacionais com PK/UNIQUE reais. `player_season_stats` também é
colunar (não payload JSON) — é o dataset que alimenta o scout, e percentil/
rank por posição é exatamente o tipo de query que DuckDB faz bem
(`query_league_player_metrics`, via PERCENT_RANK() OVER, sem pandas). As
camadas mais voláteis (team_metrics, match_reports, analysis) ficam como
payload JSON indexado pela chave relacional — evitam reescrever DDL toda vez
que models/derived.py ganha um campo novo ali, sem abrir mão de constraint na
parte que causava os bugs (join de identidade).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

import duckdb

logger = logging.getLogger(__name__)

# Fica fora de qualquer pasta sincronizada por iCloud (~/Documents neste Mac
# usa Desktop & Documents Folders sync, que já causou JSONDecodeError por
# write parcial no JsonStore — não repetir o problema com o arquivo do banco).
_DB_DIR = os.path.expanduser("~/.local/share/extract_futebol_info")
DB_PATH = os.path.join(_DB_DIR, "futebol.duckdb")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    team_key VARCHAR PRIMARY KEY,
    name VARCHAR,
    division VARCHAR,
    state VARCHAR,
    sofascore_team_id BIGINT UNIQUE,
    transfermarkt_id BIGINT,
    ogol_slug VARCHAR
);

CREATE TABLE IF NOT EXISTS competitions (
    comp_key VARCHAR PRIMARY KEY,
    name VARCHAR,
    sofascore_tournament_id BIGINT UNIQUE
);

CREATE TABLE IF NOT EXISTS team_competition_seasons (
    team_key VARCHAR,
    comp_key VARCHAR,
    season_label VARCHAR,
    sofascore_season_id BIGINT,
    PRIMARY KEY (team_key, comp_key, season_label)
);

CREATE TABLE IF NOT EXISTS players (
    player_key VARCHAR PRIMARY KEY,
    name VARCHAR,
    nationality VARCHAR,
    sofascore_id VARCHAR,
    ogol_id VARCHAR
);

CREATE TABLE IF NOT EXISTS player_team_season (
    player_key VARCHAR,
    team_key VARCHAR,
    season_label VARCHAR,
    jersey_number INTEGER,
    age INTEGER,
    position_group VARCHAR,
    position_detail VARCHAR,
    market_value_eur BIGINT,
    contract_until VARCHAR,
    active BOOLEAN,
    in_squad BOOLEAN,
    in_ogol_stats BOOLEAN,
    in_advanced BOOLEAN,
    PRIMARY KEY (player_key, team_key, season_label)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id VARCHAR PRIMARY KEY,
    team_key VARCHAR,
    season_label VARCHAR,
    competition VARCHAR,
    round VARCHAR,
    date VARCHAR,
    is_home BOOLEAN,
    opponent VARCHAR,
    score VARCHAR,
    goals_for INTEGER,
    goals_against INTEGER,
    points INTEGER,
    xg_for DOUBLE,
    xg_against DOUBLE,
    xgot_for DOUBLE,
    xgot_against DOUBLE,
    tm_matched BOOLEAN,
    ogol_matched BOOLEAN,
    attendance VARCHAR,
    referee VARCHAR,
    source_event_id VARCHAR
);

CREATE TABLE IF NOT EXISTS standings (
    comp_key VARCHAR,
    season_label VARCHAR,
    team_id BIGINT,
    team_key VARCHAR,
    team_name VARCHAR,
    position INTEGER,
    played INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    goal_diff VARCHAR,
    points INTEGER,
    fetched_at VARCHAR,
    PRIMARY KEY (comp_key, season_label, team_id)
);

-- Colunas tipadas (não payload JSON) -- é exatamente o formato analítico que
-- DuckDB é bom em consultar (percentil/rank via SQL em vez de pandas em
-- Python a cada carregamento de página). `key` é o nome normalizado do
-- jogador (mesma chave usada em players_master) -- não temos sofascore_id
-- aqui porque a camada Derive (models/derived.py) não o carrega adiante.
-- `in_current_squad` é copiado de players_master.in_squad no momento do
-- upsert -- é a chave pra fundir o jogador sob o clube atual quando ele
-- troca de time no meio da temporada (ver query_league_player_metrics).
CREATE TABLE IF NOT EXISTS player_season_stats (
    key VARCHAR,
    team_key VARCHAR,
    season_label VARCHAR,
    name VARCHAR,
    position_group VARCHAR,
    minutes INTEGER,
    matches INTEGER,
    starts INTEGER,
    sub_apps INTEGER,
    market_value_eur BIGINT,
    age INTEGER,
    contract_until VARCHAR,
    active BOOLEAN,
    jersey_number VARCHAR,
    nationality VARCHAR,
    in_current_squad BOOLEAN,
    goals_p90 DOUBLE, xg_p90 DOUBLE, assists_p90 DOUBLE, xa_p90 DOUBLE, shots_p90 DOUBLE,
    touches_p90 DOUBLE, passes_p90 DOUBLE, key_passes_p90 DOUBLE, long_balls_p90 DOUBLE,
    crosses_p90 DOUBLE, poss_lost_p90 DOUBLE, ball_recovery_p90 DOUBLE, progressive_carries_p90 DOUBLE,
    duels_won_p90 DOUBLE, aerials_won_p90 DOUBLE, interceptions_p90 DOUBLE, clearances_p90 DOUBLE,
    fouls_p90 DOUBLE, accurate_passes_p90 DOUBLE,
    pass_accuracy DOUBLE, long_ball_accuracy DOUBLE, cross_accuracy DOUBLE, duel_win_pct DOUBLE,
    turnover_rate DOUBLE, opp_half_pass_share DOUBLE,
    tier VARCHAR, goals INTEGER, assists INTEGER, goals_conceded INTEGER, avg_rating DOUBLE,
    PRIMARY KEY (key, team_key, season_label)
);

CREATE TABLE IF NOT EXISTS team_metrics (
    team_key VARCHAR,
    season_label VARCHAR,
    payload JSON,
    PRIMARY KEY (team_key, season_label)
);

CREATE TABLE IF NOT EXISTS match_reports (
    team_key VARCHAR,
    season_label VARCHAR,
    payload JSON,
    PRIMARY KEY (team_key, season_label)
);

CREATE TABLE IF NOT EXISTS team_analysis (
    team_key VARCHAR,
    season_label VARCHAR,
    payload JSON,
    PRIMARY KEY (team_key, season_label)
);

CREATE TABLE IF NOT EXISTS ufmg_probabilities (
    comp_key VARCHAR PRIMARY KEY,
    payload JSON,
    fetched_at VARCHAR
);

CREATE TABLE IF NOT EXISTS league_player_metrics (
    id INTEGER PRIMARY KEY DEFAULT 1,
    generated_at VARCHAR,
    payload JSON
);

CREATE TABLE IF NOT EXISTS raw_snapshots (
    source VARCHAR,
    team_key VARCHAR,
    kind VARCHAR,
    fetched_at VARCHAR,
    payload JSON,
    PRIMARY KEY (source, team_key, kind)
);
"""

_conn = None


def get_conn(read_only: bool = False):
    """Conexão DuckDB do processo (singleton). DuckDB só permite 1 conexão de
    escrita por arquivo por vez — a esteira (main.py) escreve, o dashboard
    Streamlit (scout) deve abrir com read_only=True pra nunca disputar lock
    com um --batch-full rodando em paralelo."""
    global _conn
    os.makedirs(_DB_DIR, exist_ok=True)
    if _conn is None:
        _conn = duckdb.connect(DB_PATH, read_only=read_only)
        if not read_only:
            _conn.execute(_SCHEMA)
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(fn):
    """Roda um upsert sem derrubar o pipeline de JSON se o banco falhar —
    JSON continua sendo escrito de qualquer forma (ver storage/json_store.py)."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning("db upsert falhou em %s: %s: %s", fn.__name__, type(e).__name__, e)
    return wrapper


# ---------------------------------------------------------------------------
# config.py -> teams / competitions / team_competition_seasons
# ---------------------------------------------------------------------------
@_safe
def sync_config(teams: dict, competitions: dict) -> None:
    conn = get_conn()
    for key, cfg in teams.items():
        sf = cfg.get("sofascore") or {}
        conn.execute(
            """INSERT INTO teams (team_key, name, division, state, sofascore_team_id, transfermarkt_id, ogol_slug)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (team_key) DO UPDATE SET
                   name = excluded.name, division = excluded.division, state = excluded.state,
                   sofascore_team_id = excluded.sofascore_team_id,
                   transfermarkt_id = excluded.transfermarkt_id, ogol_slug = excluded.ogol_slug""",
            [key, cfg.get("name"), cfg.get("division"), cfg.get("state"),
             sf.get("team_id"), (cfg.get("transfermarkt") or {}).get("id"),
             (cfg.get("ogol") or {}).get("slug")],
        )
        for season_label, s in (sf.get("seasons") or {}).items():
            comp_key = season_label.rsplit("-", 1)[0] if "-" in season_label else season_label
            conn.execute(
                """INSERT INTO team_competition_seasons (team_key, comp_key, season_label, sofascore_season_id)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (team_key, comp_key, season_label) DO UPDATE SET
                       sofascore_season_id = excluded.sofascore_season_id""",
                [key, comp_key, season_label, s.get("season_id")],
            )
    for key, cfg in competitions.items():
        conn.execute(
            """INSERT INTO competitions (comp_key, name, sofascore_tournament_id) VALUES (?, ?, ?)
               ON CONFLICT (comp_key) DO UPDATE SET
                   name = excluded.name, sofascore_tournament_id = excluded.sofascore_tournament_id""",
            [key, cfg.get("name"), cfg.get("sofascore_tournament_id")],
        )


def get_comp_key_for_tournament(sofascore_tournament_id) -> Optional[str]:
    """Comp_key já cadastrado pra esse tournament_id, se houver — usado antes de
    slugificar um nome novo, pra não duplicar linha (competitions tem UNIQUE em
    sofascore_tournament_id; ON CONFLICT só cobre a PK comp_key, não essa outra
    coluna, então inserir um comp_key novo pro mesmo tournament_id derruba a
    constraint em vez de atualizar)."""
    try:
        conn = get_conn()
    except Exception as e:
        logger.warning("get_comp_key_for_tournament: banco indisponível: %s", e)
        return None
    row = conn.execute(
        "SELECT comp_key FROM competitions WHERE sofascore_tournament_id = ?", [sofascore_tournament_id]
    ).fetchone()
    return row[0] if row else None


@_safe
def upsert_competition(comp_key: str, name: str, sofascore_tournament_id) -> None:
    get_conn().execute(
        """INSERT INTO competitions (comp_key, name, sofascore_tournament_id) VALUES (?, ?, ?)
           ON CONFLICT (comp_key) DO UPDATE SET
               name = excluded.name, sofascore_tournament_id = excluded.sofascore_tournament_id""",
        [comp_key, name, sofascore_tournament_id],
    )


@_safe
def upsert_team_competition_season(team_key: str, comp_key: str, season_label: str, sofascore_season_id) -> None:
    get_conn().execute(
        """INSERT INTO team_competition_seasons (team_key, comp_key, season_label, sofascore_season_id)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (team_key, comp_key, season_label) DO UPDATE SET
               sofascore_season_id = excluded.sofascore_season_id""",
        [team_key, comp_key, season_label, sofascore_season_id],
    )


# ---------------------------------------------------------------------------
# players_master / matches_master
# ---------------------------------------------------------------------------
@_safe
def upsert_players_master(team_key: str, season_label: str, rows: list) -> None:
    conn = get_conn()
    for p in rows:
        player_key = p.get("sofascore_id") or p.get("ogol_id") or p.get("key")
        if not player_key:
            continue
        player_key = str(player_key)
        conn.execute(
            """INSERT INTO players (player_key, name, nationality, sofascore_id, ogol_id) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (player_key) DO UPDATE SET
                   name = excluded.name, nationality = excluded.nationality,
                   sofascore_id = excluded.sofascore_id, ogol_id = excluded.ogol_id""",
            [player_key, p.get("name"), p.get("nationality"),
             str(p.get("sofascore_id")) if p.get("sofascore_id") else None,
             str(p.get("ogol_id")) if p.get("ogol_id") else None],
        )
        conn.execute(
            """INSERT INTO player_team_season
                   (player_key, team_key, season_label, jersey_number, age, position_group, position_detail,
                    market_value_eur, contract_until, active, in_squad, in_ogol_stats, in_advanced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (player_key, team_key, season_label) DO UPDATE SET
                   jersey_number = excluded.jersey_number, age = excluded.age,
                   position_group = excluded.position_group, position_detail = excluded.position_detail,
                   market_value_eur = excluded.market_value_eur, contract_until = excluded.contract_until,
                   active = excluded.active, in_squad = excluded.in_squad,
                   in_ogol_stats = excluded.in_ogol_stats, in_advanced = excluded.in_advanced""",
            [player_key, team_key, season_label, p.get("jersey_number"), p.get("age"),
             p.get("position_group"), p.get("position_detail"), p.get("market_value_eur"),
             p.get("contract_until"), p.get("active"), p.get("in_squad"),
             p.get("in_ogol_stats"), p.get("in_advanced")],
        )


@_safe
def upsert_matches_master(team_key: str, season_label: str, rows: list) -> None:
    conn = get_conn()
    for m in rows:
        event_id = m.get("event_id") or f"{m.get('date')}|{m.get('opponent')}"
        match_id = f"{team_key}:{event_id}"
        conn.execute(
            """INSERT INTO matches (match_id, team_key, season_label, competition, round, date, is_home,
                    opponent, score, goals_for, goals_against, points, xg_for, xg_against, xgot_for,
                    xgot_against, tm_matched, ogol_matched, attendance, referee, source_event_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (match_id) DO UPDATE SET
                   competition = excluded.competition, round = excluded.round, date = excluded.date,
                   is_home = excluded.is_home, opponent = excluded.opponent, score = excluded.score,
                   goals_for = excluded.goals_for, goals_against = excluded.goals_against,
                   points = excluded.points, xg_for = excluded.xg_for, xg_against = excluded.xg_against,
                   xgot_for = excluded.xgot_for, xgot_against = excluded.xgot_against,
                   tm_matched = excluded.tm_matched, ogol_matched = excluded.ogol_matched,
                   attendance = excluded.attendance, referee = excluded.referee""",
            [match_id, team_key, season_label, m.get("competition"), m.get("round"), m.get("date"),
             m.get("is_home"), m.get("opponent"), m.get("score"), m.get("goals_for"), m.get("goals_against"),
             m.get("points"), m.get("xg_for"), m.get("xg_against"), m.get("xgot_for"), m.get("xgot_against"),
             m.get("tm_matched"), m.get("ogol_matched"), m.get("attendance"), m.get("referee"), event_id],
        )


# ---------------------------------------------------------------------------
# standings — fonte única de pontos/posição oficial
# ---------------------------------------------------------------------------
@_safe
def upsert_standings(comp_key: str, season_label: str, rows: list, team_key_by_sofascore_id: Optional[dict] = None) -> None:
    conn = get_conn()
    team_key_by_sofascore_id = team_key_by_sofascore_id or {}
    fetched_at = _now()
    for r in rows:
        team_id = r.get("team_id")
        conn.execute(
            """INSERT INTO standings (comp_key, season_label, team_id, team_key, team_name, position, played,
                    wins, draws, losses, goals_for, goals_against, goal_diff, points, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (comp_key, season_label, team_id) DO UPDATE SET
                   team_key = excluded.team_key, team_name = excluded.team_name, position = excluded.position,
                   played = excluded.played, wins = excluded.wins, draws = excluded.draws, losses = excluded.losses,
                   goals_for = excluded.goals_for, goals_against = excluded.goals_against,
                   goal_diff = excluded.goal_diff, points = excluded.points, fetched_at = excluded.fetched_at""",
            [comp_key, season_label, team_id, team_key_by_sofascore_id.get(team_id), r.get("team_name"),
             r.get("position"), r.get("played"), r.get("wins"), r.get("draws"), r.get("losses"),
             r.get("goals_for"), r.get("goals_against"), str(r.get("goal_diff")), r.get("points"), fetched_at],
        )


# ---------------------------------------------------------------------------
# camadas de métrica derivada — payload JSON indexado pela chave relacional
# ---------------------------------------------------------------------------
def _upsert_json_blob(table: str, key_cols: dict, payload: dict) -> None:
    conn = get_conn()
    cols = list(key_cols) + ["payload"]
    placeholders = ", ".join(["?"] * len(cols))
    conflict_cols = ", ".join(key_cols)
    update_set = "payload = excluded.payload"
    conn.execute(
        f"""INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders})
            ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}""",
        list(key_cols.values()) + [json.dumps(payload, ensure_ascii=False)],
    )


# Mesmo conjunto usado em models/derived.py::PlayerMetrics (só sem os campos
# derivados que a query de liga recalcula: xg_overperformance, xa_overperformance,
# shot_quality). Uma lista central evita o INSERT desalinhar do schema.
_PLAYER_SEASON_COLS = [
    "key", "team_key", "season_label", "name", "position_group", "minutes", "matches",
    "starts", "sub_apps", "market_value_eur", "age", "contract_until", "active",
    "jersey_number", "nationality", "in_current_squad",
    "goals_p90", "xg_p90", "assists_p90", "xa_p90", "shots_p90", "touches_p90", "passes_p90",
    "key_passes_p90", "long_balls_p90", "crosses_p90", "poss_lost_p90", "ball_recovery_p90",
    "progressive_carries_p90", "duels_won_p90", "aerials_won_p90", "interceptions_p90",
    "clearances_p90", "fouls_p90", "accurate_passes_p90",
    "pass_accuracy", "long_ball_accuracy", "cross_accuracy", "duel_win_pct", "turnover_rate",
    "opp_half_pass_share", "tier", "goals", "assists", "goals_conceded", "avg_rating",
]


@_safe
def upsert_player_season_stats(team_key: str, season_label: str, players: list) -> None:
    """`players` já deve trazer `in_current_squad` por linha -- calculado em
    storage/json_store.py::save_player_metrics a partir de players_master.
    in_squad (mesma chave normalizada `key`, sem precisar de join no banco;
    players_master usa sofascore_id/ogol_id como PK em player_team_season,
    que não bate 1:1 com a `key` normalizada usada aqui)."""
    conn = get_conn()
    placeholders = ", ".join(["?"] * len(_PLAYER_SEASON_COLS))
    update_set = ", ".join(f"{c} = excluded.{c}" for c in _PLAYER_SEASON_COLS if c not in ("key", "team_key", "season_label"))
    for p in players:
        passes_p90, pass_acc = p.get("passes_p90"), p.get("pass_accuracy")
        accurate_passes_p90 = round(passes_p90 * pass_acc / 100, 2) if passes_p90 is not None and pass_acc is not None else None
        row = dict(p)
        row["team_key"] = team_key
        row["season_label"] = season_label
        row["accurate_passes_p90"] = accurate_passes_p90
        values = [row.get(c) for c in _PLAYER_SEASON_COLS]
        conn.execute(
            f"""INSERT INTO player_season_stats ({", ".join(_PLAYER_SEASON_COLS)}) VALUES ({placeholders})
                ON CONFLICT (key, team_key, season_label) DO UPDATE SET {update_set}""",
            values,
        )


@_safe
def upsert_team_metrics(team_key: str, season_label: str, data: dict) -> None:
    _upsert_json_blob("team_metrics", {"team_key": team_key, "season_label": season_label}, data)


@_safe
def upsert_match_reports(team_key: str, season_label: str, data: dict) -> None:
    _upsert_json_blob("match_reports", {"team_key": team_key, "season_label": season_label}, data)


@_safe
def upsert_team_analysis(team_key: str, season_label: str, data: dict) -> None:
    _upsert_json_blob("team_analysis", {"team_key": team_key, "season_label": season_label}, data)


@_safe
def upsert_ufmg(comp_key: str, data: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO ufmg_probabilities (comp_key, payload, fetched_at) VALUES (?, ?, ?)
           ON CONFLICT (comp_key) DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at""",
        [comp_key, json.dumps(data, ensure_ascii=False), _now()],
    )


@_safe
def upsert_league_player_metrics(data: dict) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO league_player_metrics (id, generated_at, payload) VALUES (1, ?, ?)
           ON CONFLICT (id) DO UPDATE SET generated_at = excluded.generated_at, payload = excluded.payload""",
        [data.get("generated_at"), json.dumps(data, ensure_ascii=False)],
    )


def get_team_competitions(team_key: str) -> list:
    """Todas as competições/season_id descobertas pra um time (inclui Série A/B,
    Copa do Brasil/Nordeste, estaduais — tudo que sync_config/discovery achou)."""
    try:
        conn = get_conn(read_only=True)
    except Exception as e:
        logger.warning("get_team_competitions: banco indisponível: %s", e)
        return []
    rows = conn.execute(
        """SELECT tcs.comp_key, c.name, tcs.season_label, tcs.sofascore_season_id, c.sofascore_tournament_id
           FROM team_competition_seasons tcs
           LEFT JOIN competitions c ON c.comp_key = tcs.comp_key
           WHERE tcs.team_key = ?""",
        [team_key],
    ).fetchall()
    return [
        {"comp_key": r[0], "name": r[1], "season_label": r[2], "season_id": r[3], "tournament_id": r[4]}
        for r in rows
    ]


@_safe
def upsert_raw_snapshot(source: str, team_key: str, kind: str, payload) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO raw_snapshots (source, team_key, kind, fetched_at, payload) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (source, team_key, kind) DO UPDATE SET
               fetched_at = excluded.fetched_at, payload = excluded.payload""",
        [source, team_key, kind, _now(), json.dumps(payload, ensure_ascii=False, default=str)],
    )


# ---------------------------------------------------------------------------
# liga inteira: merge de transferência + percentil, tudo em SQL
# ---------------------------------------------------------------------------
_RATE_FIELDS = [
    "goals_p90", "xg_p90", "assists_p90", "xa_p90", "shots_p90", "touches_p90",
    "passes_p90", "key_passes_p90", "long_balls_p90", "crosses_p90", "poss_lost_p90",
    "ball_recovery_p90", "progressive_carries_p90", "duels_won_p90", "aerials_won_p90",
    "interceptions_p90", "clearances_p90", "fouls_p90", "accurate_passes_p90",
]
_RATIO_FIELDS = [
    "pass_accuracy", "long_ball_accuracy", "cross_accuracy", "duel_win_pct",
    "turnover_rate", "opp_half_pass_share", "avg_rating",
]
_SUM_FIELDS = ["goals", "assists", "matches", "starts", "sub_apps"]
_IDENTITY_FIELDS = [
    "name", "position_group", "market_value_eur", "age", "contract_until",
    "jersey_number", "nationality", "active", "tier", "team_key",
]

# Mesmo conjunto que o scout expõe (views/scout.py _METRIC_GROUPS) — qualquer
# métrica nova precisa entrar aqui pra ganhar percentil de liga/divisão.
_PCTL_METRICS = [
    "xg_p90", "xa_p90", "key_passes_p90", "progressive_carries_p90",
    "ball_recovery_p90", "duel_win_pct", "pass_accuracy", "touches_p90",
    "turnover_rate", "accurate_passes_p90", "duels_won_p90",
    "interceptions_p90", "clearances_p90", "aerials_won_p90",
    "crosses_p90", "long_balls_p90", "shots_p90", "fouls_p90", "poss_lost_p90",
]
_LOWER_IS_BETTER = {"turnover_rate", "fouls_p90", "poss_lost_p90"}
MIN_MINUTES = 270  # amostra mínima pra entrar no percentil -- público, usado por models/league.py


def _sanitize(rows: List[dict]) -> List[dict]:
    """DataFrame vindo do DuckDB usa NaN pra NULL em coluna float e ndarray
    pra coluna LIST (`prior_clubs`) — nenhum dos dois é JSON serializável, e o
    scout/`--league` export esperam None e list() puros."""
    import math
    import numpy as np

    def clean(v):
        if isinstance(v, float) and math.isnan(v):
            return None
        if isinstance(v, np.ndarray):
            return [clean(x) for x in v.tolist()]
        return v

    return [{k: clean(v) for k, v in r.items()} for r in rows]


def query_league_player_metrics(divisions: Optional[List[str]] = None, min_minutes: int = MIN_MINUTES) -> List[dict]:
    """Dataset da liga inteira pronto pro scout: um jogador que trocou de clube
    na temporada some fundido sob o clube atual (ver `in_current_squad`), com
    percentil por posição calculado via PERCENT_RANK (janela SQL) em vez de
    pandas.rank em Python -- é o trabalho que antes vivia em models/league.py.
    """
    try:
        conn = get_conn(read_only=True)
    except Exception as e:
        logger.warning("query_league_player_metrics: banco indisponível: %s", e)
        return []

    identity_exprs = ",\n            ".join(f"MAX({f}) FILTER (WHERE rn = 1) AS {f}" for f in _IDENTITY_FIELDS)
    rate_exprs = ",\n            ".join(
        f"CASE WHEN SUM(minutes) > 0 THEN ROUND(SUM(COALESCE({f},0) * minutes / 90.0) / (SUM(minutes)/90.0), 3) "
        f"ELSE 0 END AS {f}"
        for f in _RATE_FIELDS
    )
    ratio_exprs = ",\n            ".join(
        f"CASE WHEN SUM(CASE WHEN {f} IS NOT NULL THEN minutes ELSE 0 END) > 0 THEN "
        f"ROUND(SUM(COALESCE({f},0) * CASE WHEN {f} IS NOT NULL THEN minutes ELSE 0 END) "
        f"/ SUM(CASE WHEN {f} IS NOT NULL THEN minutes ELSE 0 END), 2) ELSE NULL END AS {f}"
        for f in _RATIO_FIELDS
    )
    sum_exprs = ",\n            ".join(f"SUM(COALESCE({f},0)) AS {f}" for f in _SUM_FIELDS)

    where_sql, params = "", []
    if divisions:
        where_sql = f"WHERE t.division IN ({', '.join('?' for _ in divisions)})"
        params = list(divisions)

    pctl_league_exprs = ",\n            ".join(
        f"ROUND(PERCENT_RANK() OVER (PARTITION BY position_group "
        f"ORDER BY {m} {'DESC' if m in _LOWER_IS_BETTER else 'ASC'}) * 100, 1) AS {m}_league_pctl"
        for m in _PCTL_METRICS
    )
    pctl_division_exprs = ",\n            ".join(
        f"ROUND(PERCENT_RANK() OVER (PARTITION BY position_group, division "
        f"ORDER BY {m} {'DESC' if m in _LOWER_IS_BETTER else 'ASC'}) * 100, 1) AS {m}_division_pctl"
        for m in _PCTL_METRICS
    )

    query = f"""
    WITH stints AS (
        SELECT pss.*, t.name AS team_name_full, t.division AS division, t.state AS state,
            ROW_NUMBER() OVER (
                PARTITION BY pss.key
                ORDER BY COALESCE(pss.in_current_squad, false) DESC, pss.minutes DESC
            ) AS rn,
            COUNT(*) OVER (PARTITION BY pss.key) AS n_stints
        FROM player_season_stats pss
        JOIN teams t ON t.team_key = pss.team_key
        {where_sql}
    ),
    merged AS (
        SELECT
            key,
            {identity_exprs},
            MAX(team_name_full) FILTER (WHERE rn = 1) AS team_name,
            MAX(division) FILTER (WHERE rn = 1) AS division,
            MAX(state) FILTER (WHERE rn = 1) AS state,
            SUM(minutes) AS minutes,
            {sum_exprs},
            {rate_exprs},
            {ratio_exprs},
            MAX(n_stints) AS n_stints,
            list(team_name_full) FILTER (WHERE rn != 1) AS prior_clubs
        FROM stints
        GROUP BY key
    ),
    derived AS (
        SELECT *,
            CASE WHEN matches > 0 THEN ROUND(starts::DOUBLE / matches, 3) ELSE NULL END AS starts_share,
            ROUND(goals - xg_p90 * minutes / 90.0, 2) AS xg_overperformance,
            ROUND(assists - xa_p90 * minutes / 90.0, 2) AS xa_overperformance,
            CASE WHEN shots_p90 > 0 THEN ROUND(xg_p90 / shots_p90, 3) ELSE NULL END AS shot_quality,
            (n_stints > 1) AS transferred
        FROM merged
    ),
    eligible AS (
        SELECT * FROM derived WHERE minutes >= {int(min_minutes)}
    ),
    pctl AS (
        SELECT key,
            {pctl_league_exprs},
            {pctl_division_exprs}
        FROM eligible
    )
    SELECT d.*, p.* EXCLUDE (key)
    FROM derived d
    LEFT JOIN pctl p ON p.key = d.key
    """
    try:
        df = conn.execute(query, params).df()
    except Exception as e:
        logger.warning("query_league_player_metrics: falha na query: %s: %s", type(e).__name__, e)
        return []
    return _sanitize(df.to_dict("records"))
