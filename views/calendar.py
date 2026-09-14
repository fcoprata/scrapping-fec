import pandas as pd
import streamlit as st

from config import TEAMS
from views._common import load_json, render_page_header

render_page_header(
    title="Calendário & Classificação",
    subtitle="Próximos jogos de Fortaleza e Ceará, e a tabela da Série B 2026.",
    tag="Série B 2026",
)

FIXTURE_COLS = {
    "date": "Data",
    "round": "Rodada",
    "home_team": "Mandante",
    "away_team": "Visitante",
    "competition": "Competição",
}


def _fixtures_df(team: str) -> pd.DataFrame:
    data = load_json(f"{team}_fixtures.json")
    rows = data.get("fixtures", []) if isinstance(data, dict) else []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    cols = [c for c in FIXTURE_COLS if c in df.columns]
    return df[cols].rename(columns=FIXTURE_COLS)


st.subheader("📅 Próximos Jogos")
col_for, col_cea = st.columns(2)

for col, team_key in ((col_for, "fortaleza"), (col_cea, "ceara")):
    with col:
        team_name = TEAMS.get(team_key, {}).get("name", team_key.title())
        st.markdown(f"**{team_name}**")
        df = _fixtures_df(team_key)
        if df.empty:
            st.caption("Sem jogos futuros cadastrados.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)

st.divider()

st.subheader("🏆 Classificação — Série B 2026")
standings_data = load_json("standings_serie_b_2026.json")
rows = standings_data.get("standings", []) if isinstance(standings_data, dict) else []
if not rows:
    st.caption("Classificação ainda não coletada.")
else:
    sdf = pd.DataFrame(rows)
    highlight_ids = {
        TEAMS.get("fortaleza", {}).get("sofascore", {}).get("team_id"),
        TEAMS.get("ceara", {}).get("sofascore", {}).get("team_id"),
    }

    display_cols = {
        "position": "Pos",
        "team_name": "Time",
        "played": "J",
        "wins": "V",
        "draws": "E",
        "losses": "D",
        "goals_for": "GP",
        "goals_against": "GC",
        "goal_diff": "SG",
        "points": "Pts",
    }
    cols = [c for c in display_cols if c in sdf.columns]
    view_df = sdf[cols].rename(columns=display_cols)

    def _highlight_row(row):
        team_id = sdf.loc[row.name, "team_id"] if "team_id" in sdf.columns else None
        color = "background-color: rgba(0, 43, 127, 0.12);" if team_id in highlight_ids else ""
        return [color] * len(row)

    st.dataframe(
        view_df.style.apply(_highlight_row, axis=1),
        width="stretch",
        hide_index=True,
    )
