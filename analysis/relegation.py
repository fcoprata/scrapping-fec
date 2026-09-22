"""Motor de análise determinística para a luta contra o rebaixamento (Z-4) na Série B.

Cruza dados da tabela de classificação oficial e da esteira analítica com os cálculos
de probabilidade e desempenho segmentado da UFMG.
"""

import logging
from typing import Any, Dict, List, Optional
from name_match import normalize_name

logger = logging.getLogger(__name__)


def _calc_target_combo(pts_needed: int, matches_remaining: int) -> str:
    """Calcula combinação de V, E, D para atingir a meta de pontos."""
    if pts_needed <= 0:
        return "Meta atingida 🎉"
    if pts_needed > matches_remaining * 3:
        return "Inviável matematicamente ❌"
    for e in [1, 2, 0, 3, 4]:
        v = (pts_needed - e + 2) // 3
        if v < 0:
            v = 0
        if (v * 3 + e) >= pts_needed and (v + e) <= matches_remaining:
            d = matches_remaining - v - e
            return f"{v}V {e}E {d}D"
    v = (pts_needed + 2) // 3
    d = matches_remaining - v
    return f"{v}V {d}D"


def _match_team_name(name_a: str, name_b: str) -> bool:
    na = normalize_name(name_a)
    nb = normalize_name(name_b)
    return na == nb or na in nb or nb in na


