import pandas as pd
import streamlit as st

from config import TEAMS
from views._common import (
    get_active_team,
    get_active_team_name,
    get_available_teams,
    load_json,
    render_page_header,
)


def _fmt_eur(v) -> str:
    """Compact euro string: 1.8M / 900K / — ."""
    if v is None or pd.isna(v) or v == 0:
        return "—"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"€ {v / 1_000_000:.1f} mi".replace(".", ",")
    if abs(v) >= 1_000:
        return f"€ {v / 1_000:.0f} mil"
    return f"€ {v:.0f}"


_EUR_COL = st.column_config.NumberColumn("Valor (€)", format="compact")
_PCT_COL = st.column_config.NumberColumn("% Titular", format="percent", help="Titularidades ÷ jogos do time.")

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
        key="squad_team_select",
    )
    if selected_team != st.session_state.get("active_team"):
        st.session_state["active_team"] = selected_team
        st.rerun()

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Planejador de Elenco — {team_name}",
    subtitle="Gestão de profundidade de elenco, distribuição de minutagem, alertas de contrato e eficiência de valor.",
    tag=team_name,
)

pm_data = load_json(f"{team}_player_metrics.json")
master_data = load_json(f"{team}_players_master.json")
mm_data = load_json(f"{team}_matches_master.json")
squad_data = load_json(f"{team}_squad.json")
stats_data = load_json(f"{team}_player_stats.json")

team_games = len(mm_data.get("matches", [])) or 24
players = pm_data.get("players", [])

if not players:
    st.warning(f"Sem dados analíticos de elenco para o {team_name}. Rode a esteira analítica para gerar métricas.")
    st.stop()

df = pd.DataFrame(players)

# Fallback inteligente para elenco ativo
# Se houver jogadores explicitamente marcados como 'active' = True, usa eles.
# Se todos forem False/None (clubes sem squad do Transfermarkt), considera quem jogou na temporada (minutos > 0 ou jogos > 0).
has_active_flag = df["active"].fillna(False).any() if "active" in df.columns else False
if has_active_flag:
    active_df = df[df["active"].fillna(True)].copy()
else:
    active_df = df[(df["minutes"].fillna(0) > 0) | (df["matches"].fillna(0) > 0)].copy()
    if active_df.empty:
        active_df = df.copy()

# Cálculo de produção ofensiva
active_df["prod_p90"] = (active_df["xg_p90"].fillna(0) + active_df["xa_p90"].fillna(0)).round(3)
active_df["prod_total"] = ((active_df["prod_p90"] * active_df["minutes"].fillna(0)) / 90.0).round(2)

total_market_val = active_df["market_value_eur"].dropna().sum() if "market_value_eur" in active_df.columns else 0
avg_age = active_df["age"].dropna().mean() if "age" in active_df.columns and not active_df["age"].dropna().empty else float("nan")
total_prod = active_df["prod_total"].sum()
top3_prod = active_df.sort_values("prod_total", ascending=False).head(3)["prod_total"].sum()
top3_share = round((top3_prod / total_prod * 100), 1) if total_prod > 0 else 0.0

# 1. KPIs Gerais
c1, c2, c3, c4 = st.columns(4)
c1.metric("Atletas no Elenco / Utilizados", len(active_df))
c2.metric(
    "Valor Total do Elenco",
    _fmt_eur(total_market_val) if total_market_val > 0 else "Sob consulta",
    help="Valor de mercado consolidado via Transfermarkt (se disponível)",
)
c3.metric(
    "Média de Idade",
    f"{avg_age:.1f} anos" if not pd.isna(avg_age) else "—",
    help="Média de idade dos atletas com registro de nascimento",
)
c4.metric(
    "Concentração Top 3 (xG+xA)",
    f"{top3_share}%",
    help="Percentual da produção ofensiva direta (xG+xA) gerada pelos 3 atletas mais produtivos.",
)

st.divider()

# Lookup de métricas analíticas por nome do jogador
pm_lookup = {p.get("name"): p for p in players}

tab_squad_table, tab_planner = st.tabs(
    ["📋 Plantel Geral", "📊 Profundidade & Minutagem"]
)

