"""Camada Derive: métricas calculadas a partir das camadas Resolve + raw.

Puro: sem rede. Só lê dicts já carregados. Estilo copiado de
models/player_stats.py (dataclass + @property + guarda contra zero) e
models/aggregate.py (função pura com acumulador).
"""

from dataclasses import asdict, dataclass, field
from math import exp, factorial
from typing import List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Fase 2 — player_metrics
# ---------------------------------------------------------------------------

# advanced_season attr -> per-90 metric name
_P90_FIELDS = {
    "goals": "goals_p90",
    "xg": "xg_p90",
    "assists": "assists_p90",
    "xa": "xa_p90",
    "shots": "shots_p90",
    "touches": "touches_p90",
    "passes": "passes_p90",
    "key_passes": "key_passes_p90",
    "long_balls": "long_balls_p90",
    "crosses": "crosses_p90",
    "possession_lost": "poss_lost_p90",
    "ball_recovery": "ball_recovery_p90",
    "progressive_carries": "progressive_carries_p90",
    "duels_won": "duels_won_p90",
    "aerials_won": "aerials_won_p90",
    "interceptions": "interceptions_p90",
    "clearances": "clearances_p90",
    "fouls": "fouls_p90",
}

# percentil por grupo de posição — subconjunto do plano Fase 2.1 bloco 4
_PCTL_METRICS = [
    "xg_p90", "xa_p90", "key_passes_p90", "progressive_carries_p90",
    "ball_recovery_p90", "duel_win_pct", "pass_accuracy", "touches_p90",
    "turnover_rate",  # invertido: menos perda = percentil maior
]


@dataclass
class PlayerMetrics:
    key: str
    name: str
    position_group: Optional[str]
    minutes: int
    matches: int
    starts: int
    sub_apps: int
    starts_share: Optional[float]  # titularidades / jogos do time (% titular real)
    market_value_eur: Optional[int]
    age: Optional[int]
    contract_until: Optional[str]
    active: bool

    # per-90 (None se minutes == 0)
    goals_p90: Optional[float] = None
    xg_p90: Optional[float] = None
    assists_p90: Optional[float] = None
    xa_p90: Optional[float] = None
    shots_p90: Optional[float] = None
    touches_p90: Optional[float] = None
    passes_p90: Optional[float] = None
    key_passes_p90: Optional[float] = None
    long_balls_p90: Optional[float] = None
    crosses_p90: Optional[float] = None
    poss_lost_p90: Optional[float] = None
    ball_recovery_p90: Optional[float] = None
    progressive_carries_p90: Optional[float] = None
    duels_won_p90: Optional[float] = None
    aerials_won_p90: Optional[float] = None
    interceptions_p90: Optional[float] = None
    clearances_p90: Optional[float] = None
    fouls_p90: Optional[float] = None

    # razões / performance
    pass_accuracy: Optional[float] = None
    long_ball_accuracy: Optional[float] = None
    cross_accuracy: Optional[float] = None
    duel_win_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    opp_half_pass_share: Optional[float] = None  # sem dado em advanced_season -> None
    xg_overperformance: Optional[float] = None
    xa_overperformance: Optional[float] = None
    shot_quality: Optional[float] = None

    # tier OGol (quando não há advanced SofaScore): absolutos da temporada
    tier: str = "sofascore"
    goals: Optional[int] = None
    assists: Optional[int] = None
    goals_conceded: Optional[int] = None
    avg_rating: Optional[float] = None


def _p90(value, minutes) -> Optional[float]:
    return round(value / minutes * 90, 3) if minutes else None


def _pct(num, den) -> Optional[float]:
    return round(num / den * 100, 1) if den else None


