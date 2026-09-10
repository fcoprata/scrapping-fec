"""Narrative synthesis generator (rule-based, deterministic — no external API)."""

from typing import Optional
from config import TEAMS
from storage.json_store import JsonStore


def generate_match_narrative(match_analysis: dict, report: dict, team_name: str = "A equipe") -> str:
    """Gera uma síntese executiva textual para uma partida a partir dos dados derivados."""
    opp = report.get("opponent", "Adversário")
    date = report.get("date", "")
    score = report.get("score", "")
    mando = "em casa" if report.get("is_home") else "fora de casa"
    xf = report.get("xg_for", 0) or 0
    xa = report.get("xg_against", 0) or 0

    strengths = [s["text"] for s in match_analysis.get("strengths", [])]
    weaknesses = [w["text"] for w in match_analysis.get("weaknesses", [])]
    notes = [n["text"] for n in match_analysis.get("notes", [])]
    top = report.get("top_contributors", [])

    lines = []
    lines.append(
        f"No confronto contra o **{opp}** ({date}, {mando}), finalizado com o placar de **{score}**, "
        f"o {team_name} registrou **{xf:.2f} xG gerados** contra **{xa:.2f} xG concedidos**."
    )

    if strengths:
        s_list = "; ".join(s.rstrip(".") for s in strengths)
        lines.append(f"**Destaques positivos:** {s_list}.")
    if weaknesses:
        w_list = "; ".join(w.rstrip(".") for w in weaknesses)
        lines.append(f"**Pontos de atenção:** {w_list}.")
    if notes:
        n_list = "; ".join(n.rstrip(".") for n in notes)
        lines.append(f"**Observações:** {n_list}.")
    if top:
        lines.append(f"Os atletas com maior participação na criação ofensiva (xG + xA) foram **{', '.join(top)}**.")

    return "\n\n".join(lines)


def generate_season_narrative(season_analysis: dict, team_metrics: dict, team_name: str = "A equipe") -> str:
    """Gera uma síntese executiva textual para a temporada."""
    s = team_metrics.get("summary", {})
    strengths = [s_item["text"] for s_item in season_analysis.get("strengths", [])]
    weaknesses = [w["text"] for w in season_analysis.get("weaknesses", [])]
    notes = [n["text"] for n in season_analysis.get("notes", [])]

    pts_exp = s.get("points_expected")
    xg_diff = s.get("xg_diff")
    exp_txt = ""
    if pts_exp is not None:
        exp_txt += f", com expectativa Poisson de **{pts_exp:.1f} xPts**"
    if xg_diff is not None:
        exp_txt += f" e saldo acumulado de xG de **{xg_diff:+.2f}**"

    lines = []
    lines.append(
        f"O {team_name} soma **{s.get('points_real', 0)} pontos reais** em {s.get('matches', 0)} jogos "
        f"({s.get('wins', 0)}V, {s.get('draws', 0)}E, {s.get('losses', 0)}D){exp_txt}."
    )

    if strengths:
        s_list = "; ".join(s.rstrip(".") for s in strengths)
        lines.append(f"**Principais virtudes da equipe:** {s_list}.")
    if weaknesses:
        w_list = "; ".join(w.rstrip(".") for w in weaknesses)
        lines.append(f"**Vulnerabilidades monitoradas:** {w_list}.")
    if notes:
        n_list = "; ".join(n.rstrip(".") for n in notes)
        lines.append(f"**Padrões táticos observados:** {n_list}.")

    return "\n\n".join(lines)


def narrate(team: str, store: JsonStore, scope: str = "all", limit: Optional[int] = None) -> None:
    """Entrypoint CLI: enriquece data/<team>_analysis.json com narrativas determinísticas."""
    analysis = store.load_analysis(team)
    if not analysis:
        print(f"Sem análise prévia para '{team}'. Rode --build primeiro.")
        return

    team_name = TEAMS.get(team, {}).get("name", team.title())
    team_metrics = store.load_team_metrics(team)
    reports = store.load_match_reports(team).get("reports", [])
    rep_by_id = {str(r.get("event_id")): r for r in reports}

    print("Gerando narrativas determinísticas offline...")

    if scope in ("season", "all") and "season" in analysis:
        analysis["season"]["narrative"] = generate_season_narrative(
            analysis["season"], team_metrics, team_name
        )
        print("  -> temporada: narrativa gerada.")

    if scope in ("matches", "all") and "matches" in analysis:
        match_keys = list(analysis["matches"].keys())
        if limit:
            match_keys = match_keys[:limit]
        for eid in match_keys:
            rep = rep_by_id.get(eid, {})
            analysis["matches"][eid]["narrative"] = generate_match_narrative(
                analysis["matches"][eid], rep, team_name
            )
        print(f"  -> {len(match_keys)} partidas: narrativas geradas.")

    season_year = team_metrics.get("season_year", "")
    saved_path = store.save_analysis(team, analysis, season_year)
    print(f"\nSalvo com sucesso -> {saved_path}")
