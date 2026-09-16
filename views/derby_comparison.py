import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from views._common import load_json, render_page_header
from views.pitch import BODY_PART_PT

render_page_header(
    title="⚔️ Clássico-Rei — Comparativo Direto",
    subtitle="Raio-X estatístico avançado e confronto lado a lado entre Fortaleza EC e Ceará SC na temporada 2026.",
    tag="Confronto Cearense",
)

# Carregar dados de ambos os clubes
f_tm = load_json("fortaleza_team_metrics.json")
c_tm = load_json("ceara_team_metrics.json")
f_pm = load_json("fortaleza_player_metrics.json")
c_pm = load_json("ceara_player_metrics.json")

f_players = f_pm.get("players", []) if isinstance(f_pm, dict) else (f_pm or [])
c_players = c_pm.get("players", []) if isinstance(c_pm, dict) else (c_pm or [])

f_s = f_tm.get("summary", {}) if f_tm else {}
c_s = c_tm.get("summary", {}) if c_tm else {}

# Helpers para valores numéricos
def _v(summary, key, default=0.0):
    val = summary.get(key)
    return default if val is None else val

# --- Top Banner Confronto ---
col_f, col_vs, col_c = st.columns([5, 1, 5])

with col_f:
    st.markdown(
        """
        <div style="background: #F0F4FA; border: 2px solid #002B7F; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2.2rem;">🦁</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: #002B7F;">FORTALEZA EC</div>
            <div style="font-size: 0.85rem; color: #64748B; font-weight: 600;">Tricolor do Pici</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_vs:
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 90px;">
            <span style="font-size: 1.5rem; font-weight: 900; color: #94A3B8;">VS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_c:
    st.markdown(
        """
        <div style="background: #F8FAFC; border: 2px solid #1E293B; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2.2rem;">🏁</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: #1E293B;">CEARÁ SC</div>
            <div style="font-size: 0.85rem; color: #64748B; font-weight: 600;">Vozão</div>
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
        f_pts, c_pts = _v(f_s, "points_real"), _v(c_s, "points_real")
        st.metric(
            "Pontos Reais",
            f"{f_pts} vs {c_pts}",
            delta=f"{f_pts - c_pts:+} pts (FEC)" if f_pts != c_pts else "Empate",
        )
    with c2:
        f_xp, c_xp = _v(f_s, "points_expected"), _v(c_s, "points_expected")
        st.metric(
            "Pontos Esperados (xPts)",
            f"{f_xp:.1f} vs {c_xp:.1f}",
            delta=f"{f_xp - c_xp:+.1f} xPts (FEC)",
        )
    with c3:
        f_xgd, c_xgd = _v(f_s, "xg_diff"), _v(c_s, "xg_diff")
        st.metric(
            "Saldo de xG Acumulado",
            f"{f_xgd:+.2f} vs {c_xgd:+.2f}",
            delta=f"{f_xgd - c_xgd:+.2f} ΔxG",
        )
    with c4:
        f_luck, c_luck = _v(f_s, "points_luck"), _v(c_s, "points_luck")
        st.metric(
            "Sorte / Overperformance",
            f"{f_luck:+.1f} vs {c_luck:+.1f}",
            help="Pontos reais menos pontos esperados (Poisson).",
        )

    st.divider()

    # Tabela comparativa detalhada
    f_ha = f_tm.get("home_away", {})
    c_ha = c_tm.get("home_away", {})

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
        "Fortaleza EC 🦁": [
            f_s.get("matches", 0),
            f"{f_s.get('wins', 0)}V / {f_s.get('draws', 0)}E / {f_s.get('losses', 0)}D",
            f"{f_s.get('goals_for', 0)} / {f_s.get('goals_against', 0)}",
            f"{(f_s.get('goals_for', 0) - f_s.get('goals_against', 0)):+d}",
            f"{_v(f_s, 'xg_for_total'):.1f} ({_v(f_s, 'xg_for_total') / max(f_s.get('matches', 1), 1):.2f}/j)",
            f"{_v(f_s, 'xg_against_total'):.1f} ({_v(f_s, 'xg_against_total') / max(f_s.get('matches', 1), 1):.2f}/j)",
            f"{_v(f_s, 'finishing'):+.2f}",
            f"{_v(f_s, 'keeping'):+.2f}",
            f"{f_ha.get('home', {}).get('ppg', 0.0):.2f} pts/j",
            f"{f_ha.get('away', {}).get('ppg', 0.0):.2f} pts/j",
        ],
        "Ceará SC 🏁": [
            c_s.get("matches", 0),
            f"{c_s.get('wins', 0)}V / {c_s.get('draws', 0)}E / {c_s.get('losses', 0)}D",
            f"{c_s.get('goals_for', 0)} / {c_s.get('goals_against', 0)}",
            f"{(c_s.get('goals_for', 0) - c_s.get('goals_against', 0)):+d}",
            f"{_v(c_s, 'xg_for_total'):.1f} ({_v(c_s, 'xg_for_total') / max(c_s.get('matches', 1), 1):.2f}/j)",
            f"{_v(c_s, 'xg_against_total'):.1f} ({_v(c_s, 'xg_against_total') / max(c_s.get('matches', 1), 1):.2f}/j)",
            f"{_v(c_s, 'finishing'):+.2f}",
            f"{_v(c_s, 'keeping'):+.2f}",
            f"{c_ha.get('home', {}).get('ppg', 0.0):.2f} pts/j",
            f"{c_ha.get('away', {}).get('ppg', 0.0):.2f} pts/j",
        ],
    }
    st.dataframe(pd.DataFrame(comp_data), width="stretch", hide_index=True)

    # Gráfico Barras Comparativo Plotly
    fig = go.Figure()
    categories = ["xG Pró/Jogo", "xG Concedido/Jogo", "PPG Casa", "PPG Fora", "Gols Evitados/10"]
    f_n = max(f_s.get("matches", 1), 1)
    c_n = max(c_s.get("matches", 1), 1)

    f_vals = [
        round(_v(f_s, "xg_for_total") / f_n, 2),
        round(_v(f_s, "xg_against_total") / f_n, 2),
        f_ha.get("home", {}).get("ppg", 0.0) or 0.0,
        f_ha.get("away", {}).get("ppg", 0.0) or 0.0,
        round(_v(f_s, "keeping") / 10, 2),
    ]
    c_vals = [
        round(_v(c_s, "xg_for_total") / c_n, 2),
        round(_v(c_s, "xg_against_total") / c_n, 2),
        c_ha.get("home", {}).get("ppg", 0.0) or 0.0,
        c_ha.get("away", {}).get("ppg", 0.0) or 0.0,
        round(_v(c_s, "keeping") / 10, 2),
    ]

    fig.add_trace(go.Bar(
        name="Fortaleza EC",
        x=categories,
        y=f_vals,
        marker_color="#002B7F",
        text=f_vals,
        textposition="auto",
    ))
    fig.add_trace(go.Bar(
        name="Ceará SC",
        x=categories,
        y=c_vals,
        marker_color="#1E293B",
        text=c_vals,
        textposition="auto",
    ))
    fig.update_layout(
        barmode="group",
        title="Duelo Direto: Índices de Desempenho",
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

    f_sp = f_tm.get("set_pieces", {})
    c_sp = c_tm.get("set_pieces", {})
    f_sb = f_tm.get("shot_breakdown", {}).get("for", {})
    c_sb = c_tm.get("shot_breakdown", {}).get("for", {})
    f_style = f_tm.get("style", {})
    c_style = c_tm.get("style", {})

    c1, c2, c3 = st.columns(3)
    with c1:
        f_sp_f = f_sp.get("xg_for_setpiece_pct") or 0.0
        c_sp_f = c_sp.get("xg_for_setpiece_pct") or 0.0
        st.metric("% xG de Bola Parada (Pró)", f"{f_sp_f:.1f}% vs {c_sp_f:.1f}%", help="Fortaleza vs Ceará")
    with c2:
        f_sp_a = f_sp.get("xg_against_setpiece_pct") or 0.0
        c_sp_a = c_sp.get("xg_against_setpiece_pct") or 0.0
        st.metric("% xG de Bola Parada (Contra)", f"{f_sp_a:.1f}% vs {c_sp_a:.1f}%", help="Vulnerabilidade defensiva")
    with c3:
        f_poss = f_style.get("avg_possession") or 0.0
        c_poss = c_style.get("avg_possession") or 0.0
        st.metric("Posse de Bola Média", f"{f_poss:.1f}% vs {c_poss:.1f}%")

    st.divider()

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("**🦁 Fortaleza EC — Anatomia dos Chutes**")
        f_body = f_sb.get("by_body_part", {})
        if f_body:
            f_b_df = pd.DataFrame([
                {
                    "Parte do Corpo": BODY_PART_PT.get(k, k.replace("-", " ").title()),
                    "Finalizações": v["count"],
                    "Gols": v["goals"],
                    "xG": v["xg"],
                    "Conv. %": f"{v['conversion_pct']}%",
                }
                for k, v in f_body.items()
            ])
            st.dataframe(f_b_df, width="stretch", hide_index=True)
        else:
            st.caption("Sem dados de finalizações.")

    with col_t2:
        st.markdown("**🏁 Ceará SC — Anatomia dos Chutes**")
        c_body = c_sb.get("by_body_part", {})
        if c_body:
            c_b_df = pd.DataFrame([
                {
                    "Parte do Corpo": BODY_PART_PT.get(k, k.replace("-", " ").title()),
                    "Finalizações": v["count"],
                    "Gols": v["goals"],
                    "xG": v["xg"],
                    "Conv. %": f"{v['conversion_pct']}%",
                }
                for k, v in c_body.items()
            ])
            st.dataframe(c_b_df, width="stretch", hide_index=True)
        else:
            st.caption("Sem dados de finalizações.")

    # Game State Comparado
    st.subheader("⏱️ Game State: Comportamento por Placar (xG/90min)")
    f_gs = f_tm.get("game_state", {})
    c_gs = c_tm.get("game_state", {})

    gs_data = []
    labels = [("winning", "Vencendo (À frente)"), ("drawing", "Empatando"), ("losing", "Perdendo (Atrás)")]
    for st_key, st_name in labels:
        f_st = f_gs.get(st_key, {})
        c_st = c_gs.get(st_key, {})
        gs_data.append({
            "Estado do Jogo": st_name,
            "FEC xG Pró/90": f_st.get("xg_for_p90", 0.0),
            "FEC xG Contra/90": f_st.get("xg_against_p90", 0.0),
            "CSC xG Pró/90": c_st.get("xg_for_p90", 0.0),
            "CSC xG Contra/90": c_st.get("xg_against_p90", 0.0),
        })
    st.dataframe(pd.DataFrame(gs_data), width="stretch", hide_index=True)


# ============================================================
# TAB 3: Elenco & Destaques Cara a Cara
# ============================================================
with tab_elenco:
    st.subheader("💰 Comparativo Financeiro e Perfil de Elenco")

    f_df = pd.DataFrame(f_players) if f_players else pd.DataFrame()
    c_df = pd.DataFrame(c_players) if c_players else pd.DataFrame()

    f_val = f_df["market_value_eur"].dropna().sum() if "market_value_eur" in f_df.columns else 0
    c_val = c_df["market_value_eur"].dropna().sum() if "market_value_eur" in c_df.columns else 0
    f_age = f_df["age"].dropna().mean() if "age" in f_df.columns and not f_df["age"].dropna().empty else 0
    c_age = c_df["age"].dropna().mean() if "age" in c_df.columns and not c_df["age"].dropna().empty else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Valor de Mercado do Plantel",
            f"€ {f_val / 1_000_000:.1f} mi vs € {c_val / 1_000_000:.1f} mi".replace(".", ","),
            delta=f"€ {(f_val - c_val) / 1_000_000:+.1f} mi (FEC)",
        )
    with c2:
        st.metric(
            "Idade Média do Elenco",
            f"{f_age:.1f} anos vs {c_age:.1f} anos",
            delta=f"{f_age - c_age:+.1f} anos",
        )
    with c3:
        st.metric(
            "Total de Atletas Registrados",
            f"{len(f_df)} vs {len(c_df)}",
        )

    st.divider()

    st.subheader("👤 Duelos Individuais Cara a Cara")

    def _get_top(players_list, sort_key):
        valid = [p for p in players_list if (p.get("minutes") or 0) >= 300]
        if not valid:
            valid = players_list
        return sorted(valid, key=lambda x: (x.get(sort_key) or 0), reverse=True)[0] if valid else {}

    f_artilheiro = _get_top(f_players, "goals")
    c_artilheiro = _get_top(c_players, "goals")
    f_garcom = _get_top(f_players, "xa_p90")
    c_garcom = _get_top(c_players, "xa_p90")
    f_rating = _get_top(f_players, "avg_rating")
    c_rating = _get_top(c_players, "avg_rating")

    duel_cols = st.columns(3)

    with duel_cols[0]:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #F59E0B; border-radius: 10px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-weight: 800; font-size: 0.95rem; color: #1E293B; margin-bottom: 8px;">🎯 Duelo dos Goleadores</div>
                <div style="padding-bottom: 6px; border-bottom: 1px solid #F1F5F9;">
                    <span style="font-weight: 700; color: #002B7F;">🦁 {f_artilheiro.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{f_artilheiro.get('goals', 0)} gols ({f_artilheiro.get('xg_p90', 0):.2f} xG/90)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">🏁 {c_artilheiro.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{c_artilheiro.get('goals', 0)} gols ({c_artilheiro.get('xg_p90', 0):.2f} xG/90)</small>
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
                    <span style="font-weight: 700; color: #002B7F;">🦁 {f_garcom.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{f_garcom.get('xa_p90', 0):.2f} xA/90 ({f_garcom.get('assists', 0)} assistências)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">🏁 {c_garcom.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">{c_garcom.get('xa_p90', 0):.2f} xA/90 ({c_garcom.get('assists', 0)} assistências)</small>
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
                    <span style="font-weight: 700; color: #002B7F;">🦁 {f_rating.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">Nota Média: {f_rating.get('avg_rating', 0):.2f} ({f_rating.get('minutes', 0)} min)</small>
                </div>
                <div style="padding-top: 6px;">
                    <span style="font-weight: 700; color: #1E293B;">🏁 {c_rating.get('name', 'N/A')}</span><br>
                    <small style="color: #64748B;">Nota Média: {c_rating.get('avg_rating', 0):.2f} ({c_rating.get('minutes', 0)} min)</small>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
