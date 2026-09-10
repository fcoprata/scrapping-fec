# Plano 01 — Esteira Analítica (Fortaleza EC) [CONCLUÍDO]

Status: **CONCLUÍDO** (Todas as Fases 0 a 6 implementadas e validadas)

Objetivo: transformar os JSON crus de 3 fontes (ogol, transfermarkt, sofascore) numa
esteira de 5 estágios que entrega **camada de resolução** (ids unificados), **camada
derivada** (métricas /90, percentis, over/under-performance, forma móvel, pontos
esperados) e **camada de serviço** (Streamlit multipage), com **refresh incremental**
por um único comando.

Estágio 1 (Ingest) já existe. Este plano cobre estágios 2→5.

```
1. Ingest     scrapers → data/<team>_*.json                         [PRONTO]
2. Resolve    data/<team>_players_master.json + _matches_master.json  (Fase 1)
3. Derive     data/<team>_player_metrics.json                         (Fase 2)
              data/<team>_team_metrics.json                           (Fase 3)
              data/<team>_match_reports.json                          (Fase 3)
4. Serve      app.py multipage (4 páginas)                            (Fase 4)
5. Refresh    python main.py --team <t> --all  (incremental)          (Fase 5)
6. Verificação final                                                  (Fase 6)
```

Cada fase é auto-contida: pode rodar em contexto novo lendo só este arquivo + os
arquivos citados por `path:linha`.

---

## Fase 0 — Discovery / APIs permitidas (LER ANTES DE TUDO)

Não há doc externo. As "APIs permitidas" são padrões **já presentes no repo** +
libs padrão. Confirme cada item abrindo o arquivo citado antes de codar.

### 0.1 Padrões do repo a COPIAR (não reinventar)

| Padrão | Onde copiar | Uso |
|---|---|---|
| Dataclass de modelo | `models/player_match_stats.py:1-40` | novos modelos das camadas derivadas |
| `@property` derivada em dataclass | `models/player_stats.py:60-70` (`pass_accuracy`, `touches_per90`, `xg_per90`) | métricas calculadas |
| Persistência JSON envelope `{season_year, <lista>}` | `storage/json_store.py:31-50` (`save_squad`, `save_player_stats`) | `save_*` das novas camadas |
| `save_*` + `load_*` com `_DATA_DIR` e `os.path.abspath` | `storage/json_store.py:12`, `:67-96` | idem |
| Serializar dataclass com `dataclasses.asdict` | `storage/json_store.py:3`, `:22` | idem |
| Expor `@property` no dict salvo | `storage/json_store.py` `_advanced_row_dict` (bloco adicionado nesta sessão, ~`:99-105`) | achatar helpers pro JSON |
| Normalização de nome (NFKD + lower + strip) | `name_match.py:1-8` (`normalize_name`) | join entre fontes |
| Fuzzy match nome (exato → substring) | `main.py:120-133` (loop `tm_by_name` em `_fetch_squad`) | join players_master |
| Sub-comando CLI = flag `action="store_true"` + função `_fetch_*(team, ...)` + early return | `main.py:20-21`, `:36-42`, `:196-232` (`_fetch_advanced`) | novos sub-comandos `--build`, `--all` |
| Agregação soma jogo→temporada por dict acumulador | `models/aggregate.py:44-66` (`aggregate_player_season`) | recomputar métricas derivadas |
| Leitura defensiva de JSON no dashboard | `app.py:9-15` (`load_json` devolve `{}` se não existe) | páginas novas |
| Merge de DataFrames por `player_id` string | `app.py:37-40` (`.astype(str)` antes de `.merge`) | páginas novas |
| Tabela renomeada + subset de colunas + `hide_index=True` | `app.py:82-108` | páginas novas |

### 0.2 Libs permitidas (versões do `.venv` REAL — diferem do `requirements.txt`)

Rodar `python -c "import streamlit, pandas, numpy; print(streamlit.__version__, pandas.__version__)"`
antes de codar. Nesta sessão: **streamlit 1.62.0, pandas 3.0.5**. `numpy` vem com pandas.

APIs permitidas:
- `pandas`: `DataFrame`, `merge`, `groupby().agg()`, `rank(pct=True)`, `rolling(window).mean()`,
  `concat`, `to_dict("records")`, `pivot_table`. NÃO usar `df.append` (removido no pandas 2+).
- `numpy`: `np.clip`, `np.where`, aritmética vetorizada. Sem SciPy.
- `streamlit` (1.62): **multipage via `st.navigation` + `st.Page`** (NÃO criar pasta `pages/`
  automágica — usar navegação declarativa). `st.dataframe`, `st.metric`, `st.columns`,
  `st.tabs`, `st.radio(..., horizontal=True)`, `st.selectbox(..., format_func=...)`,
  `st.bar_chart`, `st.line_chart`, `st.scatter_chart`, `st.area_chart`, `st.altair_chart`.
  `st.set_page_config` só UMA vez, no entrypoint.
