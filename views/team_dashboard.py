import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import importlib
from config import TEAMS
from analysis.engine import build_season_analysis
import views._common as _common

if not hasattr(_common, "render_insight_cards"):
    importlib.reload(_common)

from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_analysis_section,
    render_insight_cards,
    render_page_header,
    render_squad_quadrant,
)
from views.pitch import create_2d_pitch_figure, SITUATION_PT, BODY_PART_PT, SHOT_TYPE_PT

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Dashboard da Equipe — {team_name}",
    subtitle="Análise estatística avançada, evolução por turnos, Campo 2D de finalizações e matriz tática.",
    tag=team_name,
)

tm = load_json(f"{team}_team_metrics.json")
adv_matches_data = load_json(f"{team}_advanced_matches.json")
adv_season_data = load_json(f"{team}_advanced_season.json")
pm_data = load_json(f"{team}_player_metrics.json")

s = tm.get("summary", {}) if tm else {}
matches_count = s.get("matches", 0)

if matches_count == 0:
    st.warning(f"Sem dados coletados para {team_name}. Execute: `python main.py --team {team} --build`")
    st.stop()

players_list = pm_data.get("players", []) if isinstance(pm_data, dict) else (pm_data or [])
season_analysis = build_season_analysis(tm, players_list)


def sv(key, default=0.0):
    v = s.get(key)
    return default if v is None else v


_has_xg = s.get("points_expected") is not None

# Pontos Reais: prefere a tabela oficial (standings_*.json, casada por team_id
# do SofaScore) — matches_master pode estar incompleto (rodada faltando,
# incremental parcial) e subestimar os pontos. Cai pro cálculo local só se a
# tabela oficial ainda não foi coletada pra essa divisão.
_division = TEAMS.get(team, {}).get("division", "Série B")
_standings_key = "serie_a_2026" if _division == "Série A" else "serie_b_2026"
_team_sofascore_id = TEAMS.get(team, {}).get("sofascore", {}).get("team_id")
_standings_rows = load_json(f"standings_{_standings_key}.json").get("standings", [])
_official_row = next((r for r in _standings_rows if r.get("team_id") == _team_sofascore_id), None)

points_real = sv("points_real")
if _official_row is not None:
    points_real = _official_row.get("points", points_real)
    if _official_row.get("points") != sv("points_real"):
        st.info(
            f"Pontos oficiais ({_official_row.get('points')}) divergem do cálculo local a partir dos jogos "
            f"coletados ({sv('points_real'):.0f}) — provavelmente falta rodada em matches_master. "
            f"Exibindo o valor oficial."
        )

# Destaques Narrativos & Anomalias Táticas (Insight do Dia antes dos KPIs)
render_insight_cards(season_analysis.get("editorial_hooks", []), title="💡 Destaques & Anomalias Táticas")

# Top KPIs Numéricos
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Pontos Reais",
    points_real,
    delta=round(sv("points_luck"), 1) if _has_xg else None,
    help="delta = Sorte / Overperformance (pontos reais − pontos esperados)",
)
c2.metric(
    "Pontos Esperados (xPts)",
    f"{sv('points_expected'):.1f}" if _has_xg else "—",
    help=f"Modelo Poisson sobre as {sv('matches', 0)} partidas da temporada.",
)
c3.metric(
    "Saldo de xG (ΔxG)",
    f"{sv('xg_diff'):+.2f}" if _has_xg else "—",
    help="xG a favor − xG contra acumulado",
)
c4.metric(
    "Eficiência Finalização / Defesa",
    f"{sv('finishing'):+.2f} / {sv('keeping'):+.2f}" if _has_xg else "—",
    help="Gols marcados − xG pró / xG contra − gols sofridos",
)

st.markdown(
    f"""
    <div style="background: #F1F5F9; border-radius: 8px; padding: 10px 16px; margin: 12px 0 20px 0; font-size: 0.95rem; color: #1E293B;">
        🦁 <b>Campanha Oficial</b>: <b>{sv('wins', 0)} Vitórias</b> &nbsp;·&nbsp;
        <b>{sv('draws', 0)} Empates</b> &nbsp;·&nbsp;
        <b>{sv('losses', 0)} Derrotas</b> &nbsp;|&nbsp;
        xG Acumulado: <b style="color:#002B7F;">{sv('xg_for_total'):.2f} Pró</b> vs
        <b style="color:#E31A2C;">{sv('xg_against_total'):.2f} Contra</b>
    </div>
    """,
    unsafe_allow_html=True,
)