def _ogol_player_metrics(players_master: dict, player_stats: dict) -> List[dict]:
    """player_metrics tier OGol: absolutos + p90 de gols/assist a partir de player_stats."""
    from name_match import normalize_name

    ps_by_name = {normalize_name(p["name"]): p for p in (player_stats or {}).get("players", [])}
    ps_by_ogol = {
        str(p.get("player_id")): p
        for p in (player_stats or {}).get("players", []) if p.get("player_id")
    }

    rows: List[dict] = []
    for pm in players_master.get("players", []):
        ps = ps_by_ogol.get(str(pm.get("ogol_id"))) or ps_by_name.get(normalize_name(pm.get("name", "")))
        ps = ps or {}
        minutes = ps.get("total_minutes", 0) or 0
        matches = ps.get("total_appearances", 0) or 0
        starts = ps.get("starts", 0) or 0
        goals = ps.get("total_goals")
        assists = ps.get("total_assists")
        m = PlayerMetrics(
            key=pm["key"],
            name=pm.get("name") or ps.get("name", ""),
            position_group=pm.get("position_group") or ps.get("position"),
            minutes=minutes,
            matches=matches,
            starts=starts,
            sub_apps=ps.get("substitute_appearances", max(matches - starts, 0)) or 0,
            starts_share=None,
            market_value_eur=pm.get("market_value_eur"),
            age=pm.get("age"),
            contract_until=pm.get("contract_until"),
            active=bool(pm.get("active")),
            goals_p90=_p90(goals or 0, minutes),
            assists_p90=_p90(assists or 0, minutes),
            tier="ogol",
            goals=goals,
            assists=assists,
            goals_conceded=ps.get("total_goals_conceded"),
            avg_rating=ps.get("avg_rating"),
        )
        rows.append(asdict(m))
    _inject_percentiles(rows)
    return rows


def build_player_metrics(
    players_master: dict, advanced_season: dict, advanced_matches: Optional[dict] = None,
    player_stats: Optional[dict] = None
) -> List[dict]:
    if not (advanced_season or {}).get("players") and (player_stats or {}).get("players"):
        return _ogol_player_metrics(players_master, player_stats)

    adv_by_id = {p["player_id"]: p for p in advanced_season.get("players", [])}

    # Titularidades reais a partir do dado por-jogo (advanced_season não traz starts).
    am_list = (advanced_matches or {}).get("matches", []) or []
    team_matches = len(am_list)
    starts_by_id: dict = {}
    apps_by_id: dict = {}
    ratings_by_id: dict = {}
    for match in am_list:
        for pl in match.get("players", []):
            pid = pl.get("player_id")
            if pid is None:
                continue
            apps_by_id[pid] = apps_by_id.get(pid, 0) + 1
            if pl.get("is_starter"):
                starts_by_id[pid] = starts_by_id.get(pid, 0) + 1
            if pl.get("rating") is not None:
                try:
                    ratings_by_id.setdefault(pid, []).append(float(pl["rating"]))
                except (ValueError, TypeError):
                    pass

    # Lookup de player_stats (OGol) para fallback
    ps_by_ogol = {
        str(p.get("player_id")): p
        for p in (player_stats or {}).get("players", []) if p.get("player_id")
    }
    ps_by_name = {
        (p.get("name") or "").lower(): p
        for p in (player_stats or {}).get("players", [])
    }

    rows: List[dict] = []

    for pm in players_master.get("players", []):
        adv = adv_by_id.get(pm.get("sofascore_id")) or {}
        minutes = adv.get("minutes", 0) or 0
        matches = adv.get("matches", 0) or 0
        sid = pm.get("sofascore_id")
        starts = starts_by_id.get(sid, 0) if sid else 0
        apps = apps_by_id.get(sid, matches) if sid else matches
        goals, xg = adv.get("goals", 0), adv.get("xg", 0.0)
        assists, xa = adv.get("assists", 0), adv.get("xa", 0.0)
        shots = adv.get("shots", 0)
        dw, dl = adv.get("duels_won", 0), adv.get("duels_lost", 0)

        # Média de rating das partidas
        r_list = ratings_by_id.get(sid, []) if sid else []
        calc_avg_rating = round(sum(r_list) / len(r_list), 2) if r_list else None

        # Fallback para OGol se não houver nota SofaScore
        ps = ps_by_ogol.get(str(pm.get("ogol_id"))) or ps_by_name.get((pm.get("name") or "").lower())
        if calc_avg_rating is None and ps:
            calc_avg_rating = ps.get("avg_rating")

        m = PlayerMetrics(
            key=pm["key"],
            name=pm.get("name") or adv.get("name", ""),
            position_group=pm.get("position_group"),
            minutes=minutes,
            matches=matches,
            starts=starts,
            sub_apps=max(apps - starts, 0),
            starts_share=round(starts / team_matches, 3) if team_matches else None,
            market_value_eur=pm.get("market_value_eur"),
            age=pm.get("age"),
            contract_until=pm.get("contract_until"),
            active=bool(pm.get("active")),
            pass_accuracy=_pct(adv.get("passes_accurate", 0), adv.get("passes", 0)) if adv else None,
            long_ball_accuracy=_pct(adv.get("long_balls_accurate", 0), adv.get("long_balls", 0)) if adv else None,
            cross_accuracy=_pct(adv.get("crosses_accurate", 0), adv.get("crosses", 0)) if adv else None,
            duel_win_pct=_pct(dw, dw + dl) if adv else None,
            turnover_rate=_pct(adv.get("possession_lost", 0), adv.get("touches", 0)) if adv else None,
            opp_half_pass_share=_pct(adv.get("opp_half_passes", 0), adv.get("passes", 0)) if adv else None,
            xg_overperformance=round(goals - xg, 3) if adv else None,
            xa_overperformance=round(assists - xa, 3) if adv else None,
            shot_quality=round(xg / shots, 3) if (shots and adv) else None,
            tier="sofascore",
            goals=goals,
            assists=assists,
            avg_rating=calc_avg_rating,
        )
        for src, dst in _P90_FIELDS.items():
            setattr(m, dst, _p90(adv.get(src, 0) or 0, minutes))

        rows.append(asdict(m))

    _inject_percentiles(rows)
    return rows