- Gráficos: preferir `st.line_chart` / `st.scatter_chart` / `st.bar_chart` nativos.
  Só usar `st.altair_chart` (altair vem com streamlit) se precisar de encoding custom
  (ex.: shotmap por coordenada, cor por situação). NÃO adicionar matplotlib/plotly.

### 0.3 Anti-padrões (NÃO fazer)

- ❌ `df.append(...)` — não existe no pandas 3. Usar `pd.concat`.
- ❌ Criar `pages/` para multipage — usar `st.navigation([st.Page(...)])`.
- ❌ Chamar `st.set_page_config` em página não-entrypoint.
- ❌ Re-scrapar dentro da camada derivada. Camada 3 só LÊ `data/*.json`, nunca faz rede.
- ❌ Inventar endpoint SofaScore novo. Se faltar dado, é limitação conhecida — anotar, não inventar.
- ❌ Assumir que `player_id` é igual entre fontes. NÃO é. Sempre resolver via `normalize_name`.
- ❌ Assumir que todo jogo do sofascore tem par no ogol. Join é best-effort (ver 0.4).
- ❌ Hardcodar `minutes` como divisor sem guardar contra zero (ver `player_stats.py:62` `if ... else None`).
- ❌ Escrever fórmula de xPoints "de cabeça" — usar a definição em 3.2 exatamente.

### 0.4 Gaps de dados conhecidos (confirmados nesta sessão)

- `data/fortaleza_ogol_matches.json` e `_ogol_stats.json` contêm em parte a temporada
  **2025** (ex.: primeira linha `date: 2025-12-07`). O `advanced_matches.json` é **Série B
  2026**. Logo o join sofascore↔ogol por temporada 2026 pode cobrir poucos jogos até
  re-scrapar ogol 2026. → `matches_master` deve marcar `ogol_matched: bool` e a esteira
  não pode quebrar quando faltar par.
- `player_id` do sofascore (ex.: `1166468`) ≠ ogol (`profile_url` tem outro id) ≠
  transfermarkt (sem id salvo, só nome). Join é por nome normalizado.
- `advanced_season.json` tem 34 jogadores; `squad.json` 50 (histórico, inclui inativos);
  `player_stats.json` 33 (só ativos). `players_master` é a UNIÃO por nome normalizado,
  com flags de presença por fonte.
- Shotmap: `situation` tem 8 valores confirmados: `regular`, `assisted`, `corner`,
  `free-kick`, `set-piece`, `throw-in-set-piece`, `fast-break`, `penalty`.
  `body_part`: `right-foot`, `left-foot`, `head`. `shot_type`: `goal`, `save`, `miss`,
  `block`, `post`. Bola parada = {`corner`, `free-kick`, `set-piece`, `throw-in-set-piece`, `penalty`}.
- `advanced_matches.json` cobre **24 jogos**; `xg_home/xg_away/xgot_home/xgot_away`
  presentes em todos. `players[]` por jogo tem `team` (`home`/`away`) e `team_name`.
- `matches.json` (transfermarkt, 64 linhas) tem `score` no formato `"4-2"` ou `null`;
  `home_away` `"H"`/`"A"`; usar como verdade de RESULTADO (pontos reais).

### 0.5 Saída consolidada da Fase 0

Antes de começar a Fase 1, o executor escreve um bloco `## APIs Permitidas (confirmado)`
no topo do PR/branch com: versões reais das libs + confirmação de que abriu cada
arquivo da tabela 0.1. Sem isso, não prosseguir.

---

## Fase 1 — Camada Resolve (`players_master` + `matches_master`)

### 1.1 O que implementar

**Novo módulo `resolve/__init__.py` + `resolve/master.py`** (espelhar layout de `models/`).

`resolve/master.py` expõe 2 funções puras (sem rede, só leem dicts já carregados):

```
build_players_master(squad: dict, player_stats: dict, advanced_season: dict) -> list[dict]
build_matches_master(tm_matches: list, ogol_matches: list, advanced_matches: dict) -> list[dict]
```

**`build_players_master`** — COPIAR o padrão de fuzzy match de `main.py:120-133`:
- chave = `normalize_name(name)` (de `name_match.py:4`)
- uma linha por nome normalizado, unindo as 3 fontes
- campos: `key` (nome normalizado), `name` (melhor display — o mais longo entre fontes),
  `sofascore_id`, `ogol_id` (extrair de `profile_url` com regex `/jogador/[^/]+/(\d+)` —
  ver `scrapers/ogol.py:12` `_JOGADOR_RE`), `position_group` (de squad),
  `position_detail`, `age`, `nationality`, `market_value_eur`, `contract_until`,
  `active`, e flags `in_squad`, `in_ogol_stats`, `in_advanced` (bool).
