"""Deterministic tactical analysis engine (rule-based, offline).

Processes derived metrics (team_metrics, match_reports, player_metrics) and emits
structured strengths, weaknesses, and tactical notes based on calibrated thresholds.
"""

from __future__ import annotations
from typing import List, Optional

# ---- Season thresholds --------------------------------------------------
FINISHING_GD = 4.0        # goals - xG accumulated
KEEPING_GD = 4.0          # xG against - goals conceded
LUCK_PTS = 6.0            # real points - expected points
XGDIFF_SEASON = 8.0       # accumulated xG diff
HOME_AWAY_PPG_GAP = 0.8   # home ppg - away ppg
AWAY_PPG_WEAK = 1.10
SETPIECE_PCT = 33.0       # % of xG coming from set-pieces
FOULS_GAP = 2.0           # fouls committed vs suffered per game

# ---- Match thresholds ----------------------------------------------------
MATCH_FINISH_GAP = 1.0    # |goals - xG| in match
XG_RACE_LEAD = 0.6        # accumulated xG diff to consider "controlled"
RATING_STAR = 7.3
RATING_POOR = 6.0
MIN_MINUTES = 45


def _mk(tag: str, kind: str, text: str, evidence: str = "") -> dict:
    return {"tag": tag, "kind": kind, "text": text, "evidence": evidence}


