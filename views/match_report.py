import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_analysis_section,
    render_page_header,
)
from views.pitch import create_2d_pitch_figure, SITUATION_PT, BODY_PART_PT, SHOT_TYPE_PT

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Relatório de Jogo — {team_name}",
    subtitle="Evolução cumulativa de xG (xG Race), mapa interativo de finalizações, impacto do banco e síntese de imprensa.",
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
ordered_ids = sorted(
    match_options,
    key=lambda eid: match_options[eid].get("date") or "",
    reverse=True,
)
selected_id = st.selectbox(
    "Selecione a partida para análise detalhada",
    ordered_ids,
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
    f"xG ({team_name} x Adv)",
    f"{match.get('xg_for') or 0:.2f} x {match.get('xg_against') or 0:.2f}",
)
c3.metric(
    f"xGOT ({team_name} x Adv)",
    f"{match.get('xgot_for') or 0:.2f} x {match.get('xgot_against') or 0:.2f}",
    help="Expected Goals on Target: mede a qualidade dos chutes que foram no gol",
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
            "cum_xg_for": f"{team_name} (xG acum.)",
            "cum_xg_against": f"{match.get('opponent')} (xG acum.)",
        }
    )
    st.line_chart(
        rdf.set_index("Minuto")[[f"{team_name} (xG acum.)", f"{match.get('opponent')} (xG acum.)"]],
        color=["#002B7F", "#E31A2C"],
        width="stretch",
    )
else:
    st.caption("Sem dados de finalizações para esta partida.")

# Abas para escalações, finalizações, banco e imprensa
tab_shots_map, tab_for, tab_against, tab_subs, tab_press = st.tabs(
    [
        "🎯 Mapa de Finalizações (Plotly)",
        f"🦁 {team_name}",
        f"⚔️ {match.get('opponent') or 'Adversário'}",
        "🔄 Impacto do Banco",
        "📰 Síntese de Imprensa",
    ]
)


