import numpy as np
import pandas as pd
import streamlit as st

from views._common import (
    get_active_team,
    get_active_team_name,
    load_json,
    render_page_header,
)

team = get_active_team()
team_name = get_active_team_name()

render_page_header(
    title=f"Card do Jogador — {team_name}",
    subtitle="Perfil técnico detalhado, radar de percentis por posição e histórico jogo a jogo.",
    tag="Perfil do Atleta",
)

pmj = load_json(f"{team}_player_metrics.json")
reports = load_json(f"{team}_match_reports.json").get("reports", [])
players = pmj.get("players", [])
if not players:
    st.warning(f"Sem métricas individuais de jogadores para {team_name}. Rode: `python main.py --team {team} --build`")
    st.stop()

by_name = {p["name"]: p for p in sorted(players, key=lambda x: -(x.get("minutes") or 0))}
name = st.selectbox("Selecione o Jogador do Elenco", list(by_name.keys()))
p = by_name[name]

val_str = f"€ {p['market_value_eur']:,}" if p.get("market_value_eur") else "N/A"
st.markdown(
    f"""
    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid #002B7F; border-radius: 10px; padding: 12px 18px; margin-bottom: 20px;">
        <span class="fec-badge">{p.get('position_group') or 'Posição N/A'}</span>
        <span style="color: #1E293B; font-weight: 700; font-size: 1.1rem; margin-right: 12px;">{p.get('name')}</span>
        <span style="color: #64748B; font-size: 0.95rem;">
            🎂 <b>{p.get('age') or '?'} anos</b> &nbsp;·&nbsp;
            📄 Contrato: <b>{p.get('contract_until') or '?'}</b> &nbsp;·&nbsp;
            💰 Valor: <b>{val_str}</b> &nbsp;·&nbsp;
            ⏱️ <b>{p.get('minutes', 0)} min</b> ({p.get('matches', 0)} jogos)
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
goals_calc = int(round((p.get("goals_p90") or 0) * p.get("minutes", 0) / 90.0)) if p.get("minutes") else 0
c1.metric(
    "Gols",
    goals_calc,
    delta=p.get("xg_overperformance"),
    help="delta = gols − xG na temporada (over/underperformance)",
)
c2.metric("xA/90", p.get("xa_p90") if p.get("xa_p90") is not None else "-")
c3.metric("Passes-chave/90", p.get("key_passes_p90") if p.get("key_passes_p90") is not None else "-")
c4.metric(
    "Taxa de Perda de Posse",
    f"{p.get('turnover_rate')}%" if p.get("turnover_rate") is not None else "-",
    help="% de posses perdidas por toques na bola",
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
    st.caption("Sem percentis calculados para este jogador.")

st.divider()

# Jogo a jogo
rows = []
for r in reports:
    hit = next((x for x in r.get("players_for", []) if x.get("key") == p["key"]), None)
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

# Perfis similares
same = [q for q in players if q.get("position_group") == p.get("position_group") and q["key"] != p["key"]]
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
