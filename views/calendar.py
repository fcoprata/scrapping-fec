import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import TEAMS
from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_page_header,
)

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Calendário & Pré-Jogo — {team_name}",
    subtitle="Classificação oficial, projeção matemática de acesso (Modelo G-6) e Raio-X do próximo confronto.",
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


tab_standings, tab_preview = st.tabs([
    "🏆 Classificação & Calculadora G-6",
    "📅 Próximos Jogos & Raio-X Pré-Jogo",
])

# ============================================================
# TAB 1: Classificação & Calculadora de Acesso G-6
# ============================================================
with tab_standings:
    st.subheader("🏆 Classificação — Série B 2026 (Regulamento G-6)")
    st.caption(
        "Regulamento oficial 2026: **Top 2** sobem direto para a Série A. "
        "**3º e 4º** disputam os playoffs contra **5º e 6º** com vantagem de igualdade no placar agregado."
    )

    standings_data = load_json("standings_serie_b_2026.json")
    rows = standings_data.get("standings", []) if isinstance(standings_data, dict) else []

    TOTAL_ROUNDS = 38
    played_ref = rows[0].get("played", 28) if rows else 28

    sdf = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not sdf.empty:
        highlight_ids = {
            TEAMS.get("fortaleza", {}).get("sofascore", {}).get("team_id"),
            TEAMS.get("ceara", {}).get("sofascore", {}).get("team_id"),
        }

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
        "Análise determinística para os 4 objetivos do regulamento da Série B 2026: "
        "**Título**, **Acesso Direto (Top 2)**, **Mata-mata c/ Vantagem de Empate (Top 4)** e **Mata-mata (G-6)**."
    )

    tm = load_json(f"{team}_team_metrics.json")
    s = tm.get("summary", {}) if tm else {}

    pts_real = s.get("points_real", 0)
    matches_played = s.get("matches", 0) or played_ref
    matches_remaining = max(TOTAL_ROUNDS - matches_played, 0)
    max_pts_possible = pts_real + (matches_remaining * 3)

    ppg_real = (pts_real / matches_played) if matches_played else 0.0
    xpts_total = s.get("points_expected", 0.0) or 0.0
    xpts_per_game = (xpts_total / matches_played) if matches_played else 0.0

    # Projeções finais
    proj_real = round(pts_real + (ppg_real * matches_remaining), 1)
    proj_xpts = round(pts_real + (xpts_per_game * matches_remaining), 1)

    # Metas calibradas com o ritmo projetado dos concorrentes da Série B 2026 + parâmetros históricos
    TARGET_TITULO = 70
    TARGET_ACESSO = 67
    TARGET_MATA_EMPATE = 64
    TARGET_MATA_MATA = 61

    scenarios = [
        {
            "id": "titulo",
            "nome": "Título",
            "pos_alvo": "1º Lugar",
            "meta": TARGET_TITULO,
            "icone": "🥇",
            "cor": "#F59E0B",
            "badge": "Campeão da Série B",
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
            "regras": "Enfrentam 5º e 6º com a vantagem de igualdade na soma dos placares agregados e jogo de volta em casa.",
        },
        {
            "id": "mata_mata",
            "nome": "Mata-mata",
            "pos_alvo": "G-6 (5º e 6º)",
            "meta": TARGET_MATA_MATA,
            "icone": "🎟️",
            "cor": "#8B5CF6",
            "badge": "Vaga no Playoff",
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
                <div style="border: 1px solid rgba(226, 232, 240, 0.9); border-top: 4px solid {sc['cor']}; border-radius: 8px; padding: 12px; background: #FFFFFF; min-height: 160px; margin-bottom: 8px;">
                    <div style="font-size: 0.78rem; font-weight: 700; color: {sc['cor']}; text-transform: uppercase;">{sc['pos_alvo']}</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #1E293B; margin: 2px 0 6px 0;">{sc['icone']} {sc['nome']}</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                        <span style="font-size: 0.85rem; color: #64748B;">Meta Alvo:</span>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #0F172A;">{meta} pts</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                        <span style="font-size: 0.85rem; color: #64748B;">Faltam:</span>
                        <span style="font-size: 1.1rem; font-weight: 700; color: {'#059669' if pts_needed == 0 else '#DC2626'};">{pts_needed} pts</span>
                    </div>
                    <div style="font-size: 0.78rem; color: #475569; margin-top: 4px;">
                        Aproveitamento: <b>{req_pct}%</b> ({req_ppg:.2f} pts/j)
                    </div>
                    <div style="font-size: 0.78rem; font-weight: 700; margin-top: 4px; color: {'#059669' if '🟢' in status_txt or '✅' in status_txt else ('#D97706' if '🟡' in status_txt else '#DC2626')};">
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
            "Aprov. Exigido": f"{req_pct}% ({req_ppg:.2f} pts/j)",
            "Combinação Sugerida (10j)": combo,
            "Projeção Atual vs Meta": status_txt,
            "Regulamento": sc["regras"],
        })

    tdf = pd.DataFrame(table_data)
    st.dataframe(tdf, width="stretch", hide_index=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 3. Gráfico Plotly: Projeção do Time vs Linhas de Corte
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

    st.markdown(
        f"""
        <div style="background: #F8FAFC; border-left: 4px solid #002B7F; border-radius: 8px; padding: 14px 18px; margin-top: 8px; font-size: 0.9rem; color: #334155; line-height: 1.5;">
            📊 <b>Diagnóstico Matemático do {team_name}</b>:<br>
            • <b>Pontuação Atual</b>: <b>{pts_real} pontos</b> em {matches_played} jogos ({ppg_real:.2f} pts/j).<br>
            • <b>Projeção Final pelo Ritmo Real</b>: <b>{proj_real:.1f} pontos</b> (suficiente para <b>Top 4 / Mata-mata c/ Vantagem</b>).<br>
            • <b>Projeção Tática via Poisson xG</b>: <b>{proj_xpts:.1f} pontos</b>.<br>
            • <b>Acesso Direto (Top 2)</b>: Requer <b>{max(TARGET_ACESSO - pts_real, 0)} pontos</b> nos 10 jogos restantes (aproveitamento de <b>{round((max(TARGET_ACESSO - pts_real, 0) / matches_remaining / 3.0) * 100, 1) if matches_remaining else 0}%</b>, ex: {_calc_target_combo(max(TARGET_ACESSO - pts_real, 0), matches_remaining)}).
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TAB 2: Próximos Jogos & Raio-X Pré-Jogo
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

        # Cores destacadas para os times do confronto:
        # Time ativo sempre em dourado luminoso (#FDE047), adversário em azul celeste (#38BDF8)
        if is_home:
            home_color = "#FDE047"  # Dourado luminoso (nosso clube mandante)
            away_color = "#38BDF8"  # Azul celeste (visitante)
        else:
            home_color = "#38BDF8"  # Azul celeste (mandante)
            away_color = "#FDE047"  # Dourado luminoso (nosso clube visitante)

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

        tm = load_json(f"{team}_team_metrics.json")
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

        # Disciplina e Estilo
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