# Abas do Dashboard
tab_overview, tab_pitch, tab_tactics, tab_quadrants, tab_raw_stats = st.tabs([
    "📈 Desempenho & Turnos",
    "🏟️ Campo 2D: Finalizações & Assistências",
    "⏱️ Game State & Tática",
    "👥 Matriz de Quadrantes do Elenco",
    "📊 Métricas Brutas SofaScore",
])

# ============================================================
# TAB 1: Desempenho & Comparativo de Turnos
# ============================================================
with tab_overview:
    # Comparativo 1º Turno vs 2º Turno
    st.subheader("📊 Comparativo de Turnos (Evolução na Série B)")
    pm_list = tm.get("per_match", [])

    if len(pm_list) > 19:
        t1_matches = pm_list[:19]
        t2_matches = pm_list[19:]

        def _calc_turn_stats(sub):
            n = len(sub) or 1
            pts = sum(m.get("points") or 0 for m in sub)
            gf = sum(m.get("goals_for") or 0 for m in sub)
            ga = sum(m.get("goals_against") or 0 for m in sub)
            xgf = sum(m.get("xg_for") or 0.0 for m in sub)
            xga = sum(m.get("xg_against") or 0.0 for m in sub)
            w = sum(1 for m in sub if (m.get("points") == 3))
            d = sum(1 for m in sub if (m.get("points") == 1))
            l = sum(1 for m in sub if (m.get("points") == 0))
            return {
                "Jogos": len(sub),
                "Vitórias / Empates / Derrotas": f"{w}V / {d}E / {l}D",
                "Pontos Conquistados": pts,
                "Aproveitamento (PPG)": round(pts / n, 2),
                "Gols Pró / Sofridos": f"{gf} / {ga}",
                "Saldo de Gols Real": f"{gf - ga:+d}",
                "xG Pró / Jogo": round(xgf / n, 2),
                "xG Concedido / Jogo": round(xga / n, 2),
                "Saldo de xG / Jogo (ΔxG)": round((xgf - xga) / n, 2),
                "Eficiência de Conversão (Gols − xG)": round(gf - xgf, 2),
            }

        t1_s = _calc_turn_stats(t1_matches)
        t2_s = _calc_turn_stats(t2_matches)

        turns_df = pd.DataFrame([
            {"Indicador": k, "1º Turno (Rodadas 1 a 19)": str(t1_s[k]), "2º Turno (Rodadas 20 a 28)": str(t2_s[k])}
            for k in t1_s
        ])
        st.dataframe(turns_df, width="stretch", hide_index=True)
        st.divider()

    pm = pd.DataFrame(pm_list)
    if not pm.empty:
        pm["rotulo"] = pm["date"].astype(str) + " (" + pm["opponent"].fillna("?").astype(str) + ")"
        st.subheader("📈 Evolução da Forma (Média Móvel - 5 Jogos)")
        tab_xg_roll, tab_pts_roll = st.tabs(["Média Móvel de xG (Pró x Contra)", "Média Móvel de Pontos"])
        with tab_xg_roll:
            chart_df = pm.rename(
                columns={
                    "xg_for_roll5": "xG Pró (MM 5j)",
                    "xg_against_roll5": "xG Contra (MM 5j)",
                }
            )
            st.line_chart(chart_df.set_index("rotulo")[["xG Pró (MM 5j)", "xG Contra (MM 5j)"]], width="stretch")
        with tab_pts_roll:
            chart_pts = pm.rename(columns={"points_roll5": "Pontos (MM 5j)"})
            st.line_chart(chart_pts.set_index("rotulo")[["Pontos (MM 5j)"]], width="stretch")

        st.subheader("📋 Histórico Jogo a Jogo")
        st.dataframe(
            pm[
                [
                    "date",
                    "opponent",
                    "is_home",
                    "score",
                    "points",
                    "xg_for",
                    "xg_against",
                    "xg_diff",
                    "xpoints",
                    "p_win",
                    "p_draw",
                    "p_loss",
                ]
            ].rename(
                columns={
                    "date": "Data",
                    "opponent": "Adversário",
                    "is_home": "Mando",
                    "score": "Placar",
                    "points": "Pts",
                    "xg_for": "xG Pró",
                    "xg_against": "xG Contra",
                    "xg_diff": "ΔxG",
                    "xpoints": "xPts",
                    "p_win": "P(Vitória)",
                    "p_draw": "P(Empate)",
                    "p_loss": "P(Derrota)",
                }
            ),
            width="stretch",
            hide_index=True,
        )


