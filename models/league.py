"""Camada League: agrega player_metrics de todos os clubes cadastrados (Série A + B)
num dataset único, com percentis calculados na liga inteira (e por divisão) em vez
de dentro de um único time — base para scout e comparação de confronto.

Puro: sem rede. Lê os `{team}_player_metrics.json` já gerados pela camada Derive
(models/derived.py) para cada clube, então recalcula os percentis por posição sobre
o conjunto combinado.
"""

from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from config import TEAMS

# Mesmas métricas usadas no percentil por time em models/derived.py — mantém
# consistência entre "percentil no elenco" e "percentil na liga".
_PCTL_METRICS = [
    "xg_p90", "xa_p90", "key_passes_p90", "progressive_carries_p90",
    "ball_recovery_p90", "duel_win_pct", "pass_accuracy", "touches_p90",
    "turnover_rate",
]

# Amostra mínima para entrar no ranking de percentil (evita 1 jogo bom distorcer).
_MIN_MINUTES = 270  # ~3 jogos completos


def load_all_player_metrics(store, divisions: Optional[List[str]] = None) -> List[dict]:
    """Lê player_metrics de cada clube configurado e marca time/divisão em cada linha.

    `divisions`: filtro opcional, ex.: ["Série A"] ou ["Série A", "Série B"].
    Times sem arquivo `{team}_player_metrics.json` ainda coletado são ignorados
    silenciosamente (a coleta em massa pode estar parcial).
    """
    rows: List[dict] = []
    for team_key, cfg in TEAMS.items():
        division = cfg.get("division")
        if divisions and division not in divisions:
            continue
        data = store.load_player_metrics(team_key)
        players = data.get("players") or []
        if not players:
            continue
        for p in players:
            row = dict(p)
            row["team_key"] = team_key
            row["team_name"] = cfg.get("name", team_key)
            row["division"] = division
            row["state"] = cfg.get("state")
            rows.append(row)
    return rows


def build_league_player_metrics(store) -> dict:
    """Monta o dataset league-wide: todas as linhas + percentis (liga inteira e
    por divisão), pronto para persistir via JsonStore.save_league_player_metrics.
    """
    rows = load_all_player_metrics(store)
    n_teams = len({r["team_key"] for r in rows})

    _inject_league_percentiles(rows, scope_col=None, suffix="league_pctl")
    _inject_league_percentiles(rows, scope_col="division", suffix="division_pctl")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "teams_covered": n_teams,
        "players": rows,
    }


def _inject_league_percentiles(rows: List[dict], scope_col: Optional[str], suffix: str) -> None:
    """Calcula percentil por position_group (e opcionalmente por `scope_col`,
    ex. divisão) sobre `_PCTL_METRICS`, só considerando quem bateu `_MIN_MINUTES`.

    Escreve `<metric>_<suffix>` em cada dict de `rows` (in-place); fica `None`
    para quem não tem amostra suficiente.
    """
    if not rows:
        return
    df = pd.DataFrame(rows)
    eligible = df["minutes"].fillna(0) >= _MIN_MINUTES if "minutes" in df.columns else pd.Series([False] * len(df))

    group_cols = ["position_group"] + ([scope_col] if scope_col else [])
    for metric in _PCTL_METRICS:
        col = f"{metric}_{suffix}"
        for row in rows:
            row[col] = None
        if metric not in df.columns:
            continue
        sub = df[eligible]
        if sub.empty:
            continue
        # turnover_rate: menor é melhor -> ascending=False mantém "percentil
        # alto = bom" em todas as métricas (mesma convenção de derived.py).
        ascending = metric != "turnover_rate"
        pct = sub.groupby(group_cols)[metric].rank(pct=True, ascending=ascending) * 100
        for i, val in zip(sub.index, pct):
            if pd.isna(val):
                continue
            rows[i][col] = round(float(val), 1)


def top_by_metric(
    league_rows: List[dict], metric: str, position_group: Optional[str] = None,
    division: Optional[str] = None, min_minutes: int = _MIN_MINUTES, n: int = 20,
) -> List[dict]:
    """Ranking simples da liga por uma métrica per-90 (ou %), com filtros comuns
    de posição/divisão/minutagem mínima — usado pela página de scout."""
    out = [
        r for r in league_rows
        if (r.get(metric) is not None)
        and (r.get("minutes") or 0) >= min_minutes
        and (position_group is None or r.get("position_group") == position_group)
        and (division is None or r.get("division") == division)
    ]
    out.sort(key=lambda r: r[metric], reverse=True)
    return out[:n]


def find_player(league_rows: List[dict], name_query: str) -> List[dict]:
    """Busca case-insensitive por substring no nome — para a página de scout."""
    q = name_query.strip().lower()
    if not q:
        return []
    return [r for r in league_rows if q in (r.get("name") or "").lower()]
