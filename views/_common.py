import json
import os
import re
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
from config import TEAMS, get_team_config

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_available_teams() -> List[str]:
    """Retorna a lista de times que possuem dados derivados processados na pasta data/."""
    available = []
    if os.path.exists(DATA_DIR):
        for fname in os.listdir(DATA_DIR):
            if fname.endswith("_team_metrics.json"):
                t = fname.replace("_team_metrics.json", "")
                available.append(t)
    if not available:
        available = ["fortaleza"]
    return sorted(available)


def get_active_team() -> str:
    """Retorna o slug do time ativo na sessão (padrão: fortaleza)."""
    t = st.session_state.get("active_team", "fortaleza")
    return t if t in get_available_teams() else "fortaleza"


def get_active_team_name() -> str:
    """Retorna o nome oficial de exibição do clube ativo."""
    t = get_active_team()
    return TEAMS.get(t, {}).get("name", t.title())


# Compatibilidade legada
TEAM = "fortaleza"


def load_json(name: str) -> dict:
    """Carrega arquivo JSON direto pelo nome do arquivo."""
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_team_json(suffix: str, team: Optional[str] = None) -> dict:
    """Carrega JSON de um time específico (ex: suffix='player_metrics.json')."""
    t = team or get_active_team()
    fname = f"{t}_{suffix}" if not suffix.startswith(f"{t}_") else suffix
    return load_json(fname)