# =========================================================================
# SEASON ANALYSIS
# =========================================================================
def build_season_analysis(team_metrics: dict, player_metrics: Optional[List[dict]] = None) -> dict:
    s = team_metrics.get("summary", {})
    items: List[dict] = []

    fin = s.get("finishing")
    if fin is not None:
        if fin >= FINISHING_GD:
            items.append(_mk("finalizacao", "strength",
                             "Converte finalizações acima do esperado (xG).",
                             f"{s.get('goals_for')} gols vs {s.get('xg_for_total')} xG (+{fin:.1f})"))
        elif fin <= -FINISHING_GD:
            items.append(_mk("finalizacao", "weakness",
                             "Desperdiça chances: produz xG mas não converte.",
                             f"{s.get('goals_for')} gols vs {s.get('xg_for_total')} xG ({fin:.1f})"))

    keep = s.get("keeping")
    if keep is not None:
        if keep >= KEEPING_GD:
            items.append(_mk("defesa", "strength",
                             "Defesa/goleiro seguram abaixo do xG sofrido.",
                             f"{s.get('goals_against')} sofridos vs {s.get('xg_against_total')} xG (+{keep:.1f})"))
        elif keep <= -KEEPING_GD:
            items.append(_mk("defesa", "weakness",
                             "Sofre mais gols do que o xG concedido sugere.",
                             f"{s.get('goals_against')} sofridos vs {s.get('xg_against_total')} xG ({keep:.1f})"))

    luck = s.get("points_luck")
    if luck is not None:
        if luck >= LUCK_PTS:
            items.append(_mk("sorte", "note",
                             "Pontuação acima do desempenho — regressão provável.",
                             f"{s.get('points_real')} pts reais vs {s.get('points_expected')} esperados (+{luck:.1f})"))
        elif luck <= -LUCK_PTS:
            items.append(_mk("sorte", "note",
                             "Merecia mais pontos pelo desempenho (azar/eficiência baixa).",
                             f"{s.get('points_real')} pts reais vs {s.get('points_expected')} esperados ({luck:.1f})"))

    xgd = s.get("xg_diff")
    if xgd is not None:
        if xgd >= XGDIFF_SEASON:
            items.append(_mk("controle", "strength",
                             "Domina o volume de chances na temporada.",
                             f"xG diff acumulado {xgd:+.1f}"))
        elif xgd <= -XGDIFF_SEASON:
            items.append(_mk("controle", "weakness",
                             "É dominado no volume de chances na temporada.",
                             f"xG diff acumulado {xgd:+.1f}"))

    ha = team_metrics.get("home_away", {})
    h, a = ha.get("home", {}), ha.get("away", {})
    if h.get("ppg") is not None and a.get("ppg") is not None:
        gap = h["ppg"] - a["ppg"]
        if gap >= HOME_AWAY_PPG_GAP:
            items.append(_mk("mando", "note",
                             "Rendimento muito superior como mandante.",
                             f"{h['ppg']:.2f} ppg casa vs {a['ppg']:.2f} fora"))
        if a["ppg"] <= AWAY_PPG_WEAK:
            items.append(_mk("mando", "weakness",
                             "Fraco fora de casa.",
                             f"{a['ppg']:.2f} ppg fora em {a.get('matches')} jogos"))

    sp = team_metrics.get("set_pieces", {})
    if (sp.get("xg_against_setpiece_pct") or 0) >= SETPIECE_PCT:
        items.append(_mk("bola_parada", "weakness",
                         "Vulnerável em bola parada defensiva.",
                         f"{sp['xg_against_setpiece_pct']:.0f}% do xG sofrido vem de bola parada"))
    if (sp.get("xg_for_setpiece_pct") or 0) >= SETPIECE_PCT:
        items.append(_mk("bola_parada", "strength",
                         "Arma ofensiva forte em bola parada.",
                         f"{sp['xg_for_setpiece_pct']:.0f}% do xG criado vem de bola parada"))

    tl = (team_metrics.get("timeline") or {}).get("against") or {}
    if tl:
        worst = max(tl, key=lambda k: tl[k])
        if tl[worst] > 0 and worst in ("75-90", "90+"):
            items.append(_mk("resistencia", "weakness",
                             "Concede mais no fim do jogo — queda física/concentração.",
                             f"xG sofrido pico no intervalo {worst}' ({tl[worst]:.2f})"))
        elif tl[worst] > 0:
            items.append(_mk("resistencia", "note",
                             f"Período mais frágil defensivamente: {worst}'.",
                             f"xG sofrido {tl[worst]:.2f} no intervalo"))

    stl = team_metrics.get("style", {})
    if stl.get("label") == "direto":
        items.append(_mk("estilo", "note", "Estilo direto/vertical.",
                         f"posse média {stl.get('avg_possession')}%"))
    elif stl.get("label") == "apoio":
        items.append(_mk("estilo", "note", "Estilo de posse/construção.",
                         f"posse média {stl.get('avg_possession')}%"))
    if (stl.get("avg_possession") or 100) < 45 and (xgd or 0) > 0:
        items.append(_mk("estilo", "strength",
                         "Eficiente com pouca posse — cria mais do que domina a bola.",
                         f"posse {stl.get('avg_possession')}% e xG diff {xgd:+.1f}"))

    disc = team_metrics.get("discipline", {})
    af, aa = disc.get("avg_fouls"), disc.get("avg_fouls_against")
    if af is not None and aa is not None and (af - aa) >= FOULS_GAP:
        items.append(_mk("disciplina", "weakness",
                         "Comete bem mais faltas que o adversário — jogo truncado/cartões.",
                         f"{af:.1f} faltas/jogo vs {aa:.1f} do rival"))

    if player_metrics:
        prod = [(p["name"], (p.get("xg_p90") or 0) + (p.get("xa_p90") or 0), p.get("minutes", 0))
                for p in player_metrics if p.get("minutes", 0) >= 300]
        prod.sort(key=lambda x: -x[1])
        if prod:
            total = sum(x[1] * x[2] / 90 for x in prod) or 1
            top3 = sum(x[1] * x[2] / 90 for x in prod[:3])
            share = top3 / total * 100
            if share >= 55:
                items.append(_mk("dependencia", "weakness",
                                 "Produção ofensiva muito concentrada no top-3.",
                                 f"{share:.0f}% do (xG+xA) vem de {', '.join(x[0] for x in prod[:3])}"))

    editorial_hooks = build_editorial_hooks(team_metrics, player_metrics)

    return {
        "strengths": [i for i in items if i["kind"] == "strength"],
        "weaknesses": [i for i in items if i["kind"] == "weakness"],
        "notes": [i for i in items if i["kind"] == "note"],
        "editorial_hooks": editorial_hooks,
        "facts": {
            "points_real": s.get("points_real"),
            "points_expected": s.get("points_expected"),
            "xg_diff": s.get("xg_diff"),
            "finishing": s.get("finishing"),
            "keeping": s.get("keeping"),
            "ppg_home": h.get("ppg"),
            "ppg_away": a.get("ppg"),
        },
    }


