# Fortaleza Analytics

Plataforma independente de estatística avançada de futebol — foco no **Fortaleza EC**,
com cobertura secundária do **Ceará SC**. Reúne dados de **OGol**, **SofaScore** e
**Transfermarkt** numa esteira analítica offline e um dashboard **Streamlit** para consulta
por uma equipe de jornalistas.

Sem módulo de scout de mercado e sem agente de IA — todas as análises são **regras
determinísticas sobre os números**, cada uma acompanhada da estatística que a sustenta.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rodar o dashboard

```bash
streamlit run app.py
```

Páginas:

1. **Dashboard da Equipe** — KPIs reais vs esperados (Poisson xPts), Comparativo de Turnos (1º vs 2º Turno), Campo 2D Interativo de Finalizações e Assistências (trajetórias reais e passes de gol), Matriz Tática de Quadrantes (xG/90 vs xA/90), Game State (comportamento por placar), Raio-X de finalizações e impacto das substituições.
2. **Relatório de Jogo** — xG Race, diagnóstico tático estatístico, Campo 2D do Jogo (trajetória de chutes e passes de assistência), impacto dos reservas e tabela analítica.
3. **Comparador de Clubes** — Duelo direto lado a lado entre quaisquer dois clubes das Séries A e B (campanha, ataque, defesa, bola parada, mercado, probabilidades da UFMG e destaques individuais cara a cara, com atalhos para os principais clássicos nacionais).
4. **Calendário & Inteligência de Tabela** — Classificação oficial da Série B 2026, calculadora matemática de acesso (Modelo G-6), análise aprofundada dos candidatos ao rebaixamento (Z-4 Watch, metas de permanência 45/46 pts), estatísticas e probabilidades oficiais da UFMG (mandantes, visitantes, últimas 10 rodadas), comparativo com a média histórica rodada a rodada, próximos jogos e Raio-X pré-jogo.
5. **Planejador de Elenco** — Minutagem e profundidade de elenco para todos os 40 clubes, dependência tática (concentração Top 3), contratos e eficiência de valor.
6. **Card do Jogador** — Radar de percentis por posição, eficiência de finalização/criação, notas médias e histórico jogo a jogo para qualquer atleta cadastrado.
7. **Sobre** — Fontes, metodologia e contato do autor.

Troque o clube em análise no seletor da barra lateral ou diretamente nas páginas.

## Atualizar os dados

```bash
python main.py --team fortaleza --all       # coleta incremental + esteira analítica (inclui próximos jogos)
python main.py --team ceara --all
python main.py --team fortaleza --build     # só recalcula a esteira offline (<5s)
python main.py --team fortaleza --analyze   # gera as sínteses textuais determinísticas
python main.py --team fortaleza --fixtures  # só os próximos jogos do time
python main.py --standings                  # classificação da Série B (compartilhada entre os times)
python main.py --ufmg                       # estatísticas e probabilidades da UFMG (mandante, visitante, rebaixamento, título)
python main.py --list-teams
```

No deploy (Streamlit Community Cloud), um workflow do GitHub Actions roda essa coleta
semanalmente e faz commit dos JSON em `data/`, disparando o redeploy automático.

## Arquitetura

```
scrapers/    OGol, SofaScore, Transfermarkt
resolve/     unificação de identidades de atletas e casamento de partidas
models/      camada derivada (player_metrics, team_metrics, match_reports)
analysis/    engine (regras determinísticas) + narrative (sínteses textuais)
storage/     JsonStore (data/*.json)
views/       páginas Streamlit
```

Projeto **independente**, sem vínculo oficial com os clubes citados.
