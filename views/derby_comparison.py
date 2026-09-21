import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import TEAMS
from views._common import get_available_teams, load_json, render_page_header
from views.pitch import BODY_PART_PT

render_page_header(
    title="⚔️ Comparador de Clubes — Confronto Direto",
    subtitle="Raio-X estatístico avançado e duelo lado a lado entre quaisquer duas equipes das Séries A e B na temporada 2026.",
    tag="Duelo Tático",
)

available_teams = get_available_teams()

# Presets Rápidos de Clássicos
st.markdown("##### ⚡ Atalhos de Clássicos & Duelos:")
col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)

if "comp_team_a" not in st.session_state:
    st.session_state["comp_team_a"] = "fortaleza"
if "comp_team_b" not in st.session_state:
    st.session_state["comp_team_b"] = "ceara"

with col_p1:
    if st.button("🦁🏁 Clássico-Rei", use_container_width=True):
        st.session_state["comp_team_a"] = "fortaleza"
        st.session_state["comp_team_b"] = "ceara"
        st.rerun()

with col_p2:
    if st.button("🔴⚫⚪ Fla-Flu", use_container_width=True):
        st.session_state["comp_team_a"] = "flamengo"
        st.session_state["comp_team_b"] = "fluminense"
        st.rerun()

with col_p3:
    if st.button("🐷🦅 Dérbi Paulista", use_container_width=True):
        st.session_state["comp_team_a"] = "palmeiras"
        st.session_state["comp_team_b"] = "corinthians"
        st.rerun()

with col_p4:
    if st.button("🐓🦊 Clássico Mineiro", use_container_width=True):
        st.session_state["comp_team_a"] = "atletico-mineiro"
        st.session_state["comp_team_b"] = "cruzeiro"
        st.rerun()

with col_p5:
    if st.button("🐋🦁 Santos vs Sport", use_container_width=True):
        st.session_state["comp_team_a"] = "santos"
        st.session_state["comp_team_b"] = "sport-recife"
        st.rerun()

# Seleção dos Dois Clubes
st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
col_sel_a, col_sel_vs, col_sel_b = st.columns([5, 1, 5])

curr_a = st.session_state.get("comp_team_a", "fortaleza")
curr_b = st.session_state.get("comp_team_b", "ceara")

idx_a = available_teams.index(curr_a) if curr_a in available_teams else 0
idx_b = available_teams.index(curr_b) if curr_b in available_teams else (1 if len(available_teams) > 1 else 0)

with col_sel_a:
    team_a = st.selectbox(
        "Selecione o Time A",
        options=available_teams,
        index=idx_a,
        format_func=lambda t: f"{TEAMS.get(t, {}).get('name', t.title())} ({TEAMS.get(t, {}).get('division', '')})",
        key="sel_comp_team_a",
    )
    if team_a != curr_a:
        st.session_state["comp_team_a"] = team_a
        st.rerun()

with col_sel_vs:
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 70px;">
            <span style="font-size: 1.4rem; font-weight: 900; color: #94A3B8;">VS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_sel_b:
    team_b = st.selectbox(
        "Selecione o Time B",
        options=available_teams,
        index=idx_b,
        format_func=lambda t: f"{TEAMS.get(t, {}).get('name', t.title())} ({TEAMS.get(t, {}).get('division', '')})",
        key="sel_comp_team_b",
    )
    if team_b != curr_b:
        st.session_state["comp_team_b"] = team_b
        st.rerun()

name_a = TEAMS.get(team_a, {}).get("name", team_a.title())
name_b = TEAMS.get(team_b, {}).get("name", team_b.title())
div_a = TEAMS.get(team_a, {}).get("division", "")
div_b = TEAMS.get(team_b, {}).get("division", "")

if team_a == team_b:
    st.info("⚠️ Selecione dois clubes distintos para comparar o desempenho lado a lado.")
    st.stop()

# Carregar dados dos clubes
tm_a = load_json(f"{team_a}_team_metrics.json")
tm_b = load_json(f"{team_b}_team_metrics.json")
pm_a = load_json(f"{team_a}_player_metrics.json")
pm_b = load_json(f"{team_b}_player_metrics.json")

players_a = pm_a.get("players", []) if isinstance(pm_a, dict) else (pm_a or [])
players_b = pm_b.get("players", []) if isinstance(pm_b, dict) else (pm_b or [])

sum_a = tm_a.get("summary", {}) if tm_a else {}
sum_b = tm_b.get("summary", {}) if tm_b else {}

def _v(summary, key, default=0.0):
    val = summary.get(key)
    return default if val is None else val

