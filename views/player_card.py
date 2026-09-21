import numpy as np
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

team = get_active_team()
team_name = get_active_team_name()
division_name = TEAMS.get(team, {}).get("division", "Série B")

render_page_header(
    title=f"Card do Jogador — {team_name}",
    subtitle=f"Perfil técnico detalhado, radar de percentis e histórico jogo a jogo ({division_name} 2026).",
    tag="Perfil do Atleta",
)

pmj = load_json(f"{team}_player_metrics.json")
reports = load_json(f"{team}_match_reports.json").get("reports", [])
stats_data = load_json(f"{team}_player_stats.json")
ogol_players = stats_data.get("players", []) if isinstance(stats_data, dict) else []

players = pmj.get("players", [])
if not players:
    st.warning(f"Sem métricas individuais de jogadores para o {team_name}. Rode a esteira analítica para gerar métricas.")
    st.stop()

by_name = {p["name"]: p for p in sorted(players, key=lambda x: -(x.get("minutes") or 0))}
name = st.selectbox("Selecione o Jogador do Elenco", list(by_name.keys()))
p = by_name[name]

# Dados complementares do OGol (ano todo / todas competições)
ogol_hit = next(
    (
        x
        for x in ogol_players
        if (x.get("name") or "").lower() == (p.get("name") or "").lower()
        or str(x.get("player_id")) == str(p.get("ogol_id"))
    ),
    {},
)
ogol_mins = ogol_hit.get("total_minutes")
ogol_apps = ogol_hit.get("total_appearances")
ogol_rating = ogol_hit.get("avg_rating")
ogol_goals = ogol_hit.get("total_goals")
ogol_assists = ogol_hit.get("total_assists")
ogol_conceded = ogol_hit.get("total_goals_conceded")

# Calcular nota média real a partir das partidas do SofaScore
match_ratings = [
    float(x["rating"])
    for r in reports
    for x in r.get("players_for", [])
    if (x.get("key") == p.get("key") or (x.get("name") or "").lower() == (p.get("name") or "").lower())
    and x.get("rating") is not None
]
sofascore_rating = round(sum(match_ratings) / len(match_ratings), 2) if match_ratings else None
rating_final = p.get("avg_rating") or sofascore_rating or ogol_rating

val_str = f"€ {p['market_value_eur']:,}" if p.get("market_value_eur") else "Sob consulta"
age_str = f"{p.get('age')} anos" if p.get("age") else "Idade sob consulta"
contract_str = p.get("contract_until") or "Sob consulta"

# Texto comparativo de minutagem
min_badge = f"⏱️ <b>{p.get('minutes', 0)} min</b> ({p.get('matches', 0)} jgs no {division_name})"
if ogol_mins and ogol_mins != p.get("minutes"):
    min_badge += f" &nbsp;·&nbsp; 🌍 <b>{ogol_mins} min</b> ({ogol_apps} jgs no ano total)"