- fallback substring idêntico ao de `main.py:124-129`.

**`build_matches_master`** — join best-effort:
- linha canônica = cada jogo de `advanced_matches["matches"]` (tem `event_id`, `date`,
  `home_team`, `away_team`, `competition`, `round`, `xg_*`).
- tentar casar com `tm_matches` e `ogol_matches` por `(date, adversário normalizado)`:
  o adversário é o time que não contém `"fortaleza"` (lower). Do tm/ogol vem `score`,
  `home_away`, `attendance`/`referee` (ogol_stats, casar por `match_url`).
- campos: `event_id`, `date`, `competition`, `round`, `is_home` (bool, derivar de
  `home_team` contém "fortaleza"), `opponent`, `score` (str | null), `goals_for`,
  `goals_against` (int | null, parsear `score` respeitando mando), `points` (3/1/0 | null),
  `xg_for`, `xg_against`, `xgot_for`, `xgot_against` (do advanced, mapeando home/away→for/against),
  `tm_matched`, `ogol_matched` (bool), `attendance`, `referee` (se `ogol_matched`).
- NUNCA descartar jogo do advanced por falta de par. `tm_matched=False` é válido.

**Persistência** — adicionar a `storage/json_store.py` (COPIAR `save_squad`/`load_squad`
de `:31-58`):
```
save_players_master(team, rows, season_year) -> str   # data/<team>_players_master.json
load_players_master(team) -> dict
save_matches_master(team, rows, season_year) -> str   # data/<team>_matches_master.json
load_matches_master(team) -> dict
```
Envelope: `{"season_year": ..., "players": [...]}` / `{"season_year": ..., "matches": [...]}`.

### 1.2 Referências de doc

- `name_match.py:1-8` — `normalize_name` (única forma de comparar nomes)
- `main.py:113-133` — loop de match exato→substring a copiar literalmente
- `scrapers/ogol.py:12` — regex `_JOGADOR_RE` para extrair ogol id de `profile_url`
- `storage/json_store.py:31-58` — assinatura e corpo de `save_*`/`load_*` a espelhar
- `models/aggregate.py:44-66` — estilo de função pura com acumulador dict
- Estrutura real dos inputs: ver Fase 0.4 e rodar
  `python -c "import json; d=json.load(open('data/fortaleza_squad.json')); print(d['players'][0])"`
  para cada arquivo antes de mapear campos.

### 1.3 Checklist de verificação

- [x] `python -c "from resolve.master import build_players_master"` importa sem erro
- [x] Novo sub-comando `python main.py --team fortaleza --resolve` grava os 2 arquivos
- [x] `players_master`: `len` ≥ 34 e ≤ 50; todo item com `in_advanced=True` tem `sofascore_id`
- [x] `players_master`: ≥ 28 itens com `sofascore_id` E `ogol_id` preenchidos (join deu certo)
- [x] `matches_master`: `len == 24` (um por jogo do advanced)
- [x] `matches_master`: todo item tem `xg_for` e `xg_against` não-nulos
- [x] `matches_master`: `sum(m["points"] for m if m["points"] is not None)` bate com a
      contagem manual de V/E/D dos jogos com `score` conhecido
- [x] grep: `grep -rn "requests\|curl_cffi\|http" resolve/` → **zero** (camada sem rede)
- [x] `grep -rn "\.append(" resolve/` → zero em contexto de DataFrame

### 1.4 Guardas anti-padrão

- Não usar `pandas` aqui se dict/loop resolve — manter alinhado a `aggregate.py` (dict puro).
- Não criar id sintético novo; se faltar `ogol_id`, deixar `None`.
- Não assumir ordem dos arquivos; sempre casar por chave, nunca por índice.
- Parse de `score`: `"2-1"` com `is_home` define `goals_for/against`; `null` → tudo `None`.

---

## Fase 2 — Camada Derive: `player_metrics`

### 2.1 O que implementar

**Novo `models/derived.py`** com dataclass `PlayerMetrics` (COPIAR estilo de
`models/player_stats.py:30-70`, incluindo `@property`). Campos = 3 blocos:

1. **Volume & base**: `key`, `name`, `position_group`, `minutes`, `matches`, `starts_share`
   (min / (matches*90) aprox), `market_value_eur`, `age`, `contract_until`, `active`.
2. **Absolutos /90** (todos = `valor / minutes * 90`, guardando contra `minutes==0` →
   `None`, igual a `player_stats.py:62`): `goals_p90`, `xg_p90`, `assists_p90`, `xa_p90`,
   `shots_p90`, `touches_p90`, `passes_p90`, `key_passes_p90`, `long_balls_p90`,
   `crosses_p90`, `poss_lost_p90`, `ball_recovery_p90`, `progressive_carries_p90`,
   `duels_won_p90`, `aerials_won_p90`, `interceptions_p90`, `clearances_p90`, `fouls_p90`.