# ------------------------------------------------------------
# ABA 1: Campo 2D Interativo (Finalizações & Assistências)
# ------------------------------------------------------------
with tab_shots_map:
    shots = match.get("shots", [])
    if shots:
        st.subheader("🏟️ Campo 2D: Mapa de Finalizações & Assistências")
        st.caption("Plotagem espacial exata no gramado com trajetórias de finalização e linhas de passe de assistência.")

        opp_name = match.get("opponent", "Adversário")
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            side_filter = st.radio(
                "Filtrar por Equipe",
                ["Todas", f"{team_name}", f"{opp_name}"],
                horizontal=True,
                key="mr_pitch_team_filter",
            )
        with col_f2:
            show_traj = st.checkbox("Exibir Trajetórias", value=True, key="mr_pitch_traj")
        with col_f3:
            show_ast = st.checkbox("Exibir Assistências", value=True, key="mr_pitch_ast")

        # Filtrar chutes
        if side_filter == team_name:
            active_shots = [s for s in shots if s.get("side") == "for"]
        elif side_filter == opp_name:
            active_shots = [s for s in shots if s.get("side") == "against"]
        else:
            active_shots = shots

        # Renderizar Campo 2D
        pitch_fig = create_2d_pitch_figure(
            active_shots,
            title=f"Campo 2D — {team_name} vs {opp_name} ({len(active_shots)} finalizações)",
            show_trajectories=show_traj,
            show_assists=show_ast,
            height=530,
        )
        st.plotly_chart(pitch_fig, width="stretch", config={"responsive": True, "displayModeBar": False})

        # Tabela das finalizações
        st.subheader("📋 Detalhamento Lance a Lance")
        if active_shots:
            sdf = pd.DataFrame(active_shots)
            sdf["Time"] = sdf["side"].map({"for": team_name, "against": opp_name}).fillna(sdf.get("side", "")) if "side" in sdf.columns else ""
            sdf["Resultado"] = sdf["shot_type"].map(SHOT_TYPE_PT).fillna(sdf.get("shot_type", "")) if "shot_type" in sdf.columns else ""
            sdf["Situação"] = sdf["situation"].map(SITUATION_PT).fillna(sdf.get("situation", "")) if "situation" in sdf.columns else ""
            sdf["Parte"] = sdf["body_part"].map(BODY_PART_PT).fillna(sdf.get("body_part", "")) if "body_part" in sdf.columns else ""
            sdf["is_goal"] = sdf["is_goal"].map({True: "⚽ Sim", False: "Não"}) if "is_goal" in sdf.columns else "Não"
            if "xg" in sdf.columns:
                sdf["xg"] = sdf["xg"].apply(lambda v: f"{float(v):.2f}" if v is not None and not pd.isna(v) else "-")
            if "xgot" in sdf.columns:
                sdf["xgot"] = sdf["xgot"].apply(lambda v: f"{float(v):.2f}" if v is not None and not pd.isna(v) else "-")

            shot_cols = [c for c in ["minute", "player_name", "Time", "xg", "xgot", "Resultado", "Situação", "Parte", "is_goal"] if c in sdf.columns]
            rename_dict = {
                "minute": "Min",
                "player_name": "Finalizador",
                "xg": "xG",
                "xgot": "xGOT",
                "is_goal": "Gol?",
            }
            st.dataframe(
                sdf[shot_cols].rename(columns={k: v for k, v in rename_dict.items() if k in shot_cols}),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Nenhuma finalização encontrada para o filtro selecionado.")
    else:
        st.caption("Sem registro detalhado de finalizações.")


# ------------------------------------------------------------
# Helper para tabelas de atletas
# ------------------------------------------------------------
def _format_players_df(players_list):
    if not players_list:
        return pd.DataFrame()
    df = pd.DataFrame(players_list)

    if {"passes_accurate", "passes_total"}.issubset(df.columns):
        denom = df["passes_total"].astype(float).replace(0, float("nan"))
        df["pct_passes_certos"] = (df["passes_accurate"] / denom * 100).round(1)
    if {"possession_lost", "touches"}.issubset(df.columns):
        denom = df["touches"].astype(float).replace(0, float("nan"))
        df["pct_bolas_perdidas"] = (df["possession_lost"] / denom * 100).round(1)
    if {"duels_won", "duels_lost"}.issubset(df.columns):
        total_duels = (df["duels_won"] + df["duels_lost"]).astype(float).replace(0, float("nan"))
        df["pct_duelos_ganhos"] = (df["duels_won"] / total_duels * 100).round(1)

    cols = [
        "name",
        "is_starter",
        "minutes_played",
        "rating",
        "touches",
        "passes_total",
        "passes_accurate",
        "pct_passes_certos",
        "key_passes",
        "possession_lost",
        "pct_bolas_perdidas",
        "ball_recovery",
        "duels_won",
        "duels_lost",
        "pct_duelos_ganhos",
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
        "pct_passes_certos": "% Passes certos",
        "key_passes": "Passes-chave",
        "possession_lost": "Bola perdida",
        "pct_bolas_perdidas": "% Bolas perdidas",
        "ball_recovery": "Bola recup.",
        "duels_won": "Duelos ganhos",
        "duels_lost": "Duelos perdidos",
        "pct_duelos_ganhos": "% Duelos ganhos",
        "xg": "xG",
        "xa": "xA",
        "shots_total": "Finaliz.",
        "goals": "Gols",
    }
    return df[cols].rename(columns=rename_map)


with tab_for:
    st.markdown(f"**Atletas do {team_name} em Campo**")
    p_for_df = _format_players_df(match.get("players_for", []))
    if not p_for_df.empty:
        st.dataframe(p_for_df, width="stretch", hide_index=True)
    else:
        st.caption("Sem estatísticas individuais.")

with tab_against:
    st.markdown(f"**Atletas de {match.get('opponent') or 'Adversário'}**")
    p_against_df = _format_players_df(match.get("players_against", []))
    if not p_against_df.empty:
        st.dataframe(p_against_df, width="stretch", hide_index=True)
    else:
        st.caption("Sem estatísticas individuais para o adversário.")


# ------------------------------------------------------------
# ABA 4: Impacto do Banco de Reservas
# ------------------------------------------------------------
with tab_subs:
    st.subheader("🔄 Rendimento dos Reservas que Entraram")
    players_for = match.get("players_for", [])
    subs_in_match = [p for p in players_for if not p.get("is_starter") and (p.get("minutes_played") or 0) > 0]

    if subs_in_match:
        sub_df = pd.DataFrame(subs_in_match)
        tot_sub_mins = sub_df["minutes_played"].sum()
        tot_sub_xg = sub_df["xg"].sum() if "xg" in sub_df.columns else 0.0
        tot_sub_xa = sub_df["xa"].sum() if "xa" in sub_df.columns else 0.0
        tot_sub_goals = sub_df["goals"].sum() if "goals" in sub_df.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Reservas Utilizados", len(sub_df))
        c2.metric("Minutos Jogados", f"{tot_sub_mins} min")
        c3.metric("Gols dos Reservas", tot_sub_goals)
        c4.metric("Produção (xG + xA)", f"{tot_sub_xg + tot_sub_xa:.2f}")

        st.divider()

        display_subs = sub_df[[
            "name", "minutes_played", "rating", "goals", "xg", "xa", "key_passes", "shots_total"
        ]].rename(
            columns={
                "name": "Jogador",
                "minutes_played": "Minutos",
                "rating": "Nota",
                "goals": "Gols",
                "xg": "xG",
                "xa": "xA",
                "key_passes": "Passes-Chave",
                "shots_total": "Finalizações",
            }
        )
        st.dataframe(display_subs, width="stretch", hide_index=True)
    else:
        st.caption("Sem registro de substituições ou nenhum reserva atuou nesta partida.")


# ------------------------------------------------------------
# ABA 5: Síntese de Imprensa (Copiar Texto)
# ------------------------------------------------------------
with tab_press:
    st.subheader("📰 Síntese Pronta para Imprensa / Redação")
    st.caption("Texto formatado pronto para copiar e colar em reportagens, newsletters ou roteiros de rádio/TV.")

    opp = match.get("opponent", "Adversário")
    score = match.get("score", "—")
    date = match.get("date", "")
    mando = "em casa" if match.get("is_home") else "fora de casa"
    xf = match.get("xg_for", 0.0) or 0.0
    xa = match.get("xg_against", 0.0) or 0.0
    xgot_f = match.get("xgot_for", 0.0) or 0.0
    xgot_a = match.get("xgot_against", 0.0) or 0.0

    delta_xg = xf - xa
    justo_str = "vitória justa pelo volume de jogo" if delta_xg > 0.5 and (match.get("points") == 3) else (
        "resultado condizente com o equilíbrio" if abs(delta_xg) <= 0.5 else "resultado que descolou da produção de chances"
    )

    press_text = f"""### RAIO-X DO JOGO: {team_name.upper()} {score} {opp.upper()}

**Data:** {date} | **Mando:** {mando.title()}
**Placar Real:** {score}
**Placar Esperado (xG):** {team_name} {xf:.2f} x {xa:.2f} {opp}
**Qualidade no Alvo (xGOT):** {team_name} {xgot_f:.2f} x {xgot_a:.2f} {opp}

#### Análise Rápida
No confronto contra o {opp}, finalizado em {score}, o {team_name} registrou um saldo de {delta_xg:+.2f} xG ({justo_str}).
Na criação ofensiva, os destaques da equipe foram {top_str}.
"""
    if match_analysis:
        strengths = [s["text"] for s in match_analysis.get("strengths", [])]
        weaknesses = [w["text"] for w in match_analysis.get("weaknesses", [])]
        if strengths:
            press_text += f"\n**Pontos Fortes Observados:** {'; '.join(strengths)}"
        if weaknesses:
            press_text += f"\n**Vulnerabilidades:** {'; '.join(weaknesses)}"

    st.code(press_text, language="markdown")