def build_editorial_hooks(team_metrics: dict, player_metrics: Optional[List[dict]] = None) -> List[dict]:
    """Gera pautas jornalísticas e manchetes com embasamento estatístico determinístico."""
    hooks: List[dict] = []
    s = team_metrics.get("summary", {})
    luck = s.get("points_luck")
    pts_real = s.get("points_real", 0)
    pts_exp = s.get("points_expected")

    # 1. Sorte vs Desempenho
    if luck is not None:
        if luck >= 4.0:
            hooks.append({
                "type": "alert",
                "tag": "Regressão à Média",
                "headline": f"Pontuação inflada: {pts_real} pontos reais vs {pts_exp:.1f} esperados",
                "lead": f"O time soma +{luck:.1f} pontos acima do modelo Poisson de xG. Eficiência defensiva ou sorte que tendem a regredir no médio prazo.",
                "badge": "Alerta Amarelo",
            })
        elif luck <= -4.0:
            hooks.append({
                "type": "opportunity",
                "tag": "Potencial Reprimido",
                "headline": f"Desempenho não reflete na tabela: {pts_real} pontos reais vs {pts_exp:.1f} esperados",
                "lead": f"A equipe merecia {abs(luck):.1f} pontos a mais pela qualidade das chances geradas e sofridas.",
                "badge": "Tendência de Alta",
            })

    # 2. Garçom Oculto
    if player_metrics:
        underperforming_creators = []
        for p in player_metrics:
            mins = p.get("minutes", 0) or 0
            if mins < 300:
                continue
            xa = (p.get("xa_p90") or 0.0) * mins / 90.0
            assists = p.get("assists", 0) or 0
            gap = xa - assists
            if gap >= 1.0:
                underperforming_creators.append((p["name"], gap, xa, assists))
        if underperforming_creators:
            underperforming_creators.sort(key=lambda x: -x[1])
            top_c = underperforming_creators[0]
            hooks.append({
                "type": "tactical",
                "tag": "O Garçom Oculto",
                "headline": f"{top_c[0]} cria chances de elite que os companheiros não convertem",
                "lead": f"Produziu {top_c[2]:.2f} em Expected Assists (xA), mas soma apenas {top_c[3]} assistências reais por ineficiência dos finalizadores.",
                "badge": "Destaque Individual",
            })

    # 3. Game State (Comportamento em Vantagem)
    gs = team_metrics.get("game_state", {})
    win_state = gs.get("winning", {})
    draw_state = gs.get("drawing", {})
    if win_state.get("minutes", 0) >= 100 and draw_state.get("minutes", 0) >= 100:
        win_xga = win_state.get("xg_against_p90", 0.0)
        draw_xga = draw_state.get("xg_against_p90", 0.0)
        if win_xga >= draw_xga * 1.3 and (win_xga - draw_xga) >= 0.35:
            hooks.append({
                "type": "alert",
                "tag": "Síndrome do Recuo",
                "headline": f"Vulnerabilidade ao liderar: xG concedido sobe para {win_xga:.2f}/90min ao abrir vantagem",
                "lead": f"Quando está empatando o time concede {draw_xga:.2f} xG/90, mas recua e cede {win_xga:.2f} xG/90 quando está à frente no placar.",
                "badge": "Atenção Tática",
            })

    # 4. Impacto do Banco (Supersubs)
    subs = team_metrics.get("substitutions", {})
    supersubs = subs.get("supersubs", [])
    if supersubs:
        top_sub = supersubs[0]
        if top_sub.get("goal_involvements", 0) >= 2 or top_sub.get("prod_total", 0) >= 1.5:
            hooks.append({
                "type": "trend",
                "tag": "O 12º Jogador",
                "headline": f"{top_sub['name']} é o reserva mais decisivo do elenco",
                "lead": f"Saindo do banco em {top_sub['sub_apps']} partidas, acumula {top_sub['goal_involvements']} participações em gols ({top_sub['goals']}G / {top_sub['assists']}A) e {top_sub['prod_total']:.2f} (xG+xA).",
                "badge": "Arma Secreta",
            })

    # 5. Bola Parada & Aérea
    sb = team_metrics.get("shot_breakdown", {}).get("for", {})
    by_body = sb.get("by_body_part", {})
    head_shots = by_body.get("head", {})
    tot_goals = sb.get("total_goals", 0)
    if tot_goals >= 5 and head_shots.get("goals", 0) >= 2:
        head_share = round(head_shots["goals"] / tot_goals * 100, 1)
        if head_share >= 25:
            hooks.append({
                "type": "strength",
                "tag": "Força Aérea",
                "headline": f"Jogo aéreo letal: {head_share:.0f}% dos gols da equipe são de cabeça",
                "lead": f"{head_shots.get('goals', 0)} gols em {head_shots.get('count', 0)} finalizações de cabeça com média de {head_shots.get('xg_per_shot', 0):.2f} xG por tentativa.",
                "badge": "Padrão Ofensivo",
            })

    return hooks