# ============================================================
# TAB 1 — Tabela Geral do Plantel
# ============================================================
with tab_squad_table:
    st.subheader(f"👥 Plantel Completo — {team_name}")
    squad = squad_data.get("players", [])
    player_stats = stats_data.get("players", [])

    if squad:
        # Cenário A: Clube possui dados do OGol/Transfermarkt (Fortaleza / Ceará)
        squad_df = pd.DataFrame(squad)
        stats_by_id = {s["player_id"]: s for s in player_stats}

        stats_cols = [
            "total_appearances",
            "total_minutes",
            "total_goals",
            "total_goals_conceded",
            "total_assists",
            "starts",
            "substitute_appearances",
            "avg_rating",
        ]
        stats_df = (
            pd.DataFrame(player_stats)[["player_id"] + stats_cols]
            if player_stats
            else pd.DataFrame(columns=["player_id"] + stats_cols)
        )

        squad_df["player_id"] = squad_df["player_id"].astype(str)
        stats_df["player_id"] = stats_df["player_id"].astype(str)
        df_merged = squad_df.merge(stats_df, on="player_id", how="left")

        for col in stats_cols:
            if col not in df_merged.columns:
                df_merged[col] = None

        def _xgxa(name):
            p = pm_lookup.get(name)
            if not p:
                return None
            xg = float(p.get("xg_p90") or 0)
            xa = float(p.get("xa_p90") or 0)
            return round(xg + xa, 3) if (xg + xa) > 0 else None

        df_merged["xg_xa_p90"] = df_merged["name"].map(_xgxa)

        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            show_inactive = st.checkbox("Mostrar inativos / transferidos", value=False, key="sq_inactive")
        with col_f2:
            positions_raw = sorted([p for p in df_merged["position"].dropna().unique()])
            sel_pos_raw = st.multiselect("Filtrar Posição", positions_raw, default=positions_raw, key="sq_pos")

        filtered_raw = df_merged[df_merged["position"].isin(sel_pos_raw)]
        if not show_inactive:
            filtered_raw = filtered_raw[filtered_raw["active"]]

        sort_options = {
            "Minutos": "total_minutes",
            "Jogos": "total_appearances",
            "Gols": "total_goals",
            "Assistências": "total_assists",
            "Rating médio": "avg_rating",
            "xG+xA/90": "xg_xa_p90",
            "Idade": "age",
            "Valor de mercado": "market_value_eur",
        }
        sort_lbl = st.selectbox("Ordenar tabela por", list(sort_options.keys()), key="sq_sort")
        filtered_raw = filtered_raw.sort_values(sort_options[sort_lbl], ascending=False, na_position="last")

        display_raw = filtered_raw.rename(
            columns={
                "jersey_number": "#",
                "name": "Nome",
                "position": "Posição",
                "age": "Idade",
                "nationality": "País",
                "market_value_eur": "Valor (€)",
                "contract_until": "Contrato",
                "total_appearances": "Jogos",
                "total_minutes": "Minutos",
                "total_goals": "Gols",
                "total_goals_conceded": "Gols sofr.",
                "total_assists": "Assist.",
                "starts": "Titular",
                "substitute_appearances": "Banco",
                "avg_rating": "Rating",
                "xg_xa_p90": "xG+xA/90",
            }
        )[[
            "#",
            "Nome",
            "Posição",
            "Idade",
            "País",
            "Valor (€)",
            "Contrato",
            "Jogos",
            "Titular",
            "Banco",
            "Minutos",
            "Gols",
            "Assist.",
            "xG+xA/90",
            "Rating",
        ]]

        st.dataframe(
            display_raw,
            width="stretch",
            hide_index=True,
            column_config={
                "Valor (€)": _EUR_COL,
                "xG+xA/90": st.column_config.NumberColumn("xG+xA/90", format="%.3f"),
                "Rating": st.column_config.NumberColumn("Rating", format="%.2f"),
            },
        )

        st.divider()
        st.subheader("🏆 Detalhe por Campeonato")
        names = filtered_raw["name"].tolist()
        if names:
            selected_name = st.selectbox("Selecione o Atleta", names, key="sq_detail_player")
            row = filtered_raw[filtered_raw["name"] == selected_name].iloc[0]
            detail = stats_by_id.get(row["player_id"])
            if detail and detail.get("competitions"):
                comp_df = pd.DataFrame(detail["competitions"]).rename(
                    columns={
                        "competition": "Competição",
                        "appearances": "Jogos",
                        "minutes": "Minutos",
                        "goals": "Gols",
                        "goals_conceded": "Gols sofridos",
                        "assists": "Assist.",
                    }
                )
                if detail.get("position") != "Goleiro":
                    comp_df = comp_df.drop(columns=["Gols sofridos"], errors="ignore")
                st.dataframe(comp_df, width="stretch", hide_index=True)
            else:
                st.caption("Sem estatísticas detalhadas de competições para este atleta.")
    else:
        # Cenário B: Fallback universal a partir de player_metrics (demais 38 clubes)
        fallback_df = active_df.copy()
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            st.caption(f"Exibindo {len(fallback_df)} atletas utilizados na temporada por {team_name} (SofaScore).")
        with col_f2:
            positions_raw = sorted([p for p in fallback_df["position_group"].dropna().unique()])
            sel_pos_raw = st.multiselect(
                "Filtrar Posição",
                positions_raw,
                default=positions_raw,
                key="sq_fallback_pos",
            )

        filtered_fallback = fallback_df[fallback_df["position_group"].isin(sel_pos_raw)]

        sort_options = {
            "Minutos": "minutes",
            "Jogos": "matches",
            "Titularidades": "starts",
            "Gols": "goals",
            "Assistências": "assists",
            "Rating médio": "avg_rating",
            "xG+xA/90": "prod_p90",
        }
        sort_lbl = st.selectbox("Ordenar tabela por", list(sort_options.keys()), key="sq_fallback_sort")
        filtered_fallback = filtered_fallback.sort_values(sort_options[sort_lbl], ascending=False, na_position="last")

        display_fallback = filtered_fallback.rename(
            columns={
                "name": "Nome",
                "position_group": "Posição",
                "matches": "Jogos",
                "starts": "Titular",
                "sub_apps": "Banco",
                "minutes": "Minutos",
                "goals": "Gols",
                "assists": "Assist.",
                "prod_p90": "xG+xA/90",
                "avg_rating": "Rating",
            }
        )[[
            "Nome",
            "Posição",
            "Jogos",
            "Titular",
            "Banco",
            "Minutos",
            "Gols",
            "Assist.",
            "xG+xA/90",
            "Rating",
        ]]

        st.dataframe(
            display_fallback,
            width="stretch",
            hide_index=True,
            column_config={
                "xG+xA/90": st.column_config.NumberColumn("xG+xA/90", format="%.3f"),
                "Rating": st.column_config.NumberColumn("Rating", format="%.2f"),
            },
        )

