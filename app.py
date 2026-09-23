import importlib
import streamlit as st
from config import TEAMS
import views._common as _common

if not hasattr(_common, "render_insight_cards"):
    importlib.reload(_common)

from views._common import (
    get_active_team,
    get_active_team_name,
    get_available_teams,
    get_team_badge_html,
    inject_fortaleza_theme,
    render_team_badge_selector,
)

st.set_page_config(
    page_title="Futebol Analytics — Inteligência de Dados",
    page_icon="⚽",
    layout="wide",
)

available_teams = get_available_teams()
_TEAM_LABELS = {t: TEAMS.get(t, {}).get("name", t.title()) for t in available_teams}

# 1. Sincronização via Query Params (ao clicar no escudo de qualquer clube)
if "team" in st.query_params:
    qp_team = st.query_params.get("team")
    if qp_team in available_teams:
        st.session_state["active_team"] = qp_team
        qp_div = TEAMS.get(qp_team, {}).get("division")
        if qp_div in ("Série A", "Série B"):
            st.session_state["filter_division"] = qp_div

if "active_team" not in st.session_state:
    st.session_state["active_team"] = "fortaleza"

active = get_active_team()
active_name = get_active_team_name()
active_div = TEAMS.get(active, {}).get("division", "Série B")

if "filter_division" not in st.session_state:
    st.session_state["filter_division"] = active_div

# Sincronização caso a divisão mude pelo rádio e o time atual não pertença a ela
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
                Inteligência de Dados
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if len(available_teams) > 1:
        st.markdown("<div style='font-weight:700; font-size:0.85rem; margin-bottom:2px;'>Divisão:</div>", unsafe_allow_html=True)
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

        # Seletor Visual por Escudo (Clickable Badges Grid)
        st.markdown(
            f"""
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; margin: 10px 0 4px 0;">
                ⚡ Selecione pelo Escudo ({div_choice}):
            </div>
            """,
            unsafe_allow_html=True,
        )

        if div_choice in ("Série A", "Série B"):
            badge_grid_html = render_team_badge_selector(filtered_teams, st.session_state.get("active_team"), cols_count=5)
            st.markdown(badge_grid_html, unsafe_allow_html=True)
        else:
            # Modo Todas: exibe os escudos de ambas as divisões
            teams_a = [t for t in available_teams if TEAMS.get(t, {}).get("division") == "Série A"]
            teams_a.sort(key=lambda t: _TEAM_LABELS.get(t, t.title()))
            st.markdown("<div style='font-size:0.75rem; font-weight:700; color:#64748B; margin-top:4px;'>Série A (20 Clubes)</div>", unsafe_allow_html=True)
            st.markdown(render_team_badge_selector(teams_a, st.session_state.get("active_team"), cols_count=5), unsafe_allow_html=True)

            teams_b = [t for t in available_teams if TEAMS.get(t, {}).get("division") == "Série B"]
            teams_b.sort(key=lambda t: _TEAM_LABELS.get(t, t.title()))
            st.markdown("<div style='font-size:0.75rem; font-weight:700; color:#64748B; margin-top:6px;'>Série B (20 Clubes)</div>", unsafe_allow_html=True)
            st.markdown(render_team_badge_selector(teams_b, st.session_state.get("active_team"), cols_count=5), unsafe_allow_html=True)


pages = [
    st.Page("views/team_dashboard.py", title="Dashboard da Equipe", icon="📊", default=True),
    st.Page("views/match_report.py", title="Relatório de Jogo", icon="⚽"),
    st.Page("views/derby_comparison.py", title="Comparador de Clubes", icon="⚔️"),
    st.Page("views/calendar.py", title="Calendário & Pré-Jogo", icon="📅"),
    st.Page("views/squad_planner.py", title="Planejador de Elenco", icon="📋"),
    st.Page("views/player_card.py", title="Card do Jogador", icon="👤"),
    st.Page("views/scout.py", title="Scout — Ranking de Jogadores", icon="🔎"),
    st.Page("views/about.py", title="Sobre", icon="ℹ️"),
]

nav = st.navigation(pages)
nav.run()
