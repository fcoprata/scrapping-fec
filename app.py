import streamlit as st
from config import TEAMS
from views._common import (
    get_active_team,
    get_active_team_name,
    get_available_teams,
    get_team_badge_html,
    inject_fortaleza_theme,
)

st.set_page_config(
    page_title="Futebol Analytics — Inteligência de Dados",
    page_icon="⚽",
    layout="wide",
)

available_teams = get_available_teams()
if "active_team" not in st.session_state:
    st.session_state["active_team"] = "fortaleza"

_TEAM_LABELS = {t: TEAMS.get(t, {}).get("name", t.title()) for t in available_teams}

if "filter_division" in st.session_state:
    div_sel = st.session_state["filter_division"]
    if div_sel in ("Série A", "Série B"):
        if TEAMS.get(st.session_state.get("active_team"), {}).get("division") != div_sel:
            matches = [t for t in available_teams if TEAMS.get(t, {}).get("division") == div_sel]
            matches.sort(key=lambda t: _TEAM_LABELS.get(t, t.title()))
            if matches:
                st.session_state["active_team"] = matches[0]

active = get_active_team()
active_name = get_active_team_name()
active_div = TEAMS.get(active, {}).get("division", "Série B")
inject_fortaleza_theme(active)

with st.sidebar:
    badge_hero = get_team_badge_html(active, size=64, margin_right=0, extra_style="margin-bottom: 6px;")
    st.markdown(
        f"""
        <div style="text-align: center; padding: 10px 0 14px 0; border-bottom: 2px solid #E2E8F0; margin-bottom: 16px;">
            <div style="display: flex; justify-content: center; align-items: center; min-height: 68px;">
                {badge_hero if badge_hero else '<div style="font-size: 2.5rem;">⚽</div>'}
            </div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #1E293B; letter-spacing: 0.5px; margin-top: 4px;">{active_name.upper()}</div>
            <div style="display: flex; justify-content: center; gap: 4px; margin-top: 6px;">
                <span class="fec-badge" style="font-size: 0.75rem; padding: 2px 8px;">{active_div}</span>
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
        st.markdown("**Divisão:**")
        if "filter_division" not in st.session_state:
            st.session_state["filter_division"] = active_div

        div_choice = st.radio(
            "Filtrar por Divisão",
            options=["Série A", "Série B", "Todas"],
            horizontal=True,
            label_visibility="collapsed",
            key="filter_division",
        )

        if div_choice == "Série A":
            filtered_teams = [t for t in available_teams if TEAMS.get(t, {}).get("division") == "Série A"]
        elif div_choice == "Série B":
            filtered_teams = [t for t in available_teams if TEAMS.get(t, {}).get("division") == "Série B"]
        else:
            filtered_teams = list(available_teams)

        filtered_teams.sort(key=lambda t: _TEAM_LABELS.get(t, t.title()))

        if st.session_state.get("active_team") not in filtered_teams:
            st.session_state["active_team"] = filtered_teams[0]

        st.selectbox(
            "Clube em análise",
            options=filtered_teams,
            format_func=lambda t: _TEAM_LABELS.get(t, t.title()),
            key="active_team",
        )

    # Galeria Visual dos 40 Clubes
    with st.expander("🛡️ Galeria dos 40 Clubes (Séries A & B)", expanded=False):
        for div_title, div_key in [("Série A (20 Clubes)", "Série A"), ("Série B (20 Clubes)", "Série B")]:
            st.markdown(f"<div style='font-size:0.8rem; font-weight:700; margin:6px 0 4px 0;'>{div_title}</div>", unsafe_allow_html=True)
            t_list = [t for t in available_teams if TEAMS.get(t, {}).get("division") == div_key]
            t_list.sort(key=lambda t: _TEAM_LABELS.get(t, t.title()))
            cols = st.columns(5)
            for i, t_slug in enumerate(t_list):
                with cols[i % 5]:
                    b_html = get_team_badge_html(t_slug, size=28, margin_right=0)
                    st.markdown(f"<div style='text-align:center; padding:3px 0;' title='{_TEAM_LABELS.get(t_slug)}'>{b_html}</div>", unsafe_allow_html=True)

pages = [
    st.Page("views/team_dashboard.py", title="Dashboard da Equipe", icon="📊", default=True),
    st.Page("views/match_report.py", title="Relatório de Jogo", icon="⚽"),
    st.Page("views/derby_comparison.py", title="Comparador de Clubes", icon="⚔️"),
    st.Page("views/calendar.py", title="Calendário & Pré-Jogo", icon="📅"),
    st.Page("views/squad_planner.py", title="Planejador de Elenco", icon="📋"),
    st.Page("views/player_card.py", title="Card do Jogador", icon="👤"),
    st.Page("views/about.py", title="Sobre", icon="ℹ️"),
]

nav = st.navigation(pages)
nav.run()
