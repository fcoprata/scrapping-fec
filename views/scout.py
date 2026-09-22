import pandas as pd
import streamlit as st

from models.league import find_player, top_by_metric
from views._common import get_team_badge_html, load_json, render_page_header

render_page_header(
    title="Scout — Ranking & Comparador de Jogadores",
    subtitle="Percentis calculados na liga inteira (40 clubes, Série A + B) por grupo de posição — "
              "base pra identificar jogadores acima da média sem depender só de olho clínico.",
    tag="Liga",
)

league_data = load_json("league_player_metrics.json")
league_rows = league_data.get("players", [])

if not league_rows:
    st.warning(
        "Sem dataset de liga ainda. Rode `python main.py --league` depois de coletar os clubes "
        "(`--batch-full`)."
    )
    st.stop()

st.caption(
    f"Dataset gerado em {league_data.get('generated_at', '—')} · "
    f"{league_data.get('teams_covered', 0)} clubes cobertos · {len(league_rows)} jogadores."
)

_METRIC_LABELS = {
    "xg_p90": "xG / 90min",
    "xa_p90": "xA / 90min",
    "key_passes_p90": "Passes-chave / 90min",
    "progressive_carries_p90": "Conduções progressivas / 90min",
    "ball_recovery_p90": "Recuperações / 90min",
    "duel_win_pct": "% Duelos ganhos",
    "pass_accuracy": "Precisão de passe",
    "touches_p90": "Toques / 90min",
    "turnover_rate": "Taxa de perda de posse (menor = melhor)",
}

tab_ranking, tab_compare = st.tabs(["🏆 Ranking por Métrica", "⚖️ Comparador de Jogadores"])

# ============================================================
# TAB 1: Ranking
# ============================================================
with tab_ranking:
    c1, c2, c3, c4 = st.columns([1.2, 1, 1.4, 1])
    with c1:
        division = st.selectbox("Divisão", ["Todas", "Série A", "Série B"], index=0, key="scout_division")
    with c2:
        positions = sorted({r.get("position_group") for r in league_rows if r.get("position_group")})
        position = st.selectbox("Posição", ["Todas"] + positions, index=0, key="scout_position")
    with c3:
        metric = st.selectbox(
            "Métrica", list(_METRIC_LABELS.keys()), format_func=lambda k: _METRIC_LABELS[k], key="scout_metric"
        )
    with c4:
        min_minutes = st.number_input("Minutos mín.", min_value=0, value=270, step=90, key="scout_min_minutes")

    div_filter = None if division == "Todas" else division
    pos_filter = None if position == "Todas" else position

    ranked = top_by_metric(
        league_rows, metric, position_group=pos_filter, division=div_filter,
        min_minutes=min_minutes, n=50,
    )

    if not ranked:
        st.info("Nenhum jogador encontrado com esses filtros — tente reduzir os minutos mínimos.")
    else:
        pctl_col = f"{metric}_league_pctl"
        df = pd.DataFrame([
            {
                "Jogador": r.get("name"),
                "Clube": r.get("team_name"),
                "Divisão": r.get("division"),
                "Posição": r.get("position_group"),
                "Minutos": r.get("minutes"),
                _METRIC_LABELS[metric]: round(r.get(metric, 0.0), 2) if r.get(metric) is not None else None,
                "Percentil (liga)": r.get(pctl_col),
            }
            for r in ranked
        ])
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Percentil (liga)": st.column_config.ProgressColumn(
                    "Percentil (liga)", min_value=0, max_value=100, format="%.0f",
                ),
            },
        )

# ============================================================
# TAB 2: Comparador
# ============================================================
with tab_compare:
    st.caption("Busque até 3 jogadores pelo nome pra comparar lado a lado.")
    query = st.text_input("Buscar jogador", key="scout_search")

    hits = find_player(league_rows, query) if query else []
    hit_labels = [f"{h['name']} ({h.get('team_name')}, {h.get('position_group')})" for h in hits[:30]]
    label_to_row = dict(zip(hit_labels, hits[:30]))

    selected_labels = st.multiselect(
        "Selecione até 3 jogadores", hit_labels, max_selections=3, key="scout_compare_select",
    )
    selected = [label_to_row[label] for label in selected_labels]

    if not selected:
        st.info("Digite um nome acima e selecione os jogadores pra comparar.")
    else:
        cols = st.columns(len(selected))
        for col, player in zip(cols, selected):
            with col:
                team_key = player.get("team_key")
                if team_key:
                    st.markdown(get_team_badge_html(team_key, size=40), unsafe_allow_html=True)
                st.markdown(f"**{player.get('name')}**")
                st.caption(f"{player.get('team_name')} · {player.get('position_group')} · {player.get('division')}")
                st.metric("Minutos", player.get("minutes") or 0)
                for m, label in _METRIC_LABELS.items():
                    v = player.get(m)
                    pctl = player.get(f"{m}_league_pctl")
                    if v is None:
                        continue
                    st.write(f"{label}: **{round(v, 2)}**" + (f" · percentil {pctl:.0f}" if pctl is not None else ""))
