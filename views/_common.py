import base64
import json
import os
import re
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
from config import TEAMS, get_team_config

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ASSETS_BADGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "badges"))


@st.cache_data(show_spinner=False)
def get_team_badge_b64(team_slug: str) -> Optional[str]:
    """Retorna a string base64 Data URI do escudo oficial PNG do clube."""
    if not team_slug:
        return None
    path = os.path.join(ASSETS_BADGES_DIR, f"{team_slug}.png")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded}"
        except Exception:
            return None
    return None


def get_team_badge_html(
    team_slug: str,
    size: int = 36,
    margin_right: int = 8,
    extra_style: str = "",
) -> str:
    """Retorna uma tag <img> inline com o escudo oficial do clube."""
    b64 = get_team_badge_b64(team_slug)
    if b64:
        return (
            f'<img src="{b64}" width="{size}" height="{size}" '
            f'style="object-fit: contain; vertical-align: middle; margin-right: {margin_right}px; '
            f'filter: drop-shadow(0 2px 4px rgba(0,0,0,0.18)); {extra_style}" />'
        )
    return ""


_STATE_EXPANSIONS = {
    "mg": "mineiro",
    "pr": "",
    "go": "goianiense",
    "sp": "sp",
}


@st.cache_data(show_spinner=False)
def find_team_slug_by_name(team_name: str) -> Optional[str]:
    """Tenta encontrar o slug do time no config.TEAMS a partir do nome ou apelido."""
    if not team_name:
        return None
    from name_match import normalize_name

    t = normalize_name(team_name)
    if t in TEAMS:
        return t

    for slug, info in TEAMS.items():
        if t == normalize_name(slug) or t == normalize_name(info.get("name", "")):
            return slug

    for st_abbr, exp in _STATE_EXPANSIONS.items():
        t_exp = t.replace(f"-{st_abbr}", f" {exp}").replace(f" {st_abbr}", f" {exp}").strip()
        for slug, info in TEAMS.items():
            if t_exp == normalize_name(slug) or t_exp == normalize_name(info.get("name", "")):
                return slug

    for slug, info in TEAMS.items():
        c = normalize_name(info.get("name", ""))
        s = normalize_name(slug)
        if len(t) >= 4 and (t in c or c in t or t in s or s in t):
            return slug

    return None


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