# ============================================================
# TAB 2 — Profundidade & Minutagem
# ============================================================
with tab_planner:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📋 Depth Chart por Posição")
        pos_list = sorted([p for p in active_df["position_group"].dropna().unique()])
        selected_pos = st.selectbox("Filtrar Posição", ["Todas"] + pos_list)

        display_subset = (
            active_df if selected_pos == "Todas"
            else active_df[active_df["position_group"] == selected_pos]
        ).copy()
        display_subset["titular_txt"] = (
            display_subset["starts"].astype("Int64").astype(str) + f"/{team_games}"
        )
        depth_table = (
            display_subset.sort_values(["position_group", "minutes"], ascending=[True, False])
            .rename(
                columns={
                    "name": "Nome",
                    "position_group": "Posição",
                    "age": "Idade",
                    "minutes": "Minutos",
                    "titular_txt": "Titular",
                    "starts_share": "% Titular",
                    "contract_until": "Contrato até",
                    "market_value_eur": "Valor (€)",
                    "prod_p90": "xG+xA/90",
                }
            )[["Nome", "Posição", "Idade", "Minutos", "Titular", "% Titular", "xG+xA/90", "Contrato até", "Valor (€)"]]
        )
        st.dataframe(
            depth_table,
            width="stretch",
            hide_index=True,
            column_config={"% Titular": _PCT_COL, "Valor (€)": _EUR_COL},
        )

    with col_right:
        st.subheader("⏱️ Minutos por Posição")
        min_by_pos = (
            active_df.groupby("position_group")["minutes"]
            .sum()
            .reset_index()
            .rename(columns={"position_group": "Posição", "minutes": "Total Minutos"})
        )
        st.bar_chart(min_by_pos.set_index("Posição"), color="#002B7F", width="stretch")

    st.divider()

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.subheader("⚠️ Alertas de Vencimento de Contrato")
        has_contracts = (
            "contract_until" in active_df.columns
            and active_df["contract_until"].dropna().any()
        )
        if has_contracts:
            expiring = active_df[
                active_df["contract_until"].str.contains("2025|2026", na=False)
            ].sort_values("contract_until")
            if not expiring.empty:
                exp_table = expiring[
                    ["name", "position_group", "age", "minutes", "contract_until", "market_value_eur"]
                ].rename(
                    columns={
                        "name": "Atleta",
                        "position_group": "Posição",
                        "age": "Idade",
                        "minutes": "Minutos",
                        "contract_until": "Vencimento",
                        "market_value_eur": "Valor (€)",
                    }
                )
                st.dataframe(
                    exp_table,
                    width="stretch",
                    hide_index=True,
                    column_config={"Valor (€)": _EUR_COL},
                )
            else:
                st.info("Nenhum contrato com vencimento próximo identificado.")
        else:
            st.info(f"Dados contratuais sob consulta para o {team_name}.")

    with col_c2:
        st.subheader("💰 Eficiência de Mercado (Valor vs Produção)")
        has_market = (
            "market_value_eur" in active_df.columns
            and active_df["market_value_eur"].dropna().sum() > 0
        )
        if has_market:
            scatter_df = active_df[active_df["minutes"] >= 180].dropna(
                subset=["market_value_eur", "prod_total"]
            )
            if not scatter_df.empty:
                st.scatter_chart(
                    scatter_df,
                    x="market_value_eur",
                    y="prod_total",
                    color="position_group",
                    size="minutes",
                    width="stretch",
                )
                st.caption("Eixo X: Valor de Mercado (€) | Eixo Y: Produção Total (xG + xA acumulado)")
            else:
                st.caption("Dados insuficientes para o gráfico de dispersão.")
        else:
            st.info(f"Valores de mercado detalhados sob consulta para o {team_name}.")