# =========================================================================
# MATCH ANALYSIS
# =========================================================================
def _pm_lookup(team_metrics: dict, date: str, opponent: str) -> dict:
    for m in team_metrics.get("per_match", []):
        if m.get("date") == date and m.get("opponent") == opponent:
            return m
    return {}


def _ogol_match_analysis(report: dict) -> dict:
    """Análise de jogo no tier OGol: placar, finalizações, posse, faltas, cartões."""
    items: List[dict] = []
    gf, ga = report.get("goals_for"), report.get("goals_against")
    sf, sa = report.get("shots_for"), report.get("shots_against")
    sot_f, sot_a = report.get("shots_on_target_for"), report.get("shots_on_target_against")
    pos_f = report.get("possession_for")
    ff, fa = report.get("fouls_for"), report.get("fouls_against")

    if gf is not None and ga is not None:
        if ga >= 3 and ga - gf >= 2:
            items.append(_mk("resultado", "weakness", "Goleada sofrida.", f"{gf}-{ga}"))
        elif gf >= 3 and gf - ga >= 2:
            items.append(_mk("resultado", "strength", "Goleada aplicada.", f"{gf}-{ga}"))

    if sf is not None and sa is not None:
        if sf - sa >= 6:
            items.append(_mk("controle", "strength", "Dominou o volume de finalizações.", f"{sf} x {sa} chutes"))
        elif sa - sf >= 6:
            items.append(_mk("controle", "weakness", "Foi amassado no volume de finalizações.", f"{sf} x {sa} chutes"))

    if gf is not None and sot_f is not None:
        if sot_f >= 6 and gf <= 1:
            items.append(_mk("finalizacao", "weakness", "Pouca pontaria: muito chute no alvo, poucos gols.",
                             f"{gf} gol(s) de {sot_f} no alvo"))
        elif sot_f and gf >= sot_f * 0.6 and gf >= 2:
            items.append(_mk("finalizacao", "strength", "Aproveitamento clínico das chances.",
                             f"{gf} gol(s) de {sot_f} no alvo"))

    if ga is not None and sot_a is not None and sot_a <= 3 and ga >= 2:
        items.append(_mk("defesa", "weakness", "Punição acima do esperado — poucos chutes, muitos gols sofridos.",
                         f"{ga} sofridos de {sot_a} no alvo"))

    if pos_f is not None:
        if pos_f >= 58:
            items.append(_mk("estilo", "note", "Time dominou a posse.", f"{pos_f}% de posse"))
        elif pos_f <= 40:
            items.append(_mk("estilo", "note", "Abriu mão da posse.", f"{pos_f}% de posse"))

    if ff is not None and fa is not None and ff - fa >= 6:
        items.append(_mk("disciplina", "weakness", "Jogo muito truncado pelo próprio time.",
                         f"{ff} faltas x {fa} do rival"))

    reds = [c for c in (report.get("cards") or []) if str(c.get("type", "")).lower().startswith(("v", "r", "2"))]
    if reds:
        items.append(_mk("disciplina", "weakness", "Jogou com um a menos (cartão vermelho).", f"{len(reds)} expulso(s)"))

    strengths = [i for i in items if i["kind"] == "strength"]
    weaknesses = [i for i in items if i["kind"] == "weakness"]
    notes = [i for i in items if i["kind"] == "note"]

    opp = report.get("opponent", "Adversário")
    mando = "em casa" if report.get("is_home") else "fora de casa"
    parts = [f"Partida contra o **{opp}** ({report.get('date')}, {mando}), encerrada em **{report.get('score')}**"
             + (f", {sf} x {sa} finalizações" if sf is not None and sa is not None else "")
             + (f" e {pos_f}% de posse" if pos_f is not None else "") + "."]
    if strengths:
        parts.append("**Pontos Positivos:** " + "; ".join(s["text"].rstrip(".") for s in strengths) + ".")
    if weaknesses:
        parts.append("**Pontos Negativos:** " + "; ".join(w["text"].rstrip(".") for w in weaknesses) + ".")
    if notes:
        parts.append("**Observações Táticas:** " + "; ".join(n["text"].rstrip(".") for n in notes) + ".")

    return {
        "event_id": report.get("event_id"),
        "date": report.get("date"),
        "opponent": report.get("opponent"),
        "score": report.get("score"),
        "tier": "ogol",
        "strengths": strengths,
        "weaknesses": weaknesses,
        "notes": notes,
        "narrative": "\n\n".join(parts),
    }