# --- Top Banner Confronto ---
st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
col_b_a, col_b_vs, col_b_b = st.columns([5, 1, 5])

icon_a = "🦁" if team_a == "fortaleza" else ("🏁" if team_a == "ceara" else "⚽")
icon_b = "🦁" if team_b == "fortaleza" else ("🏁" if team_b == "ceara" else "⚽")

color_a = "#002B7F" if team_a == "fortaleza" else "#1E293B"
color_b = "#002B7F" if team_b == "fortaleza" else "#1E293B"

with col_b_a:
    st.markdown(
        f"""
        <div style="background: #F0F4FA; border: 2px solid {color_a}; border-radius: 12px; padding: 14px; text-align: center;">
            <div style="font-size: 2rem;">{icon_a}</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: {color_a};">{name_a.upper()}</div>
            <div style="font-size: 0.85rem; color: #64748B; font-weight: 600;">{div_a} · Temporada 2026</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_b_vs:
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 80px;">
            <span style="font-size: 1.6rem; font-weight: 900; color: #94A3B8;">VS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_b_b:
    st.markdown(
        f"""
        <div style="background: #F8FAFC; border: 2px solid {color_b}; border-radius: 12px; padding: 14px; text-align: center;">
            <div style="font-size: 2rem;">{icon_b}</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: {color_b};">{name_b.upper()}</div>
            <div style="font-size: 0.85rem; color: #64748B; font-weight: 600;">{div_b} · Temporada 2026</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# Tabs de Conteúdo
tab_campanha, tab_tatica, tab_elenco = st.tabs([
    "📊 Campanha & Desempenho",
    "⚽ Ataque, Defesa & Bola Parada",
    "👥 Elenco & Destaques Cara a Cara",
])

# ============================================================
# TAB 1: Campanha & Desempenho
# ============================================================
with tab_campanha:
    st.subheader("📋 Resumo da Temporada (Real vs Esperado)")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pts_a, pts_b = _v(sum_a, "points_real"), _v(sum_b, "points_real")
        st.metric(
            "Pontos Reais",
            f"{pts_a} vs {pts_b}",
            delta=f"{pts_a - pts_b:+} pts ({name_a})" if pts_a != pts_b else "Empate",
        )
    with c2:
        xp_a, xp_b = _v(sum_a, "points_expected"), _v(sum_b, "points_expected")
        st.metric(
            "Pontos Esperados (xPts)",
            f"{xp_a:.1f} vs {xp_b:.1f}",
            delta=f"{xp_a - xp_b:+.1f} xPts ({name_a})",
        )
    with c3:
        xgd_a, xgd_b = _v(sum_a, "xg_diff"), _v(sum_b, "xg_diff")
        st.metric(
            "Saldo de xG Acumulado",
            f"{xgd_a:+.2f} vs {xgd_b:+.2f}",
            delta=f"{xgd_a - xgd_b:+.2f} ΔxG",
        )
    with c4:
        luck_a, luck_b = _v(sum_a, "points_luck"), _v(sum_b, "points_luck")
        st.metric(
            "Sorte / Overperformance",
            f"{luck_a:+.1f} vs {luck_b:+.1f}",
            help="Pontos reais menos pontos esperados pelo modelo de Poisson.",
        )

    # Bloco UFMG de Probabilidades Matemáticas (se ambos ou algum for da Série B)
    ufmg_data = load_json("ufmg_serie_b_2026.json") or {}
    if ufmg_data:
        from name_match import normalize_name
        teams_sum = {r.get("norm_team"): r for r in ufmg_data.get("teams_summary", [])}
        norm_a = normalize_name(name_a)
        norm_b = normalize_name(name_b)
        u_a = teams_sum.get(norm_a) or teams_sum.get(team_a, {})
        u_b = teams_sum.get(norm_b) or teams_sum.get(team_b, {})
        if u_a or u_b:
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 🎯 Probabilidades Matemáticas — Departamento de Matemática UFMG")
            u1, u2, u3, u4 = st.columns(4)
            with u1:
                st.metric("🏆 Prob. Título", f"{u_a.get('prob_campeao', 0.0):.1f}% vs {u_b.get('prob_campeao', 0.0):.1f}%")
            with u2:
                st.metric("🚀 Acesso Direto (Top 2)", f"{u_a.get('prob_acesso_direto', 0.0):.1f}% vs {u_b.get('prob_acesso_direto', 0.0):.1f}%")
            with u3:
                st.metric("🎟️ Vaga Playoffs (G-6)", f"{u_a.get('prob_playoffs', 0.0):.1f}% vs {u_b.get('prob_playoffs', 0.0):.1f}%")
            with u4:
                st.metric("🛑 Risco de Rebaixamento", f"{u_a.get('prob_rebaixamento', 0.0):.1f}% vs {u_b.get('prob_rebaixamento', 0.0):.1f}%")

    st.divider()

    # Tabela comparativa detalhada
    ha_a = tm_a.get("home_away", {})
    ha_b = tm_b.get("home_away", {})

    comp_data = {
        "Métrica": [
            "Jogos Disputados",
            "Vitórias / Empates / Derrotas",
            "Gols Marcados / Sofridos",
            "Saldo de Gols Real",
            "xG Gerado (Total / Média p/ jogo)",
            "xG Concedido (Total / Média p/ jogo)",
            "Eficiência de Finalização (Gols − xG)",
            "Gols Evitados Defensivos (xGA − Gols Sofridos)",
            "Aproveitamento em Casa (PPG Casa)",
            "Aproveitamento Fora (PPG Fora)",
        ],
        f"{name_a}": [
            str(sum_a.get("matches", 0)),
            f"{sum_a.get('wins', 0)}V / {sum_a.get('draws', 0)}E / {sum_a.get('losses', 0)}D",
            f"{sum_a.get('goals_for', 0)} / {sum_a.get('goals_against', 0)}",
            f"{(sum_a.get('goals_for', 0) - sum_a.get('goals_against', 0)):+d}",
            f"{_v(sum_a, 'xg_for_total'):.1f} ({_v(sum_a, 'xg_for_total') / max(sum_a.get('matches', 1), 1):.2f}/j)",
            f"{_v(sum_a, 'xg_against_total'):.1f} ({_v(sum_a, 'xg_against_total') / max(sum_a.get('matches', 1), 1):.2f}/j)",
            f"{_v(sum_a, 'finishing'):+.2f}",
            f"{_v(sum_a, 'keeping'):+.2f}",
            f"{ha_a.get('home', {}).get('ppg', 0.0):.2f} pts/j",
            f"{ha_a.get('away', {}).get('ppg', 0.0):.2f} pts/j",
        ],
        f"{name_b}": [
            str(sum_b.get("matches", 0)),
            f"{sum_b.get('wins', 0)}V / {sum_b.get('draws', 0)}E / {sum_b.get('losses', 0)}D",
            f"{sum_b.get('goals_for', 0)} / {sum_b.get('goals_against', 0)}",
            f"{(sum_b.get('goals_for', 0) - sum_b.get('goals_against', 0)):+d}",
            f"{_v(sum_b, 'xg_for_total'):.1f} ({_v(sum_b, 'xg_for_total') / max(sum_b.get('matches', 1), 1):.2f}/j)",
            f"{_v(sum_b, 'xg_against_total'):.1f} ({_v(sum_b, 'xg_against_total') / max(sum_b.get('matches', 1), 1):.2f}/j)",
            f"{_v(sum_b, 'finishing'):+.2f}",
            f"{_v(sum_b, 'keeping'):+.2f}",
            f"{ha_b.get('home', {}).get('ppg', 0.0):.2f} pts/j",
            f"{ha_b.get('away', {}).get('ppg', 0.0):.2f} pts/j",
        ],
    }
    st.dataframe(pd.DataFrame(comp_data), width="stretch", hide_index=True)

    # Gráfico Barras Comparativo Plotly
    fig = go.Figure()
    categories = ["xG Pró/Jogo", "xG Concedido/Jogo", "PPG Casa", "PPG Fora", "Gols Evitados/10"]
    n_a = max(sum_a.get("matches", 1), 1)
    n_b = max(sum_b.get("matches", 1), 1)

    vals_a = [
        round(_v(sum_a, "xg_for_total") / n_a, 2),
        round(_v(sum_a, "xg_against_total") / n_a, 2),
        ha_a.get("home", {}).get("ppg", 0.0) or 0.0,
        ha_a.get("away", {}).get("ppg", 0.0) or 0.0,
        round(_v(sum_a, "keeping") / 10, 2),
    ]
    vals_b = [
        round(_v(sum_b, "xg_for_total") / n_b, 2),
        round(_v(sum_b, "xg_against_total") / n_b, 2),
        ha_b.get("home", {}).get("ppg", 0.0) or 0.0,
        ha_b.get("away", {}).get("ppg", 0.0) or 0.0,
        round(_v(sum_b, "keeping") / 10, 2),
    ]

    fig.add_trace(go.Bar(
        name=name_a,
        x=categories,
        y=vals_a,
        marker_color="#002B7F",
        text=vals_a,
        textposition="auto",
    ))
    fig.add_trace(go.Bar(
        name=name_b,
        x=categories,
        y=vals_b,
        marker_color="#1E293B",
        text=vals_b,
        textposition="auto",
    ))
    fig.update_layout(
        barmode="group",
        title=f"Duelo Direto: {name_a} vs {name_b}",
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch", config={"responsive": True, "displayModeBar": False})

# ============================================================
# TAB 2: Ataque, Defesa & Bola Parada
# ============================================================
with tab_tatica:
    st.subheader("🎯 Perfil Tático e Eficiência de Finalizações")

    sp_a = tm_a.get("set_pieces", {})
    sp_b = tm_b.get("set_pieces", {})
    sb_a = tm_a.get("shot_breakdown", {}).get("for", {})
    sb_b = tm_b.get("shot_breakdown", {}).get("for", {})
    style_a = tm_a.get("style", {})
    style_b = tm_b.get("style", {})

    c1, c2, c3 = st.columns(3)
    with c1:
        sp_f_a = sp_a.get("xg_for_setpiece_pct") or 0.0
        sp_f_b = sp_b.get("xg_for_setpiece_pct") or 0.0
        st.metric("% xG de Bola Parada (Pró)", f"{sp_f_a:.1f}% vs {sp_f_b:.1f}%")
    with c2:
        sp_a_a = sp_a.get("xg_against_setpiece_pct") or 0.0
        sp_a_b = sp_b.get("xg_against_setpiece_pct") or 0.0
        st.metric("% xG de Bola Parada (Contra)", f"{sp_a_a:.1f}% vs {sp_a_b:.1f}%", help="Vulnerabilidade defensiva")
    with c3:
        poss_a = style_a.get("avg_possession") or 0.0
        poss_b = style_b.get("avg_possession") or 0.0
        st.metric("Posse de Bola Média", f"{poss_a:.1f}% vs {poss_b:.1f}%")

    st.divider()

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown(f"**{icon_a} {name_a} — Anatomia dos Chutes**")
        body_a = sb_a.get("by_body_part", {})
        if body_a:
            b_df_a = pd.DataFrame([
                {
                    "Parte do Corpo": BODY_PART_PT.get(k, k.replace("-", " ").title()),
                    "Finalizações": v["count"],
                    "Gols": v["goals"],
                    "xG": v["xg"],
                    "Conv. %": f"{v['conversion_pct']}%",
                }
                for k, v in body_a.items()
            ])
            st.dataframe(b_df_a, width="stretch", hide_index=True)
        else:
            st.caption("Sem dados de finalizações por parte do corpo.")

    with col_t2:
        st.markdown(f"**{icon_b} {name_b} — Anatomia dos Chutes**")
        body_b = sb_b.get("by_body_part", {})
        if body_b:
            b_df_b = pd.DataFrame([
                {
                    "Parte do Corpo": BODY_PART_PT.get(k, k.replace("-", " ").title()),
                    "Finalizações": v["count"],
                    "Gols": v["goals"],
                    "xG": v["xg"],
                    "Conv. %": f"{v['conversion_pct']}%",
                }
                for k, v in body_b.items()
            ])
            st.dataframe(b_df_b, width="stretch", hide_index=True)
        else:
            st.caption("Sem dados de finalizações por parte do corpo.")

    # Game State Comparado
    st.subheader("⏱️ Game State: Comportamento por Placar (xG/90min)")
    gs_a = tm_a.get("game_state", {})
    gs_b = tm_b.get("game_state", {})

    gs_data = []
    labels = [("winning", "Vencendo (À frente)"), ("drawing", "Empatando"), ("losing", "Perdendo (Atrás)")]
    for st_key, st_name in labels:
        s_a = gs_a.get(st_key, {})
        s_b = gs_b.get(st_key, {})
        gs_data.append({
            "Estado do Jogo": st_name,
            f"{name_a} xG Pró/90": s_a.get("xg_for_p90", 0.0),
            f"{name_a} xG Contra/90": s_a.get("xg_against_p90", 0.0),
            f"{name_b} xG Pró/90": s_b.get("xg_for_p90", 0.0),
            f"{name_b} xG Contra/90": s_b.get("xg_against_p90", 0.0),
        })
    st.dataframe(pd.DataFrame(gs_data), width="stretch", hide_index=True)

# ============================================================
# TAB 3: Elenco & Destaques Cara a Cara
# ============================================================
with tab_elenco:
    st.subheader("💰 Comparativo Financeiro e Perfil de Elenco")

    df_a = pd.DataFrame(players_a) if players_a else pd.DataFrame()
    df_b = pd.DataFrame(players_b) if players_b else pd.DataFrame()

    val_a = df_a["market_value_eur"].dropna().sum() if "market_value_eur" in df_a.columns else 0
    val_b = df_b["market_value_eur"].dropna().sum() if "market_value_eur" in df_b.columns else 0
    age_a = df_a["age"].dropna().mean() if "age" in df_a.columns and not df_a["age"].dropna().empty else 0
    age_b = df_b["age"].dropna().mean() if "age" in df_b.columns and not df_b["age"].dropna().empty else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        str_val_a = f"€ {val_a / 1_000_000:.1f} mi".replace(".", ",") if val_a > 0 else "Sob consulta"
        str_val_b = f"€ {val_b / 1_000_000:.1f} mi".replace(".", ",") if val_b > 0 else "Sob consulta"
        st.metric(
            "Valor de Mercado do Plantel",
            f"{str_val_a} vs {str_val_b}",
            delta=f"€ {(val_a - val_b) / 1_000_000:+.1f} mi" if val_a > 0 and val_b > 0 else None,
        )
    with c2:
        str_age_a = f"{age_a:.1f} anos" if age_a > 0 else "—"
        str_age_b = f"{age_b:.1f} anos" if age_b > 0 else "—"
        st.metric(
            "Idade Média do Elenco",
            f"{str_age_a} vs {str_age_b}",
            delta=f"{age_a - age_b:+.1f} anos" if age_a > 0 and age_b > 0 else None,
        )
    with c3:
        st.metric(
            "Atletas Registrados / Utilizados",
            f"{len(df_a)} vs {len(df_b)}",
        )

    st.divider()

    st.subheader("👤 Duelos Individuais Cara a Cara")

    def _get_top(players_list, sort_key):
        valid = [p for p in players_list if (p.get("minutes") or 0) >= 200]
        if not valid:
            valid = players_list
        return sorted(valid, key=lambda x: (x.get(sort_key) or 0), reverse=True)[0] if valid else {}

    top_gol_a = _get_top(players_a, "goals")
    top_gol_b = _get_top(players_b, "goals")
    top_gar_a = _get_top(players_a, "xa_p90")
    top_gar_b = _get_top(players_b, "xa_p90")
    top_rt_a = _get_top(players_a, "avg_rating")
    top_rt_b = _get_top(players_b, "avg_rating")

    duel_cols = st.columns(3)

    with duel_cols[0]:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #F59E0B; border-radius: 10px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-weight: 800; font-size: 0.95rem; color: #1E293B; margin-bottom: 8px;">🎯 Duelo dos Goleadores</div>
                <div style="padding-bottom: 6px; border-bottom: 1px solid #F1F5F9;">
                    <span style="font-weight: 700; color: #002B7F;">{name_a}: {top_gol_a.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{top_gol_a.get('goals', 0)} gols ({top_gol_a.get('xg_p90', 0) or 0:.2f} xG/90)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">{name_b}: {top_gol_b.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{top_gol_b.get('goals', 0)} gols ({top_gol_b.get('xg_p90', 0) or 0:.2f} xG/90)</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with duel_cols[1]:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #0284C7; border-radius: 10px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-weight: 800; font-size: 0.95rem; color: #1E293B; margin-bottom: 8px;">🎁 Mestres da Criação (xA)</div>
                <div style="padding-bottom: 6px; border-bottom: 1px solid #F1F5F9;">
                    <span style="font-weight: 700; color: #002B7F;">{name_a}: {top_gar_a.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{top_gar_a.get('xa_p90', 0) or 0:.2f} xA/90 ({top_gar_a.get('assists', 0)} assistências)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">{name_b}: {top_gar_b.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{top_gar_b.get('xa_p90', 0) or 0:.2f} xA/90 ({top_gar_b.get('assists', 0)} assistências)</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with duel_cols[2]:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #16A34A; border-radius: 10px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-weight: 800; font-size: 0.95rem; color: #1E293B; margin-bottom: 8px;">⭐ Maior Regularidade (Nota)</div>
                <div style="padding-bottom: 6px; border-bottom: 1px solid #F1F5F9;">
                    <span style="font-weight: 700; color: #002B7F;">{name_a}: {top_rt_a.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">Nota Média: {top_rt_a.get('avg_rating', 0) or 0:.2f} ({top_rt_a.get('minutes', 0)} min)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">{name_b}: {top_rt_b.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">Nota Média: {top_rt_b.get('avg_rating', 0) or 0:.2f} ({top_rt_b.get('minutes', 0)} min)</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
