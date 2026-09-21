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
    get_available_teams,
    load_json,
    render_page_header,
)

available_teams = get_available_teams()
active_curr = get_active_team()

# Seletor de clube no topo da página
col_head1, col_head2 = st.columns([3, 1])
with col_head2:
    idx_def = available_teams.index(active_curr) if active_curr in available_teams else 0
    selected_team = st.selectbox(
        "Clube em Análise",
        options=available_teams,
        index=idx_def,
        format_func=lambda t: f"{TEAMS.get(t, {}).get('name', t.title())} ({TEAMS.get(t, {}).get('division', '')})",
        key="calendar_team_select",
    )
    if selected_team != st.session_state.get("active_team"):
        st.session_state["active_team"] = selected_team
        st.rerun()

team = get_active_team()
team_name = get_active_team_name()
division = TEAMS.get(team, {}).get("division", "Série B")
is_serie_a = (division == "Série A")

render_page_header(
    title=f"Calendário & Inteligência de Tabela — {team_name}",
    subtitle=f"Classificação oficial ({division} 2026), metas matemáticas, análise de rebaixamento Z-4 e Raio-X pré-jogo.",
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
        ogol = load_json(f"{team_key}_ogol_matches.json")
        t_name = TEAMS.get(team_key, {}).get("name", team_key.title())
        div_name = TEAMS.get(team_key, {}).get("division", "Campeonato")
        if isinstance(ogol, list):
            for m in ogol:
                if m.get("status") == "upcoming" or m.get("score") is None:
                    ha = m.get("home_away", "H")
                    opp = m.get("opponent", "Adversário")
                    rows.append({
                        "date": m.get("date", "A definir"),
                        "round": "—",
                        "home_team": t_name if ha == "H" else opp,
                        "away_team": opp if ha == "H" else t_name,
                        "competition": m.get("competition", div_name),
                    })
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


# Carregar dados fundamentais com base na divisão
standings_file = "standings_serie_a_2026.json" if is_serie_a else "standings_serie_b_2026.json"
standings_data = load_json(standings_file)
rows = standings_data.get("standings", []) if isinstance(standings_data, dict) else []
if not rows:
    standings_data = load_json("standings_serie_b_2026.json")
    rows = standings_data.get("standings", [])

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

active_team_id = TEAMS.get(team, {}).get("sofascore", {}).get("team_id")
highlight_ids = {active_team_id} if active_team_id else set()
if team in ("fortaleza", "ceara"):
    highlight_ids.add(TEAMS.get("fortaleza", {}).get("sofascore", {}).get("team_id"))
    highlight_ids.add(TEAMS.get("ceara", {}).get("sofascore", {}).get("team_id"))

# ============================================================
# TABS PRINCIPAIS
# ============================================================
tab_title_1 = "🏆 Título & Libertadores (G-4 / G-6)" if is_serie_a else "🏆 Acesso & Título (Calculadora G-6 + UFMG)"
tab_title_3 = "📊 Desempenho Mandante & Visitante" if is_serie_a else "📊 Estatísticas UFMG (Mandante, Visitante & Momento)"

tab_access, tab_relegation, tab_ufmg, tab_preview = st.tabs([
    tab_title_1,
    "🛑 Luta contra o Rebaixamento & Z-4",
    tab_title_3,
    "📅 Próximos Jogos & Raio-X Pré-Jogo",
])

# ============================================================
# TAB 1: Metas de Cima (Série A: Libertadores / Série B: Acesso)
# ============================================================
with tab_access:
    st.subheader(f"🏆 Classificação Oficial — {division} 2026")
    if is_serie_a:
        st.caption(
            "Regulamento oficial 2026: **Top 4** garantem vaga direta na fase de grupos da Libertadores. "
            "**5º e 6º** vão para a Pré-Libertadores. **7º ao 12º** classificam para a Copa Sul-Americana. "
            "Os **quatro últimos (17º ao 20º)** são rebaixados para a Série B."
        )
    else:
        st.caption(
            "Regulamento oficial 2026: **Top 2** sobem direto para a Série A. "
            "**3º e 4º** disputam os playoffs contra **5º e 6º** com vantagem de igualdade no placar agregado. "
            "Os **quatro últimos (17º ao 20º)** caem para a Série C."
        )

    sdf = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not sdf.empty:
        def _zone_badge(pos):
            if is_serie_a:
                if pos <= 4:
                    return "🟢 Libertadores Direta"
                elif pos in (5, 6):
                    return "🔵 Pré-Libertadores"
                elif pos in range(7, 13):
                    return "🟡 Sul-Americana"
                elif pos >= 17:
                    return "🔴 Z-4"
                return "⚪ Manutenção"
            else:
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
            is_active = (team_id in highlight_ids) or (normalize_name(row.get("Time", "")) == normalize_name(team_name))

            if is_active:
                return ["background-color: rgba(0, 43, 127, 0.18); font-weight: 700;"] * len(row)
            if pos in (1, 2) or (is_serie_a and pos <= 4):
                return ["background-color: rgba(16, 185, 129, 0.05);"] * len(row)
            elif (not is_serie_a and pos in (3, 4)) or (is_serie_a and pos in (5, 6)):
                return ["background-color: rgba(59, 130, 246, 0.05);"] * len(row)
            elif (not is_serie_a and pos in (5, 6)) or (is_serie_a and pos in range(7, 13)):
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

    # --- CALCULADORA DE METAS MATEMÁTICAS ---
    if is_serie_a:
        st.subheader("🎯 Calculadora de Metas — Série A (Título & Libertadores)")
        st.caption("Projeções de pontuação calibradas para o Brasileirão Série A 2026.")
        scenarios = [
            {
                "id": "titulo",
                "nome": "Título",
                "pos_alvo": "1º Lugar",
                "meta": 78,
                "icone": "🥇",
                "cor": "#F59E0B",
                "badge": "Campeão Brasileiro",
                "prob_ufmg": "—",
                "regras": "Campeão brasileiro e vaga direta na Supercopa do Brasil.",
            },
            {
                "id": "libertadores_g4",
                "nome": "Libertadores (G-4)",
                "pos_alvo": "Top 4 (1º ao 4º)",
                "meta": 65,
                "icone": "🚀",
                "cor": "#10B981",
                "badge": "Fase de Grupos",
                "prob_ufmg": "—",
                "regras": "Vaga direta na fase de grupos da Copa Libertadores da América.",
            },
            {
                "id": "pre_libertadores",
                "nome": "Pré-Libertadores",
                "pos_alvo": "G-6 (5º e 6º)",
                "meta": 59,
                "icone": "🔵",
                "cor": "#3B82F6",
                "badge": "Fase Preliminar",
                "prob_ufmg": "—",
                "regras": "Disputa as fases preliminares eliminatórias da Copa Libertadores.",
            },
            {
                "id": "sul_americana",
                "nome": "Sul-Americana",
                "pos_alvo": "G-12 (7º ao 12º)",
                "meta": 48,
                "icone": "🟡",
                "cor": "#8B5CF6",
                "badge": "Copa Sul-Americana",
                "prob_ufmg": "—",
                "regras": "Classificação para a fase de grupos da Copa Sul-Americana.",
            },
        ]
    else:
        st.subheader("🎯 Calculadora de Acesso & Mata-mata — Modelo G-6 (Série B)")
        st.caption("Metas calibradas com o ritmo projetado dos concorrentes da Série B 2026 + parâmetros históricos e dados probabilísticos da UFMG.")
        prob_camp = team_ufmg_probs.get("prob_campeao", 0.0)
        prob_dir = team_ufmg_probs.get("prob_acesso_direto", 0.0)
        prob_play = team_ufmg_probs.get("prob_playoffs", 0.0)
        scenarios = [
            {
                "id": "titulo",
                "nome": "Título",
                "pos_alvo": "1º Lugar",
                "meta": 70,
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
                "meta": 67,
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
                "meta": 64,
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
                "meta": 61,
                "icone": "🎟️",
                "cor": "#8B5CF6",
                "badge": "Vaga no Playoff",
                "prob_ufmg": f"{prob_play:.1f}% (G-6)",
                "regras": "Classificam para os playoffs de acesso, porém decidem fora e sem vantagem do empate no agregado.",
            },
        ]

    # Cards de Indicadores
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

            ufmg_lbl = f"<span style='font-size: 0.72rem; background: #EFF6FF; color: #1D4ED8; padding: 1px 6px; border-radius: 4px; font-weight: 700;'>UFMG: {sc['prob_ufmg']}</span>" if sc.get("prob_ufmg") != "—" else ""

            st.markdown(
                f"""
                <div style="border: 1px solid rgba(226, 232, 240, 0.9); border-top: 4px solid {sc['cor']}; border-radius: 8px; padding: 12px; background: #FFFFFF; min-height: 180px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.75rem; font-weight: 700; color: {sc['cor']}; text-transform: uppercase;">{sc['pos_alvo']}</span>
                        {ufmg_lbl}
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

    # Matriz Comparativa de Cenários
    st.markdown(f"#### 📋 Matriz de Cenários ({matches_remaining} Rodadas Restantes)")
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
            "Aprov. Exigido": f"{req_pct}% ({req_ppg:.2f} pts/j)",
            "Combinação Sugerida": combo,
            "Projeção Atual vs Meta": status_txt,
            "Regulamento": sc["regras"],
        })

    tdf = pd.DataFrame(table_data)
    st.dataframe(tdf, width="stretch", hide_index=True)

    # Gráfico Plotly: Projeção vs Metas
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
            title=f"Pontuação no {division} 2026",
            range=[0, max(max_pts_possible, 80)],
            dtick=10,
        ),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1),
    )
    st.plotly_chart(fig_proj, width="stretch", config={"responsive": True, "displayModeBar": False})

# ============================================================
# TAB 2: Luta contra o Rebaixamento & Z-4
# ============================================================
with tab_relegation:
    st.subheader(f"🛑 Luta contra o Rebaixamento & Análise de Sobrevivência ({division})")
    div_down = "Série B" if is_serie_a else "Série C"
    st.caption(
        f"Diagnóstico de risco de queda para a {div_down}. "
        "A régua matemática histórica estabelece **45 pontos** como o patamar clássico de segurança na permanência."
    )

    reb_prof = calc_team_relegation_profile(team_name, rows, ufmg_data if not is_serie_a else None)

    # Banner Principal de Status
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
                    <span style="font-size: 0.85rem; color: #94A3B8;">Risco Estimado:</span>
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
                    Combinação: <b>{t45['combo']}</b><br>
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
                <div style="font-size: 0.8rem; font-weight: 700; color: #059669; text-transform: uppercase;">Garantia Matemática</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B; margin: 4px 0;">🔒 Meta 46 Pontos</div>
                <div style="display: flex; justify-content: space-between; margin: 6px 0;">
                    <span style="color: #64748B; font-size: 0.85rem;">Faltam:</span>
                    <span style="font-size: 1.1rem; font-weight: 800; color: {'#059669' if t46['needed'] == 0 else '#DC2626'};">{t46['needed']} pts</span>
                </div>
                <div style="font-size: 0.8rem; color: #475569;">
                    Aproveitamento: <b>{t46['req_pct']}%</b> ({t46['req_ppg']:.2f} pts/j)<br>
                    Combinação: <b>{t46['combo']}</b><br>
                    Status: <b>{'🟢 Confortável' if t46['needed'] == 0 else 'Em disputa'}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_hist:
        hist_comp = compare_team_to_historical(played_ref, pts_real, team_name)
        bm = hist_comp["benchmark"]
        diff_p16 = hist_comp["diffs"]["p16_permanencia"]

        st.markdown(
            f"""
            <div style="border: 1px solid #E2E8F0; border-top: 4px solid #6366F1; border-radius: 8px; padding: 14px; background: #FFFFFF;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #6366F1; text-transform: uppercase;">Régua Histórica (Rodada {played_ref})</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B; margin: 4px 0;">📈 Comparativo Histórico</div>
                <div style="font-size: 0.85rem; color: #334155; line-height: 1.4;">
                    • Média do 16º (Corte Z-4): <b>{bm['p16_permanencia']} pts</b><br>
                    • Desempenho do {team_name}: <b>{pts_real} pts</b> ({diff_p16:+.1f} pts vs corte)<br>
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

    # Panorama Geral Z-4 Watch
    st.markdown("#### 🚨 Panorama Geral da Luta contra o Rebaixamento (Z-4 Watch)")
    overview_rows = build_relegation_overview(rows, ufmg_data if not is_serie_a else None, safe_target=45)
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
            "prob_ufmg": "Risco Rebaixamento (%)",
            "last_10_pts": "Pts (Últimas 10)",
            "last_10_eff": "Aprov. Recente",
        }
        show_cols = [c for c in col_renames if c in odf.columns]
        view_odf = odf[show_cols].rename(columns=col_renames)
        
        # Blindagem contra erro de tipo Arrow
        if "Pts (Últimas 10)" in view_odf.columns:
            view_odf["Pts (Últimas 10)"] = view_odf["Pts (Últimas 10)"].astype(str)

        def _highlight_relegation(row):
            pos = row.get("Pos", 0)
            p_ufmg = float(row.get("Risco Rebaixamento (%)", 0.0) or 0.0)
            tname = row.get("Time", "")
            is_active = (normalize_name(tname) == normalize_name(team_name))

            if is_active:
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

# ============================================================
# TAB 3: Estatísticas de Mando & Momento
# ============================================================
with tab_ufmg:
    if not is_serie_a and ufmg_data:
        st.subheader("📊 Estatísticas Oficiais do Departamento de Matemática da UFMG")
        st.caption("Desempenho segmentado: aproveitamento como mandante, visitante e retrospecto recente nas últimas 10 rodadas.")

        tables = ufmg_data.get("tables", {})
        home_t = tables.get("mandante", {})
        away_t = tables.get("visitante", {})
        last10_t = tables.get("ultimas_10", {})

        def _fmt_table(t_dict: dict) -> pd.DataFrame:
            headers = t_dict.get("headers", [])
            raw_rows = t_dict.get("rows", [])
            if not headers or not raw_rows:
                return pd.DataFrame()
            return pd.DataFrame(raw_rows, columns=headers)

        col_h, col_a = st.columns(2)
        with col_h:
            st.markdown("#### 🏠 Classificação como Mandante")
            df_home = _fmt_table(home_t)
            if not df_home.empty:
                st.dataframe(df_home, width="stretch", hide_index=True)
        with col_a:
            st.markdown("#### ✈️ Classificação como Visitante")
            df_away = _fmt_table(away_t)
            if not df_away.empty:
                st.dataframe(df_away, width="stretch", hide_index=True)

        st.markdown("#### 🔥 Momento Recente: Classificação das Últimas 10 Rodadas")
        df_l10 = _fmt_table(last10_t)
        if not df_l10.empty:
            st.dataframe(df_l10, width="stretch", hide_index=True)
    else:
        st.subheader(f"📊 Desempenho em Casa vs Fora ({division} 2026)")
        st.caption(f"Comparativo de aproveitamento mandante e visitante do {team_name} e adversários.")

        ha = tm.get("home_away", {})
        c_home = ha.get("home", {})
        c_away = ha.get("away", {})

        col_h1, col_h2, col_h3 = st.columns(3)
        with col_h1:
            st.metric("PPG em Casa", f"{c_home.get('ppg', 0.0):.2f} pts/j", f"{c_home.get('wins', 0)}V {c_home.get('draws', 0)}E {c_home.get('losses', 0)}D")
        with col_h2:
            st.metric("PPG Fora de Casa", f"{c_away.get('ppg', 0.0):.2f} pts/j", f"{c_away.get('wins', 0)}V {c_away.get('draws', 0)}E {c_away.get('losses', 0)}D")
        with col_h3:
            st.metric("Gols Pró/Contra", f"{s.get('goals_for', 0)} / {s.get('goals_against', 0)}", f"Saldo: {s.get('goals_for', 0) - s.get('goals_against', 0):+d}")

# ============================================================
# TAB 4: Próximos Jogos & Raio-X Pré-Jogo
# ============================================================
with tab_preview:
    st.subheader(f"📅 Próximos Confrontos — {team_name}")

    fixtures_data = load_json(f"{team}_fixtures.json")
    fixtures_list = fixtures_data.get("fixtures", []) if isinstance(fixtures_data, dict) else []

    if not fixtures_list:
        ogol = load_json(f"{team}_ogol_matches.json")
        if isinstance(ogol, list):
            for m in ogol:
                if m.get("status") == "upcoming" or m.get("score") is None:
                    ha = m.get("home_away", "H")
                    opp = m.get("opponent", "Adversário")
                    fixtures_list.append({
                        "date": m.get("date", "A definir"),
                        "round": "—",
                        "home_team": team_name if ha == "H" else opp,
                        "away_team": opp if ha == "H" else team_name,
                        "competition": m.get("competition", division),
                        "home_id": None,
                        "away_id": None,
                    })

    if fixtures_list:
        next_match = fixtures_list[0]
        cfg_team_id = TEAMS.get(team, {}).get("sofascore", {}).get("team_id")
        home_id = next_match.get("home_id")
        home_team_name = next_match.get("home_team", "")
        away_team_name = next_match.get("away_team", "")

        if cfg_team_id and home_id:
            is_home = (home_id == cfg_team_id)
        else:
            is_home = normalize_name(team_name) in normalize_name(home_team_name) or normalize_name(home_team_name) in normalize_name(team_name)

        opp = away_team_name if is_home else home_team_name
        date_str = next_match.get("date", "A definir")
        rnd = next_match.get("round", "—")
        mando_str = "Mandante (Em Casa)" if is_home else f"Visitante (contra {opp})"

        home_color = "#FDE047" if is_home else "#38BDF8"
        away_color = "#38BDF8" if is_home else "#FDE047"

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #0A1E4A 0%, #002B7F 100%); color: #FFFFFF; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; border-left: 6px solid #F59E0B; box-shadow: 0 4px 15px rgba(0,0,0,0.25);">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <span class="fec-badge" style="background:#F59E0B; color:#0F172A; font-weight:800; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; letter-spacing: 0.5px;">PRÓXIMO CONFRONTO ({rnd})</span>
                    <span style="background: rgba(255,255,255,0.12); color: #E2E8F0; font-size: 0.8rem; padding: 3px 8px; border-radius: 4px; font-weight: 600;">{division} 2026</span>
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

    st.subheader(f"📋 Lista de Próximos Jogos — {team_name}")
    df_fix = _fixtures_df(team)
    if not df_fix.empty:
        st.dataframe(df_fix, width="stretch", hide_index=True)
    else:
        st.info(f"Sem partidas futuras catalogadas para o {team_name}.")