3. **Razões & performance**:
   - `pass_accuracy` = passes_accurate / passes_total * 100
   - `long_ball_accuracy`, `cross_accuracy` (idem, guardar zero)
   - `duel_win_pct` = duels_won / (duels_won + duels_lost) * 100
   - `aerial_win_pct` = aerials_won / (aerials_won + (duels? não há aerial_lost)) →
     **NÃO há `aerial_lost`**: reportar só `aerials_won_p90`, sem pct. (anti-padrão: não inventar denominador)
   - `turnover_rate` = poss_lost / touches * 100
   - `opp_half_pass_share` = opp_half_passes_total / passes_total * 100 (proxy playmaker avançado)
   - `xg_overperformance` = goals - xg  (finalização acima/abaixo do esperado)
   - `xa_overperformance` = assists - xa
   - `shot_quality` = xg / shots  (xG por finalização; guardar shots==0 → None)
4. **Percentis (0-100) vs grupo de posição do elenco** — `<metric>_pctl` para um subconjunto
   escolhido (xg_p90, xa_p90, key_passes_p90, progressive_carries_p90, ball_recovery_p90,
   duel_win_pct, pass_accuracy, touches_p90, turnover_rate[invertido: menor=melhor]).
   Calcular com `pandas.DataFrame.groupby("position_group")[col].rank(pct=True) * 100`.
   Guardar como coluna extra no JSON (não no dataclass — achatar no `save_*`, padrão
   `_advanced_row_dict` de `storage/json_store.py`).

**Função** em `models/derived.py`:
```
build_player_metrics(players_master: list[dict], advanced_season: dict) -> list[dict]
```
- une por `key` (players_master) com `advanced_season["players"]` (por `sofascore_id`↔`player_id`)
- calcula blocos 1-3 por jogador (dataclass → asdict)
- bloco 4 (percentis) calculado depois com pandas sobre a lista inteira, injetado nos dicts
- retorna `list[dict]` pronta pra salvar

**Persistência**: `save_player_metrics` / `load_player_metrics` em `storage/json_store.py`
(envelope `{season_year, players:[...]}`), espelhando `:42-51`.

### 2.2 Referências de doc

- `models/player_stats.py:30-70` — dataclass + `@property` + guarda contra zero
- `models/aggregate.py:9-42` — mapa de campos origem→destino (reusar nomes de
  `advanced_season`: `possession_lost`, `ball_recovery`, `progressive_carries`, etc.)
- `storage/json_store.py` `_advanced_row_dict` (~`:99-105`) — como achatar `@property`/percentil no dict
- pandas: `df.groupby(col)[m].rank(pct=True)` — API confirmada na Fase 0.2
- Campos reais de `advanced_season`: `python -c "import json;print(list(json.load(open('data/fortaleza_advanced_season.json'))['players'][0].keys()))"`

### 2.3 Checklist de verificação

- [x] `python main.py --team fortaleza --build` gera `data/fortaleza_player_metrics.json`
- [x] Todo jogador com `minutes > 0` tem `xg_p90` não-nulo; com `minutes == 0` tem `None`
- [x] `xg_overperformance` de um artilheiro conhecido (ex.: Juan Miritello) é finito e = `goals - xg`
- [x] Percentis: para cada `position_group`, `max(<m>_pctl) ≈ 100` e `min ≈` (1/n*100)
- [x] `turnover_rate` entre 0 e 100 para todos
- [x] grep sem rede: `grep -rn "http\|requests\|curl_cffi" models/derived.py` → zero
- [x] `python -c "import json; d=json.load(open('data/fortaleza_player_metrics.json')); assert all(0<=p['pass_accuracy']<=100 for p in d['players'] if p['pass_accuracy'] is not None)"`

### 2.4 Guardas anti-padrão

- ❌ `aerial_win_pct` — não há `aerial_lost`. Não criar.
- ❌ Dividir por `minutes` sem `if minutes else None`.
- ❌ `df.append` para montar a tabela de percentis — usar `pd.DataFrame(list_of_dicts)`.
- ❌ Percentil global ignorando posição — sempre `groupby("position_group")`.
- ❌ Puxar dado que só existe em `advanced_matches` (por-jogo) aqui — esta fase é temporada.

---

## Fase 3 — Camada Derive: `team_metrics` + `match_reports`

### 3.1 O que implementar — `team_metrics`

**`models/derived.py`** ganha `build_team_metrics(matches_master: list[dict],
advanced_matches: dict, ogol_stats: list[dict]) -> dict`. Saída (um dict, salvo como
`data/<team>_team_metrics.json`):

