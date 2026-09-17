import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import TEAMS
from name_match import normalize_name
from analysis.relegation import calc_team_relegation_profile, build_relegation_overview
from analysis.historical import compare_team_to_historical, get_round_benchmark
from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_page_header,
)

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Calendário & Inteligência de Tabela — {team_name}",
    subtitle="Classificação oficial, projeção de acesso G-6, análise de rebaixamento Z-4, estatísticas UFMG e Raio-X pré-jogo.",
    tag=team_name,
)

FIXTURE_COLS = {
    "date": "Data",
    "round": "Rodada",
    "home_team": "Mandante",
    "away_team": "Visitante",
    "competition": "Competição",
}


def _fixtures_df(team_key: str) -> pd.DataFrame:
    data = load_json(f"{team_key}_fixtures.json")
    rows = data.get("fixtures", []) if isinstance(data, dict) else []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    cols = [c for c in FIXTURE_COLS if c in df.columns]
    return df[cols].rename(columns=FIXTURE_COLS)


def _calc_target_combo(pts_needed: int, matches_remaining: int) -> str:
    """Calcula combinação realista de V, E, D para atingir a meta."""
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


# Carregar dados fundamentais
standings_data = load_json("standings_serie_b_2026.json")
rows = standings_data.get("standings", []) if isinstance(standings_data, dict) else []
TOTAL_ROUNDS = 38
played_ref = rows[0].get("played", 28) if rows else 28

ufmg_data = load_json("ufmg_serie_b_2026.json") or {}


def _get_team_ufmg_probs(t_name: str) -> dict:
    if not ufmg_data:
        return {}
    teams_sum = ufmg_data.get("teams_summary", [])
    nt = normalize_name(t_name)
    for row in teams_sum:
        r_nt = row.get("norm_team", "")
        if r_nt == nt or r_nt in nt or nt in r_nt:
            return row
    return {}


team_ufmg_probs = _get_team_ufmg_probs(team_name)

# Carregar métricas do clube
tm = load_json(f"{team}_team_metrics.json")
s = tm.get("summary", {}) if tm else {}
pts_real = s.get("points_real", 0)
matches_played = s.get("matches", 0) or played_ref
matches_remaining = max(TOTAL_ROUNDS - matches_played, 0)
max_pts_possible = pts_real + (matches_remaining * 3)
ppg_real = (pts_real / matches_played) if matches_played else 0.0
xpts_total = s.get("points_expected", 0.0) or 0.0
xpts_per_game = (xpts_total / matches_played) if matches_played else 0.0
proj_real = round(pts_real + (ppg_real * matches_remaining), 1)
proj_xpts = round(pts_real + (xpts_per_game * matches_remaining), 1)

highlight_ids = {
    TEAMS.get("fortaleza", {}).get("sofascore", {}).get("team_id"),
    TEAMS.get("ceara", {}).get("sofascore", {}).get("team_id"),
}

# ============================================================
# TABS PRINCIPAIS
# ============================================================
tab_access, tab_relegation, tab_ufmg, tab_preview = st.tabs([
    "🏆 Acesso & Título (Calculadora G-6 + UFMG)",
    "🛑 Luta contra o Rebaixamento & Z-4",
    "📊 Estatísticas UFMG (Mandante, Visitante & Momento)",
    "📅 Próximos Jogos & Raio-X Pré-Jogo",
])

