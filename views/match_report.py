import os
import pandas as pd
import streamlit as st

from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_analysis_section,
    render_page_header,
)

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Relatório de Jogo — {team_name}",
    subtitle="Evolução cumulativa de xG (xG Race), estatísticas detalhadas e mapa de finalizações.",
    tag="Match Report",
)

mr_data = load_json(f"{team}_match_reports.json")
analysis_data = load_json(f"{team}_analysis.json")
reports = mr_data.get("reports", [])
if not reports:
    st.warning(f"Sem relatórios de jogo para {team_name}. Rode: `python main.py --team {team} --build`")
    st.stop()


def _format_match(r: dict) -> str:
    date = r.get("date") or "Data desconhecida"
    opp = r.get("opponent") or "Adversário"
    mando = "Casa" if r.get("is_home") else "Fora"
    score = r.get("score")
    score_str = f"({score})" if score else ""
    xg_for = f"{r.get('xg_for'):.2f}" if r.get("xg_for") is not None else "?"
    xg_against = f"{r.get('xg_against'):.2f}" if r.get("xg_against") is not None else "?"
    comp = r.get("competition") or ""
    rnd = f"r{r.get('round')}" if r.get("round") else ""
    return f"{date} · vs {opp} {score_str} [{mando}] · xG: {xg_for} x {xg_against} ({comp} {rnd})".strip()


match_options = {r["event_id"]: r for r in reports}
selected_id = st.selectbox(
    "Selecione a partida para análise detalhada",
    list(match_options.keys()),
    format_func=lambda eid: _format_match(match_options[eid]),
)

match = match_options[selected_id]
match_analysis = (analysis_data.get("matches") or {}).get(str(selected_id), {})

# Linha de métricas no topo
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Resultado / Placar",
    match.get("score") or "Sem placar",
    help=f"{match.get('points', '-')} pontos obtidos",
)
c2.metric(
    "xG (Fortaleza x Adv)",
    f"{match.get('xg_for') or 0:.2f} x {match.get('xg_against') or 0:.2f}",
)
c3.metric(
    "xGOT (Fortaleza x Adv)",
    f"{match.get('xgot_for') or 0:.2f} x {match.get('xgot_against') or 0:.2f}",
)
top_str = ", ".join(match.get("top_contributors") or []) or "N/A"
c4.metric("Destaques (xG + xA)", top_str)

st.divider()

# Diagnóstico tático inteligente da partida
if match_analysis:
    render_analysis_section(match_analysis, title=f"Diagnóstico Tático da Partida (vs {match.get('opponent')})")
    st.divider()

# Gráfico de evolução de xG (xG Race)
st.subheader("🏁 Evolução de xG na Partida (xG Race)")
race = match.get("xg_race", [])
if race:
    rdf = pd.DataFrame(race)
    rdf = rdf.rename(
        columns={
            "minute": "Minuto",
            "cum_xg_for": "Fortaleza (xG acum.)",
            "cum_xg_against": f"{match.get('opponent')} (xG acum.)",
        }
    )
    st.line_chart(
        rdf.set_index("Minuto")[["Fortaleza (xG acum.)", f"{match.get('opponent')} (xG acum.)"]],
        color=["#002B7F", "#E31A2C"],
        width="stretch",
    )
else:
    st.caption("Sem dados de finalizações para esta partida.")

# Abas para escalações e finalizações
tab_for, tab_against, tab_shots = st.tabs(
    ["🦁 Fortaleza", f"⚔️ Adversário ({match.get('opponent') or 'Adversário'})", "🎯 Finalizações"]
)


def _format_players_df(players_list):
    if not players_list:
        return pd.DataFrame()
    df = pd.DataFrame(players_list)
    cols = [
        "name",
        "is_starter",
        "minutes_played",
        "rating",
        "touches",
        "passes_total",
        "passes_accurate",
        "key_passes",
        "possession_lost",
        "ball_recovery",
        "duels_won",
        "duels_lost",
        "xg",
        "xa",
        "shots_total",
        "goals",
    ]
    cols = [c for c in cols if c in df.columns]
    rename_map = {
        "name": "Nome",
        "is_starter": "Titular",
        "minutes_played": "Min",
        "rating": "Rating",
        "touches": "Toques",
        "passes_total": "Passes",
        "passes_accurate": "Passes certos",
        "key_passes": "Passes-chave",
        "possession_lost": "Bola perdida",
        "ball_recovery": "Bola recup.",
        "duels_won": "Duelos ganhos",
        "duels_lost": "Duelos perdidos",
        "xg": "xG",
        "xa": "xA",
        "shots_total": "Finaliz.",
        "goals": "Gols",
    }
    return df[cols].rename(columns=rename_map)


with tab_for:
    st.markdown("**Atletas do Fortaleza em Campo**")
    p_for_df = _format_players_df(match.get("players_for", []))
    if not p_for_df.empty:
        st.dataframe(p_for_df, width="stretch", hide_index=True)
    else:
        st.caption("Sem estatísticas individuais para o Fortaleza.")

with tab_against:
    st.markdown(f"**Atletas de {match.get('opponent') or 'Adversário'}**")
    p_against_df = _format_players_df(match.get("players_against", []))
    if not p_against_df.empty:
        st.dataframe(p_against_df, width="stretch", hide_index=True)
    else:
        st.caption("Sem estatísticas individuais para o adversário.")

with tab_shots:
    shots = match.get("shots", [])
    if shots:
        st.markdown("**Lista Detalhada de Finalizações**")
        sdf = pd.DataFrame(shots)
        shot_cols = [
            "minute",
            "player_name",
            "side",
            "xg",
            "xgot",
            "shot_type",
            "situation",
            "body_part",
            "is_goal",
        ]
        shot_cols = [c for c in shot_cols if c in sdf.columns]
        display_sdf = sdf[shot_cols].rename(
            columns={
                "minute": "Min",
                "player_name": "Jogador",
                "side": "Lado",
                "xg": "xG",
                "xgot": "xGOT",
                "shot_type": "Resultado",
                "situation": "Situação",
                "body_part": "Parte do corpo",
                "is_goal": "Gol",
            }
        )
        st.dataframe(display_sdf, width="stretch", hide_index=True)

        st.subheader("📊 xG por Tipo de Jogada")
        by_sit = (
            sdf.groupby(["situation", "side"])["xg"]
            .agg(finalizacoes="count", xg_total="sum")
            .round(3)
            .reset_index()
            .rename(
                columns={
                    "situation": "Situação",
                    "side": "Lado",
                    "finalizacoes": "Finaliz.",
                    "xg_total": "xG Total",
                }
            )
        )
        st.dataframe(by_sit, width="stretch", hide_index=True)
    else:
        st.caption("Sem registro de finalizações.")