- **`summary`**: `matches`, `wins/draws/losses` (de `points`), `points_real`,
  `xg_for_total`, `xg_against_total`, `xg_diff`, `points_expected` (ver 3.2),
  `points_luck` = `points_real - points_expected`, `goals_for/against`,
  `finishing` = `goals_for - xg_for_total`, `keeping` = `xg_against_total - goals_against`
  (defesa/goleiro acima do esperado).
- **`per_match`**: lista ordenada por data com `date`, `opponent`, `is_home`, `score`,
  `points`, `xg_for`, `xg_against`, `xg_diff`, `xg_for_roll5`, `xg_against_roll5`
  (média móvel 5 jogos via `pandas.Series.rolling(5, min_periods=1).mean()`),
  `points_roll5`.
- **`home_away`**: dict com médias de `xg_for`, `xg_against`, `points`, `ppg` para
  `home` e `away` (split por `is_home`).
- **`set_pieces`**: usando `advanced_matches[*].shots`:
  `xg_for_setpiece_pct` = soma xg de chutes de Fortaleza em situação de bola parada /
  soma xg total de Fortaleza; idem `xg_against_setpiece_pct`. Identificar lado de
  Fortaleza por `is_home` do jogo vs `shot.is_home`. Bola parada = conjunto da Fase 0.4.
- **`shot_situations`**: `groupby(situation)` sobre todos os chutes de Fortaleza →
  `count`, `xg_sum`, `goals` (for) e o mesmo para `against`.
- **`timeline`**: buckets de 15min (`0-15,15-30,...,90+`) somando `xg` dos chutes
  `for` e `against` por bucket (usar `shot.minute`). Revela períodos fortes/fracos.
- **`discipline`**: de `ogol_stats` casado via `matches_master.ogol_matched` — média de
  `fouls`, contagem de `cards` amarelos/vermelhos por jogo (quando disponível).
  Quando `ogol_matched` cobre poucos jogos, incluir `coverage: n/24`.
- **`style`**: para os jogos com `ogol_matched`, correlação simples (ou só médias lado a
  lado) entre `possession_pct` (ogol) e `xg_for` — flag `direct` vs `possession` por
  heurística: `xg_for / possession_pct` alto ⇒ mais direto. Reportar como
  `avg_possession`, `xg_per_possession_point`.

### 3.2 Definição fechada de `points_expected` (usar EXATAMENTE)

Por jogo, a partir de `xg_for` (xf) e `xg_against` (xa), modelo Poisson simples:

```
from math import exp, factorial
def poisson_pmf(k, lam): return exp(-lam) * lam**k / factorial(k)
MAXG = 10
p_win  = sum(poisson_pmf(i, xf) * poisson_pmf(j, xa) for i in range(MAXG) for j in range(i))
p_draw = sum(poisson_pmf(i, xf) * poisson_pmf(i, xa) for i in range(MAXG))
p_loss = 1 - p_win - p_draw
xpoints_match = 3*p_win + 1*p_draw
```
`points_expected` (summary) = soma de `xpoints_match` sobre os 24 jogos.
Guardar `xpoints` também em cada `per_match`.
NÃO usar outra fórmula, NÃO trocar por "xG diff * fator".

### 3.3 O que implementar — `match_reports`

`build_match_reports(matches_master, advanced_matches, players_master) -> list[dict]`,
salvo em `data/<team>_match_reports.json` (envelope `{season_year, reports:[...]}`).
Um report por `event_id`:
- cabeçalho: `date`, `competition`, `round`, `opponent`, `is_home`, `score`, `points`,
  `xg_for`, `xg_against`, `xgot_for`, `xgot_against`
- `players_for` / `players_against`: lista de `advanced_matches[*].players` filtrada por
  lado, enriquecida com `key` (via players_master quando for Fortaleza), colunas:
  `name`, `is_starter`, `minutes_played`, `rating`, `touches`, `passes_total`,
  `passes_accurate`, `key_passes`, `possession_lost`, `ball_recovery`, `duels_won`,
  `duels_lost`, `xg`, `xa`, `shots_total`, `goals`
- `shots`: cópia direta de `advanced_matches[*].shots` + campo `side` (`for`/`against`)
- `xg_race`: lista `[{minute, cum_xg_for, cum_xg_against}]` — acumulado de `shot.xg`
  ordenado por minuto (para `st.line_chart` na Fase 4)
- `top_contributors`: 3 jogadores de Fortaleza com maior `xg + xa` no jogo

### 3.4 Referências de doc

- `models/aggregate.py:44-66` — padrão de varrer `advanced_matches["matches"]` e
  `match["players"]`, filtrar por `team_name`/`team`
- `scrapers/sofascore.py` `_match_xg` (~`:150-175`) — como `xg_home/away` mapeia p/ time
- `app.py:170-210` (aba avançada desta sessão) — já faz `groupby("situation")["xg"]`,
  copiar a ideia