def inject_fortaleza_theme(team: Optional[str] = None):
    """Injeta a identidade visual do clube ativo."""
    active = team or get_active_team()
    
    # Cores dinâmicas por clube
    if active == "fortaleza":
        primary = "#002B7F"
        secondary = "#E31A2C"
        accent = "#F59E0B"
    elif active in ("ceara", "santos", "corinthians", "botafogo", "atletico-mg", "vasco"):
        primary = "#1E293B"
        secondary = "#0F172A"
        accent = "#64748B"
    elif active in ("bahia", "gremio"):
        primary = "#0284C7"
        secondary = "#DC2626"
        accent = "#0284C7"
    elif active in ("palmeiras", "goias", "coritiba", "juventude", "chapecoense"):
        primary = "#15803D"
        secondary = "#166534"
        accent = "#86EFAC"
    elif active in ("flamengo", "sport", "athletico-pr", "vitoria", "vila-nova"):
        primary = "#DC2626"
        secondary = "#991B1B"
        accent = "#F59E0B"
    else:
        primary = "#002B7F"
        secondary = "#E31A2C"
        accent = "#F59E0B"

    st.markdown(
        f"""
        <style>
        /* ========================================================
           IDENTIDADE VISUAL DINÂMICA — {active.upper()}
           ======================================================== */

        /* Top ribbon */
        header[data-testid="stHeader"] {{
            border-bottom: 4px solid transparent;
            border-image: linear-gradient(to right, {primary} 0%, {primary} 45%, {accent} 45%, {accent} 55%, {secondary} 55%, {secondary} 100%) 1;
            background-color: #FFFFFF !important;
        }}

        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background-color: #F8FAFC !important;
            border-right: 1px solid #E2E8F0;
        }}

        /* Tipografia de Cabeçalhos */
        h1 {{
            color: {primary} !important;
            font-weight: 800 !important;
            letter-spacing: -0.5px;
            padding-bottom: 4px;
        }}

        h2, h3 {{
            color: {primary} !important;
            font-weight: 700 !important;
            margin-top: 1.2rem !important;
        }}

        /* Cards de Métricas (st.metric) */
        div[data-testid="stMetric"] {{
            background: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-left: 5px solid {primary} !important;
            border-radius: 12px !important;
            padding: 16px 18px !important;
            box-shadow: 0 4px 12px rgba(0, 43, 127, 0.05) !important;
            transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }}

        div[data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0, 43, 127, 0.1) !important;
            border-left-color: {secondary} !important;
        }}

        div[data-testid="stMetric"] label {{
            font-size: 0.82rem !important;
            font-weight: 700 !important;
            color: #475569 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
            font-size: 1.85rem !important;
            font-weight: 800 !important;
            color: {primary} !important;
        }}

        /* Abas (st.tabs) */
        button[data-baseweb="tab"] {{
            font-weight: 600 !important;
            color: #64748B !important;
            padding: 10px 20px !important;
            border-radius: 6px 6px 0 0 !important;
        }}

        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {primary} !important;
            border-bottom: 3px solid {primary} !important;
            font-weight: 700 !important;
        }}

        button[data-baseweb="tab"]:hover {{
            color: {secondary} !important;
        }}

        /* Botões */
        .stButton > button {{
            background-color: {primary} !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 8px 18px !important;
            transition: all 0.2s ease;
        }}

        .stButton > button:hover {{
            background-color: {secondary} !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 12px rgba(227, 26, 44, 0.25) !important;
        }}

        /* Tag / Badge estilizado */
        .fec-badge {{
            display: inline-block;
            background: linear-gradient(135deg, {primary} 0%, #0A1E4A 100%);
            color: #FFFFFF;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            box-shadow: 0 2px 6px rgba(0, 43, 127, 0.2);
            margin-right: 6px;
        }}

        .fec-badge-red {{
            background: linear-gradient(135deg, {secondary} 0%, #B71C1C 100%);
            box-shadow: 0 2px 6px rgba(227, 26, 44, 0.25);
        }}

        .fec-badge-gold {{
            background: linear-gradient(135deg, {accent} 0%, #D97706 100%);
            color: #1E293B;
            box-shadow: 0 2px 6px rgba(245, 158, 11, 0.25);
        }}

        /* Card customizado para cabeçalho de seção */
        .fec-header-card {{
            background: linear-gradient(135deg, {primary} 0%, #0A1E4A 100%);
            border-radius: 12px;
            padding: 20px 24px;
            color: #FFFFFF;
            margin-bottom: 20px;
            border-left: 6px solid {secondary};
            box-shadow: 0 6px 18px rgba(0, 43, 127, 0.15);
        }}

        .fec-header-card h2 {{
            color: #FFFFFF !important;
            margin: 0 !important;
            font-size: 1.6rem !important;
        }}

        .fec-header-card p {{
            color: #E2E8F0 !important;
            margin: 4px 0 0 0 !important;
            font-size: 0.95rem;
        }}

        /* Cards de Análise Tática */
        .tactical-card {{
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .tactical-strength {{
            background: #F0FDF4;
            border: 1px solid #BBF7D0;
            border-left: 5px solid #16A34A;
        }}
        .tactical-weakness {{
            background: #FEF2F2;
            border: 1px solid #FECACA;
            border-left: 5px solid #DC2626;
        }}
        .tactical-note {{
            background: #EFF6FF;
            border: 1px solid #BFDBFE;
            border-left: 5px solid #2563EB;
        }}
        .tactical-title {{
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 4px;
        }}
        .tactical-evidence {{
            font-size: 0.85rem;
            color: #475569;
            font-weight: 500;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str = "", tag: str = "Tricolor do Pici"):
    """Renderiza um cabeçalho estilizado nas cores do clube ativo."""
    inject_fortaleza_theme()
    tag_html = f'<span class="fec-badge">{tag}</span>' if tag else ""
    st.markdown(
        f"""
        <div class="fec-header-card">
            <div>{tag_html}</div>
            <h2 style="margin-top: 8px !important;">{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_analysis_section(analysis: dict, title: str = "Diagnóstico Tático"):
    """Renderiza o diagnóstico tático determinístico: síntese, forças, fraquezas e notas."""
    if not analysis:
        return

    st.subheader(f"🧠 {title}")

    strengths = analysis.get("strengths", [])
    weaknesses = analysis.get("weaknesses", [])
    notes = analysis.get("notes", [])
    narrative = analysis.get("narrative")

    if narrative:
        with st.container(border=True):
            st.markdown(narrative)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 Pontos Fortes / Destaques**")
        if strengths:
            for s in strengths:
                clean_text = s["text"].rstrip(".")
                ev_html = f"<div class='tactical-evidence'>📊 {s['evidence']}</div>" if s.get("evidence") else ""
                st.markdown(
                    f"""
                    <div class="tactical-card tactical-strength">
                        <div class="tactical-title" style="color: #14532D;">✓ {clean_text}</div>
                        {ev_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sem pontos fortes críticos registrados.")

    with c2:
        st.markdown("**🔴 Pontos Fracos / Vulnerabilidades**")
        if weaknesses:
            for w in weaknesses:
                clean_text = w["text"].rstrip(".")
                ev_html = f"<div class='tactical-evidence'>⚠️ {w['evidence']}</div>" if w.get("evidence") else ""
                st.markdown(
                    f"""
                    <div class="tactical-card tactical-weakness">
                        <div class="tactical-title" style="color: #7F1D1D;">⚠️ {clean_text}</div>
                        {ev_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Nenhuma vulnerabilidade crítica registrada.")

    if notes:
        st.markdown("**💡 Alertas & Observações Táticas**")
        cols = st.columns(min(len(notes), 3)) if len(notes) > 1 else [st.container()]
        for i, n in enumerate(notes):
            col_target = cols[i % len(cols)] if isinstance(cols, list) else cols
            clean_text = n["text"].rstrip(".")
            ev_html = f"<div class='tactical-evidence'>ℹ️ {n['evidence']}</div>" if n.get("evidence") else ""
            with col_target:
                st.markdown(
                    f"""
                    <div class="tactical-card tactical-note">
                        <div class="tactical-title" style="color: #1E3A8A;">{clean_text}</div>
                        {ev_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
