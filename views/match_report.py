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
# Suite Visual Ilustrativa para Atletas na Partida
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _load_match_positions(team_slug: str, event_id: int) -> dict:
    adv_data = load_json(f"{team_slug}_advanced_matches.json")
    for m in adv_data.get("matches", []):
        if m.get("event_id") == event_id:
            return {
                (p.get("name") or "").strip(): p.get("position")
                for p in m.get("players", [])
                if p.get("name")
            }
    return {}


def _rating_badge_html(rating) -> str:
    if rating is None or pd.isna(rating) or rating == 0:
        return "<span style='background-color: #6B7280; color: white; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;'>—</span>"
    try:
        r_val = float(rating)
    except (ValueError, TypeError):
        return "<span style='background-color: #6B7280; color: white; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;'>—</span>"

    if r_val >= 7.5:
        bg = "#10B981"  # Verde Esmeralda
    elif r_val >= 7.0:
        bg = "#2563EB"  # Azul Destaque
    elif r_val >= 6.5:
        bg = "#D97706"  # Âmbar Médio
    else:
        bg = "#DC2626"  # Vermelho Abaixo
    return f"<span style='background-color: {bg}; color: white; padding: 2px 7px; border-radius: 6px; font-weight: 700; font-size: 0.85rem;'>★ {r_val:.1f}</span>"


def _calc_radar_dimensions(p: dict) -> dict:
    shots = p.get("shots_total") or 0
    xg = p.get("xg") or 0.0
    goals = p.get("goals") or 0
    fin = min(100.0, round(shots * 20.0 + xg * 80.0 + goals * 30.0, 1))

    kp = p.get("key_passes") or 0
    xa = p.get("xa") or 0.0
    cri = min(100.0, round(kp * 25.0 + xa * 100.0, 1))

    p_acc = p.get("passes_accurate") or 0
    p_tot = p.get("passes_total") or 0
    pct_p = (p_acc / p_tot * 100) if p_tot > 0 else 0
    vol_p = min(1.0, p_tot / 25.0)
    dis = round(pct_p * (0.6 + 0.4 * vol_p), 1)

    rec = p.get("ball_recovery") or 0
    recup = min(100.0, round((rec / 8.0) * 100.0, 1))

    dw = p.get("duels_won") or 0
    dl = p.get("duels_lost") or 0
    dtot = dw + dl
    pct_d = (dw / dtot * 100) if dtot > 0 else 0
    vol_d = min(1.0, dtot / 8.0)
    comb = round(pct_d * (0.5 + 0.5 * vol_d), 1) if dtot > 0 else 0.0

    return {
        "Finalização": fin,
        "Criação": cri,
        "Distribuição": dis,
        "Recuperação": recup,
        "Combate": comb,
    }


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
        "rating": "Nota",
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


