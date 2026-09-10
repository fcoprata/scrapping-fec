import pandas as pd
import streamlit as st

from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_analysis_section,
    render_page_header,
)

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Dashboard da Equipe — {team_name}",
    subtitle="Análise global de desempenho, pontos esperados (Poisson), forma recente e inteligência tática.",
    tag=team_name,
)

tm = load_json(f"{team}_team_metrics.json")
analysis_data = load_json(f"{team}_analysis.json")
adv_season_data = load_json(f"{team}_advanced_season.json")

s = tm.get("summary", {}) if tm else {}
matches_count = s.get("matches", 0)

if matches_count == 0:
    # Exibir Visão de Elenco & Métricas Financeiras
    pm_raw = load_json(f"{team}_player_metrics.json")
    players = pm_raw.get("players", []) if isinstance(pm_raw, dict) else (pm_raw or [])
    if not players:
        pm_master = load_json(f"{team}_players_master.json")
        players = pm_master.get("players", []) if isinstance(pm_master, dict) else []

    if players:
        p_df = pd.DataFrame(players)
        total_val = p_df["market_value_eur"].sum() if "market_value_eur" in p_df.columns else 0
        avg_age = p_df["age"].mean() if "age" in p_df.columns and not p_df["age"].dropna().empty else 0
        exp_count = p_df["contract_until"].astype(str).str.contains("2025|2026", na=False).sum() if "contract_until" in p_df.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Valor Total do Elenco", f"€ {total_val / 1_000_000:.1f} mi".replace(".", ",") if total_val > 0 else "—")
        with c2:
            st.metric("Idade Média", f"{avg_age:.1f} anos" if avg_age > 0 else "—")
        with c3:
            st.metric("Plantel Profissional", f"{len(p_df)} atletas")
        with c4:
            st.metric("Fim de Contrato (25/26)", f"{exp_count}")

        st.divider()

        st.info(
            f"ℹ️ **Elenco e valores de mercado carregados com sucesso para {team_name}.**\n\n"
            f"Para baixar e analisar as partidas detalhadas com xG e Poisson, execute: `python main.py --team {team} --advanced`"
        )
        st.stop()
    else:
        st.warning(f"Sem dados coletados para {team_name}. Execute: `python main.py --team {team} --squad --build`")
        st.stop()

def sv(key, default=0.0):
    """team_metrics summary value, tolerante a None (tier OGol deixa campos de xG nulos)."""
    v = s.get(key)
    return default if v is None else v


_has_xg = s.get("points_expected") is not None

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Pontos Reais",
    sv("points_real"),
    delta=round(sv("points_luck"), 1) if _has_xg else None,
    help="delta = Sorte / Overperformance (pontos reais − pontos esperados)",
)
c2.metric(
    "Pontos Esperados (xPts)",
    f"{sv('points_expected'):.1f}" if _has_xg else "—",
    help=f"Modelo Poisson sobre as {sv('matches', 0)} partidas da temporada.",
)
c3.metric(
    "Saldo de xG (ΔxG)",
    f"{sv('xg_diff'):+.2f}" if _has_xg else "—",
    help="xG a favor − xG contra",
)
c4.metric(
    "Finalização / Defesa",
    f"{sv('finishing'):+.2f} / {sv('keeping'):+.2f}" if _has_xg else "—",
    help="Gols marcados − xG pró (ataque) / xG contra − gols sofridos (defesa)",
)