# ============================================================
# TAB 2: Campo 2D (Finalizações & Assistências da Temporada)
# ============================================================
with tab_pitch:
    st.subheader(f"🏟️ Campo 2D — Mapa de Finalizações & Assistências ({team_name})")
    st.caption("Visualização espacial de todas as finalizações e passes para gol na temporada 2026.")

    # Extrair todos os chutes do time ativo
    from resolve.master import _team_aliases
    aliases = _team_aliases(team)

    all_season_shots = []
    for m in adv_matches_data.get("matches", []):
        hs = (m.get("home_team") or "").lower()
        is_home_match = any(a in hs for a in aliases)
        opp_str = m.get("away_team" if is_home_match else "home_team")
        for s in m.get("shots", []):
            if s.get("is_home") == is_home_match and s.get("x") is not None:
                all_season_shots.append({
                    **s,
                    "date": m.get("date"),
                    "opponent": opp_str,
                })

    if all_season_shots:
        # Filtros Interativos
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)

        # 1. Filtro por Jogador
        all_players = sorted(list({s["player_name"] for s in all_season_shots if s.get("player_name")}))
        with col_f1:
            sel_player = st.selectbox("Atleta Finalizador", ["Todo o Elenco"] + all_players, key="p2d_player")

        # 2. Filtro por Desfecho
        outcomes_map = {
            "Todas as Finalizações": None,
            "Apenas Gols ⚽": "goal",
            "No Alvo (Gols + Defesas)": "target",
            "Para Fora / Na Trave": "miss",
            "Bloqueadas": "block",
        }
        with col_f2:
            sel_outcome_label = st.selectbox("Desfecho do Lance", list(outcomes_map.keys()), key="p2d_outcome")
            sel_outcome = outcomes_map[sel_outcome_label]

        # 3. Filtro por Situação (PT-BR)
        raw_situations = sorted(list({s.get("situation") for s in all_season_shots if s.get("situation")}))
        sit_label_to_key = {SITUATION_PT.get(rs, rs.replace("-", " ").title()): rs for rs in raw_situations}
        sit_options = ["Todas as Situações"] + list(sit_label_to_key.keys())
        with col_f3:
            sel_sit = st.selectbox("Situação da Jogada", sit_options, key="p2d_sit")

        # 4. Filtro por Parte do Corpo (PT-BR)
        with col_f4:
            sel_body = st.selectbox("Parte do Corpo", ["Todas", "Pé Direito", "Pé Esquerdo", "Cabeça", "Outro"], key="p2d_body")

        # Aplicar filtros
        filtered_pitch_shots = all_season_shots
        if sel_player != "Todo o Elenco":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("player_name") == sel_player]

        if sel_outcome == "goal":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("is_goal")]
        elif sel_outcome == "target":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("is_goal") or s.get("shot_type") == "save"]
        elif sel_outcome == "miss":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("shot_type") in ("miss", "post")]
        elif sel_outcome == "block":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("shot_type") in ("block", "blocked-off-line")]

        if sel_sit != "Todas as Situações":
            target_sit_key = sit_label_to_key.get(sel_sit)
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("situation") == target_sit_key]

        if sel_body == "Pé Direito":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("body_part") == "right-foot"]
        elif sel_body == "Pé Esquerdo":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("body_part") == "left-foot"]
        elif sel_body == "Cabeça":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("body_part") == "head"]
        elif sel_body == "Outro":
            filtered_pitch_shots = [s for s in filtered_pitch_shots if s.get("body_part") in ("other", "other-body-part")]

        # KPIs do Filtro Selecionado
        n_shots = len(filtered_pitch_shots)
        n_goals = sum(1 for s in filtered_pitch_shots if s.get("is_goal"))
        tot_xg = sum(s.get("xg") or 0.0 for s in filtered_pitch_shots)
        tot_xgot = sum(s.get("xgot") or 0.0 for s in filtered_pitch_shots)
        conv_rate = round(n_goals / n_shots * 100, 1) if n_shots else 0.0
        avg_xg_shot = round(tot_xg / n_shots, 3) if n_shots else 0.0

        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        kc1.metric("Chutes Filtrados", n_shots)
        kc2.metric("Gols Marcados", n_goals)
        kc3.metric("Taxa de Conversão", f"{conv_rate}%")
        kc4.metric("xG Acumulado", f"{tot_xg:.2f}")
        kc5.metric("Qualidade Média", f"{avg_xg_shot:.3f} xG/chute")

        st.divider()

        # Renderizar Campo 2D
        pitch_theme = st.radio("Tema do Gramado", ["Grama Verde", "Modo Escuro"], horizontal=True, key="p2d_theme")
        theme_val = "grass" if pitch_theme == "Grama Verde" else "dark"

        title_pitch = f"Campo 2D — {sel_player} ({n_shots} finalizações, {n_goals} gols)"
        fig_pitch = create_2d_pitch_figure(
            filtered_pitch_shots,
            title=title_pitch,
            show_trajectories=True,
            show_assists=True,
            pitch_theme=theme_val,
            height=580,
        )
        st.plotly_chart(fig_pitch, width="stretch", config={"responsive": True, "displayModeBar": False})

        # Tabela ordenada por perigo da chance (xG)
        st.subheader("📋 Finalizações do Filtro Selecionado (Ordenadas por xG)")
        pitch_table = pd.DataFrame([
            {
                "Data": s.get("date"),
                "Adversário": s.get("opponent"),
                "Minuto": f"{s.get('minute')}'",
                "Jogador": s.get("player_name"),
                "Resultado": "⚽ Gol" if s.get("is_goal") else SHOT_TYPE_PT.get(s.get("shot_type", ""), (s.get("shot_type") or "").title()),
                "xG": round(s.get("xg") or 0.0, 3),
                "xGOT": round(s.get("xgot") or 0.0, 3),
                "Parte": BODY_PART_PT.get(s.get("body_part", ""), (s.get("body_part") or "").replace("-", " ").title()),
                "Situação": SITUATION_PT.get(s.get("situation", ""), (s.get("situation") or "").replace("-", " ").title()),
                "Assistência": s.get("assist_name") or "—",
            }
            for s in sorted(filtered_pitch_shots, key=lambda x: (x.get("xg") or 0.0), reverse=True)
        ])
        st.dataframe(pitch_table, width="stretch", hide_index=True)
    else:
        st.info("Sem coordenadas de finalizações registradas.")