def _find_standings_row(
    team_name: str, standings_rows: List[Dict[str, Any]], team_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Casa o time com uma linha da tabela de classificação.

    `team_id` (SofaScore, já presente em cada row de `get_standings`) é a chave
    real e sempre preferida quando disponível — nomes de exibição divergem
    entre fontes, `team_id` não. Nomes só entram como fallback pra tabelas sem
    `team_id` (ex.: dados UFMG). Exact match de nome antes de substring; nunca
    cai de volta pro primeiro item da tabela — isso já causou pontos/posição de
    outro clube sendo exibidos silenciosamente.
    """
    if team_id is not None:
        for r in standings_rows:
            if r.get("team_id") == team_id:
                return r
        logger.warning("relegation: team_id=%s não encontrado na tabela (%d rows)", team_id, len(standings_rows))
        return None

    norm_target = normalize_name(team_name)

    for r in standings_rows:
        if normalize_name(r.get("team_name", "")) == norm_target:
            return r

    candidates = [r for r in standings_rows if _match_team_name(r.get("team_name", ""), norm_target)]
    if len(candidates) == 1:
        logger.warning(
            "relegation: '%s' casado por substring com '%s' na tabela (sem match exato)",
            team_name, candidates[0].get("team_name"),
        )
        return candidates[0]
    if len(candidates) > 1:
        logger.warning(
            "relegation: '%s' ambíguo entre %d times na tabela (%s) — nenhum retornado",
            team_name, len(candidates), [c.get("team_name") for c in candidates],
        )
        return None

    logger.warning("relegation: '%s' não encontrado na tabela de classificação", team_name)
    return None


def calc_team_relegation_profile(
    team_name: str,
    standings_rows: List[Dict[str, Any]],
    ufmg_data: Optional[Dict[str, Any]] = None,
    total_rounds: int = 38,
    team_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Calcula diagnóstico detalhado de permanência/rebaixamento para uma equipe.

    `team_id` (SofaScore) deve ser passado sempre que disponível — é a chave
    confiável pra achar a linha certa na tabela de classificação.
    """
    norm_target = normalize_name(team_name)
    row = _find_standings_row(team_name, standings_rows, team_id=team_id)
    unmatched = row is None

    pos = row.get("position", 0) if row else 0
    played = row.get("played", 28) if row else 28
    points = row.get("points", 0) if row else 0
    wins = row.get("wins", 0) if row else 0
    draws = row.get("draws", 0) if row else 0
    losses = row.get("losses", 0) if row else 0
    gd = row.get("goal_diff", 0) if row else 0

    remaining = max(0, total_rounds - played)
    max_pts = points + (remaining * 3)
    ppg_real = (points / played) if played else 0.0
    proj_real = round(points + (ppg_real * remaining), 1)

    # Probabilidade UFMG
    ufmg_prob = 0.0
    if ufmg_data:
        reb_list = ufmg_data.get("probabilities", {}).get("rebaixamento", [])
        for u in reb_list:
            if _match_team_name(u.get("team", ""), norm_target):
                ufmg_prob = u.get("prob", 0.0)
                break

    # Metas de corte (45 pts = corte seguro tradicional; 46 pts = garantia ~93% UFMG)
    TARGET_SAFE_45 = 45
    TARGET_SAFE_46 = 46

    needed_45 = max(0, TARGET_SAFE_45 - points)
    needed_46 = max(0, TARGET_SAFE_46 - points)

    req_ppg_45 = round(needed_45 / remaining, 2) if remaining else 0.0
    req_pct_45 = round((req_ppg_45 / 3.0) * 100, 1) if remaining else 0.0
    combo_45 = _calc_target_combo(needed_45, remaining)

    req_ppg_46 = round(needed_46 / remaining, 2) if remaining else 0.0
    req_pct_46 = round((req_ppg_46 / 3.0) * 100, 1) if remaining else 0.0
    combo_46 = _calc_target_combo(needed_46, remaining)

    # Avaliação do Nível de Risco
    if points >= TARGET_SAFE_45:
        risk_level = "Seguro"
        risk_color = "#10B981"
        badge = "🟢 Permanência Praticamente Assegurada"
        desc = "A equipe já alcançou a margem matemática segura de 45+ pontos."
    elif ufmg_prob >= 75.0:
        risk_level = "Crítico"
        risk_color = "#EF4444"
        badge = "🔴 Risco Crítico de Rebaixamento"
        desc = "Probabilidade de queda alarmante acima de 75%. Exige campanha de G-4 na reta final."
    elif ufmg_prob >= 30.0:
        risk_level = "Alto Risco"
        risk_color = "#F97316"
        badge = "🟠 Alto Risco (Zona de Degola Iminente)"
        desc = "Equipe sob forte ameaça de rebaixamento. Margem de erro mínima nos jogos restantes."
    elif ufmg_prob >= 5.0 or pos >= 15:
        risk_level = "Alerta"
        risk_color = "#F59E0B"
        badge = "🟡 Estado de Alerta (Próximo ao Z-4)"
        desc = "Pontuação perigosa próxima da zona de degola. Requer aceleração no aproveitamento."
    elif ufmg_prob > 0.0:
        risk_level = "Atenção"
        risk_color = "#3B82F6"
        badge = "🔵 Risco Residual"
        desc = "Probabilidade baixa, mas matematicamente ainda vulnerável a oscilações extremas."
    else:
        risk_level = "Livre"
        risk_color = "#10B981"
        badge = "🟢 Risco Zero (0.0% UFMG)"
        desc = "Sem risco prático de rebaixamento para a Série C."

    return {
        "team_name": team_name,
        "unmatched": unmatched,
        "position": pos,
        "played": played,
        "points": points,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goal_diff": gd,
        "remaining_matches": remaining,
        "max_possible_points": max_pts,
        "ppg_real": ppg_real,
        "proj_final_points": proj_real,
        "ufmg_relegation_prob": ufmg_prob,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "badge": badge,
        "description": desc,
        "target_45": {
            "target": TARGET_SAFE_45,
            "needed": needed_45,
            "req_ppg": req_ppg_45,
            "req_pct": req_pct_45,
            "combo": combo_45,
            "sufficient_pace": proj_real >= TARGET_SAFE_45,
        },
        "target_46": {
            "target": TARGET_SAFE_46,
            "needed": needed_46,
            "req_ppg": req_ppg_46,
            "req_pct": req_pct_46,
            "combo": combo_46,
            "sufficient_pace": proj_real >= TARGET_SAFE_46,
        },
    }


def build_relegation_overview(
    standings_rows: List[Dict[str, Any]],
    ufmg_data: Optional[Dict[str, Any]] = None,
    safe_target: int = 45,
    total_rounds: int = 38,
) -> List[Dict[str, Any]]:
    """Gera matriz comparativa de todos os clubes ameaçados pelo rebaixamento."""
    ufmg_reb_map = {}
    last10_map = {}
    home_map = {}
    away_map = {}

    if ufmg_data:
        for u in ufmg_data.get("probabilities", {}).get("rebaixamento", []):
            ufmg_reb_map[normalize_name(u.get("team", ""))] = u.get("prob", 0.0)

        for l in ufmg_data.get("standings", {}).get("last_10_rounds", []):
            last10_map[normalize_name(l.get("team", ""))] = l

        for h in ufmg_data.get("standings", {}).get("home", []):
            home_map[normalize_name(h.get("team", ""))] = h

        for a in ufmg_data.get("standings", {}).get("away", []):
            away_map[normalize_name(a.get("team", ""))] = a

    overview = []
    for r in standings_rows:
        tname = r.get("team_name", "")
        norm = normalize_name(tname)
        pos = r.get("position", 0)
        played = r.get("played", 28)
        points = r.get("points", 0)
        gd = r.get("goal_diff", 0)
        remaining = max(0, total_rounds - played)

        # Buscar probabilidade UFMG correspondente
        prob = ufmg_reb_map.get(norm)
        if prob is None:
            substr_hits = [(k, v) for k, v in ufmg_reb_map.items() if k in norm or norm in k]
            if len(substr_hits) == 1:
                prob = substr_hits[0][1]
            elif len(substr_hits) > 1:
                logger.warning(
                    "relegation overview: '%s' ambíguo entre %d times UFMG (%s) — prob 0.0",
                    tname, len(substr_hits), [k for k, _ in substr_hits],
                )
        prob = prob if prob is not None else 0.0

        # Considerar ameaçados: probabilidade > 0 ou posição >= 13 ou pontos < 45
        if prob > 0.0 or pos >= 13 or points < safe_target:
            needed = max(0, safe_target - points)
            req_ppg = round(needed / remaining, 2) if remaining else 0.0
            req_pct = round((req_ppg / 3.0) * 100, 1) if remaining else 0.0
            ppg = (points / played) if played else 0.0
            proj = round(points + (ppg * remaining), 1)

            # Buscar momento nas últimas 10 rodadas
            l10 = last10_map.get(norm, {})
            l10_pts = l10.get("points", "—")
            l10_eff = f"{l10.get('efficiency', 0.0):.1f}%" if "efficiency" in l10 else "—"

            overview.append({
                "pos": pos,
                "team": tname,
                "played": played,
                "points": points,
                "needed_45": needed,
                "req_pct": req_pct,
                "req_ppg": req_ppg,
                "combo_10j": _calc_target_combo(needed, remaining),
                "proj_final": proj,
                "prob_ufmg": prob,
                "last_10_pts": l10_pts,
                "last_10_eff": l10_eff,
                "in_z4": pos >= 17,
            })

    # Ordenar por probabilidade de queda descrescente e depois posição decrescente
    overview.sort(key=lambda x: (x["prob_ufmg"], -x["pos"]), reverse=True)
    return overview
