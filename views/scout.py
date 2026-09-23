import pandas as pd
import streamlit as st

from models.league import find_player
from storage import db as _db
from views._common import get_team_badge_html, load_json, render_page_header

render_page_header(
    title="Scout — Ranking & Comparador de Jogadores",
    subtitle="Percentis calculados na liga inteira (40 clubes, Série A + B) por grupo de posição — "
              "base pra identificar jogadores acima da média sem depender só de olho clínico.",
    tag="Liga",
)


@st.cache_resource
def _bootstrap_db_once() -> bool:
    """Roda uma vez por processo do servidor: se o DuckDB existe mas está vazio
    (caso do deploy no Streamlit Community Cloud -- o arquivo vive fora do repo
    de propósito, ver storage/db.py, então cada container sobe sem ele),
    reconstrói a partir do data/*.json já commitado. Sem rede, ~15s pros 40
    clubes. `st.cache_resource` garante que só a primeira visita de cada
    container paga esse custo; visitas seguintes reusam o banco já montado."""
    from scripts.migrate_json_to_duckdb import migrate
    try:
        migrate(verbose=False)
        return True
    except Exception as e:
        st.session_state["_scout_bootstrap_error"] = f"{type(e).__name__}: {e}"
        return False


@st.cache_data(ttl=300)
def _load_league_rows():
    """Consulta o DuckDB direto (read-only) quando ele existe -- é o caso local,
    com merge de transferência e percentil calculados em SQL (storage/db.py::
    query_league_player_metrics). Se vier vazio, tenta montar o banco a partir
    do JSON commitado (`_bootstrap_db_once`, caso Cloud) antes de desistir e
    cair pro export estático (`league_player_metrics.json`) como último recurso."""
    rows = _db.query_league_player_metrics()
    if rows:
        return rows, "db"

    _bootstrap_db_once()
    rows = _db.query_league_player_metrics()
    if rows:
        return rows, "db_bootstrapped"

    return load_json("league_player_metrics.json").get("players", []), "json_export"


league_rows, _source = _load_league_rows()

if not league_rows:
    st.warning(
        "Sem dataset de liga ainda. Rode `python main.py --build` (ou `--batch-full`) pra pelo "
        "menos alguns clubes, depois `python main.py --league` pra gerar o export."
    )
    st.stop()

if _source == "db_bootstrapped":
    st.caption(
        f"🔧 Banco reconstruído agora a partir do JSON commitado (primeira carga deste servidor). "
        f"{len({r.get('team_key') for r in league_rows})} clubes · {len(league_rows)} jogadores."
    )
