import pandas as pd
import streamlit as st

from config import TEAMS
from views._common import (
    get_active_team,
    get_active_team_name,
    get_available_teams,
    get_team_badge_html,
    load_json,
    render_page_header,
    render_squad_quadrant,
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

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Planejador de Elenco — {team_name}",
    subtitle="Gestão de profundidade de elenco, matriz tática de quadrantes, minutagem e eficiência de mercado.",
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
tot_goals = int(active_df["goals"].sum()) if "goals" in active_df.columns else 0
tot_mins = int(active_df["minutes"].sum()) if "minutes" in active_df.columns else 0
total_prod = active_df["prod_total"].sum()
top3_prod = active_df.sort_values("prod_total", ascending=False).head(3)["prod_total"].sum()
top3_share = round((top3_prod / total_prod * 100), 1) if total_prod > 0 else 0.0

# 1. KPIs Gerais
c1, c2, c3, c4 = st.columns(4)
c1.metric("Atletas no Elenco", len(active_df), help="Atletas ativos ou que atuaram na temporada 2026")

if total_market_val > 0:
    c2.metric(
        "Valor Total do Elenco",
        _fmt_eur(total_market_val),
        help="Valor de mercado consolidado via Transfermarkt",
    )
else:
    c2.metric(
        "Gols Marcados",
        f"{tot_goals} gols",
        help="Total de gols marcados pelos atletas do elenco na temporada",
    )

if not pd.isna(avg_age):
    c3.metric(
        "Média de Idade",
        f"{avg_age:.1f} anos",
        help="Média de idade dos atletas com registro de nascimento",
    )
else:
    c3.metric(
        "Minutos Acumulados",
        f"{tot_mins:,} min".replace(",", "."),
        help="Total de minutos disputados pelo elenco na temporada",
    )

c4.metric(
    "Concentração Top 3 (xG+xA)",
    f"{top3_share}%",
    help="Percentual da produção ofensiva direta (xG+xA) gerada pelos 3 atletas mais produtivos.",
)

st.divider()

# Enriquecer active_df com metadados de camisa (#), idade, valor, contrato e nacionalidade (País)
squad_players = squad_data.get("players", []) if squad_data else []
master_players = master_data.get("players", []) if master_data else []

squad_lookup = {p["name"].lower(): p for p in squad_players if p.get("name")}
master_lookup = {p["name"].lower(): p for p in master_players if p.get("name")}

for col in ["jersey_number", "age", "market_value_eur", "contract_until"]:
    if col not in active_df.columns:
        active_df[col] = None
    active_df[col] = active_df.apply(
        lambda r: (
            r[col]
            if pd.notna(r.get(col)) and str(r.get(col)) not in ("None", "", "nan")
            else (
                squad_lookup.get(str(r["name"]).lower(), {}).get(col)
                or master_lookup.get(str(r["name"]).lower(), {}).get(col)
            )
        ),
        axis=1,
    )

active_df["nationality"] = active_df.apply(
    lambda r: (
        r.get("nationality")
        if pd.notna(r.get("nationality")) and str(r.get("nationality")) not in ("None", "", "nan")
        else (
            squad_lookup.get(str(r["name"]).lower(), {}).get("nationality")
            or master_lookup.get(str(r["name"]).lower(), {}).get("nationality")
            or "Brasil"
        )
    ),
    axis=1,
)

# Lookup de métricas analíticas por nome do jogador
pm_lookup = {p.get("name"): p for p in players}

tab_squad_table, tab_quadrant, tab_planner = st.tabs(
    ["📋 Plantel Geral", "🎯 Matriz de Quadrantes", "📊 Profundidade & Minutagem"]
)

# ============================================================
# TAB 1 — Tabela Geral do Plantel Oficial (Universal para os 40 Clubes)
# ============================================================
with tab_squad_table:
    st.subheader(f"👥 Plantel Oficial na Temporada — {team_name}")
    st.caption("Estatísticas oficiais de atuação pelo clube em 2026 (SofaScore) integradas com dados contratuais (Transfermarkt).")

    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        show_unplayed = st.checkbox("Mostrar atletas sem minutagem na temporada", value=True, key="sq_unplayed")
    with col_f2:
        positions_raw = sorted([p for p in active_df["position_group"].dropna().unique()])
        sel_pos_raw = st.multiselect("Filtrar Posição", positions_raw, default=positions_raw, key="sq_pos")

    filtered_df = active_df[active_df["position_group"].isin(sel_pos_raw)].copy()
    if not show_unplayed:
        filtered_df = filtered_df[filtered_df["minutes"].fillna(0) > 0]

    sort_options = {
        "Minutos": "minutes",
        "Jogos": "matches",
        "Titularidades": "starts",
        "Banco": "sub_apps",
        "Gols": "goals",
        "Assistências": "assists",
        "xG+xA/90": "prod_p90",
        "Rating médio": "avg_rating",
        "Valor de mercado": "market_value_eur",
        "Idade": "age",
    }
    sort_lbl = st.selectbox("Ordenar tabela por", list(sort_options.keys()), key="sq_sort")
    filtered_df = filtered_df.sort_values(sort_options[sort_lbl], ascending=False, na_position="last")

    display_df = filtered_df.rename(
        columns={
            "jersey_number": "#",
            "name": "Nome",
            "position_group": "Posição",
            "age": "Idade",
            "nationality": "País",
            "market_value_eur": "Valor (€)",
            "contract_until": "Contrato",
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

    # Formatação limpa de valores nulos (evita exibir o texto literal 'None')
    display_df["#"] = display_df["#"].apply(
        lambda v: f"{int(float(v))}" if pd.notna(v) and str(v).replace(".0", "").isdigit() else (str(v) if pd.notna(v) and v and str(v) != "None" else "—")
    )
    display_df["Idade"] = display_df["Idade"].apply(
        lambda v: f"{int(float(v))}" if pd.notna(v) and str(v).replace(".0", "").isdigit() else "—"
    )
    display_df["Contrato"] = display_df["Contrato"].fillna("—").replace({None: "—", "None": "—", "": "—"})
    display_df["País"] = display_df["País"].fillna("Brasil").replace({None: "Brasil", "None": "Brasil", "": "Brasil"})
    display_df["Valor (€)"] = pd.to_numeric(display_df["Valor (€)"], errors="coerce")

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "#": st.column_config.TextColumn("#", width="small", help="Número da camisa oficial"),
            "Idade": st.column_config.TextColumn("Idade", width="small", help="Idade do atleta"),
            "Valor (€)": _EUR_COL,
            "Contrato": st.column_config.TextColumn("Contrato", help="Término do contrato profissional"),
            "xG+xA/90": st.column_config.NumberColumn("xG+xA/90", format="%.3f"),
            "Rating": st.column_config.NumberColumn("Rating", format="%.2f"),
        },
    )

# ============================================================
# TAB 2 — Matriz Tática de Quadrantes do Elenco
# ============================================================
with tab_quadrant:
    st.subheader(f"🎯 Matriz Tática de Quadrantes — {team_name}")
    st.caption("Distribuição estatística dos atletas em produção ofensiva por 90 minutos (xG/90 vs xA/90) de jogadores no elenco.")
    render_squad_quadrant(
        players_list=players,
        master_players=master_lookup,
        team_name=team_name,
        key_prefix="squad_plan",
    )

# ============================================================
# TAB 3 — Profundidade & Minutagem
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