- pandas `Series.rolling(window, min_periods=1).mean()` — API confirmada Fase 0.2
- `storage/json_store.py:31-51` — envelopes `save_*`

### 3.5 Checklist de verificação

- [x] `python main.py --team fortaleza --build` também gera `team_metrics.json` e `match_reports.json`
- [x] `summary.wins + draws + losses == 24` (ou == nº de jogos com `points` não-nulo; documentar)
- [x] `abs(sum(pm["xpoints"] for pm in per_match) - summary["points_expected"]) < 1e-6`
- [x] `0 <= p_win, p_draw, p_loss <= 1` e `p_win+p_draw+p_loss ≈ 1` em todo jogo (assert no teste)
- [x] `set_pieces.xg_for_setpiece_pct` entre 0 e 100
- [x] `timeline`: 7 buckets, soma dos `xg_for` dos buckets ≈ `summary.xg_for_total` (±0.1)
- [x] `match_reports`: `len(reports) == 24`; cada `xg_race` é monotônico não-decrescente nas 2 colunas
- [x] `top_contributors` de cada report tem exatamente 3 nomes (ou menos se jogo com <3 finalizadores)
- [x] grep sem rede em `models/derived.py`

### 3.6 Guardas anti-padrão

- ❌ Trocar a fórmula Poisson de 3.2 por aproximação.
- ❌ `range(MAXG)` com `MAXG` pequeno demais (usar 10).
- ❌ Somar xG de bola parada sem filtrar pelo lado certo (checar `is_home` do jogo × `shot.is_home`).
- ❌ Assumir que `ogol_stats` cobre os 24 — usar `coverage` e degradar suave.
- ❌ `df.append` para o `per_match` — montar lista e `pd.DataFrame(...).rolling(...)`.

---

## Fase 4 — Camada Serve: Streamlit multipage

### 4.1 O que implementar

Reescrever `app.py` como **entrypoint** que só faz `st.set_page_config` + `st.navigation`.
COPIAR `load_json` de `app.py:9-15`. Usar `st.navigation` + `st.Page` (Fase 0.2 —
**não** criar pasta `pages/`).

```
views/player_card.py     — Card do jogador
views/team_dashboard.py  — Dashboard do time
views/match_report.py    — Relatório de jogo
views/squad_planner.py   — Planejador de elenco
```

Cada view lê só `data/*.json` já derivados (nunca recomputa, nunca rede).

**`team_dashboard.py`**:
- `st.metric` row: pontos reais vs esperados (`points_luck` com delta), xG diff,
  finishing, keeping
- `st.line_chart` de `per_match` (`xg_for_roll5` vs `xg_against_roll5`) e de `points_roll5`
- tabela `home_away`
- `st.bar_chart` de `timeline` (xg_for vs xg_against por bucket 15min)
- `st.bar_chart` de `shot_situations` (for vs against)
- bloco set-pieces (2 `st.metric` com os %)
- `style`: avg_possession + xg_per_possession_point + rótulo direct/possession

**`player_card.py`**:
- `st.selectbox` de jogador (de `player_metrics.json`)
- header: nome, posição, idade, contrato, valor €, minutos, jogos
- `st.metric` row: gols vs xG (`xg_overperformance` como delta), assist vs xA,
  key_passes_p90, turnover_rate
- **radar de percentis** via `st.altair_chart` (altair já vem com streamlit) OU, se
  radar custar caro, `st.bar_chart` horizontal dos `*_pctl` (0-100). Escolher barra
  se em dúvida (anti-over-engineering).
- jogo-a-jogo do jogador: varrer `match_reports` pegando a linha do jogador em
  `players_for`, montar tabela rating/touches/xg/xa/passes por data + `st.line_chart` do rating
- "similares": 3 jogadores do mesmo `position_group` com menor distância euclidiana
  nos `*_pctl` (cálculo simples em numpy)

**`match_report.py`**:
- `st.selectbox` de jogo (`match_reports`, `format_func` com placar + xG)
- `st.metric` xG for/against, xGOT for/against
- `st.line_chart` do `xg_race` (2 séries)
- `st.tabs(["Fortaleza","Adversário"])` com as tabelas `players_for`/`players_against`
- tabela `shots` + `groupby('situation')` (copiar de `app.py` aba avançada)
- `top_contributors`

**`squad_planner.py`**:
- de `players_master` + `player_metrics`: depth chart por `position_group`
  (tabela: jogador, idade, minutos, share de minutos, contrato até, valor €)
- `st.bar_chart` distribuição de minutos por posição
- alerta contrato: filtro `contract_until` <= ano+1
- concentração de produção: % de (xg+xa) do elenco vindo do top-3 (de `player_metrics`)
- eficiência de valor: `st.scatter_chart` x=`market_value_eur` y=`xg_p90 + xa_p90`
- gaps: posições com menor mediana de `xg_p90+xa_p90` ⇒ candidatas a reforço