def _inject_percentiles(rows: List[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)  # nunca df.append (removido no pandas 3)
    for metric in _PCTL_METRICS:
        if metric not in df.columns:
            continue
        # turnover_rate: menor é melhor -> ascending=False dá percentil alto para
        # quem perde menos bola (mantém a convenção "percentil alto = bom" em
        # todas as métricas, igual xg_p90/duel_win_pct/etc).
        ascending = metric != "turnover_rate"
        pct = df.groupby("position_group")[metric].rank(pct=True, ascending=ascending) * 100
        col = f"{metric}_pctl"
        for i, row in enumerate(rows):
            val = pct.iloc[i]
            row[col] = None if pd.isna(val) else round(float(val), 1)


# ---------------------------------------------------------------------------
# Fase 3 — team_metrics
# ---------------------------------------------------------------------------

_SET_PIECE = {"corner", "free-kick", "set-piece", "throw-in-set-piece", "penalty"}
_MAXG = 10


def _poisson_pmf(k: int, lam: float) -> float:
    return exp(-lam) * lam ** k / factorial(k)


def _xpoints(xf: float, xa: float) -> dict:
    xf = max(xf or 0.0, 1e-9)
    xa = max(xa or 0.0, 1e-9)
    p_win = sum(
        _poisson_pmf(i, xf) * _poisson_pmf(j, xa)
        for i in range(_MAXG) for j in range(i)
    )
    p_draw = sum(_poisson_pmf(i, xf) * _poisson_pmf(i, xa) for i in range(_MAXG))
    p_loss = 1.0 - p_win - p_draw
    return {
        "p_win": round(p_win, 4),
        "p_draw": round(p_draw, 4),
        "p_loss": round(p_loss, 4),
        "xpoints": round(3 * p_win + 1 * p_draw, 4),
    }


def _team_aliases(team: str) -> set:
    from resolve.master import _team_aliases as _ta
    return _ta(team)


def _team_side(match: dict, aliases: set) -> str:
    """'home' ou 'away' — lado do time no jogo do advanced_matches."""
    hs = (match.get("home_team", "") or "").lower()
    return "home" if any(a in hs for a in aliases) else "away"


def _calculate_game_state(adv_list: list, aliases: set) -> dict:
    mins_by_state = {"winning": 0, "drawing": 0, "losing": 0}
    state_stats = {
        "winning": {"for": {"shots": 0, "goals": 0, "xg": 0.0}, "against": {"shots": 0, "goals": 0, "xg": 0.0}},
        "drawing": {"for": {"shots": 0, "goals": 0, "xg": 0.0}, "against": {"shots": 0, "goals": 0, "xg": 0.0}},
        "losing":  {"for": {"shots": 0, "goals": 0, "xg": 0.0}, "against": {"shots": 0, "goals": 0, "xg": 0.0}},
    }

    for adv in adv_list:
        side = _team_side(adv, aliases)
        # Identificar gols da partida
        goals = []
        for s in sorted(adv.get("shots", []), key=lambda x: x.get("minute") or 0):
            if s.get("is_goal"):
                m_min = s.get("minute") or 0
                scoring_side = "home" if s.get("is_home") else "away"
                delta = 1 if scoring_side == side else -1
                goals.append((m_min, delta))

        # Rastrear minutos jogados em cada estado (0 a 90)
        curr_diff = 0
        t_prev = 0
        for g_min, delta in goals:
            g_min_clamped = min(max(g_min, 0), 90)
            dur = max(0, g_min_clamped - t_prev)
            state = "drawing" if curr_diff == 0 else ("winning" if curr_diff > 0 else "losing")
            mins_by_state[state] += dur
            curr_diff += delta
            t_prev = g_min_clamped

        # Minutos restantes até 90
        rem_dur = max(0, 90 - t_prev)
        state = "drawing" if curr_diff == 0 else ("winning" if curr_diff > 0 else "losing")
        mins_by_state[state] += rem_dur

        # Classificar cada chute no estado do placar antes do chute
        for s in adv.get("shots", []):
            m_min = s.get("minute") or 0
            is_for = s.get("is_home") == (side == "home")
            bucket = "for" if is_for else "against"
            diff_before = sum(d for gm, d in goals if gm < m_min)
            sh_state = "drawing" if diff_before == 0 else ("winning" if diff_before > 0 else "losing")

            state_stats[sh_state][bucket]["shots"] += 1
            state_stats[sh_state][bucket]["xg"] += (s.get("xg") or 0.0)
            if s.get("is_goal"):
                state_stats[sh_state][bucket]["goals"] += 1

    total_mins = sum(mins_by_state.values()) or 1
    out = {}
    for st_name in ("winning", "drawing", "losing"):
        m = mins_by_state[st_name]
        f = state_stats[st_name]["for"]
        a = state_stats[st_name]["against"]
        out[st_name] = {
            "minutes": m,
            "share_pct": round(m / total_mins * 100, 1),
            "goals_for": f["goals"],
            "goals_against": a["goals"],
            "xg_for": round(f["xg"], 2),
            "xg_against": round(a["xg"], 2),
            "xg_diff": round(f["xg"] - a["xg"], 2),
            "xg_for_p90": round(f["xg"] / m * 90, 2) if m > 0 else 0.0,
            "xg_against_p90": round(a["xg"] / m * 90, 2) if m > 0 else 0.0,
            "shots_for": f["shots"],
            "shots_against": a["shots"],
        }
    return out


def _calculate_substitutions_impact(adv_list: list, aliases: set) -> dict:
    starters = {"count": 0, "minutes": 0, "xg": 0.0, "xa": 0.0, "goals": 0, "assists": 0, "ratings": []}
    subs = {"count": 0, "minutes": 0, "xg": 0.0, "xa": 0.0, "goals": 0, "assists": 0, "ratings": []}
    player_subs: dict = {}

    for adv in adv_list:
        side = _team_side(adv, aliases)
        for p in adv.get("players", []):
            if p.get("team") != side:
                continue
            is_st = p.get("is_starter", True)
            mins = p.get("minutes_played", 0) or 0
            xg = p.get("xg", 0.0) or 0.0
            xa = p.get("xa", 0.0) or 0.0
            goals = p.get("goals", 0) or 0
            assists = p.get("assists", 0) or 0
            r = p.get("rating")

            target = starters if is_st else subs
            target["count"] += 1
            target["minutes"] += mins
            target["xg"] += xg
            target["xa"] += xa
            target["goals"] += goals
            target["assists"] += assists
            if r is not None:
                try:
                    target["ratings"].append(float(r))
                except (ValueError, TypeError):
                    pass

            if not is_st and mins > 0:
                pid = str(p.get("player_id") or p.get("name"))
                if pid not in player_subs:
                    player_subs[pid] = {
                        "name": p.get("name", ""),
                        "sub_apps": 0,
                        "minutes": 0,
                        "goals": 0,
                        "assists": 0,
                        "xg": 0.0,
                        "xa": 0.0,
                        "ratings": [],
                    }
                entry = player_subs[pid]
                entry["sub_apps"] += 1
                entry["minutes"] += mins
                entry["goals"] += goals
                entry["assists"] += assists
                entry["xg"] = round(entry["xg"] + xg, 3)
                entry["xa"] = round(entry["xa"] + xa, 3)
                if r is not None:
                    try:
                        entry["ratings"].append(float(r))
                    except (ValueError, TypeError):
                        pass

    supersubs = []
    for pid, entry in player_subs.items():
        avg_r = round(sum(entry["ratings"]) / len(entry["ratings"]), 2) if entry["ratings"] else None
        supersubs.append({
            "name": entry["name"],
            "sub_apps": entry["sub_apps"],
            "minutes": entry["minutes"],
            "goals": entry["goals"],
            "assists": entry["assists"],
            "goal_involvements": entry["goals"] + entry["assists"],
            "xg": round(entry["xg"], 2),
            "xa": round(entry["xa"], 2),
            "prod_total": round(entry["xg"] + entry["xa"], 2),
            "avg_rating": avg_r,
        })
    supersubs.sort(key=lambda x: (x["goal_involvements"], x["prod_total"]), reverse=True)

    def _summary_sub(t):
        mins = t["minutes"] or 1
        return {
            "total_apps": t["count"],
            "total_minutes": t["minutes"],
            "goals": t["goals"],
            "assists": t["assists"],
            "xg": round(t["xg"], 2),
            "xa": round(t["xa"], 2),
            "xg_p90": round(t["xg"] / mins * 90, 2),
            "xa_p90": round(t["xa"] / mins * 90, 2),
            "avg_rating": round(sum(t["ratings"]) / len(t["ratings"]), 2) if t["ratings"] else None,
        }

    return {
        "starters_summary": _summary_sub(starters),
        "subs_summary": _summary_sub(subs),
        "supersubs": supersubs,
    }


def _detailed_shot_breakdown(shots: list) -> dict:
    by_body: dict = {}
    by_situation: dict = {}
    total_xg = 0.0
    total_xgot = 0.0
    total_goals = 0

    for s in shots:
        bp = s.get("body_part") or "other"
        sit = s.get("situation") or "other"
        xg = s.get("xg") or 0.0
        xgot = s.get("xgot") or 0.0
        is_g = 1 if s.get("is_goal") else 0

        total_xg += xg
        total_xgot += xgot
        total_goals += is_g

        # body part
        b_entry = by_body.setdefault(bp, {"count": 0, "goals": 0, "xg": 0.0, "xgot": 0.0})
        b_entry["count"] += 1
        b_entry["goals"] += is_g
        b_entry["xg"] = round(b_entry["xg"] + xg, 3)
        b_entry["xgot"] = round(b_entry["xgot"] + xgot, 3)

        # situation
        s_entry = by_situation.setdefault(sit, {"count": 0, "goals": 0, "xg": 0.0, "xgot": 0.0})
        s_entry["count"] += 1
        s_entry["goals"] += is_g
        s_entry["xg"] = round(s_entry["xg"] + xg, 3)
        s_entry["xgot"] = round(s_entry["xgot"] + xgot, 3)

    for group in (by_body, by_situation):
        for k, v in group.items():
            cnt = v["count"] or 1
            v["conversion_pct"] = round(v["goals"] / cnt * 100, 1)
            v["xg_per_shot"] = round(v["xg"] / cnt, 3)

    tot_shots = len(shots) or 1
    return {
        "total_shots": len(shots),
        "total_goals": total_goals,
        "total_xg": round(total_xg, 2),
        "total_xgot": round(total_xgot, 2),
        "xgot_diff": round(total_xgot - total_xg, 2),
        "avg_xg_per_shot": round(total_xg / tot_shots, 3),
        "by_body_part": by_body,
        "by_situation": by_situation,
    }


def build_team_metrics(
    matches_master: dict, advanced_matches: dict, ogol_stats: list, team: str = "fortaleza"
) -> dict:
    aliases = _team_aliases(team)
    mm = sorted(matches_master.get("matches", []), key=lambda x: x.get("date") or "")
    adv_by_id = {m["event_id"]: m for m in advanced_matches.get("matches", [])}
    stats_by_url = {s.get("match_url"): s for s in (ogol_stats or []) if s.get("match_url")}

    per_match: List[dict] = []
    shots_for: List[dict] = []
    shots_against: List[dict] = []

    for m in mm:
        adv = adv_by_id.get(m["event_id"])
        xf, xa = m.get("xg_for"), m.get("xg_against")
        has_xg = xf is not None or xa is not None
        xp = _xpoints(xf or 0.0, xa or 0.0) if has_xg else {
            "xpoints": None, "p_win": None, "p_draw": None, "p_loss": None
        }
        per_match.append({
            "date": m.get("date"),
            "opponent": m.get("opponent"),
            "is_home": m.get("is_home"),
            "score": m.get("score"),
            "points": m.get("points"),
            "goals_for": m.get("goals_for"),
            "goals_against": m.get("goals_against"),
            "xg_for": xf,
            "xg_against": xa,
            "xg_diff": round((xf or 0) - (xa or 0), 3) if has_xg else None,
            "xpoints": xp["xpoints"],
            "p_win": xp["p_win"],
            "p_draw": xp["p_draw"],
            "p_loss": xp["p_loss"],
        })
        if adv:
            side = _team_side(adv, aliases)
            for s in adv.get("shots", []):
                bucket = shots_for if (s.get("is_home") == (side == "home")) else shots_against
                bucket.append(s)

    # médias móveis 5 jogos
    pm_df = pd.DataFrame(per_match)
    if not pm_df.empty:
        pm_df["xg_for_roll5"] = pm_df["xg_for"].rolling(5, min_periods=1).mean().round(3)
        pm_df["xg_against_roll5"] = pm_df["xg_against"].rolling(5, min_periods=1).mean().round(3)
        pm_df["points_roll5"] = pm_df["points"].rolling(5, min_periods=1).mean().round(3)
        per_match = pm_df.to_dict("records")
        # pandas transforma None -> nan; restaura None p/ os filtros abaixo
        for p in per_match:
            pts = p.get("points")
            p["points"] = None if pts is None or (isinstance(pts, float) and pd.isna(pts)) else int(pts)
            for k in ("xg_for", "xg_against", "xg_diff", "xpoints", "p_win", "p_draw",
                      "p_loss", "goals_for", "goals_against"):
                v = p.get(k)
                if isinstance(v, float) and pd.isna(v):
                    p[k] = None

    has_xg = any(p.get("xg_for") is not None or p.get("xg_against") is not None for p in per_match)
    scored = [p for p in per_match if p["points"] is not None]
    wins = sum(1 for p in scored if p["points"] == 3)
    draws = sum(1 for p in scored if p["points"] == 1)
    losses = sum(1 for p in scored if p["points"] == 0)
    gf = sum(p["xg_for"] or 0 for p in per_match)
    ga = sum(p["xg_against"] or 0 for p in per_match)
    goals_for = sum((p.get("goals_for") or 0) for p in mm)
    goals_against = sum((p.get("goals_against") or 0) for p in mm)

    summary = {
        "tier": "sofascore" if has_xg else "ogol",
        "matches": len(per_match),
        "scored_matches": len(scored),
        "wins": wins, "draws": draws, "losses": losses,
        "points_real": sum(p["points"] for p in scored),
        "goals_for": goals_for,
        "goals_against": goals_against,
        # xG-derived — só no tier SofaScore
        "points_expected": round(sum(p["xpoints"] or 0 for p in per_match), 4) if has_xg else None,
        "points_expected_scored": round(sum(p["xpoints"] or 0 for p in scored), 4) if has_xg else None,
        "points_luck": round(
            sum(p["points"] for p in scored) - sum(p["xpoints"] or 0 for p in scored), 3
        ) if has_xg else None,
        "xg_for_total": round(gf, 3) if has_xg else None,
        "xg_against_total": round(ga, 3) if has_xg else None,
        "xg_diff": round(gf - ga, 3) if has_xg else None,
        "finishing": round(goals_for - gf, 3) if has_xg else None,
        "keeping": round(ga - goals_against, 3) if has_xg else None,
    }

    def _split(is_home: bool) -> dict:
        sub = [p for p in per_match if p["is_home"] == is_home]
        sub_scored = [p for p in sub if p["points"] is not None]
        n = len(sub) or 1
        return {
            "matches": len(sub),
            "xg_for": round(sum(p["xg_for"] or 0 for p in sub) / n, 3),
            "xg_against": round(sum(p["xg_against"] or 0 for p in sub) / n, 3),
            "ppg": round(sum(p["points"] for p in sub_scored) / len(sub_scored), 3) if sub_scored else None,
        }

    def _sit_breakdown(shots: list) -> dict:
        out: dict = {}
        for s in shots:
            sit = s.get("situation") or "unknown"
            e = out.setdefault(sit, {"count": 0, "xg_sum": 0.0, "goals": 0})
            e["count"] += 1
            e["xg_sum"] = round(e["xg_sum"] + (s.get("xg") or 0), 3)
            e["goals"] += 1 if s.get("is_goal") else 0
        return out

    def _sp_pct(shots: list) -> Optional[float]:
        tot = sum(s.get("xg") or 0 for s in shots)
        sp = sum(s.get("xg") or 0 for s in shots if s.get("situation") in _SET_PIECE)
        return round(sp / tot * 100, 1) if tot else None

    def _timeline(shots: list) -> dict:
        buckets = {b: 0.0 for b in ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90", "90+"]}
        for s in shots:
            mnt = s.get("minute") or 0
            if mnt <= 15: b = "0-15"
            elif mnt <= 30: b = "15-30"
            elif mnt <= 45: b = "30-45"
            elif mnt <= 60: b = "45-60"
            elif mnt <= 75: b = "60-75"
            elif mnt <= 90: b = "75-90"
            else: b = "90+"
            buckets[b] = round(buckets[b] + (s.get("xg") or 0), 3)
        return buckets

    # disciplina + estilo (só jogos com ogol casado — hoje 0, degrada suave)
    ogol_matched = [m for m in mm if m.get("ogol_matched")]
    discipline = {"coverage": f"{len(ogol_matched)}/{len(mm)}"}
    style = {"coverage": f"{len(ogol_matched)}/{len(mm)}"}
    if ogol_matched:
        fouls = []
        fouls_opp = []
        poss = []
        for m in ogol_matched:
            s = stats_by_url.get(m.get("ogol_url"), {})
            f_for = "fouls_home" if m.get("is_home") else "fouls_away"
            f_opp = "fouls_away" if m.get("is_home") else "fouls_home"
            if s.get(f_for) is not None:
                fouls.append(s[f_for])
            if s.get(f_opp) is not None:
                fouls_opp.append(s[f_opp])
            p_key = "possession_home_pct" if m.get("is_home") else "possession_away_pct"
            if s.get(p_key) is not None:
                poss.append(s[p_key])
        discipline["games_with_fouls"] = len(fouls)
        discipline["avg_fouls"] = round(sum(fouls) / len(fouls), 2) if fouls else None
        discipline["avg_fouls_against"] = round(sum(fouls_opp) / len(fouls_opp), 2) if fouls_opp else None
        if poss:
            avg_poss = sum(poss) / len(poss)
            # tier SofaScore usa xG/jogo; tier OGol usa gols/jogo como proxy de produção
            prod_per_match = (gf / len(per_match)) if has_xg else (goals_for / (len(per_match) or 1))
            style["games_with_possession"] = len(poss)
            style["avg_possession"] = round(avg_poss, 1)
            style["prod_per_possession_point"] = round(prod_per_match / avg_poss, 4) if avg_poss else None
            style["label"] = "direto" if avg_poss and prod_per_match / avg_poss > 0.03 else "apoio"

    # Game State (comportamento por placar) & Substituições
    adv_list = (advanced_matches or {}).get("matches", []) or []
    game_state = _calculate_game_state(adv_list, aliases)
    subs_impact = _calculate_substitutions_impact(adv_list, aliases)
    shot_breakdown = {
        "for": _detailed_shot_breakdown(shots_for),
        "against": _detailed_shot_breakdown(shots_against),
    }

    return {
        "summary": summary,
        "per_match": per_match,
        "home_away": {"home": _split(True), "away": _split(False)},
        "set_pieces": {
            "xg_for_setpiece_pct": _sp_pct(shots_for),
            "xg_against_setpiece_pct": _sp_pct(shots_against),
        },
        "shot_situations": {
            "for": _sit_breakdown(shots_for),
            "against": _sit_breakdown(shots_against),
        },
        "shot_breakdown": shot_breakdown,
        "timeline": {"for": _timeline(shots_for), "against": _timeline(shots_against)},
        "game_state": game_state,
        "substitutions": subs_impact,
        "discipline": discipline,
        "style": style,
    }


# ---------------------------------------------------------------------------
# Fase 3 — match_reports
# ---------------------------------------------------------------------------

_REPORT_PLAYER_COLS = [
    "name", "is_starter", "minutes_played", "rating", "touches", "passes_total",
    "passes_accurate", "key_passes", "possession_lost", "ball_recovery",
    "duels_won", "duels_lost", "xg", "xa", "shots_total", "goals",
]


def _ogol_match_reports(matches_master: dict, ogol_stats: list) -> List[dict]:
    """Basic per-match reports from OGol only (score, possession, shots, cards) — no xG/per-player."""
    stats_by_url = {s.get("match_url"): s for s in (ogol_stats or []) if s.get("match_url")}
    reports = []
    for m in sorted(matches_master.get("matches", []), key=lambda x: x.get("date") or ""):
        s = stats_by_url.get(m.get("ogol_url"), {})
        is_home = m.get("is_home")
        suf = "home" if is_home else "away"
        opp_suf = "away" if is_home else "home"
        reports.append({
            "event_id": m.get("event_id"),
            "date": m.get("date"),
            "competition": m.get("competition"),
            "round": m.get("round"),
            "opponent": m.get("opponent"),
            "is_home": is_home,
            "score": m.get("score"),
            "points": m.get("points"),
            "goals_for": m.get("goals_for"),
            "goals_against": m.get("goals_against"),
            "possession_for": s.get(f"possession_{suf}_pct"),
            "possession_against": s.get(f"possession_{opp_suf}_pct"),
            "shots_for": s.get(f"shots_{suf}"),
            "shots_against": s.get(f"shots_{opp_suf}"),
            "shots_on_target_for": s.get(f"shots_on_target_{suf}"),
            "shots_on_target_against": s.get(f"shots_on_target_{opp_suf}"),
            "corners_for": s.get(f"corners_{suf}"),
            "corners_against": s.get(f"corners_{opp_suf}"),
            "fouls_for": s.get(f"fouls_{suf}"),
            "fouls_against": s.get(f"fouls_{opp_suf}"),
            "referee": s.get("referee") or m.get("referee"),
            "attendance": s.get("attendance") or m.get("attendance"),
            "scorers": [g for g in (s.get("goals") or [])],
            "cards": [c for c in (s.get("cards") or [])],
            "tier": "ogol",
        })
    return reports


def build_match_reports(
    matches_master: dict, advanced_matches: dict, players_master: dict,
    ogol_stats: Optional[list] = None, team: str = "fortaleza"
) -> List[dict]:
    adv_list = (advanced_matches or {}).get("matches", []) or []
    if not adv_list:
        return _ogol_match_reports(matches_master, ogol_stats or [])

    aliases = _team_aliases(team)
    mm_by_id = {m["event_id"]: m for m in matches_master.get("matches", [])}
    key_by_sofa = {
        p["sofascore_id"]: p["key"]
        for p in players_master.get("players", []) if p.get("sofascore_id")
    }
    reports: List[dict] = []

    for adv in adv_list:
        mm = mm_by_id.get(adv["event_id"], {})
        side = _team_side(adv, aliases)
        players_for, players_against = [], []
        for p in adv.get("players", []):
            row = {c: p.get(c) for c in _REPORT_PLAYER_COLS}
            if p.get("team") == side:
                row["key"] = key_by_sofa.get(str(p.get("player_id")))
                players_for.append(row)
            else:
                players_against.append(row)

        shots = []
        cum_f = cum_a = 0.0
        race = []
        for s in sorted(adv.get("shots", []), key=lambda x: x.get("minute") or 0):
            is_for = s.get("is_home") == (side == "home")
            shots.append({**s, "side": "for" if is_for else "against"})
            if is_for:
                cum_f += s.get("xg") or 0
            else:
                cum_a += s.get("xg") or 0
            race.append({
                "minute": s.get("minute"),
                "cum_xg_for": round(cum_f, 3),
                "cum_xg_against": round(cum_a, 3),
            })

        top = sorted(
            players_for, key=lambda r: (r.get("xg") or 0) + (r.get("xa") or 0), reverse=True
        )[:3]

        reports.append({
            "event_id": adv["event_id"],
            "date": adv.get("date") or mm.get("date"),
            "competition": adv.get("competition"),
            "round": adv.get("round"),
            "opponent": mm.get("opponent"),
            "is_home": mm.get("is_home", side == "home"),
            "score": mm.get("score"),
            "points": mm.get("points"),
            "xg_for": mm.get("xg_for"),
            "xg_against": mm.get("xg_against"),
            "xgot_for": mm.get("xgot_for"),
            "xgot_against": mm.get("xgot_against"),
            "players_for": players_for,
            "players_against": players_against,
            "shots": shots,
            "xg_race": race,
            "top_contributors": [t["name"] for t in top],
        })
    return reports