CLUB_PALETTES = {
    # Fortaleza EC
    "fortaleza": {"primary": "#002B7F", "secondary": "#E31A2C", "accent": "#F59E0B"},
    # Ceará SC
    "ceara": {"primary": "#18181B", "secondary": "#27272A", "accent": "#F59E0B"},
    # Palmeiras
    "palmeiras": {"primary": "#0F5132", "secondary": "#198754", "accent": "#86EFAC"},
    # Flamengo
    "flamengo": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#F59E0B"},
    # Corinthians
    "corinthians": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#E4E4E7"},
    # São Paulo
    "sao-paulo": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#E4E4E7"},
    # Santos
    "santos": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#D4AF37"},
    # Grêmio
    "gremio": {"primary": "#0284C7", "secondary": "#18181B", "accent": "#E4E4E7"},
    # Internacional
    "internacional": {"primary": "#DC2626", "secondary": "#991B1B", "accent": "#FFFFFF"},
    # Atlético Mineiro
    "atletico-mineiro": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#D4AF37"},
    # Cruzeiro
    "cruzeiro": {"primary": "#1D4ED8", "secondary": "#1E40AF", "accent": "#60A5FA"},
    # Botafogo
    "botafogo": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#E4E4E7"},
    # Fluminense
    "fluminense": {"primary": "#831843", "secondary": "#14532D", "accent": "#F59E0B"},
    # Vasco da Gama
    "vasco-da-gama": {"primary": "#18181B", "secondary": "#DC2626", "accent": "#E4E4E7"},
    # Bahia
    "bahia": {"primary": "#0284C7", "secondary": "#DC2626", "accent": "#F59E0B"},
    # Athletico
    "athletico": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#EF4444"},
    # Red Bull Bragantino
    "red-bull-bragantino": {"primary": "#B91C1C", "secondary": "#1E3A8A", "accent": "#F59E0B"},
    # Coritiba
    "coritiba": {"primary": "#15803D", "secondary": "#166534", "accent": "#E4E4E7"},
    # Goiás
    "goias": {"primary": "#15803D", "secondary": "#166534", "accent": "#86EFAC"},
    # Sport Recife
    "sport-recife": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#F59E0B"},
    # Vitória
    "vitoria": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#F59E0B"},
    # América Mineiro
    "america-mineiro": {"primary": "#15803D", "secondary": "#18181B", "accent": "#86EFAC"},
    # Juventude
    "juventude": {"primary": "#15803D", "secondary": "#166534", "accent": "#E4E4E7"},
    # Chapecoense
    "chapecoense": {"primary": "#15803D", "secondary": "#14532D", "accent": "#E4E4E7"},
    # Avaí
    "avai": {"primary": "#0284C7", "secondary": "#0369A1", "accent": "#E4E4E7"},
    # Criciúma
    "criciuma": {"primary": "#D97706", "secondary": "#18181B", "accent": "#FBBF24"},
    # Cuiabá
    "cuiaba": {"primary": "#15803D", "secondary": "#D97706", "accent": "#FBBF24"},
    # CRB
    "crb": {"primary": "#DC2626", "secondary": "#B91C1C", "accent": "#FFFFFF"},
    # Náutico
    "nautico": {"primary": "#DC2626", "secondary": "#991B1B", "accent": "#FFFFFF"},
    # Ponte Preta
    "ponte-preta": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#FFFFFF"},
    # Vila Nova FC
    "vila-nova-fc": {"primary": "#DC2626", "secondary": "#991B1B", "accent": "#FFFFFF"},
    # Operário-PR
    "operario-pr": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#FFFFFF"},
    # Botafogo-SP
    "botafogo-sp": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#FFFFFF"},
    # Grêmio Novorizontino
    "gremio-novorizontino": {"primary": "#D97706", "secondary": "#18181B", "accent": "#FBBF24"},
    # Mirassol
    "mirassol": {"primary": "#D97706", "secondary": "#15803D", "accent": "#FBBF24"},
    # Londrina
    "londrina": {"primary": "#0284C7", "secondary": "#0369A1", "accent": "#FFFFFF"},
    # Remo
    "remo": {"primary": "#1E3A8A", "secondary": "#172554", "accent": "#FFFFFF"},
    # Athletic Club
    "athletic-club": {"primary": "#18181B", "secondary": "#3F3F46", "accent": "#FFFFFF"},
    # São Bernardo
    "sao-bernardo": {"primary": "#D97706", "secondary": "#18181B", "accent": "#FBBF24"},
    # Atlético Goianiense
    "atletico-goianiense": {"primary": "#B91C1C", "secondary": "#18181B", "accent": "#FFFFFF"},
}