elif _source == "json_export":
    err = st.session_state.get("_scout_bootstrap_error")
    st.caption(
        f"⚠️ Lendo o export estático (`league_player_metrics.json`, não consegui montar o banco aqui"
        f"{f': {err}' if err else ''}) — pode estar desatualizado em relação à última coleta. "
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
_LOWER_IS_BETTER = {"turnover_rate", "fouls_p90", "poss_lost_p90"}

tab_ranking, tab_compare = st.tabs(["🏆 Ranking por Métrica", "⚖️ Comparador de Jogadores"])

# ============================================================
# TAB 1: Ranking
# ============================================================
with tab_ranking:
    st.caption(
        "Escolha a área, depois a métrica — a tabela ordena pelos melhores nessa métrica específica. "
        "As outras métricas da área ficam visíveis do lado pra dar contexto, mas não entram no ranking."
    )
    c1, c2, c3, c4 = st.columns([1, 0.9, 1.3, 0.9])
    with c1:
        division = st.selectbox("Divisão", ["Todas", "Série A", "Série B"], index=0, key="scout_division")
    with c2:
        positions = sorted({r.get("position_group") for r in league_rows if r.get("position_group")})
        position = st.selectbox("Posição", ["Todas"] + positions, index=0, key="scout_position")
    with c3:
        group = st.selectbox("Área", list(_METRIC_GROUPS.keys()), key="scout_group")
    with c4:
        min_minutes = st.number_input("Minutos mín.", min_value=0, value=270, step=90, key="scout_min_minutes")

    group_metrics = _METRIC_GROUPS[group]
    metric_key = st.selectbox(
        "Ranquear por", list(group_metrics.keys()), format_func=lambda m: group_metrics[m], key="scout_metric",
    )

    if position == "Todas":
        st.caption(
            "⚠️ Posição em \"Todas\" — a área só escolhe quais colunas aparecem, não filtra quem entra na "
            "lista. Goleiro/zagueiro com dado nessa métrica também aparece. Escolha uma posição pra comparar "
            "só entre pares."
        )

    div_filter = None if division == "Todas" else division
    pos_filter = None if position == "Todas" else position

    filtered = [
        r for r in league_rows
        if (r.get("minutes") or 0) >= min_minutes
        and (pos_filter is None or r.get("position_group") == pos_filter)
        and (div_filter is None or r.get("division") == div_filter)
        and r.get(metric_key) is not None
    ]

    if not filtered:
        st.info("Nenhum jogador encontrado com esses filtros — tente reduzir os minutos mínimos.")
    else:
        metric_label = group_metrics[metric_key]
        pctl_label = f"Percentil ({metric_label})"
        rows_out = []
        for r in filtered:
            row = {
                "Jogador": r.get("name"),
                "Clube": r.get("team_name") + (" 🔁" if r.get("transferred") else ""),
                "Divisão": r.get("division"),
                "Posição": r.get("position_group"),
                "Minutos": r.get("minutes"),
            }
            for m, label in group_metrics.items():
                v = r.get(m)
                row[label] = round(v, 2) if v is not None else None
            row[pctl_label] = r.get(f"{metric_key}_league_pctl")
            rows_out.append(row)

        ascending = metric_key in _LOWER_IS_BETTER
        df = pd.DataFrame(rows_out).sort_values(metric_label, ascending=ascending, na_position="last")

        if not df.empty:
            top_leader = df.iloc[0]
            leader_name = top_leader["Jogador"]
            leader_club = top_leader["Clube"]
            leader_val = top_leader[metric_label]
            leader_pctl = top_leader.get(pctl_label)
            pctl_str = f" · Percentil **{leader_pctl:.0f}** na posição" if pd.notna(leader_pctl) else ""
            st.markdown(
                f"""
                <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-left: 5px solid #16A34A; border-radius: 8px; padding: 10px 14px; margin: 10px 0 12px 0; font-size: 0.92rem; color: #14532D;">
                    ⭐ <b>Destaque do Ranking:</b> <b>{leader_name}</b> ({leader_club}) é o líder em <b>{metric_label}</b> com <b>{leader_val}</b>{pctl_str}.
                </div>
                """,
                unsafe_allow_html=True,
            )

        if any(r.get("transferred") for r in filtered):
            st.caption("🔁 trocou de clube na temporada — minutos e métricas somam todos os clubes; clube exibido é o atual.")
        st.caption(
            f"{len(df)} jogadores nesse filtro, ordenados por **{metric_label}**"
            f"{' (menor primeiro)' if ascending else ' (maior primeiro)'}. "
            f"\"{pctl_label}\" é a posição de cada um só nessa métrica, comparado com todos da mesma posição "
            f"na liga — 100 = melhor da posição, independe do filtro de divisão/minutos acima."
        )
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                pctl_label: st.column_config.ProgressColumn(
                    pctl_label, min_value=0, max_value=100, format="%.0f",
                ),
            },
        )

# ============================================================
# TAB 2: Comparador
# ============================================================
def _find_player_standout(player: dict) -> str:
    """Retorna uma frase descritiva com o maior diferencial ou métrica de elite do atleta."""
    best_pctl = -1
    best_label = ""
    best_val = None

    for g_name, metrics in _METRIC_GROUPS.items():
        for m, label in metrics.items():
            pctl = player.get(f"{m}_league_pctl")
            v = player.get(m)
            if pctl is not None and v is not None and pctl > best_pctl:
                best_pctl = pctl
                best_label = label
                best_val = round(v, 2)

    if best_pctl >= 80:
        return f"🏆 <b>Destaque de Elite:</b> Top {100 - best_pctl:.0f}% da liga em <b>{best_label}</b> ({best_val})"
    elif best_pctl >= 60:
        return f"⭐ <b>Ponto Forte:</b> Percentil {best_pctl:.0f} em <b>{best_label}</b> ({best_val})"
    elif best_label:
        return f"📊 <b>Maior Marca:</b> {best_label} ({best_val} · pctl {best_pctl:.0f})"
    return "📊 Sem métricas de percentil suficientes para destaque."


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

                standout_txt = _find_player_standout(player)
                st.markdown(
                    f"""
                    <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-left: 4px solid #2563EB; border-radius: 6px; padding: 7px 10px; margin: 8px 0 12px 0; font-size: 0.83rem; color: #1E40AF; line-height: 1.35;">
                        {standout_txt}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                for group_name, metrics in _METRIC_GROUPS.items():
                    with st.expander(f"📁 {group_name}", expanded=False):
                        for m, label in metrics.items():
                            v = player.get(m)
                            pctl = player.get(f"{m}_league_pctl")
                            if v is None:
                                continue
                            st.write(f"{label}: **{round(v, 2)}**" + (f" · percentil {pctl:.0f}" if pctl is not None else ""))