st.markdown(
    f"""
    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid #002B7F; border-radius: 10px; padding: 12px 18px; margin-bottom: 20px;">
        <span class="fec-badge">{p.get('position_group') or 'Posição N/A'}</span>
        <span style="color: #1E293B; font-weight: 700; font-size: 1.1rem; margin-right: 12px;">{p.get('name')}</span>
        <span style="color: #64748B; font-size: 0.95rem;">
            🎂 <b>{age_str}</b> &nbsp;·&nbsp;
            📄 Contrato: <b>{contract_str}</b> &nbsp;·&nbsp;
            💰 Valor: <b>{val_str}</b> &nbsp;·&nbsp;
            {min_badge}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)

pos_group = (p.get("position_group") or "").lower()
is_goalkeeper = "goleiro" in pos_group

if is_goalkeeper:
    # Goleiro: Nota Média | Gols Sofridos | Jogos | Minutos
    c1.metric(
        "Nota Média",
        f"{rating_final:.2f}" if rating_final else "—",
        help=f"Nota SofaScore ({division_name}): {sofascore_rating or 'N/A'} | Nota OGol (Ano Todo): {ogol_rating or 'N/A'}",
    )
    goals_conceded = p.get("goals_conceded") or ogol_conceded or 0
    c2.metric(
        "Gols Sofridos",
        int(goals_conceded) if goals_conceded else "0",
        help=f"Gols sofridos na temporada: {ogol_conceded if ogol_conceded is not None else goals_conceded}",
    )
    c3.metric(
        "Jogos",
        int(p.get("matches") or 0),
        delta=f"{ogol_apps} jgs no ano" if ogol_apps and ogol_apps != p.get("matches") else None,
        delta_color="off",
        help=f"Jogos no {division_name}: {p.get('matches', 0)}. Jogos no ano todo: {ogol_apps or p.get('matches', 0)}.",
    )
    c4.metric(
        "Minutos",
        int(p.get("minutes") or 0),
        delta=f"{ogol_mins} min no ano" if ogol_mins and ogol_mins != p.get("minutes") else None,
        delta_color="off",
        help=f"Minutos no {division_name}: {p.get('minutes', 0)}. Minutos no ano todo: {ogol_mins or p.get('minutes', 0)}.",
    )
else:
    # Jogadores de linha: Nota Média | Gols | Assistências | Minutos
    goals = p.get("goals") if p.get("goals") is not None else int(round((p.get("goals_p90") or 0) * (p.get("minutes") or 0) / 90.0))
    assists = p.get("assists") if p.get("assists") is not None else int(round((p.get("assists_p90") or 0) * (p.get("minutes") or 0) / 90.0))
    
    c1.metric(
        "Nota Média",
        f"{rating_final:.2f}" if rating_final else "—",
        help=f"Nota SofaScore ({division_name}): {sofascore_rating or 'N/A'} | Nota OGol (Ano Todo): {ogol_rating or 'N/A'}",
    )
    c2.metric(
        "Gols",
        int(goals),
        delta=f"{ogol_goals} no ano" if ogol_goals and ogol_goals != goals else (round(p.get("xg_overperformance"), 2) if p.get("xg_overperformance") is not None else None),
        help=f"Gols no {division_name}: {goals}. Gols no ano todo (todas as competições): {ogol_goals if ogol_goals is not None else goals}. Delta xG: {p.get('xg_overperformance')}",
    )
    c3.metric(
        "Assist.",
        int(assists),
        delta=f"{ogol_assists} no ano" if ogol_assists and ogol_assists != assists else None,
        delta_color="off",
        help=f"Assistências no {division_name}: {assists}. Assistências no ano todo: {ogol_assists if ogol_assists is not None else assists}.",
    )
    c4.metric(
        "Minutos",
        int(p.get("minutes") or 0),
        delta=f"{ogol_mins} min no ano" if ogol_mins and ogol_mins != p.get("minutes") else f"{int(p.get('matches') or 0)} jogos",
        delta_color="off",
        help=f"Minutos no {division_name}: {p.get('minutes', 0)} ({p.get('matches', 0)} jogos). Minutos somando todas as competições: {ogol_mins or p.get('minutes', 0)} ({ogol_apps or p.get('matches', 0)} jogos).",
    )

st.divider()

PCTL = [
    "xg_p90",
    "xa_p90",
    "key_passes_p90",
    "progressive_carries_p90",
    "ball_recovery_p90",
    "duel_win_pct",
    "pass_accuracy",
    "touches_p90",
    "turnover_rate",
]
LBL = {
    "xg_p90": "xG/90",
    "xa_p90": "xA/90",
    "key_passes_p90": "Passes-chave/90",
    "progressive_carries_p90": "Cond. progr./90",
    "ball_recovery_p90": "Recuperações/90",
    "duel_win_pct": "% Duelos",
    "pass_accuracy": "% Passe",
    "touches_p90": "Toques/90",
    "turnover_rate": "Retenção de posse",
}

radar = pd.DataFrame(
    {
        "Métrica": [LBL[m] for m in PCTL],
        "Percentil": [p.get(f"{m}_pctl") for m in PCTL],
    }
).dropna()

st.subheader(f"📊 Perfil de Percentis vs {p.get('position_group') or 'Posição'} (no Elenco)")
if not radar.empty:
    st.bar_chart(radar.set_index("Métrica"))
else:
    st.caption("Sem percentis calculados para este atleta.")

st.divider()

# Jogo a jogo
rows = []
for r in reports:
    hit = next((x for x in r.get("players_for", []) if x.get("key") == p.get("key") or (x.get("name") or "").lower() == (p.get("name") or "").lower()), None)
    if hit:
        rows.append(
            {
                "Data": r.get("date"),
                "Adversário": r.get("opponent"),
                "Rating": hit.get("rating"),
                "Min": hit.get("minutes_played"),
                "Toques": hit.get("touches"),
                "xG": hit.get("xg"),
                "xA": hit.get("xa"),
                "Passes": hit.get("passes_total"),
                "Chave": hit.get("key_passes"),
                "Perda de bola": hit.get("possession_lost"),
                "Recuperação": hit.get("ball_recovery"),
            }
        )

if rows:
    g = pd.DataFrame(rows)
    st.subheader("📅 Desempenho Jogo a Jogo")
    if "Rating" in g.columns and g["Rating"].dropna().any():
        st.line_chart(g.set_index("Data")[["Rating"]])
    st.dataframe(g, width="stretch", hide_index=True)
else:
    st.caption("Sem participações em partidas registradas nesta temporada.")

# Perfis similares no elenco
same = [q for q in players if q.get("position_group") == p.get("position_group") and q.get("key") != p.get("key")]
if same:
    cols = [f"{m}_pctl" for m in PCTL]
    base = np.array([p.get(c) or 0 for c in cols], float)
    sims = sorted(
        same,
        key=lambda q: np.linalg.norm(np.array([q.get(c) or 0 for c in cols], float) - base),
    )[:3]
    if sims:
        st.markdown(
            f"""
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 10px 16px; margin-top: 16px;">
                💡 <b>Perfis mais similares no elenco</b>: {", ".join(q["name"] for q in sims)}
            </div>
            """,
            unsafe_allow_html=True,
        )