Manter a aba/página "Elenco" e "Métricas avançadas" atuais convertidas em views
(mover o corpo de `app.py:31-210` para `views/squad_legacy.py` e `views/advanced_legacy.py`,
ou incorporá-las às novas — decisão do executor, documentar).

### 4.2 Referências de doc

- `app.py:1-15` — `load_json` (copiar tal qual)
- `app.py:31-135` — padrão merge/rename/subset/`st.dataframe(hide_index=True)`
- `app.py:137-210` — `st.tabs`, `st.radio(horizontal=True)`, `st.selectbox(format_func=...)`,
  `st.columns` + `st.metric`, `groupby("situation")["xg"].agg(...)` — reusar
- streamlit 1.62 `st.navigation` / `st.Page` — API confirmada Fase 0.2 (rodar
  `python -c "import streamlit as st; print(hasattr(st,'navigation'), hasattr(st,'Page'))"` ⇒ deve dar `True True`)
- `st.line_chart` / `st.bar_chart` / `st.scatter_chart` — nativos, sem lib extra

### 4.3 Checklist de verificação

- [x] `python -c "import streamlit as st; assert hasattr(st,'navigation') and hasattr(st,'Page')"`
- [x] `streamlit run app.py` sobe sem exceção
- [x] As páginas abrem e renderizam ao menos uma tabela/gráfico sem erro
- [x] Nenhuma view importa `requests`/`curl_cffi`/`scrapers` — `grep -rn "scrapers\|requests\|curl_cffi" views/` → zero
- [x] `st.set_page_config` aparece 1x só — `grep -rn "set_page_config" app.py views/` → 1
- [x] `grep -rn "\.append(" views/` → zero (usar `pd.concat`)
- [x] Com um `data/*.json` derivado ausente, a view mostra `st.warning` e não quebra
      (padrão `load_json` → `{}` de `app.py:11`)

### 4.4 Guardas anti-padrão

- ❌ Pasta `pages/` — usar `st.navigation`.
- ❌ `st.set_page_config` dentro de view.
- ❌ Recalcular métrica na view — só ler JSON derivado.
- ❌ matplotlib/plotly — só charts nativos + altair (já incluso).
- ❌ `df.append`.

---

## Fase 5 — Refresh: `--all` incremental

### 5.1 O que implementar

**`main.py`** ganha:
- `--build` (action store_true): roda SÓ as camadas derivadas (Fases 1-3) lendo os
  `data/*.json` crus existentes. Função `_build_derived(team, store)`:
  carrega squad/player_stats/advanced_season/advanced_matches/ogol_stats/matches via
  `store.load_*`, chama `build_players_master`, `build_matches_master`,
  `build_player_metrics`, `build_team_metrics`, `build_match_reports`, salva tudo.
  Espelhar a forma de `_fetch_advanced` (`main.py:196-232`): prints de progresso + paths salvos.
- `--all` (action store_true): pipeline completo =
  `_fetch_matches_ogol` → `_fetch_squad` → `_fetch_player_stats` →
  `_fetch_advanced` (INCREMENTAL, ver 5.2) → `_build_derived`.
  Um try/except por etapa (COPIAR o try/except de `main.py:113-118` do `_fetch_squad`):
  falha numa fonte não aborta o resto; loga warning e segue.
- roteamento no `main()`: checar `args.build` e `args.all` logo após `args.discover`
  (`main.py:36`), antes de `args.advanced`.

### 5.2 `--advanced` incremental

Alterar `_fetch_advanced` (`main.py:196-232`) para aceitar `incremental: bool`:
- se `incremental` e existe `data/<team>_advanced_matches.json`: carregar `event_id`s já
  salvos; `get_season_events` continua listando tudo, mas só chamar
  `get_match_advanced` para `event_id` NÃO presente; concatenar aos antigos; re-agregar
  a temporada inteira com `aggregate_player_season` sobre a lista completa.
- flag CLI `--incremental` para uso avulso; `--all` sempre passa `incremental=True`.
- NÃO refazer scrape de jogo já salvo (economia de rede + respeita `SLEEP_SECONDS`).

### 5.3 Referências de doc

- `main.py:196-232` — `_fetch_advanced` (base do `--build` e do incremental)
- `main.py:106-146` — `_fetch_squad` com `try/except` por fonte (copiar padrão de resiliência)
- `main.py:36-42` — roteamento de sub-comando (onde inserir `--build`/`--all`)
- `models/aggregate.py:31` — `aggregate_player_season(matches, club_name)` reusado tal qual
- `storage/json_store.py` `load_match_advanced` (~`:79-85`) — ler ids já salvos

### 5.4 Checklist de verificação

