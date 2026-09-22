import pandas as pd
import streamlit as st

from models.league import find_player, top_by_metric
from storage import db as _db
from views._common import get_team_badge_html, load_json, render_page_header

render_page_header(
    title="Scout — Ranking & Comparador de Jogadores",
    subtitle="Percentis calculados na liga inteira (40 clubes, Série A + B) por grupo de posição — "
              "base pra identificar jogadores acima da média sem depender só de olho clínico.",
    tag="Liga",
)


@st.cache_data(ttl=300)
def _load_league_rows():
    """Consulta o DuckDB direto (read-only) quando ele existe -- é o caso local,
    com merge de transferência e percentil calculados em SQL (storage/db.py::
    query_league_player_metrics). O banco vive fora do repo (~/.local/share,
    de propósito -- ver storage/db.py) então não existe no deploy do Streamlit
    Community Cloud, que só tem o que está no git: cai pro export JSON
    committado (`data/league_player_metrics.json`, atualizado via `--league`)
    nesse caso, em vez de mostrar a tela vazia."""
    rows = _db.query_league_player_metrics()
    if rows:
        return rows, "db"
    return load_json("league_player_metrics.json").get("players", []), "json_export"


league_rows, _source = _load_league_rows()

if not league_rows:
    st.warning(
        "Sem dataset de liga ainda. Rode `python main.py --build` (ou `--batch-full`) pra pelo "
        "menos alguns clubes, depois `python main.py --league` pra gerar o export."
    )
    st.stop()

if _source == "json_export":
    st.caption(
        f"⚠️ Lendo o export estático (`league_player_metrics.json`, sem banco local disponível aqui) — "
        f"pode estar desatualizado em relação à última coleta. "
        f"{len({r.get('team_key') for r in league_rows})} clubes · {len(league_rows)} jogadores."
    )
else:
    st.caption(f"{len({r.get('team_key') for r in league_rows})} clubes cobertos · {len(league_rows)} jogadores.")

# Agrupado por área do jogo — evita um dropdown único de 19 itens e ajuda a
# escolher a métrica certa pra cada posição (zagueiro não se compara por xG).
_METRIC_GROUPS = {
    "Ataque": {
        "xg_p90": "xG / 90min",
        "shots_p90": "Finalizações / 90min",
        "xa_p90": "xA / 90min",
        "key_passes_p90": "Passes-chave / 90min",
    },
    "Passe & Progressão": {
        "pass_accuracy": "% Passes certos",
        "accurate_passes_p90": "Passes certos / 90min",
        "touches_p90": "Toques / 90min",
        "progressive_carries_p90": "Conduções progressivas / 90min",
        "long_balls_p90": "Bolas longas / 90min",
        "crosses_p90": "Cruzamentos / 90min",
    },
    "Defesa & Duelos": {
        "ball_recovery_p90": "Recuperações de bola / 90min",
        "interceptions_p90": "Interceptações / 90min",
        "clearances_p90": "Cortes / 90min",
        "duel_win_pct": "% Duelos ganhos",
        "duels_won_p90": "Duelos ganhos / 90min",
        "aerials_won_p90": "Duelos aéreos ganhos / 90min",
    },
    "Disciplina & Posse": {
        "turnover_rate": "Taxa de perda de posse (menor = melhor)",
        "poss_lost_p90": "Perdas de posse / 90min (menor = melhor)",
        "fouls_p90": "Faltas cometidas / 90min (menor = melhor)",
    },
}
_METRIC_LABELS = {k: v for group in _METRIC_GROUPS.values() for k, v in group.items()}

tab_ranking, tab_compare = st.tabs(["🏆 Ranking por Métrica", "⚖️ Comparador de Jogadores"])

# ============================================================
# TAB 1: Ranking
# ============================================================
with tab_ranking:
    c1, c2, c3, c4, c5 = st.columns([1, 0.9, 1.1, 1.3, 0.8])
    with c1:
        division = st.selectbox("Divisão", ["Todas", "Série A", "Série B"], index=0, key="scout_division")
    with c2:
        positions = sorted({r.get("position_group") for r in league_rows if r.get("position_group")})
        position = st.selectbox("Posição", ["Todas"] + positions, index=0, key="scout_position")
    with c3:
        group = st.selectbox("Área", list(_METRIC_GROUPS.keys()), key="scout_group")
    with c4:
        group_metrics = _METRIC_GROUPS[group]
        metric = st.selectbox(
            "Métrica", list(group_metrics.keys()), format_func=lambda k: group_metrics[k], key="scout_metric"
        )
    with c5:
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
                "Clube": r.get("team_name") + (" 🔁" if r.get("transferred") else ""),
                "Divisão": r.get("division"),
                "Posição": r.get("position_group"),
                "Minutos": r.get("minutes"),
                _METRIC_LABELS[metric]: round(r.get(metric, 0.0), 2) if r.get(metric) is not None else None,
                "Percentil (liga)": r.get(pctl_col),
            }
            for r in ranked
        ])
        if any(r.get("transferred") for r in ranked):
            st.caption("🔁 trocou de clube na temporada — minutos e métricas somam todos os clubes; clube exibido é o atual.")
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
                if player.get("transferred"):
                    st.caption(f"🔁 trocou de clube — passou por: {', '.join(player.get('prior_clubs', []))}")
                st.metric("Minutos (temporada)", player.get("minutes") or 0)
                for group_name, metrics in _METRIC_GROUPS.items():
                    st.markdown(f"**{group_name}**")
                    for m, label in metrics.items():
                        v = player.get(m)
                        pctl = player.get(f"{m}_league_pctl")
                        if v is None:
                            continue
                        st.write(f"{label}: **{round(v, 2)}**" + (f" · percentil {pctl:.0f}" if pctl is not None else ""))