def render_player_match_stats(
    players_list: list,
    team_label: str,
    key_prefix: str,
    is_home_team: bool = True,
    match_positions: dict = None,
):
    if not players_list:
        st.caption(f"Sem estatísticas individuais registradas para {team_label}.")
        return

    # Atletas que de fato jogaram
    played_players = [p for p in players_list if (p.get("minutes_played") or 0) > 0]
    unplayed_players = [p for p in players_list if (p.get("minutes_played") or 0) == 0]

    if not played_players:
        st.info(f"Sem dados detalhados de minutos jogados para {team_label}.")
        return

    pos_dict = match_positions or {}

    # Destaques da Partida (Cards de Top Performers)
    best_rating = max(played_players, key=lambda p: (p.get("rating") or 0.0, p.get("minutes_played") or 0))
    best_att = max(
        played_players,
        key=lambda p: (p.get("xg") or 0.0) + (p.get("xa") or 0.0) + (p.get("goals") or 0) * 0.5,
    )
    best_def = max(
        played_players,
        key=lambda p: (p.get("ball_recovery") or 0) + (p.get("duels_won") or 0),
    )
    best_poss = max(played_players, key=lambda p: p.get("touches") or 0)

    st.markdown(f"#### 🌟 Destaques Individuais — {team_label}")
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)

    with col_c1:
        r_score = f"★ {best_rating.get('rating'):.1f}" if best_rating.get("rating") else "—"
        st.metric(
            label="Melhor em Campo",
            value=r_score,
            delta=best_rating.get("name"),
            delta_color="off",
            help=f"{best_rating.get('minutes_played')} min jogados · Maior rating SofaScore da equipe",
        )

    with col_c2:
        tot_threat = (best_att.get("xg") or 0.0) + (best_att.get("xa") or 0.0)
        st.metric(
            label="Ameaça Ofensiva (xG + xA)",
            value=f"{tot_threat:.2f}",
            delta=best_att.get("name"),
            delta_color="off",
            help=f"{best_att.get('goals', 0)} gols, {best_att.get('shots_total', 0)} chutes, {best_att.get('key_passes', 0)} passes-chave",
        )

    with col_c3:
        def_acts = (best_def.get("ball_recovery") or 0) + (best_def.get("duels_won") or 0)
        st.metric(
            label="Pilar Defensivo (Ações)",
            value=f"{def_acts}",
            delta=best_def.get("name"),
            delta_color="off",
            help=f"{best_def.get('ball_recovery', 0)} bolas recuperadas e {best_def.get('duels_won', 0)} duelos ganhos",
        )

    with col_c4:
        p_acc = best_poss.get("passes_accurate") or 0
        p_tot = best_poss.get("passes_total") or 0
        pct_p = (p_acc / p_tot * 100) if p_tot > 0 else 0
        st.metric(
            label="Regente da Posse (Toques)",
            value=f"{best_poss.get('touches', 0)}",
            delta=best_poss.get("name"),
            delta_color="off",
            help=f"{p_acc}/{p_tot} passes certos ({pct_p:.0f}%)",
        )

    st.write("")

    # Seletor de Modo de Visualização
    view_mode = st.radio(
        f"Selecione a visualização ({team_label})",
        ["📊 Ranking Comparativo", "🏟️ Linhas do Time", "🔍 Raio-X do Atleta", "📋 Tabela Completa"],
        horizontal=True,
        key=f"pstats_mode_{key_prefix}_{selected_id}",
    )

    st.divider()

    # ------------------------------------------------------------
    # MODO 1: Ranking Comparativo (Plotly Horizontal Bar)
    # ------------------------------------------------------------
    if view_mode == "📊 Ranking Comparativo":
        col_m1, col_m2 = st.columns([2, 1])
        with col_m1:
            metric_map = {
                "⭐ Rating (Nota SofaScore)": "rating",
                "🎯 Ameaça Ofensiva (xG + xA)": "xg_xa",
                "⚽ Finalizações Totais": "shots_total",
                "🪄 Passes Decisivos (Passes-chave)": "key_passes",
                "🎮 Toques na Bola (Volume)": "touches",
                "📐 % Passes Certos": "pct_passes_certos",
                "🛡️ Bolas Recuperadas": "ball_recovery",
                "⚔️ Duelos Ganhos": "duels_won",
                "💪 % Duelos Ganhos": "pct_duelos_ganhos",
            }
            selected_metric_label = st.selectbox(
                "Métrica para Comparação",
                list(metric_map.keys()),
                key=f"pstats_metric_{key_prefix}_{selected_id}",
            )
            metric_key = metric_map[selected_metric_label]

        # Processar dados para o gráfico
        chart_data = []
        for p in played_players:
            p_acc = p.get("passes_accurate") or 0
            p_tot = p.get("passes_total") or 0
            pct_p = round((p_acc / p_tot * 100), 1) if p_tot > 0 else 0.0

            dw = p.get("duels_won") or 0
            dl = p.get("duels_lost") or 0
            dtot = dw + dl
            pct_d = round((dw / dtot * 100), 1) if dtot > 0 else 0.0

            xg_xa = round((p.get("xg") or 0.0) + (p.get("xa") or 0.0), 3)

            val = 0.0
            if metric_key == "rating":
                val = p.get("rating") or 0.0
            elif metric_key == "xg_xa":
                val = xg_xa
            elif metric_key == "shots_total":
                val = p.get("shots_total") or 0
            elif metric_key == "key_passes":
                val = p.get("key_passes") or 0
            elif metric_key == "touches":
                val = p.get("touches") or 0
            elif metric_key == "pct_passes_certos":
                val = pct_p
            elif metric_key == "ball_recovery":
                val = p.get("ball_recovery") or 0
            elif metric_key == "duels_won":
                val = dw
            elif metric_key == "pct_duelos_ganhos":
                val = pct_d

            chart_data.append({
                "name": p.get("name"),
                "val": val,
                "is_starter": "Titular" if p.get("is_starter") else "Reserva",
                "minutes": p.get("minutes_played") or 0,
                "rating": p.get("rating") or "—",
            })

        # Ordenar ascendente para a barra superior ser o maior valor
        chart_data.sort(key=lambda x: x["val"])

        # Cores das barras
        colors = []
        for d in chart_data:
            if metric_key == "rating":
                r = float(d["val"]) if d["val"] else 0.0
                if r >= 7.5:
                    colors.append("#10B981")
                elif r >= 7.0:
                    colors.append("#2563EB")
                elif r >= 6.5:
                    colors.append("#D97706")
                else:
                    colors.append("#DC2626")
            else:
                colors.append("#002B7F" if d["is_starter"] == "Titular" else "#F59E0B")

        text_labels = []
        for d in chart_data:
            if metric_key in ["rating", "xg_xa"]:
                text_labels.append(f"{d['val']:.2f}" if metric_key == "xg_xa" else (f"{d['val']:.1f}" if d["val"] else "—"))
            elif "pct_" in metric_key:
                text_labels.append(f"{d['val']:.1f}%")
            else:
                text_labels.append(f"{int(d['val'])}")

        fig_bar = go.Figure(
            go.Bar(
                y=[d["name"] for d in chart_data],
                x=[d["val"] for d in chart_data],
                orientation="h",
                text=text_labels,
                textposition="outside",
                marker_color=colors,
                customdata=[(d["is_starter"], d["minutes"], d["rating"]) for d in chart_data],
                hovertemplate="<b>%{y}</b> (%{customdata[0]}, %{customdata[1]}')<br>Nota: %{customdata[2]}<br>Valor: %{x}<extra></extra>",
            )
        )
        fig_bar.update_layout(
            height=max(380, len(chart_data) * 28),
            margin=dict(l=20, r=45, t=15, b=25),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(128,128,128,0.2)",
                title=selected_metric_label,
            ),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_bar, width="stretch", config={"responsive": True, "displayModeBar": False})

    # ------------------------------------------------------------
    # MODO 2: Linhas do Time (Cards Setoriais)
    # ------------------------------------------------------------
    elif view_mode == "🏟️ Linhas do Time":
        st.caption("Organização setorial dos atletas que atuaram nesta partida.")

        # Separar titulares por setor e reservas
        starters = [p for p in played_players if p.get("is_starter")]
        subs_used = [p for p in played_players if not p.get("is_starter")]

        sectors = {
            "🧤 Goleiro & Defesa": [],
            "⚙️ Meio-Campo": [],
            "⚡ Ataque": [],
        }

        for p in starters:
            pos = pos_dict.get((p.get("name") or "").strip())
            if pos in ["G", "D"]:
                sectors["🧤 Goleiro & Defesa"].append(p)
            elif pos == "M":
                sectors["⚙️ Meio-Campo"].append(p)
            elif pos == "F":
                sectors["⚡ Ataque"].append(p)
            else:
                # Fallback por nome ou estatísticas se não mapeado
                if (p.get("shots_total") or 0) > 1:
                    sectors["⚡ Ataque"].append(p)
                elif (p.get("passes_total") or 0) > 35:
                    sectors["⚙️ Meio-Campo"].append(p)
                else:
                    sectors["🧤 Goleiro & Defesa"].append(p)

        def _render_player_cards(players_sublist):
            if not players_sublist:
                st.caption("Nenhum atleta nesta categoria.")
                return
            num_cols = min(4, len(players_sublist)) or 1
            cols = st.columns(num_cols)
            for idx, p in enumerate(players_sublist):
                with cols[idx % num_cols]:
                    p_name = p.get("name")
                    rating = p.get("rating")
                    mins = p.get("minutes_played") or 0
                    badge = _rating_badge_html(rating)
                    is_sub = not p.get("is_starter")
                    status_lbl = f"🔄 Entrou ({mins}')" if is_sub else f"⏱️ {mins} min"

                    # Destaques estatísticos
                    goals = p.get("goals") or 0
                    shots = p.get("shots_total") or 0
                    xg = p.get("xg") or 0.0
                    xa = p.get("xa") or 0.0
                    kp = p.get("key_passes") or 0
                    rec = p.get("ball_recovery") or 0
                    dw = p.get("duels_won") or 0
                    p_acc = p.get("passes_accurate") or 0
                    p_tot = p.get("passes_total") or 0
                    pct_p = (p_acc / p_tot * 100) if p_tot > 0 else 0

                    stat_lines = []
                    if goals > 0:
                        stat_lines.append(f"⚽ <b>{goals} gol(s)</b>")
                    if xg + xa > 0.1:
                        stat_lines.append(f"🎯 xG {xg:.2f} · xA {xa:.2f}")
                    if kp > 0:
                        stat_lines.append(f"🪄 {kp} passe(s) chave")
                    if rec > 0 or dw > 0:
                        stat_lines.append(f"🛡️ {rec} recup. · {dw} duelos")
                    stat_lines.append(f"📐 {p_acc}/{p_tot} passes ({pct_p:.0f}%)")

                    card_content = "<br/>".join(stat_lines[:3])

                    card_html = f"""
                    <div style="border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; background: rgba(128, 128, 128, 0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-weight: 700; font-size: 0.92rem;">{p_name}</span>
                            {badge}
                        </div>
                        <div style="font-size: 0.78rem; color: gray; margin-bottom: 8px;">
                            {status_lbl}
                        </div>
                        <div style="font-size: 0.8rem; line-height: 1.45;">
                            {card_content}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

        for sec_name, sec_players in sectors.items():
            if sec_players:
                st.markdown(f"**{sec_name} ({len(sec_players)} titulares)**")
                _render_player_cards(sec_players)
                st.write("")

        if subs_used:
            st.markdown(f"**🔄 Reservas Utilizados ({len(subs_used)} atletas)**")
            _render_player_cards(subs_used)

        if unplayed_players:
            with st.expander(f"🪑 Banco de Reservas Não Utilizado ({len(unplayed_players)} atletas)"):
                unplayed_names = [p.get("name") for p in unplayed_players]
                st.write(" · ".join(unplayed_names))

    # ------------------------------------------------------------
    # MODO 3: Raio-X do Atleta (Radar Pentagonal + Análise)
    # ------------------------------------------------------------
    elif view_mode == "🔍 Raio-X do Atleta":
        player_choices = {
            f"{p['name']} ({'Titular' if p.get('is_starter') else 'Reserva'}, {p.get('minutes_played')}' · Nota {p.get('rating') or '—'})": p
            for p in played_players
        }
        selected_player_label = st.selectbox(
            "Selecione o Atleta para Raio-X",
            list(player_choices.keys()),
            key=f"pstats_player_{key_prefix}_{selected_id}",
        )
        p = player_choices[selected_player_label]

        # Métricas do Jogador em 6 Colunas
        rc1, rc2, rc3, rc4, rc5, rc6 = st.columns(6)
        rc1.metric("Minutos", f"{p.get('minutes_played', 0)} min")
        rc2.metric("Nota SofaScore", f"{p.get('rating', '—')}")
        rc3.metric("xG + xA", f"{(p.get('xg') or 0.0) + (p.get('xa') or 0.0):.2f}")
        rc4.metric("Toques", f"{p.get('touches', 0)}")

        p_acc = p.get("passes_accurate") or 0
        p_tot = p.get("passes_total") or 0
        pct_p = (p_acc / p_tot * 100) if p_tot > 0 else 0
        rc5.metric("Passes Certos", f"{p_acc}/{p_tot}", f"{pct_p:.0f}%")

        dw = p.get("duels_won") or 0
        dl = p.get("duels_lost") or 0
        dtot = dw + dl
        pct_d = (dw / dtot * 100) if dtot > 0 else 0
        rc6.metric("Duelos Ganhos", f"{dw}/{dtot}", f"{pct_d:.0f}%")

        st.write("")
        col_rad, col_stats = st.columns([1.2, 1.0])

        with col_rad:
            radar_dims = _calc_radar_dimensions(p)
            dim_names = list(radar_dims.keys())
            dim_values = list(radar_dims.values())
            # Fechar o círculo
            dim_names_closed = dim_names + [dim_names[0]]
            dim_values_closed = dim_values + [dim_values[0]]

            fig_radar = go.Figure(
                go.Scatterpolar(
                    r=dim_values_closed,
                    theta=dim_names_closed,
                    fill="toself",
                    fillcolor="rgba(0, 43, 127, 0.35)",
                    line=dict(color="#002B7F", width=2.5),
                    hovertemplate="%{theta}: <b>%{r:.1f}</b>/100<extra></extra>",
                )
            )
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        showticklabels=True,
                        gridcolor="rgba(128,128,128,0.2)",
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(128,128,128,0.2)",
                        tickfont=dict(size=12, family="sans-serif"),
                    ),
                ),
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=30),
                height=380,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_radar, width="stretch", config={"responsive": True, "displayModeBar": False})

        with col_stats:
            st.markdown(f"**Relatório Técnico: {p.get('name')}**")
            st.caption("Avaliação de volume, eficiência e impacto na partida.")

            # Insights contextuais
            insights = []
            if (p.get("goals") or 0) > 0:
                insights.append(f"⚽ **Farol de Gol:** Marcou {p.get('goals')} gol(s) na partida.")
            if (p.get("shots_total") or 0) >= 2:
                insights.append(f"🎯 **Presença Ofensiva:** Finalizou {p.get('shots_total')} vezes (xG {p.get('xg', 0):.2f}).")
            if (p.get("key_passes") or 0) >= 2:
                insights.append(f"🪄 **Garçom:** Criou {p.get('key_passes')} passes decisivos para chute.")
            if pct_p >= 82 and p_tot >= 15:
                insights.append(f"📐 **Segurança no Passe:** Elevada precisão de passe ({pct_p:.0f}% em {p_tot} passes).")
            if (p.get("ball_recovery") or 0) >= 4:
                insights.append(f"🛡️ **Combate Defensivo:** Recuperou {p.get('ball_recovery')} posses de bola.")
            if pct_d >= 60 and dtot >= 3:
                insights.append(f"⚔️ **Imposição Física:** Venceu {pct_d:.0f}% dos duelos em campo ({dw}/{dtot}).")

            if insights:
                for ins in insights:
                    st.markdown(f"- {ins}")
            else:
                st.markdown(f"- Atuação tática regular em {p.get('minutes_played')} minutos.")

            st.write("")
            st.markdown("**Números Completos:**")
            st.markdown(
                f"""
                - **Finalizações:** {p.get('shots_total', 0)} ({p.get('goals', 0)} gols) · xG: {p.get('xg', 0.0):.2f}
                - **Criação & Passes:** {p.get('key_passes', 0)} passes-chave · xA: {p.get('xa', 0.0):.2f}
                - **Posse de Bola:** {p.get('touches', 0)} toques · {p.get('possession_lost', 0)} perdas
                - **Desarmes & Duelos:** {p.get('ball_recovery', 0)} recuperações · {dw} duelos ganhos ({dl} perdidos)
                """
            )

    # ------------------------------------------------------------
    # MODO 4: Tabela Completa (Dataframe Analítico)
    # ------------------------------------------------------------
    elif view_mode == "📋 Tabela Completa":
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            filter_played = st.checkbox(
                "Apenas atletas que entraram em campo",
                value=True,
                key=f"pstats_filter_{key_prefix}_{selected_id}",
            )

        list_to_show = played_players if filter_played else players_list
        df_full = _format_players_df(list_to_show)

        if not df_full.empty:
            # Ordenar por Nota decrescente
            if "Nota" in df_full.columns:
                df_full = df_full.sort_values(by="Nota", ascending=False)

            st.dataframe(
                df_full,
                width="stretch",
                hide_index=True,
                column_config={
                    "Nota": st.column_config.NumberColumn("Nota", format="%.1f", help="Rating SofaScore"),
                    "xG": st.column_config.NumberColumn("xG", format="%.2f", help="Expected Goals"),
                    "xA": st.column_config.NumberColumn("xA", format="%.2f", help="Expected Assists"),
                    "% Passes certos": st.column_config.ProgressColumn("% Passes", min_value=0, max_value=100, format="%.0f%%"),
                    "% Bolas perdidas": st.column_config.ProgressColumn("% Perdas", min_value=0, max_value=100, format="%.0f%%"),
                    "% Duelos ganhos": st.column_config.ProgressColumn("% Duelos", min_value=0, max_value=100, format="%.0f%%"),
                },
            )
        else:
            st.caption("Nenhum atleta para exibir.")


# Carregar posições do jogo atual
current_match_positions = _load_match_positions(team, selected_id)

with tab_for:
    render_player_match_stats(
        players_list=match.get("players_for", []),
        team_label=team_name,
        key_prefix="for",
        is_home_team=match.get("is_home", True),
        match_positions=current_match_positions,
    )

with tab_against:
    opp_label = match.get("opponent") or "Adversário"
    render_player_match_stats(
        players_list=match.get("players_against", []),
        team_label=opp_label,
        key_prefix="against",
        is_home_team=not match.get("is_home", True),
        match_positions=current_match_positions,
    )


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