def inject_fortaleza_theme(team: Optional[str] = None):
    """Injeta a identidade visual do clube ativo."""
    active = team or get_active_team()
    pal = CLUB_PALETTES.get(active, {"primary": "#002B7F", "secondary": "#E31A2C", "accent": "#F59E0B"})
    primary = pal["primary"]
    secondary = pal["secondary"]
    accent = pal["accent"]

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

        /* ========================================================
           RESPONSIVIDADE MOBILE (@media max-width: 768px)
           ======================================================== */
        @media (max-width: 768px) {{
            /* 1. Aproveitar largura útil em smartphones (reduzir margens mortas) */
            .block-container {{
                padding-top: 1.2rem !important;
                padding-bottom: 2rem !important;
                padding-left: 0.65rem !important;
                padding-right: 0.65rem !important;
            }}

            /* 2. Tipografia fluida em smartphones */
            h1 {{
                font-size: 1.45rem !important;
                line-height: 1.2 !important;
            }}
            h2 {{
                font-size: 1.25rem !important;
                line-height: 1.25 !important;
                margin-top: 1rem !important;
            }}
            h3 {{
                font-size: 1.08rem !important;
                margin-top: 0.8rem !important;
            }}

            /* 3. Cards de Métricas compactos para evitar scroll excessivo */
            div[data-testid="stMetric"] {{
                padding: 10px 12px !important;
                margin-bottom: 8px !important;
                border-left-width: 4px !important;
            }}
            div[data-testid="stMetric"] label {{
                font-size: 0.72rem !important;
                letter-spacing: 0.2px !important;
            }}
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
                font-size: 1.35rem !important;
                line-height: 1.15 !important;
            }}

            /* 4. Abas horizontais com padding reduzido para evitar rolagem horizontal agressiva */
            button[data-baseweb="tab"] {{
                padding: 6px 10px !important;
                font-size: 0.8rem !important;
            }}

            /* 5. Cabeçalhos de seção e cards customizados */
            .fec-header-card {{
                padding: 14px 16px !important;
                border-radius: 10px !important;
            }}
            .fec-header-card h2 {{
                font-size: 1.25rem !important;
            }}
            .fec-header-card p {{
                font-size: 0.85rem !important;
            }}

            /* 6. Badges compactos */
            .fec-badge {{
                font-size: 0.7rem !important;
                padding: 2px 8px !important;
            }}

            /* 7. Reduzir espaçamento entre colunas */
            div[data-testid="stHorizontalBlock"] {{
                gap: 0.5rem !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str = "", tag: Optional[str] = None):
    """Renderiza um cabeçalho estilizado nas cores e com o escudo do clube ativo."""
    active = get_active_team()
    inject_fortaleza_theme(active)

    badge_html = get_team_badge_html(active, size=52, margin_right=16)
    display_tag = tag if tag is not None else get_active_team_name()
    tag_html = f'<span class="fec-badge">{display_tag}</span>' if display_tag else ""
    st.markdown(
        f"""
        <div class="fec-header-card" style="display: flex; align-items: center;">
            {badge_html}
            <div style="flex: 1;">
                <div>{tag_html}</div>
                <h2 style="margin: 4px 0 2px 0 !important;">{title}</h2>
                <p style="margin: 0 !important;">{subtitle}</p>
            </div>
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


def render_squad_quadrant(
    players_list: list,
    master_players: dict,
    team_name: str,
    key_prefix: str = "quad",
):
    """Renderiza a Matriz Tática de Quadrantes (xG/90 vs xA/90) de forma universal para qualquer clube."""
    import plotly.graph_objects as go

    has_squad_tracking = any(
        p.get("active") is True or m.get("in_squad") is True or m.get("active") is True
        for p in players_list
        for m in [master_players.get(p.get("name"), {})]
    )

    active_players = []
    for p in players_list:
        if p.get("position_group") == "Goleiro":
            continue
        p_name = p.get("name")
        m_info = master_players.get(p_name, {})
        if has_squad_tracking and (p.get("active") is False or m_info.get("active") is False or m_info.get("in_squad") is False):
            continue
        if (p.get("minutes") or 0) <= 0:
            continue
        active_players.append({
            **p,
            "position_detail": m_info.get("position_detail") or p.get("position_group"),
        })

    if not active_players:
        st.info(f"Sem atletas de linha com minutagem registrada no elenco de {team_name}.")
        return

    col_q1, col_q2 = st.columns([2, 1])
    with col_q1:
        pos_filter = st.radio(
            "Setor do Elenco",
            ["Meias & Atacantes (Ofensivo)", "Todo o Elenco Ativo", "Apenas Atacantes", "Apenas Meias", "Apenas Defensores"],
            horizontal=True,
            key=f"quad_pos_filter_{key_prefix}",
        )
    with col_q2:
        min_min_val = st.slider(
            "Minutagem Mínima",
            min_value=60,
            max_value=800,
            value=150,
            step=30,
            key=f"quad_min_min_{key_prefix}",
            help="Filtra atletas com pelo menos esta quantidade de minutos em campo na temporada",
        )

    if pos_filter == "Meias & Atacantes (Ofensivo)":
        filtered_q = [
            p for p in active_players
            if (p.get("minutes") or 0) >= min_min_val
            and (p.get("position_group") in ("Meia", "Atacante") or (p.get("xg_p90", 0.0) + p.get("xa_p90", 0.0)) >= 0.15)
        ]
    elif pos_filter == "Apenas Atacantes":
        filtered_q = [p for p in active_players if (p.get("minutes") or 0) >= min_min_val and p.get("position_group") == "Atacante"]
    elif pos_filter == "Apenas Meias":
        filtered_q = [p for p in active_players if (p.get("minutes") or 0) >= min_min_val and p.get("position_group") == "Meia"]
    elif pos_filter == "Apenas Defensores":
        filtered_q = [p for p in active_players if (p.get("minutes") or 0) >= min_min_val and p.get("position_group") == "Defensor"]
    else:
        filtered_q = [p for p in active_players if (p.get("minutes") or 0) >= min_min_val]

    if not filtered_q:
        st.info("Nenhum atleta encontrado com os filtros selecionados (tente reduzir a minutagem mínima ou alterar o setor).")
        return

    q_df = pd.DataFrame(filtered_q)
    q_df["xg_p90"] = q_df["xg_p90"].fillna(0.0)
    q_df["xa_p90"] = q_df["xa_p90"].fillna(0.0)
    q_df["prod_p90"] = q_df["xg_p90"] + q_df["xa_p90"]

    ref_xg = round(q_df["xg_p90"].median(), 3) if len(q_df) > 3 else 0.15
    ref_xa = round(q_df["xa_p90"].median(), 3) if len(q_df) > 3 else 0.10

    max_x = max(float(q_df["xg_p90"].max()), 0.45)
    max_y = max(float(q_df["xa_p90"].max()), 0.28)

    def _get_quadrant(row):
        if row["xg_p90"] >= ref_xg and row["xa_p90"] >= ref_xa:
            return "🔥 Ameaça Total"
        elif row["xg_p90"] < ref_xg and row["xa_p90"] >= ref_xa:
            return "🎁 Criadores Puros"
        elif row["xg_p90"] >= ref_xg and row["xa_p90"] < ref_xa:
            return "🎯 Finalizadores Puros"
        else:
            return "🛡️ Suporte & Combate"

    q_df["quadrante"] = q_df.apply(_get_quadrant, axis=1)

    text_positions = []
    pts_seen = []
    pos_cycle = ["top center", "bottom right", "top left", "bottom left", "top right", "bottom center"]

    for _, r in q_df.iterrows():
        rx, ry = r["xg_p90"], r["xa_p90"]
        close_count = sum(1 for (px, py) in pts_seen if abs(px - rx) < 0.055 and abs(py - ry) < 0.04)
        text_positions.append(pos_cycle[close_count % len(pos_cycle)])
        pts_seen.append((rx, ry))

    fig_q = go.Figure()

    # 1. Shading de fundo para os 4 quadrantes
    fig_q.add_shape(
        type="rect", x0=ref_xg, y0=ref_xa, x1=max_x * 1.15, y1=max_y * 1.25,
        fillcolor="rgba(34, 197, 94, 0.08)", line=dict(width=0), layer="below"
    )
    fig_q.add_shape(
        type="rect", x0=-0.03, y0=ref_xa, x1=ref_xg, y1=max_y * 1.25,
        fillcolor="rgba(14, 165, 233, 0.08)", line=dict(width=0), layer="below"
    )
    fig_q.add_shape(
        type="rect", x0=ref_xg, y0=-0.02, x1=max_x * 1.15, y1=ref_xa,
        fillcolor="rgba(245, 158, 11, 0.08)", line=dict(width=0), layer="below"
    )
    fig_q.add_shape(
        type="rect", x0=-0.03, y0=-0.02, x1=ref_xg, y1=ref_xa,
        fillcolor="rgba(148, 163, 184, 0.06)", line=dict(width=0), layer="below"
    )

    # 2. Linhas de corte centralizadas
    fig_q.add_vline(x=ref_xg, line=dict(color="rgba(128, 128, 128, 0.4)", dash="dash", width=1.5))
    fig_q.add_hline(y=ref_xa, line=dict(color="rgba(128, 128, 128, 0.4)", dash="dash", width=1.5))

    # 3. Dispersão de Atletas
    fig_q.add_trace(go.Scatter(
        x=q_df["xg_p90"],
        y=q_df["xa_p90"],
        mode="markers+text",
        text=q_df["name"],
        textposition=text_positions,
        textfont=dict(size=11, family="sans-serif"),
        marker=dict(
            size=[max(12, min(int(m / 75), 30)) for m in q_df["minutes"]],
            color=q_df["prod_p90"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title=dict(text="xG+xA/90", side="top"), thickness=14, len=0.75),
            line=dict(color="#0F172A", width=1.5),
            opacity=0.92,
        ),
        hovertext=[
            f"<b>{row['name']}</b> ({row['position_group']})<br>"
            f"Posição Detalhada: {row.get('position_detail', '—')}<br>"
            f"Minutagem: <b>{row['minutes']} min</b> ({row.get('matches', 0)} jogos)<br>"
            f"xG/90: <b>{row['xg_p90']:.3f}</b> (Gols: {row.get('goals', 0)})<br>"
            f"xA/90: <b>{row['xa_p90']:.3f}</b> (Assistências: {row.get('assists', 0)})<br>"
            f"Produção Direta: <b>{row['prod_p90']:.3f}/90</b><br>"
            f"Classificação: <b>{row['quadrante']}</b>"
            for _, row in q_df.iterrows()
        ],
        hoverinfo="text",
    ))

    # 4. Rótulos dos 4 quadrantes
    fig_q.add_annotation(
        x=max_x * 0.88, y=max_y * 1.12,
        text="🔥 <b>Ameaça Total</b><br><span style='font-size:10px; color:#15803D;'>Alto xG/90 + Alto xA/90</span>",
        showarrow=False, align="center", font=dict(color="#15803D", size=12),
    )
    fig_q.add_annotation(
        x=ref_xg * 0.35, y=max_y * 1.12,
        text="🎁 <b>Criadores Puros</b><br><span style='font-size:10px; color:#0284C7;'>Alto xA/90 (Criação)</span>",
        showarrow=False, align="center", font=dict(color="#0284C7", size=12),
    )
    fig_q.add_annotation(
        x=max_x * 0.88, y=0.015,
        text="🎯 <b>Finalizadores Puros</b><br><span style='font-size:10px; color:#D97706;'>Alto xG/90 (Finalização)</span>",
        showarrow=False, align="center", font=dict(color="#D97706", size=12),
    )
    fig_q.add_annotation(
        x=ref_xg * 0.35, y=0.015,
        text="🛡️ <b>Suporte & Combate</b><br><span style='font-size:10px; color:#64748B;'>Menor Produção Final</span>",
        showarrow=False, align="center", font=dict(color="#64748B", size=12),
    )

    fig_q.update_layout(
        title=f"Matriz de Produção Ofensiva — {team_name} ({len(q_df)} atletas em análise)",
        xaxis=dict(
            title="Finalização (xG por 90 minutos)",
            range=[-0.02, max_x * 1.15],
            zeroline=True,
            zerolinecolor="rgba(128,128,128,0.2)",
            gridcolor="rgba(128,128,128,0.15)",
        ),
        yaxis=dict(
            title="Criação (xA por 90 minutos)",
            range=[-0.015, max_y * 1.20],
            zeroline=True,
            zerolinecolor="rgba(128,128,128,0.2)",
            gridcolor="rgba(128,128,128,0.15)",
        ),
        height=580,
        margin=dict(l=30, r=30, t=60, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_q, width="stretch", config={"responsive": True, "displayModeBar": False})

    st.markdown("##### 📋 Classificação Detalhada por Produção Ofensiva (xG+xA / 90min)")
    table_q = q_df[[
        "name", "position_group", "minutes", "goals", "assists", "xg_p90", "xa_p90", "prod_p90", "quadrante"
    ]].rename(columns={
        "name": "Atleta",
        "position_group": "Posição",
        "minutes": "Minutos",
        "goals": "Gols",
        "assists": "Assist.",
        "xg_p90": "xG/90",
        "xa_p90": "xA/90",
        "prod_p90": "xG+xA/90",
        "quadrante": "Classificação Tática",
    }).sort_values(by="xG+xA/90", ascending=False)

    st.dataframe(
        table_q,
        width="stretch",
        hide_index=True,
        column_config={
            "xG/90": st.column_config.NumberColumn("xG/90", format="%.3f"),
            "xA/90": st.column_config.NumberColumn("xA/90", format="%.3f"),
            "xG+xA/90": st.column_config.NumberColumn("xG+xA/90", format="%.3f"),
        },
    )