def build_match_analysis(report: dict, team_metrics: dict) -> dict:
    if report.get("tier") == "ogol":
        return _ogol_match_analysis(report)

    items: List[dict] = []
    xf = report.get("xg_for") or 0.0
    xa = report.get("xg_against") or 0.0
    pts = report.get("points")
    pm = _pm_lookup(team_metrics, report.get("date"), report.get("opponent"))
    xpts = pm.get("xpoints")

    gf = ga = None
    sc = report.get("score") or ""
    if ":" in sc:
        try:
            home_g, away_g = (int(x) for x in sc.split(":"))
            gf, ga = (home_g, away_g) if report.get("is_home") else (away_g, home_g)
        except ValueError:
            gf = ga = None

    # Resultado vs desempenho
    if pts is not None and xpts is not None:
        if pts >= 3 and xf < xa:
            items.append(_mk("resultado", "note",
                             "Vitória sofrida — foi superado no volume de chances.",
                             f"xG {xf:.2f}-{xa:.2f}, xPts {xpts:.2f}"))
        elif pts == 0 and xf > xa + 0.3:
            items.append(_mk("resultado", "weakness",
                             "Dominou e perdeu — falta de eficiência decidiu.",
                             f"xG {xf:.2f}-{xa:.2f}, xPts {xpts:.2f}"))
        elif pts == 1 and abs(xf - xa) > 0.8:
            side = "melhor" if xf > xa else "pior"
            items.append(_mk("resultado", "note",
                             f"Empate com desempenho {side} que o placar.",
                             f"xG {xf:.2f}-{xa:.2f}"))

    # Placar elástico
    if gf is not None and ga is not None:
        if ga >= 3 and ga - gf >= 2:
            items.append(_mk("resultado", "weakness", "Goleada sofrida.", f"{gf}-{ga}"))
        elif gf >= 3 and gf - ga >= 2:
            items.append(_mk("resultado", "strength", "Goleada aplicada.", f"{gf}-{ga}"))

    # Finalização no jogo
    if gf is not None:
        d = gf - xf
        if d >= MATCH_FINISH_GAP:
            items.append(_mk("finalizacao", "strength",
                             "Finalização clínica: converteu acima do xG.",
                             f"{gf} gols de {xf:.2f} xG"))
        elif d <= -MATCH_FINISH_GAP and xf >= 1.0:
            items.append(_mk("finalizacao", "weakness",
                             "Pouca pontaria: criou e não converteu.",
                             f"{gf} gols de {xf:.2f} xG"))
        if (report.get("xgot_for") or 0) < 0.15 and xf >= 1.0:
            items.append(_mk("finalizacao", "weakness",
                             "Quase nada no alvo apesar do volume.",
                             f"xGOT a favor {report.get('xgot_for')}"))

    # Defesa no jogo
    if ga is not None:
        d = xa - ga
        if d >= MATCH_FINISH_GAP:
            items.append(_mk("defesa", "strength",
                             "Defesa/goleiro salvaram — sofreu menos que o xG.",
                             f"{ga} sofridos de {xa:.2f} xG"))
        elif d <= -MATCH_FINISH_GAP and xa < 1.0:
            items.append(_mk("defesa", "weakness",
                             "Punição acima do esperado — erros pontuais custaram caro.",
                             f"{ga} sofridos de {xa:.2f} xG"))

    # Corrida de xG
    race = report.get("xg_race") or []
    behind_at = None
    for pt in race:
        if (pt.get("cum_xg_against", 0) - pt.get("cum_xg_for", 0)) >= XG_RACE_LEAD:
            behind_at = pt.get("minute")
            break
    ahead_all = race and all(
        pt.get("cum_xg_for", 0) >= pt.get("cum_xg_against", 0) - 0.05 for pt in race[len(race) // 3:]
    )
    end_gap = (race[-1].get("cum_xg_against", 0) - race[-1].get("cum_xg_for", 0)) if race else 0
    if end_gap >= 1.2:
        items.append(_mk("controle", "weakness",
                         "Amassado no volume de chances.",
                         f"xG final {xf:.2f}-{xa:.2f}"))
    elif behind_at is not None and behind_at <= 30:
        items.append(_mk("controle", "weakness",
                         "Entrou mal no jogo — cedeu xG cedo.",
                         f"atrás no xG já aos {behind_at}'"))
    elif ahead_all and xf > xa:
        items.append(_mk("controle", "strength",
                         "Controlou o jogo do início ao fim no xG.",
                         f"xG final {xf:.2f}-{xa:.2f}"))

    # Jogadores
    fors = [p for p in report.get("players_for", []) if (p.get("minutes_played") or 0) >= MIN_MINUTES]
    if fors:
        best = max(fors, key=lambda p: p.get("rating") or 0)
        worst = min(fors, key=lambda p: p.get("rating") or 99)
        if (best.get("rating") or 0) >= RATING_STAR:
            b_prod = (best.get("xg") or 0) + (best.get("xa") or 0)
            verb = "decisivo" if b_prod >= 0.5 else "melhor em campo"
            items.append(_mk("individual", "strength",
                             f"{best['name']} {verb}.",
                             f"nota {best['rating']}, xG+xA {b_prod:.2f}"))
        if (worst.get("rating") or 99) <= RATING_POOR:
            items.append(_mk("individual", "weakness",
                             f"{worst['name']} abaixo.",
                             f"nota {worst['rating']}"))

    # Perigo adversário
    ags = [p for p in report.get("players_against", []) if (p.get("xg") or 0) + (p.get("xa") or 0) >= 0.5]
    if ags:
        d = max(ags, key=lambda p: (p.get("xg") or 0) + (p.get("xa") or 0))
        items.append(_mk("alerta", "note",
                         f"{d['name']} foi o mais perigoso do rival.",
                         f"xG+xA {(d.get('xg') or 0) + (d.get('xa') or 0):.2f}"))

    # Bola parada
    conc_sp = [sh for sh in report.get("shots", [])
               if sh.get("side") == "against" and sh.get("is_goal")
               and sh.get("situation") in ("corner", "set-piece", "free-kick", "penalty")]
    if conc_sp:
        items.append(_mk("bola_parada", "weakness",
                         "Sofreu gol de bola parada.",
                         f"{len(conc_sp)} gol(s) em {', '.join(sorted({s['situation'] for s in conc_sp}))}"))

    strengths = [i for i in items if i["kind"] == "strength"]
    weaknesses = [i for i in items if i["kind"] == "weakness"]
    notes = [i for i in items if i["kind"] == "note"]

    opp = report.get("opponent", "Adversário")
    mando = "em casa" if report.get("is_home") else "fora de casa"
    narrative_parts = [
        f"Partida disputada contra o **{opp}** ({report.get('date')}, {mando}), encerrada em **{report.get('score')}**, com **{xf:.2f} xG gerados** e **{xa:.2f} xG concedidos**."
    ]
    if strengths:
        s_list = "; ".join(s["text"].rstrip(".") for s in strengths)
        narrative_parts.append(f"**Pontos Positivos:** {s_list}.")
    if weaknesses:
        w_list = "; ".join(w["text"].rstrip(".") for w in weaknesses)
        narrative_parts.append(f"**Pontos Negativos:** {w_list}.")
    if notes:
        n_list = "; ".join(n["text"].rstrip(".") for n in notes)
        narrative_parts.append(f"**Observações Táticas:** {n_list}.")

    return {
        "event_id": report.get("event_id"),
        "date": report.get("date"),
        "opponent": report.get("opponent"),
        "score": report.get("score"),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "notes": notes,
        "narrative": "\n\n".join(narrative_parts),
    }


def build_analysis(team_metrics: dict, match_reports: list, player_metrics: list,
                   team_name: str = "a equipe") -> dict:
    """Envelope completo salvo em ``data/<team>_analysis.json``."""
    reports = match_reports.get("reports") if isinstance(match_reports, dict) else (match_reports or [])
    season_ana = build_season_analysis(team_metrics, player_metrics)

    s = team_metrics.get("summary", {})
    xg_diff = s.get("xg_diff")
    xg_txt = f" e saldo de **{xg_diff:+.2f} xG**" if isinstance(xg_diff, (int, float)) else ""
    xpts = s.get("points_expected")
    xpts_txt = f" com **{xpts:.1f} xPts** esperados" if isinstance(xpts, (int, float)) and xpts else ""
    s_narrative = [
        f"Na temporada, {team_name} soma **{s.get('points_real', 0)} pontos reais** "
        f"({s.get('wins', 0)}V, {s.get('draws', 0)}E, {s.get('losses', 0)}D){xpts_txt}{xg_txt}."
    ]
    if season_ana.get("strengths"):
        s_list = "; ".join(x["text"].rstrip(".") for x in season_ana["strengths"])
        s_narrative.append(f"**Virtudes da Equipe:** {s_list}.")
    if season_ana.get("weaknesses"):
        w_list = "; ".join(x["text"].rstrip(".") for x in season_ana["weaknesses"])
        s_narrative.append(f"**Vulnerabilidades:** {w_list}.")
    if season_ana.get("notes"):
        n_list = "; ".join(x["text"].rstrip(".") for x in season_ana["notes"])
        s_narrative.append(f"**Padrões Táticos:** {n_list}.")
    season_ana["narrative"] = "\n\n".join(s_narrative)

    return {
        "season": season_ana,
        "matches": {
            str(r.get("event_id")): build_match_analysis(r, team_metrics) for r in reports
        },
    }