# ============================================================
# TAB 1: Acesso & Título (Calculadora G-6 + UFMG)
# ============================================================
with tab_access:
    st.subheader("🏆 Classificação Oficial — Série B 2026")
    st.caption(
        "Regulamento oficial 2026: **Top 2** sobem direto para a Série A. "
        "**3º e 4º** disputam os playoffs contra **5º e 6º** com vantagem de igualdade no placar agregado."
    )

    sdf = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not sdf.empty:
        def _zone_badge(pos):
            if pos in (1, 2):
                return "🟢 Acesso Direto"
            elif pos in (3, 4):
                return "🔵 Mata-mata (c/ Empate)"
            elif pos in (5, 6):
                return "🟡 Mata-mata (G-6)"
            elif pos >= 17:
                return "🔴 Z-4"
            return "⚪ Manutenção"

        sdf["Destino"] = sdf["position"].apply(_zone_badge)

        display_cols = {
            "position": "Pos",
            "Destino": "Zona / Destino",
            "team_name": "Time",
            "played": "J",
            "wins": "V",
            "draws": "E",
            "losses": "D",
            "goals_for": "GP",
            "goals_against": "GC",
            "goal_diff": "SG",
            "points": "Pts",
        }
        cols = [c for c in display_cols if c in sdf.columns]
        view_df = sdf[cols].rename(columns=display_cols)

        def _highlight_row(row):
            pos = row.get("Pos", 0)
            team_id = sdf.loc[row.name, "team_id"] if "team_id" in sdf.columns else None
            is_active = team_id in highlight_ids

            if is_active:
                return ["background-color: rgba(0, 43, 127, 0.16); font-weight: 700;"] * len(row)
            if pos in (1, 2):
                return ["background-color: rgba(16, 185, 129, 0.05);"] * len(row)
            elif pos in (3, 4):
                return ["background-color: rgba(59, 130, 246, 0.05);"] * len(row)
            elif pos in (5, 6):
                return ["background-color: rgba(245, 158, 11, 0.05);"] * len(row)
            elif pos >= 17:
                return ["background-color: rgba(239, 68, 68, 0.05);"] * len(row)
            return [""] * len(row)

        st.dataframe(
            view_df.style.apply(_highlight_row, axis=1),
            width="stretch",
            hide_index=True,
        )

    st.divider()

    # --- CALCULADORA DE ACESSO G-6 (SÉRIE B 2026) ---
    st.subheader("🎯 Calculadora de Acesso & Mata-mata — Modelo G-6")
    st.caption(
        "Metas calibradas com o ritmo projetado dos concorrentes da Série B 2026 + parâmetros históricos e dados probabilísticos da UFMG."
    )

    TARGET_TITULO = 70
    TARGET_ACESSO = 67
    TARGET_MATA_EMPATE = 64
    TARGET_MATA_MATA = 61

    prob_camp = team_ufmg_probs.get("prob_campeao", 0.0)
    prob_dir = team_ufmg_probs.get("prob_acesso_direto", 0.0)
    prob_play = team_ufmg_probs.get("prob_playoffs", 0.0)

    scenarios = [
        {
            "id": "titulo",
            "nome": "Título",
            "pos_alvo": "1º Lugar",
            "meta": TARGET_TITULO,
            "icone": "🥇",
            "cor": "#F59E0B",
            "badge": "Campeão da Série B",
            "prob_ufmg": f"{prob_camp:.1f}%",
            "regras": "Campeão da Série B e acesso direto à Série A com o troféu de campeão.",
        },
        {
            "id": "acesso_direto",
            "nome": "Acesso Direto",
            "pos_alvo": "Top 2 (1º e 2º)",
            "meta": TARGET_ACESSO,
            "icone": "🚀",
            "cor": "#10B981",
            "badge": "Vaga Direta Série A",
            "prob_ufmg": f"{prob_dir:.1f}%",
            "regras": "Os dois primeiros colocados sobem diretamente à Série A sem disputar playoffs.",
        },
        {
            "id": "mata_mata_empate",
            "nome": "Mata-mata c/ Vantagem",
            "pos_alvo": "Top 4 (3º e 4º)",
            "meta": TARGET_MATA_EMPATE,
            "icone": "⚖️",
            "cor": "#3B82F6",
            "badge": "Playoff c/ Vantagem",
            "prob_ufmg": f"{prob_play:.1f}% (G-6)",
            "regras": "Enfrentam 5º e 6º com vantagem de igualdade na soma dos placares e jogo de volta em casa.",
        },
        {
            "id": "mata_mata",
            "nome": "Mata-mata",
            "pos_alvo": "G-6 (5º e 6º)",
            "meta": TARGET_MATA_MATA,
            "icone": "🎟️",
            "cor": "#8B5CF6",
            "badge": "Vaga no Playoff",
            "prob_ufmg": f"{prob_play:.1f}% (G-6)",
            "regras": "Classificam para os playoffs de acesso, porém decidem fora e sem vantagem do empate no agregado.",
        },
    ]

    # 1. Quatro Cards de Indicadores
    cols_cards = st.columns(4)
    for idx, sc in enumerate(scenarios):
        with cols_cards[idx]:
            meta = sc["meta"]
            pts_needed = max(meta - pts_real, 0)
            is_possible = meta <= max_pts_possible
            is_achieved = pts_real >= meta

            req_ppg = round(pts_needed / matches_remaining, 2) if matches_remaining else 0.0
            req_pct = round((req_ppg / 3.0) * 100, 1) if matches_remaining else 0.0

            if is_achieved:
                status_txt = "✅ Conquistado!"
            elif not is_possible:
                status_txt = "❌ Inviável matematicamente"
            elif proj_real >= meta:
                status_txt = "🟢 Ritmo Suficiente"
            elif req_pct <= 65.0:
                status_txt = "🟡 Requer Aceleração"
            else:
                status_txt = "🟠 Aceleração Forte"

            st.markdown(
                f"""
                <div style="border: 1px solid rgba(226, 232, 240, 0.9); border-top: 4px solid {sc['cor']}; border-radius: 8px; padding: 12px; background: #FFFFFF; min-height: 180px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.75rem; font-weight: 700; color: {sc['cor']}; text-transform: uppercase;">{sc['pos_alvo']}</span>
                        <span style="font-size: 0.72rem; background: #EFF6FF; color: #1D4ED8; padding: 1px 6px; border-radius: 4px; font-weight: 700;">UFMG: {sc['prob_ufmg']}</span>
                    </div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #1E293B; margin: 4px 0 6px 0;">{sc['icone']} {sc['nome']}</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px;">
                        <span style="font-size: 0.82rem; color: #64748B;">Meta Alvo:</span>
                        <span style="font-size: 1.2rem; font-weight: 800; color: #0F172A;">{meta} pts</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px;">
                        <span style="font-size: 0.82rem; color: #64748B;">Faltam:</span>
                        <span style="font-size: 1.05rem; font-weight: 700; color: {'#059669' if pts_needed == 0 else '#DC2626'};">{pts_needed} pts</span>
                    </div>
                    <div style="font-size: 0.76rem; color: #475569; margin-top: 3px;">
                        Aproveitamento: <b>{req_pct}%</b> ({req_ppg:.2f} pts/j)
                    </div>
                    <div style="font-size: 0.75rem; font-weight: 700; margin-top: 4px; color: {'#059669' if '🟢' in status_txt or '✅' in status_txt else ('#D97706' if '🟡' in status_txt else '#DC2626')};">
                        {status_txt}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # 2. Tabela Analítica Comparativa dos 4 Casos
    st.markdown("#### 📋 Matriz Comparativa de Cenários (10 Rodadas Restantes)")
    table_data = []
    for sc in scenarios:
        meta = sc["meta"]
        pts_needed = max(meta - pts_real, 0)
        is_possible = meta <= max_pts_possible
        is_achieved = pts_real >= meta

        req_ppg = round(pts_needed / matches_remaining, 2) if matches_remaining else 0.0
        req_pct = round((req_ppg / 3.0) * 100, 1) if matches_remaining else 0.0
        combo = _calc_target_combo(pts_needed, matches_remaining)

        if is_achieved:
            status_txt = "✅ Garantido"
        elif not is_possible:
            status_txt = "❌ Inviável"
        elif proj_real >= meta:
            status_txt = f"🟢 No Ritmo ({proj_real:.1f} pts)"
        else:
            diff_proj = round(meta - proj_real, 1)
            status_txt = f"⚠️ Déficit de {diff_proj} pts"

        table_data.append({
            "Cenário": f"{sc['icone']} {sc['nome']}",
            "Posição Alvo": sc["pos_alvo"],
            "Meta": f"{meta} pts",
            "Faltam": f"{pts_needed} pts",
            "Prob. UFMG": sc["prob_ufmg"],
            "Aprov. Exigido": f"{req_pct}% ({req_ppg:.2f} pts/j)",
            "Combinação Sugerida (10j)": combo,
            "Projeção Atual vs Meta": status_txt,
            "Regulamento": sc["regras"],
        })

    tdf = pd.DataFrame(table_data)
    st.dataframe(tdf, width="stretch", hide_index=True)

    # 3. Gráfico Plotly: Projeção vs Metas
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 📊 Visualização de Projeção vs Linhas de Corte")
    fig_proj = go.Figure()

    fig_proj.add_trace(go.Bar(
        y=["Campanha"],
        x=[pts_real],
        name=f"Pontos Atuais ({pts_real} pts)",
        orientation="h",
        marker=dict(color="#002B7F"),
        text=[f"Atuais: {pts_real}"],
        textposition="inside",
    ))

    additional_real = max(proj_real - pts_real, 0.0)
    fig_proj.add_trace(go.Bar(
        y=["Campanha"],
        x=[additional_real],
        name=f"Projeção Ritmo Real ({proj_real:.1f} pts)",
        orientation="h",
        marker=dict(color="#60A5FA"),
        text=[f"Projeção: {proj_real:.1f}"],
        textposition="inside",
    ))

    for sc in scenarios:
        fig_proj.add_vline(
            x=sc["meta"],
            line_width=2,
            line_dash="dash",
            line_color=sc["cor"],
            annotation_text=f"{sc['icone']} {sc['nome']} ({sc['meta']} pts)",
            annotation_position="top",
            annotation_font_size=11,
            annotation_font_color=sc["cor"],
        )

    fig_proj.update_layout(
        barmode="stack",
        height=250,
        margin=dict(l=20, r=40, t=50, b=20),
        xaxis=dict(
            title="Pontuação na Série B 2026",
            range=[0, max(max_pts_possible, 75)],
            dtick=10,
        ),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1),
    )
    st.plotly_chart(fig_proj, width="stretch", config={"responsive": True, "displayModeBar": False})

    # Tabela de corte UFMG para Acesso
    if ufmg_data:
        cutoffs = ufmg_data.get("points_cutoffs", {})
        c_direct = cutoffs.get("direct", [])
        c_playoffs = cutoffs.get("playoffs", [])
        if c_direct or c_playoffs:
            with st.expander("📐 Linhas de Corte Matemáticas da UFMG (Probabilidade por Pontuação para Acesso e Playoffs)"):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown("**🚀 Probabilidade de Acesso Direto (Top 2) por Pontuação**")
                    if c_direct:
                        df_cd = pd.DataFrame(c_direct).rename(columns={"points": "Pontos", "prob": "Probabilidade (%)"})
                        st.dataframe(df_cd, width="stretch", hide_index=True)
                with col_c2:
                    st.markdown("**🎟️ Probabilidade de Vaga nos Playoffs (G-6) por Pontuação**")
                    if c_playoffs:
                        df_cp = pd.DataFrame(c_playoffs).rename(columns={"points": "Pontos", "prob": "Probabilidade (%)"})
                        st.dataframe(df_cp, width="stretch", hide_index=True)

# ============================================================
# TAB 2: Luta contra o Rebaixamento & Z-4 (NOVO!)
# ============================================================
with tab_relegation:
    st.subheader("🛑 Luta contra o Rebaixamento & Análise de Sobrevivência (Z-4)")
    st.caption(
        "Diagnóstico de risco de queda para a Série C. Segundo o Departamento de Matemática da UFMG: "
        "**45 pontos** apresenta risco de 16.6%, **46 pontos** reduz o risco para 6.9% e **50 pontos** zera o risco matematicamente."
    )

    reb_prof = calc_team_relegation_profile(team_name, rows, ufmg_data)

    # 1. Banner Principal de Status do Clube Ativo
    t45 = reb_prof["target_45"]
    t46 = reb_prof["target_46"]
    prob_reb = reb_prof["ufmg_relegation_prob"]

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); color: #FFFFFF; border-radius: 12px; padding: 18px 22px; margin-bottom: 16px; border-left: 6px solid {reb_prof['risk_color']}; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF;">
                    Termômetro de Risco: {team_name}
                </div>
                <span style="background: {reb_prof['risk_color']}; color: #FFFFFF; font-weight: 800; padding: 4px 12px; border-radius: 6px; font-size: 0.85rem;">
                    {reb_prof['badge']}
                </div>
            </div>
            <div style="display: flex; align-items: baseline; gap: 16px; margin: 12px 0 6px 0; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 0.85rem; color: #94A3B8;">Probabilidade UFMG:</span>
                    <span style="font-size: 2.2rem; font-weight: 900; color: {'#EF4444' if prob_reb >= 30 else ('#F59E0B' if prob_reb > 0 else '#10B981')}; margin-left: 6px;">
                        {prob_reb:.1f}%
                    </span>
                </div>
                <div style="color: #CBD5E1; font-size: 0.95rem;">
                    Posição Atual: <b>{reb_prof['position']}º lugar</b> &nbsp;·&nbsp;
                    Pontos: <b>{reb_prof['points']} pts</b> em {reb_prof['played']} jogos &nbsp;·&nbsp;
                    Projeção: <b>{reb_prof['proj_final_points']:.1f} pts</b>
                </div>
            </div>
            <p style="color: #E2E8F0; font-size: 0.88rem; margin: 4px 0 0 0;">
                {reb_prof['description']}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Cards das Metas de Sobrevivência (45 e 46 pontos)
    c_m1, c_m2, c_hist = st.columns([1.2, 1.2, 1.6])

    with c_m1:
        st.markdown(
            f"""
            <div style="border: 1px solid #E2E8F0; border-top: 4px solid #10B981; border-radius: 8px; padding: 14px; background: #FFFFFF;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #10B981; text-transform: uppercase;">Margem Segura Tradicional</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B; margin: 4px 0;">🛡️ Meta 45 Pontos</div>
                <div style="display: flex; justify-content: space-between; margin: 6px 0;">
                    <span style="color: #64748B; font-size: 0.85rem;">Faltam:</span>
                    <span style="font-size: 1.1rem; font-weight: 800; color: {'#059669' if t45['needed'] == 0 else '#DC2626'};">{t45['needed']} pts</span>
                </div>
                <div style="font-size: 0.8rem; color: #475569;">
                    Aproveitamento: <b>{t45['req_pct']}%</b> ({t45['req_ppg']:.2f} pts/j)<br>
                    Combinação (10j): <b>{t45['combo']}</b><br>
                    Ritmo Atual: <b>{'🟢 Suficiente' if t45['sufficient_pace'] else '⚠️ Insuficiente'}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_m2:
        st.markdown(
            f"""
            <div style="border: 1px solid #E2E8F0; border-top: 4px solid #059669; border-radius: 8px; padding: 14px; background: #FFFFFF;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #059669; text-transform: uppercase;">Garantia Matemática UFMG</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B; margin: 4px 0;">🔒 Meta 46 Pontos</div>
                <div style="display: flex; justify-content: space-between; margin: 6px 0;">
                    <span style="color: #64748B; font-size: 0.85rem;">Faltam:</span>
                    <span style="font-size: 1.1rem; font-weight: 800; color: {'#059669' if t46['needed'] == 0 else '#DC2626'};">{t46['needed']} pts</span>
                </div>
                <div style="font-size: 0.8rem; color: #475569;">
                    Aproveitamento: <b>{t46['req_pct']}%</b> ({t46['req_ppg']:.2f} pts/j)<br>
                    Combinação (10j): <b>{t46['combo']}</b><br>
                    Risco Residual: <b>6.9%</b> segundo a UFMG
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_hist:
        # Comparativo com a média histórica da rodada
        hist_comp = compare_team_to_historical(played_ref, pts_real, team_name)
        bm = hist_comp["benchmark"]
        diff_p16 = hist_comp["diffs"]["p16_permanencia"]

        st.markdown(
            f"""
            <div style="border: 1px solid #E2E8F0; border-top: 4px solid #6366F1; border-radius: 8px; padding: 14px; background: #FFFFFF;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #6366F1; text-transform: uppercase;">Média Histórica Série B (R{played_ref})</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B; margin: 4px 0;">📈 Régua dos Anos Anteriores</div>
                <div style="font-size: 0.85rem; color: #334155; line-height: 1.4;">
                    • Média do 16º (Corte Z-4): <b>{bm['p16_permanencia']} pts</b><br>
                    • Desempenho do {team_name}: <b>{pts_real} pts</b> ({diff_p16:+.1f} pts vs linha de corte)<br>
                    • Média do 17º (Degola): <b>{bm['p17_z4']} pts</b><br>
                </div>
                <div style="font-size: 0.78rem; font-weight: 700; margin-top: 6px; color: {hist_comp['status_color']};">
                    {hist_comp['status_text']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # 3. Tabela Comparativa dos Candidatos ao Rebaixamento (Z-4 Watch)
    st.markdown("#### 🚨 Panorama Geral da Luta contra o Rebaixamento (Z-4 Watch)")
    st.caption("Cruzamento oficial: classificação atual + probabilidade UFMG de rebaixamento + momento recente (últimas 10 rodadas).")

    overview_rows = build_relegation_overview(rows, ufmg_data, safe_target=45)
    if overview_rows:
        odf = pd.DataFrame(overview_rows)
        col_renames = {
            "pos": "Pos",
            "team": "Time",
            "played": "J",
            "points": "Pts",
            "needed_45": "Faltam p/ 45",
            "req_pct": "Aprov. Exigido (%)",
            "combo_10j": "Combinação (10j)",
            "proj_final": "Projeção Final",
            "prob_ufmg": "Prob. Rebaixamento UFMG (%)",
            "last_10_pts": "Pts (Últimas 10)",
            "last_10_eff": "Aprov. Recente",
        }
        show_cols = [c for c in col_renames if c in odf.columns]
        view_odf = odf[show_cols].rename(columns=col_renames)

        def _highlight_relegation(row):
            pos = row.get("Pos", 0)
            p_ufmg = row.get("Prob. Rebaixamento UFMG (%)", 0.0)
            tname = row.get("Time", "")
            is_active = normalize_name(tname) in [normalize_name(team_name), "fortaleza", "ceara"]

            if is_active and normalize_name(tname) == normalize_name(team_name):
                return ["background-color: rgba(0, 43, 127, 0.16); font-weight: 800;"] * len(row)
            if pos >= 17 or p_ufmg >= 70.0:
                return ["background-color: rgba(239, 68, 68, 0.12); font-weight: 600;"] * len(row)
            elif p_ufmg >= 30.0:
                return ["background-color: rgba(249, 115, 22, 0.10);"] * len(row)
            elif p_ufmg >= 5.0:
                return ["background-color: rgba(245, 158, 11, 0.08);"] * len(row)
            return [""] * len(row)

        st.dataframe(
            view_odf.style.apply(_highlight_relegation, axis=1),
            width="stretch",
            hide_index=True,
        )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # 4. Curva de Probabilidade de Rebaixamento por Pontuação da UFMG
    st.markdown("#### 📉 Curva de Corte: Probabilidade de Queda por Pontuação Final (UFMG)")
    pts_cutoffs = ufmg_data.get("points_cutoffs", {}).get("rebaixamento", [])
    if pts_cutoffs:
        df_cut = pd.DataFrame(pts_cutoffs)
        fig_cut = go.Figure()

        fig_cut.add_trace(go.Scatter(
            x=df_cut["points"],
            y=df_cut["prob"],
            mode="lines+markers+text",
            name="Risco de Rebaixamento (%)",
            line=dict(color="#EF4444", width=3),
            marker=dict(size=7, color="#B91C1C"),
            text=[f"{p:.1f}%" if p in [100.0, 68.3, 50.1, 31.7, 16.6, 6.9, 2.2, 0.0] or pts in [45, 46, 44] else "" for pts, p in zip(df_cut["points"], df_cut["prob"])],
            textposition="top right",
        ))

        # Adicionar linha vertical da pontuação atual do clube e projeção
        fig_cut.add_vline(
            x=pts_real,
            line_dash="dot",
            line_color="#002B7F",
            annotation_text=f"Atual: {pts_real} pts",
            annotation_position="bottom right",
        )
        fig_cut.add_vline(
            x=proj_real,
            line_dash="dash",
            line_color="#3B82F6",
            annotation_text=f"Projeção: {proj_real:.1f} pts",
            annotation_position="top right",
        )

        fig_cut.update_layout(
            height=320,
            margin=dict(l=20, r=40, t=30, b=30),
            xaxis=dict(title="Pontuação Final Acumulada", dtick=1, autorange="reversed"),
            yaxis=dict(title="Probabilidade de Queda (%)", range=[-5, 105]),
        )
        st.plotly_chart(fig_cut, width="stretch", config={"responsive": True, "displayModeBar": False})

        st.caption("Fonte: Departamento de Matemática da UFMG — Simulações probabilísticas da Série B 2026.")

# ============================================================
# TAB 3: Estatísticas UFMG (Mandante, Visitante, Momento) (NOVO!)
# ============================================================
with tab_ufmg:
    st.subheader("📊 Estatísticas Segmentadas da Série B — UFMG")
    st.caption("Classificações especiais de aproveitamento em casa, fora e nas últimas 10 rodadas calculadas pelo laboratório de futebol da UFMG.")

    st_ufmg = ufmg_data.get("standings", {})
    home_rows = st_ufmg.get("home", [])
    away_rows = st_ufmg.get("away", [])
    last10_rows = st_ufmg.get("last_10_rounds", [])
    first_half = st_ufmg.get("first_half", [])
    second_half = st_ufmg.get("second_half", [])

    # 1. Mandantes vs Visitantes Lado a Lado
    st.markdown("#### 🏠 Mandantes vs ✈️ Visitantes")
    col_home, col_away = st.columns(2)

    def _fmt_table(rows_list):
        if not rows_list:
            return pd.DataFrame()
        df = pd.DataFrame(rows_list)
        ren = {
            "position": "Pos",
            "team": "Time",
            "points": "Pts",
            "played": "J",
            "wins": "V",
            "draws": "E",
            "losses": "D",
            "goals_for": "GP",
            "goals_against": "GC",
            "goal_diff": "SG",
            "efficiency": "Aprov (%)",
        }
        cols = [c for c in ren if c in df.columns]
        return df[cols].rename(columns=ren)

    with col_home:
        st.markdown("**Desempenho Como Mandante (Casa)**")
        df_h = _fmt_table(home_rows)
        if not df_h.empty:
            def _style_h(row):
                tname = row.get("Time", "")
                if normalize_name(tname) == normalize_name(team_name):
                    return ["background-color: rgba(0, 43, 127, 0.16); font-weight: 700;"] * len(row)
                return [""] * len(row)
            st.dataframe(df_h.style.apply(_style_h, axis=1), width="stretch", hide_index=True)

    with col_away:
        st.markdown("**Desempenho Como Visitante (Fora)**")
        df_a = _fmt_table(away_rows)
        if not df_a.empty:
            def _style_a(row):
                tname = row.get("Time", "")
                if normalize_name(tname) == normalize_name(team_name):
                    return ["background-color: rgba(0, 43, 127, 0.16); font-weight: 700;"] * len(row)
                return [""] * len(row)
            st.dataframe(df_a.style.apply(_style_a, axis=1), width="stretch", hide_index=True)

    st.divider()

    # 2. Termômetro do Momento: Últimas 10 Rodadas
    st.markdown("#### 🔥 Termômetro do Momento: Classificação das Últimas 10 Rodadas")
    st.caption("Revela a forma e o ritmo recente de cada equipe no recorte mais decisivo do campeonato.")
    df_l10 = _fmt_table(last10_rows)
    if not df_l10.empty:
        def _style_l10(row):
            tname = row.get("Time", "")
            pos = row.get("Pos", 0)
            if normalize_name(tname) == normalize_name(team_name):
                return ["background-color: rgba(0, 43, 127, 0.16); font-weight: 700;"] * len(row)
            if pos <= 4:
                return ["background-color: rgba(16, 185, 129, 0.05);"] * len(row)
            elif pos >= 17:
                return ["background-color: rgba(239, 68, 68, 0.05);"] * len(row)
            return [""] * len(row)
        st.dataframe(df_l10.style.apply(_style_l10, axis=1), width="stretch", hide_index=True)

    st.divider()

    # 3. Comparativo de Turnos: 1º Turno vs Returno
    with st.expander("🔄 Comparativo de Turnos (1º Turno vs 2º Turno / Returno)"):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("**1º Turno (Rodadas 1 a 19)**")
            df_fh = _fmt_table(first_half)
            if not df_fh.empty:
                st.dataframe(df_fh, width="stretch", hide_index=True)
        with col_t2:
            st.markdown("**2º Turno (Returno em andamento)**")
            df_sh = _fmt_table(second_half)
            if not df_sh.empty:
                st.dataframe(df_sh, width="stretch", hide_index=True)

# ============================================================
# TAB 4: Próximos Jogos & Raio-X Pré-Jogo
# ============================================================
with tab_preview:
    st.subheader(f"📅 Calendário e Próximo Confronto — {team_name}")

    fixtures_data = load_json(f"{team}_fixtures.json")
    fixtures_list = fixtures_data.get("fixtures", []) if isinstance(fixtures_data, dict) else []

    if fixtures_list:
        next_match = fixtures_list[0]
        cfg_team_id = TEAMS.get(team, {}).get("sofascore", {}).get("team_id")
        home_id = next_match.get("home_id")
        home_team_name = next_match.get("home_team", "")
        away_team_name = next_match.get("away_team", "")

        # Determinar mando real comparando id do time ou nome
        if cfg_team_id and home_id:
            is_home = (home_id == cfg_team_id)
        else:
            is_home = team.lower() in home_team_name.lower()

        opp = away_team_name if is_home else home_team_name
        date_str = next_match.get("date", "A definir")
        rnd = next_match.get("round", "?")
        mando_str = "Mandante (Arena Castelão)" if is_home else f"Visitante (contra {opp})"

        if is_home:
            home_color = "#FDE047"
            away_color = "#38BDF8"
        else:
            home_color = "#38BDF8"
            away_color = "#FDE047"

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #0A1E4A 0%, #002B7F 100%); color: #FFFFFF; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; border-left: 6px solid #F59E0B; box-shadow: 0 4px 15px rgba(0,0,0,0.25);">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <span class="fec-badge" style="background:#F59E0B; color:#0F172A; font-weight:800; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; letter-spacing: 0.5px;">PRÓXIMA RODADA (R{rnd})</span>
                    <span style="background: rgba(255,255,255,0.12); color: #E2E8F0; font-size: 0.8rem; padding: 3px 8px; border-radius: 4px; font-weight: 600;">Série B 2026</span>
                </div>
                <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 12px 0 8px 0;">
                    <span style="font-size: clamp(1.2rem, 5vw, 1.85rem); font-weight: 800; color: {home_color}; letter-spacing: -0.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.3);">{home_team_name}</span>
                    <span style="font-size: clamp(0.85rem, 3vw, 1.15rem); font-weight: 900; color: #F59E0B; padding: 2px 8px; background: rgba(245, 158, 11, 0.2); border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.4);">VS</span>
                    <span style="font-size: clamp(1.2rem, 5vw, 1.85rem); font-weight: 800; color: {away_color}; letter-spacing: -0.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.3);">{away_team_name}</span>
                </div>
                <p style="color:#CBD5E1 !important; margin: 0; font-size:0.9rem;">
                    📅 <b style="color:#FFFFFF;">{date_str}</b> &nbsp;·&nbsp; Condição do {team_name}: <b style="color:#FDE047;">{mando_str}</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("🔍 Raio-X Pré-Jogo: Condições & Retrospecto")

        ha = tm.get("home_away", {}) if tm else {}
        side_key = "home" if is_home else "away"
        side_stats = ha.get(side_key, {})

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                f"Aproveitamento ({'Casa' if is_home else 'Fora'})",
                f"{side_stats.get('ppg', 0.0):.2f} pts/j",
                help="Média de pontos conquistados nesta condição na Série B",
            )
        with c2:
            st.metric(
                f"xG Pró ({'Casa' if is_home else 'Fora'})",
                f"{side_stats.get('xg_for', 0.0):.2f} /j",
                help="Volume de chances criadas por jogo nesta condição",
            )
        with c3:
            st.metric(
                f"xG Concedido ({'Casa' if is_home else 'Fora'})",
                f"{side_stats.get('xg_against', 0.0):.2f} /j",
                help="Volume de chances cedidas por jogo nesta condição",
            )

        st.divider()

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown("**🛡️ Disciplina e Arbitragem Acumulada**")
            disc = tm.get("discipline", {}) if tm else {}
            st.write(f"• **Faltas cometidas por jogo**: {disc.get('avg_fouls') or '—'}")
            st.write(f"• **Faltas sofridas por jogo**: {disc.get('avg_fouls_against') or '—'}")
            mando_txt = "mando caseiro" if is_home else "jogos fora de casa"
            st.caption(f"Perfil: Indicador geral da temporada para {mando_txt}.")

        with col_d2:
            st.markdown("**📈 Termômetro dos Últimos 5 Jogos (Média Móvel)**")
            pm = tm.get("per_match", []) if tm else []
            if pm:
                last_match = pm[-1]
                st.write(f"• **xG Pró (MM 5j)**: {last_match.get('xg_for_roll5', '—')}")
                st.write(f"• **xG Contra (MM 5j)**: {last_match.get('xg_against_roll5', '—')}")
                st.write(f"• **Pontos (MM 5j)**: {last_match.get('points_roll5', '—')} pts/j")

        st.divider()

    st.subheader("📋 Lista Completa de Próximos Jogos")
    col_f, col_c = st.columns(2)
    with col_f:
        st.markdown("**🦁 Fortaleza EC**")
        df_f = _fixtures_df("fortaleza")
        if df_f.empty:
            st.caption("Sem jogos futuros cadastrados.")
        else:
            st.dataframe(df_f, width="stretch", hide_index=True)
    with col_c:
        st.markdown("**🏁 Ceará SC**")
        df_c = _fixtures_df("ceara")
        if df_c.empty:
            st.caption("Sem jogos futuros cadastrados.")
        else:
            st.dataframe(df_c, width="stretch", hide_index=True)