st.markdown(
    f"""
    <div style="background: #F1F5F9; border-radius: 8px; padding: 10px 16px; margin: 12px 0 20px 0; font-size: 0.95rem; color: #1E293B;">
        🦁 <b>Campanha Oficial</b>: <b>{sv('wins', 0)} Vitórias</b> &nbsp;·&nbsp;
        <b>{sv('draws', 0)} Empates</b> &nbsp;·&nbsp;
        <b>{sv('losses', 0)} Derrotas</b> &nbsp;|&nbsp;
        xG Acumulado: <b style="color:#002B7F;">{sv('xg_for_total'):.2f} Pró</b> vs
        <b style="color:#E31A2C;">{sv('xg_against_total'):.2f} Contra</b>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_tactics, tab_raw_stats = st.tabs([
    "📈 Desempenho & Diagnóstico",
    "🏟️ Mando, Bola Parada & Estilo",
    "📊 Métricas Brutas SofaScore",
])

with tab_overview:
    # Diagnóstico tático da temporada
    if analysis_data.get("season"):
        render_analysis_section(analysis_data["season"], title="Diagnóstico Tático da Temporada")
        st.divider()

    pm = pd.DataFrame(tm.get("per_match", []))
    if not pm.empty:
        pm["rotulo"] = pm["date"].astype(str) + " (" + pm["opponent"].fillna("?").astype(str) + ")"
        st.subheader("📈 Evolução da Forma (Média Móvel - 5 Jogos)")
        tab_xg_roll, tab_pts_roll = st.tabs(["Média Móvel de xG (Pró x Contra)", "Média Móvel de Pontos"])
        with tab_xg_roll:
            chart_df = pm.rename(
                columns={
                    "xg_for_roll5": "xG Pró (MM 5j)",
                    "xg_against_roll5": "xG Contra (MM 5j)",
                }
            )
            st.line_chart(chart_df.set_index("rotulo")[["xG Pró (MM 5j)", "xG Contra (MM 5j)"]], width="stretch")
        with tab_pts_roll:
            chart_pts = pm.rename(columns={"points_roll5": "Pontos (MM 5j)"})
            st.line_chart(chart_pts.set_index("rotulo")[["Pontos (MM 5j)"]], width="stretch")

        st.subheader("📋 Histórico Jogo a Jogo")
        st.dataframe(
            pm[
                [
                    "date",
                    "opponent",
                    "is_home",
                    "score",
                    "points",
                    "xg_for",
                    "xg_against",
                    "xg_diff",
                    "xpoints",
                    "p_win",
                    "p_draw",
                    "p_loss",
                ]
            ].rename(
                columns={
                    "date": "Data",
                    "opponent": "Adversário",
                    "is_home": "Mando",
                    "score": "Placar",
                    "points": "Pts",
                    "xg_for": "xG Pró",
                    "xg_against": "xG Contra",
                    "xg_diff": "ΔxG",
                    "xpoints": "xPts",
                    "p_win": "P(Vitória)",
                    "p_draw": "P(Empate)",
                    "p_loss": "P(Derrota)",
                }
            ),
            width="stretch",
            hide_index=True,
        )

with tab_tactics:
    st.subheader("🏟️ Desempenho: Mandante vs Visitante")
    ha = tm.get("home_away", {})
    if ha:
        ha_df = pd.DataFrame(
            {
                "Casa": {
                    "Jogos": ha.get("home", {}).get("matches"),
                    "Média xG Pró": ha.get("home", {}).get("xg_for"),
                    "Média xG Contra": ha.get("home", {}).get("xg_against"),
                    "Aproveitamento (PPG)": ha.get("home", {}).get("ppg"),
                },
                "Fora": {
                    "Jogos": ha.get("away", {}).get("matches"),
                    "Média xG Pró": ha.get("away", {}).get("xg_for"),
                    "Média xG Contra": ha.get("away", {}).get("xg_against"),
                    "Aproveitamento (PPG)": ha.get("away", {}).get("ppg"),
                },
            }
        ).T
        st.dataframe(ha_df, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ xG por Faixa de 15 Minutos")
        tl = pd.DataFrame(
            {
                "xG a Favor": tm.get("timeline", {}).get("for", {}),
                "xG Contra": tm.get("timeline", {}).get("against", {}),
            }
        )
        st.bar_chart(tl, width="stretch")

    with col2:
        st.subheader("🎯 Impacto de Bolas Paradas")
        sp = tm.get("set_pieces", {})
        st.metric(
            "% do xG a Favor via Bola Parada",
            f"{sp.get('xg_for_setpiece_pct')}%" if sp.get("xg_for_setpiece_pct") is not None else "N/A",
        )
        st.metric(
            "% do xG Contra via Bola Parada",
            f"{sp.get('xg_against_setpiece_pct')}%" if sp.get("xg_against_setpiece_pct") is not None else "N/A",
        )

    st.divider()
    st.subheader("⚽ Detalhamento por Situação de Jogo")

    def _sit_df(d, tag):
        rows = [
            {
                "Situação": k,
                f"xG {tag}": v.get("xg_sum"),
                f"Finalizações {tag}": v.get("count"),
                f"Gols {tag}": v.get("goals"),
            }
            for k, v in d.items()
        ]
        return pd.DataFrame(rows).set_index("Situação")

    sf = _sit_df(tm.get("shot_situations", {}).get("for", {}), "Pró")
    sa = _sit_df(tm.get("shot_situations", {}).get("against", {}), "Contra")
    sit_joined = sf.join(sa, how="outer")
    st.dataframe(sit_joined, width="stretch")

    discipline = tm.get("discipline", {})
    style = tm.get("style", {})

    st.subheader("🎽 Estilo de Jogo & Disciplina")
    sc1, sc2, sc3 = st.columns(3)
    avg_poss = style.get("avg_possession")
    sc1.metric("Posse média", f"{avg_poss:.1f}%" if avg_poss is not None else "—")
    label = style.get("label")
    sc2.metric(
        "Perfil",
        {"direto": "Direto", "apoio": "Apoio/Posse"}.get(label, "—"),
        help="xG por ponto de posse: alto ⇒ jogo mais direto/vertical.",
    )
    avg_fouls = discipline.get("avg_fouls")
    avg_fouls_ag = discipline.get("avg_fouls_against")
    sc3.metric(
        "Faltas cometidas / jogo",
        f"{avg_fouls:.1f}" if avg_fouls is not None else "s/ dado",
        delta=f"{avg_fouls - avg_fouls_ag:+.1f} vs adversário" if (avg_fouls is not None and avg_fouls_ag is not None) else None,
        delta_color="inverse",
    )

with tab_raw_stats:
    st.subheader("📊 Métricas Avançadas Individuais (SofaScore)")
    adv_players = adv_season_data.get("players", [])
    if adv_players:
        adf = pd.DataFrame(adv_players)
        metric_groups = {
            "Volume": ["matches", "minutes", "touches", "touches_per90"],
            "Finalização / xG": ["xg", "xg_per90", "goals", "shots", "xa", "assists"],
            "Passe": [
                "passes",
                "passes_accurate",
                "pass_accuracy",
                "key_passes",
                "long_balls",
                "long_balls_accurate",
                "crosses",
                "crosses_accurate",
            ],
            "Posse / Progressão": [
                "possession_lost",
                "ball_recovery",
                "ball_carries",
                "progressive_carries",
            ],
            "Duelos / Defesa": [
                "duels_won",
                "duels_lost",
                "aerials_won",
                "interceptions",
                "clearances",
                "fouls",
            ],
        }

        labels = {
            "matches": "Jogos",
            "minutes": "Min",
            "touches": "Toques",
            "touches_per90": "Toques/90",
            "xg": "xG",
            "xg_per90": "xG/90",
            "goals": "Gols",
            "shots": "Finaliz.",
            "xa": "xA",
            "assists": "Assist.",
            "passes": "Passes",
            "passes_accurate": "Passes certos",
            "pass_accuracy": "% Passe",
            "key_passes": "Passes-chave",
            "long_balls": "Lançam.",
            "long_balls_accurate": "Lançam. certos",
            "crosses": "Cruzam.",
            "crosses_accurate": "Cruzam. certos",
            "possession_lost": "Bola perdida",
            "ball_recovery": "Bola recuperada",
            "ball_carries": "Conduções",
            "progressive_carries": "Cond. progr.",
            "duels_won": "Duelos ganhos",
            "duels_lost": "Duelos perdidos",
            "aerials_won": "Aéreos ganhos",
            "interceptions": "Intercept.",
            "clearances": "Cortes",
            "fouls": "Faltas",
        }

        group = st.radio("Selecione o Grupo de Métricas", list(metric_groups.keys()), horizontal=True, key="raw_metric_grp")
        cols = ["name"] + [c for c in metric_groups[group] if c in adf.columns]
        sort_col = st.selectbox(
            "Ordenar tabela por", metric_groups[group], format_func=lambda c: labels.get(c, c), key="raw_sort_col"
        )
        table = adf[cols].sort_values(sort_col, ascending=False, na_position="last")
        table = table.rename(columns={**labels, "name": "Nome"})
        st.dataframe(table, width="stretch", hide_index=True)
    else:
        st.info("Sem métricas brutas do SofaScore disponíveis.")
