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

1. **Dashboard da Equipe** — KPIs reais vs esperados (Poisson xPts), saldo de xG, diagnóstico
   tático, médias móveis, histórico jogo a jogo; mando, bola parada, estilo; métricas brutas.
2. **Relatório de Jogo** — xG Race, diagnóstico da partida, estatísticas individuais, finalizações.
3. **Planejador de Elenco** — minutagem, dependência tática, contratos, valor de mercado.
4. **Card do Jogador** — radar de percentis, eficiência de finalização/criação, histórico.
5. **Sobre** — fontes, metodologia e contato do autor.

Troque o clube em análise (Fortaleza / Ceará) no seletor da barra lateral.

## Atualizar os dados

```bash
python main.py --team fortaleza --all      # coleta incremental + esteira analítica
python main.py --team ceara --all
python main.py --team fortaleza --build     # só recalcula a esteira offline (<5s)
python main.py --team fortaleza --analyze   # gera as sínteses textuais determinísticas
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
