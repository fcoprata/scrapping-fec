import streamlit as st

from views._common import render_page_header

# ============================================================
# EDITE AQUI — seus links pessoais
# ============================================================
AUTHOR_NAME = "Francisco Prata"
LINKEDIN_URL = "https://www.linkedin.com/in/SEU-USUARIO"
INSTAGRAM_URL = "https://www.instagram.com/SEU-USUARIO"
CONTACT_EMAIL = "fcopratan@gmail.com"
# ============================================================

render_page_header(
    title="Sobre a Plataforma",
    subtitle="Inteligência de dados de futebol para consulta e produção de análises jornalísticas.",
    tag="Fortaleza Analytics",
)

st.markdown(
    f"""
### O que é

**Fortaleza Analytics** é uma plataforma independente de estatística avançada de futebol,
com foco no **Fortaleza EC** e cobertura secundária do **Ceará SC**. Reúne, por temporada:

- **xG / xGOT** (expected goals) a favor e contra, por jogo e acumulado
- **Pontos Esperados (xPts)** por modelo de Poisson vs. pontos reais
- Desempenho **mandante x visitante**, impacto de **bola parada**, timeline de xG por 15 min
- **Métricas individuais**: toques, passes, passes-chave, bola perdida/recuperada, duelos, finalizações
- **Diagnóstico tático determinístico**: forças, fraquezas e padrões, cada um com a evidência numérica
- **Planejamento de elenco**: minutagem, dependência tática, situação contratual, valor de mercado

Todas as análises são **regras determinísticas sobre os números** — sem modelos de linguagem,
sem opinião automatizada. O texto que aparece nos diagnósticos é gerado a partir de limiares
calibrados e sempre traz a estatística que o sustenta.

### Como a redação usa

Navegue pelas páginas no menu lateral, troque o **clube em análise** no seletor e consulte
tabelas e gráficos diretamente. Os números servem de base factual para reportagens, colunas
e análises pré/pós-jogo.

### Fontes de dados

- **OGol** — partidas, escalações, estatísticas de temporada
- **SofaScore** — métricas avançadas por partida (xG, xGOT, eventos)
- **Transfermarkt** — valor de mercado e situação contratual

Dados atualizados periodicamente. Projeto **independente**, sem vínculo oficial com os clubes citados.

---

### Autor

**{AUTHOR_NAME}**
"""
)

c1, c2, c3 = st.columns(3)
with c1:
    st.link_button("💼 LinkedIn", LINKEDIN_URL, use_container_width=True)
with c2:
    st.link_button("📷 Instagram", INSTAGRAM_URL, use_container_width=True)
with c3:
    st.link_button("✉️ E-mail", f"mailto:{CONTACT_EMAIL}", use_container_width=True)

st.caption(
    "Construído com Python, Streamlit, pandas e Plotly. "
    "Métricas de xG e Poisson calculadas offline a partir de dados públicos."
)