# ============================================================
# TAB 3: Game State & Tática
# ============================================================
with tab_tactics:
    # Diagnóstico Tático da Temporada (Forças, Fraquezas e Notas)
    render_analysis_section(season_analysis, title="Diagnóstico Tático da Temporada")
    st.divider()

    # 1. Game State (Comportamento por Placar)
    st.subheader("⏱️ Game State: Comportamento por Placar")
    st.caption("Taxa de produção e vulnerabilidade por 90 minutos de jogo conforme o placar da partida.")

    gs = tm.get("game_state", {})
    if gs:
        gs_rows = []
        labels_gs = [("winning", "Vencendo (À Frente)"), ("drawing", "Empatando (Igualdade)"), ("losing", "Perdendo (Atrás)")]
        for key, name in labels_gs:
            v = gs.get(key, {})
            gs_rows.append({
                "Cenário de Placar": name,
                "Minutos Jogados": f"{v.get('minutes', 0)} min",
                "% do Tempo": f"{v.get('share_pct', 0)}%",
                "Gols Pró": v.get("goals_for", 0),
                "Gols Contra": v.get("goals_against", 0),
                "xG Pró/90": v.get("xg_for_p90", 0.0),
                "xG Contra/90": v.get("xg_against_p90", 0.0),
                "Saldo ΔxG/90": round((v.get("xg_for_p90", 0.0) - v.get("xg_against_p90", 0.0)), 2),
            })
        st.dataframe(pd.DataFrame(gs_rows), width="stretch", hide_index=True)

        fig_gs = go.Figure()
        categories_gs = [name for _, name in labels_gs]
        xg_f_gs = [gs.get(k, {}).get("xg_for_p90", 0.0) for k, _ in labels_gs]
        xg_a_gs = [gs.get(k, {}).get("xg_against_p90", 0.0) for k, _ in labels_gs]

        fig_gs.add_trace(go.Bar(name="xG Pró/90min", x=categories_gs, y=xg_f_gs, marker_color="#002B7F", text=xg_f_gs, textposition="auto"))
        fig_gs.add_trace(go.Bar(name="xG Contra/90min", x=categories_gs, y=xg_a_gs, marker_color="#E31A2C", text=xg_a_gs, textposition="auto"))
        fig_gs.update_layout(
            barmode="group",
            title="Taxa de xG Pró vs xG Contra por Situação de Placar",
            height=340,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_gs, width="stretch", config={"responsive": True, "displayModeBar": False})

    st.divider()

    # 2. Impacto do Banco (Supersubs)
    st.subheader("🔄 Impacto do Banco de Reservas (Temporada)")
    subs = tm.get("substitutions", {})
    if subs:
        sub_sum = subs.get("subs_summary", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Minutos dos Reservas", f"{sub_sum.get('total_minutes', 0)} min")
        c2.metric("Gols dos Reservas", sub_sum.get("goals", 0))
        c3.metric("Assistências dos Reservas", sub_sum.get("assists", 0))
        c4.metric("xG + xA dos Reservas", f"{sub_sum.get('xg', 0.0) + sub_sum.get('xa', 0.0):.2f}")

        supersubs = subs.get("supersubs", [])
        if supersubs:
            st.markdown("**🏆 Ranking de Reservas Mais Decisivos (Supersubs)**")
            ss_df = pd.DataFrame(supersubs[:8]).rename(
                columns={
                    "name": "Jogador",
                    "sub_apps": "Jogos do Banco",
                    "minutes": "Minutos",
                    "goals": "Gols",
                    "assists": "Assist.",
                    "goal_involvements": "Partic. Gols",
                    "xg": "xG",
                    "xa": "xA",
                    "prod_total": "xG + xA",
                    "avg_rating": "Nota Média",
                }
            )
            st.dataframe(ss_df, width="stretch", hide_index=True)

    st.divider()

    # 3. Mandante vs Visitante & Bolas Paradas
    st.subheader("🏟️ Desempenho: Mandante vs Visitante")
    ha = tm.get("home_away", {})
    if ha:
        ha_df = pd.DataFrame(
            {
                "Casa": {
                    "Jogos": ha.get("home", {}).get("matches"),
                    "Média xG Pró": ha.get("home", {}).get("xg_for"),
                    "Média xG Contra": ha.get("home", {}).get("xg_against"),
                    "Aproveitamento (PPG)": ha.get("home", {}).get("ppg"),
                },
                "Fora": {
                    "Jogos": ha.get("away", {}).get("matches"),
                    "Média xG Pró": ha.get("away", {}).get("xg_for"),
                    "Média xG Contra": ha.get("away", {}).get("xg_against"),
                    "Aproveitamento (PPG)": ha.get("away", {}).get("ppg"),
                },
            }
        ).T
        st.dataframe(ha_df, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ xG por Faixa de 15 Minutos")
        tl = pd.DataFrame(
            {
                "xG a Favor": tm.get("timeline", {}).get("for", {}),
                "xG Contra": tm.get("timeline", {}).get("against", {}),
            }
        )
        st.bar_chart(tl, width="stretch")

    with col2:
        st.subheader("🎯 Impacto de Bolas Paradas")
        sp = tm.get("set_pieces", {})
        st.metric(
            "% do xG a Favor via Bola Parada",
            f"{sp.get('xg_for_setpiece_pct')}%" if sp.get("xg_for_setpiece_pct") is not None else "N/A",
        )
        st.metric(
            "% do xG Contra via Bola Parada",
            f"{sp.get('xg_against_setpiece_pct')}%" if sp.get("xg_against_setpiece_pct") is not None else "N/A",
        )


# ============================================================
# TAB 4: Matriz de Quadrantes do Elenco (xG/90 vs xA/90)
# ============================================================
with tab_quadrants:
    st.subheader("👥 Matriz Tática de Quadrantes: Finalização vs Criação")
    st.caption("Distribuição estatística dos atletas em produção ofensiva por 90 minutos (xG/90 vs xA/90) de jogadores no elenco.")

    master_data = load_json(f"{team}_players_master.json")
    master_players = {p["name"]: p for p in (master_data.get("players", []) if isinstance(master_data, dict) else [])}
    players_list = pm_data.get("players", []) if isinstance(pm_data, dict) else (pm_data or [])

    render_squad_quadrant(
        players_list=players_list,
        master_players=master_players,
        team_name=team_name,
        key_prefix="team_dash",
    )


# ============================================================
# TAB 5: Métricas Brutas SofaScore
# ============================================================
with tab_raw_stats:
    st.subheader("📊 Métricas Avançadas Individuais (SofaScore)")
    adv_players = adv_season_data.get("players", [])
    if adv_players:
        adf = pd.DataFrame(adv_players)
        metric_groups = {
            "Volume": ["matches", "minutes", "touches", "touches_per90"],
            "Finalização / xG": ["xg", "xg_per90", "goals", "shots", "xa", "assists"],
            "Passe": [
                "passes",
                "passes_accurate",
                "pass_accuracy",
                "key_passes",
                "long_balls",
                "long_balls_accurate",
                "crosses",
                "crosses_accurate",
            ],
            "Posse / Progressão": [
                "possession_lost",
                "ball_recovery",
                "ball_carries",
                "progressive_carries",
            ],
            "Duelos / Defesa": [
                "duels_won",
                "duels_lost",
                "aerials_won",
                "interceptions",
                "clearances",
                "fouls",
            ],
        }

        labels = {
            "matches": "Jogos",
            "minutes": "Min",
            "touches": "Toques",
            "touches_per90": "Toques/90",
            "xg": "xG",
            "xg_per90": "xG/90",
            "goals": "Gols",
            "shots": "Finaliz.",
            "xa": "xA",
            "assists": "Assist.",
            "passes": "Passes",
            "passes_accurate": "Passes certos",
            "pass_accuracy": "% Passe",
            "key_passes": "Passes-chave",
            "long_balls": "Lançam.",
            "long_balls_accurate": "Lançam. certos",
            "crosses": "Cruzam.",
            "crosses_accurate": "Cruzam. certos",
            "possession_lost": "Bola perdida",
            "ball_recovery": "Bola recuperada",
            "ball_carries": "Conduções",
            "progressive_carries": "Cond. progr.",
            "duels_won": "Duelos ganhos",
            "duels_lost": "Duelos perdidos",
            "aerials_won": "Aéreos ganhos",
            "interceptions": "Intercept.",
            "clearances": "Cortes",
            "fouls": "Faltas",
        }

        group = st.radio("Selecione o Grupo de Métricas", list(metric_groups.keys()), horizontal=True, key="raw_metric_grp")
        cols = ["name"] + [c for c in metric_groups[group] if c in adf.columns]
        sort_col = st.selectbox(
            "Ordenar tabela por", metric_groups[group], format_func=lambda c: labels.get(c, c), key="raw_sort_col"
        )
        table = adf[cols].sort_values(sort_col, ascending=False, na_position="last")
        table = table.rename(columns={**labels, "name": "Nome"})
        st.dataframe(table, width="stretch", hide_index=True)
    else:
        st.info("Sem métricas brutas do SofaScore disponíveis.")