- [x] `python main.py --team fortaleza --build` roda em <5s (sem rede) e (re)gera os 5 JSON derivados
- [x] `grep -n "requests\|curl_cffi" ` no caminho de `--build` → zero (não deve tocar rede)
- [x] `python main.py --team fortaleza --advanced --incremental` com os 24 já salvos:
      log diz "0 novos jogos", arquivos inalterados (comparar `md5`)
- [x] Apagar 1 jogo do `advanced_matches.json` e rodar `--incremental` → re-baixa só esse 1,
      volta a 24, `advanced_season.json` reagrega
- [x] `python main.py --team fortaleza --all` completa mesmo desligando a rede no meio
      (uma etapa falha com warning, derivadas ainda rodam sobre o que há)
- [x] `--help` lista `--build`, `--all`, `--incremental` com descrições

### 5.5 Guardas anti-padrão

- ❌ `--build` fazer qualquer request. É offline puro.
- ❌ `--all` abortar tudo se uma fonte cai — cada etapa em try/except isolado.
- ❌ Incremental re-scrapar jogo já salvo.
- ❌ Re-agregar temporada só com os jogos novos — sempre sobre a lista completa.

---

## Fase 6 — Verificação final

### 6.1 Conformidade com este plano

- [x] Todas as fases 1-5 com checklist 100% marcado
- [x] `models/derived.py`, `resolve/master.py`, `views/*.py` existem e importam
- [x] `requirements.txt` reflete o `.venv` real (bump `streamlit`/`pandas` para as versões
      confirmadas na Fase 0, + `curl_cffi` já adicionado nesta sessão)

### 6.2 Grep de anti-padrões (tem que dar VAZIO)

```
grep -rn "\.append(" models/ resolve/ views/ | grep -i "df\|frame\|series"
grep -rn "requests\|curl_cffi\|http" models/derived.py resolve/ views/
grep -rn "set_page_config" app.py views/ | wc -l        # == 1
grep -rn "pages/" app.py                                 # vazio (usa st.navigation)
grep -rn "matplotlib\|plotly" .                          # vazio
```

### 6.3 Testes funcionais ponta a ponta

```
python main.py --team fortaleza --build          # 5 JSON derivados, <5s, sem rede
python -c "
import json
for f in ['players_master','matches_master','player_metrics','team_metrics','match_reports']:
    d=json.load(open(f'data/fortaleza_{f}.json'))
    print(f, 'OK', len(d.get('players') or d.get('matches') or d.get('reports') or []))
"
python main.py --team fortaleza --all            # pipeline completo, resiliente
streamlit run app.py                             # todas as páginas sobem sem Traceback
```

### 6.4 Sanidade dos números (revisão humana)

- [x] `team_metrics.summary.points_expected` plausível vs `points_real` (diferença <
      ~12 pts em 24 jogos)
- [x] Artilheiro do `player_metrics` bate com o `advanced_season` (Miritello top xG nesta sessão)
- [x] `match_report` de 1 jogo conferido contra o placar real de `matches.json`
- [x] `timeline` soma ≈ `xg_for_total`
- [x] percentis: ninguém com `xg_p90_pctl > 100` ou `< 0`

### 6.5 Doc

- [x] `README.md`: nova seção "Esteira analítica" com `--build` / `--all` / `--incremental`
      e a lista dos 5 arquivos derivados (espelhar a seção "Métricas avançadas" atual)
- [x] `plans/01-esteira-analitica.md` marcado como concluído no topo

---

## Ordem de execução e dependências

```
Fase 0  (discovery, ~30min, inline)
  └─ Fase 1  (resolve)            depende de: dados crus já existentes
       └─ Fase 2  (player_metrics)  depende de: players_master, advanced_season
       └─ Fase 3  (team + reports)  depende de: matches_master, advanced_matches, ogol_stats
            └─ Fase 4  (streamlit)    depende de: todos os JSON derivados
                 └─ Fase 5  (--all / incremental)  depende de: build_* prontas
                      └─ Fase 6  (verificação)
```

Fases 2 e 3 são paralelizáveis após a 1. Fase 4 espera 2+3.

## Arquivos novos criados por este plano

```
resolve/__init__.py
resolve/master.py
models/derived.py
views/player_card.py
views/team_dashboard.py
views/match_report.py
views/squad_planner.py
data/fortaleza_players_master.json      (gerado)
data/fortaleza_matches_master.json      (gerado)
data/fortaleza_player_metrics.json      (gerado)
data/fortaleza_team_metrics.json        (gerado)
data/fortaleza_match_reports.json       (gerado)
```

## Arquivos alterados

```
app.py                   → vira entrypoint st.navigation
main.py                  → +--resolve? (opcional) +--build +--all +--incremental
storage/json_store.py    → +save/load_{players_master,matches_master,player_metrics,team_metrics,match_reports}
requirements.txt         → bump streamlit/pandas p/ versões do .venv
README.md                → seção "Esteira analítica"
```
