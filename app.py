import streamlit as st
from config import TEAMS
from views._common import get_active_team, get_available_teams, inject_fortaleza_theme

st.set_page_config(
    page_title="Fortaleza Analytics — Inteligência de Dados",
    page_icon="🦁",
    layout="wide",
)

available_teams = get_available_teams()
if "active_team" not in st.session_state:
    st.session_state["active_team"] = "fortaleza"

_TEAM_LABELS = {t: TEAMS.get(t, {}).get("name", t.title()) for t in available_teams}

active = get_active_team()
inject_fortaleza_theme("fortaleza")

with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 10px 0 14px 0; border-bottom: 2px solid #E2E8F0; margin-bottom: 16px;">
            <div style="font-size: 2.5rem; line-height: 1;">🦁</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: #002B7F; letter-spacing: 0.5px; margin-top: 4px;">FORTALEZA ANALYTICS</div>
            <div style="display: flex; justify-content: center; gap: 4px; margin-top: 6px;">
                <span class="fec-badge" style="font-size: 0.75rem; padding: 2px 8px;">Série B</span>
                <span class="fec-badge fec-badge-gold" style="font-size: 0.75rem; padding: 2px 8px;">Temporada 2026</span>
            </div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 8px; font-weight: 500;">
                Inteligência de Dados para Jornalistas
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if len(available_teams) > 1:
        st.selectbox(
            "Clube em análise",
            options=available_teams,
            format_func=lambda t: _TEAM_LABELS.get(t, t.title()),
            key="active_team",
        )

pages = [
    st.Page("views/team_dashboard.py", title="Dashboard da Equipe", icon="📊", default=True),
    st.Page("views/match_report.py", title="Relatório de Jogo", icon="⚽"),
    st.Page("views/derby_comparison.py", title="Clássico-Rei (Comparativo)", icon="⚔️"),
    st.Page("views/calendar.py", title="Calendário & Pré-Jogo", icon="📅"),
    st.Page("views/squad_planner.py", title="Planejador de Elenco", icon="📋"),
    st.Page("views/player_card.py", title="Card do Jogador", icon="👤"),
    st.Page("views/about.py", title="Sobre", icon="ℹ️"),
]

nav = st.navigation(pages)
nav.run()
