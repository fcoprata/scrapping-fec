import argparse
import json
import os
import sys
from config import TEAMS

_SEASON_CACHE = "data/sofascore_seasons.json"


def _load_season_cache() -> dict:
    if os.path.exists(_SEASON_CACHE):
        with open(_SEASON_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _team_seasons(team: str) -> dict:
    """Configured SofaScore seasons for a team, falling back to the discovery cache."""
    cfg = TEAMS[team].get("sofascore") or {}
    if cfg.get("seasons"):
        return cfg["seasons"]
    return _load_season_cache().get(team, {})
from name_match import normalize_name
from models.aggregate import aggregate_player_season
from resolve.master import build_players_master, build_matches_master
from models.derived import build_player_metrics, build_team_metrics, build_match_reports
from models.league import build_league_player_metrics
from analysis import build_analysis
from scrapers.transfermarkt import TransfermarktScraper
from scrapers.ogol import OGolScraper
from scrapers.sofascore import SofaScoreScraper
from scrapers.ufmg import UFMGScraper
from storage.json_store import JsonStore


def main():
    parser = argparse.ArgumentParser(
        description="🦁 Fortaleza EC — Plataforma de Extração e Inteligência Analítica de Futebol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemplos de Uso:
  python main.py --team fortaleza --build       # Recalcula toda a esteira analítica offline (<5s)
  python main.py --team fortaleza --analyze     # Gera as sínteses textuais determinísticas
  python main.py --team fortaleza --all         # Executa scrapers incrementais + esteira analítica
  streamlit run app.py                          # Inicia o dashboard interativo""",
    )
    parser.add_argument("--team", choices=list(TEAMS.keys()), help="Time a ser processado (ex: fortaleza)")
    parser.add_argument("--list-teams", action="store_true", help="Listar times configurados por divisão")
    parser.add_argument("--batch-full", action="store_true", help="Esteira COMPLETA em lote: ogol matches + squad + player-stats + ogol-stats + advanced + resolve + derived + análise para os clubes cadastrados.")
    parser.add_argument("--skip-existing", action="store_true", help="Com --batch-full: pula clubes que já têm matches_master preenchido.")
    parser.add_argument("--skip-teams", default="", help="Lista de team keys separadas por vírgula a ignorar no batch (ex: fortaleza).")
    parser.add_argument("--discover-seasons", action="store_true", help="Descobre e cacheia as temporadas 2026 (Série A/B) do SofaScore (data/sofascore_seasons.json).")
    parser.add_argument("--division", choices=["serie-a", "serie-b", "all"], default="all", help="Divisão para o batch-full (padrão: all).")

    # Grupo 1: Esteira Analítica
    g_pipeline = parser.add_argument_group("📊 Pipeline Analítico")
    g_pipeline.add_argument("--build", action="store_true", help="Executa a camada analítica offline: Resolve + Derive + Diagnóstico Tático.")
    g_pipeline.add_argument("--analyze", action="store_true", help="Gera as sínteses textuais determinísticas (temporada e partidas).")
    g_pipeline.add_argument("--analyze-scope", choices=["season", "matches", "all"], default="all", help="Escopo das sínteses: season, matches ou all (padrão: all).")
    g_pipeline.add_argument("--resolve", action="store_true", help="Executa apenas a unificação de identidades de atletas e casamentos de partidas.")
    g_pipeline.add_argument("--all", dest="run_all", action="store_true", help="Pipeline completo: coleta incremental de todas as fontes + build analítico.")
    g_pipeline.add_argument("--league", action="store_true", help="Agrega player_metrics de todos os clubes cadastrados num dataset único com percentis por liga/divisão (data/league_player_metrics.json).")

    # Grupo 2: Coleta de Dados (Scrapers)
    g_scrape = parser.add_argument_group("🌐 Coleta de Dados (Scrapers)")
    g_scrape.add_argument("--advanced", action="store_true", help="Coleta métricas avançadas e xG por partida do SofaScore.")
    g_scrape.add_argument("--incremental", action="store_true", help="Com --advanced: busca apenas partidas novas ainda não salvas.")
    g_scrape.add_argument("--squad", action="store_true", help="Coleta elenco e valores de mercado (OGol + Transfermarkt).")
    g_scrape.add_argument("--player-stats", action="store_true", help="Coleta estatísticas individuais da temporada (OGol).")
    g_scrape.add_argument("--stats", action="store_true", help="Coleta estatísticas detalhadas de partidas jogadas.")
    g_scrape.add_argument("--source", choices=["transfermarkt", "ogol"], default="ogol", help="Fonte para partidas/stats (padrão: ogol).")
    g_scrape.add_argument("--discover", action="store_true", help="Descobre torneios e IDs no SofaScore para a equipe.")
    g_scrape.add_argument("--limit", type=int, default=None, help="Limite máximo de partidas a processar.")
    g_scrape.add_argument("--fixtures", action="store_true", help="Coleta os próximos jogos (SofaScore) do time.")
    g_scrape.add_argument("--standings", action="store_true", help="Coleta a classificação (SofaScore) da Série A e Série B 2026.")
    g_scrape.add_argument("--ufmg", action="store_true", help="Coleta dados estatísticos e probabilidades da UFMG para a Série A e Série B 2026.")

    args = parser.parse_args()

    if args.list_teams:
        for div in ["Série A", "Série B"]:
            div_teams = {k: v for k, v in TEAMS.items() if v.get("division") == div}
            print(f"\n🏆 {div.upper()} ({len(div_teams)} Clubes Cadastrados):")
            for k, v in div_teams.items():
                print(f"  • {k:22} -> {v.get('name')} ({v.get('state', '')})")
        return

    store = JsonStore()

    if args.discover_seasons:
        _discover_all_seasons()
        return

    if args.batch_full:
        skip = {s.strip() for s in args.skip_teams.split(",") if s.strip()}
        _run_batch_full(args.division, store, skip=skip,
                        skip_existing=args.skip_existing, limit_teams=args.limit)
        return

    if args.standings:
        _fetch_standings(SofaScoreScraper(), store)
        return

    if args.ufmg:
        _fetch_ufmg(UFMGScraper(), store)
        return

    if args.league:
        _build_league(store)
        return

    if not args.team:
        parser.print_help()
        sys.exit(1)

    if args.discover:
        _discover_sofascore(args.team)
        return

    if args.resolve:
        _build_resolve(args.team, store)
        return

    if args.build:
        _build_resolve(args.team, store)
        _build_derived(args.team, store)
        return

    if args.analyze:
        _build_resolve(args.team, store)
        _build_derived(args.team, store)
        from analysis.narrative import narrate
        narrate(args.team, store, scope=args.analyze_scope, limit=args.limit)
        return

    if args.run_all:
        _run_all(args.team, store)
        return

    if args.advanced:
        _fetch_advanced(args.team, args.limit, SofaScoreScraper(), store, incremental=args.incremental)
        return

    if args.fixtures:
        _fetch_fixtures(args.team, SofaScoreScraper(), store)
        return

    if args.squad:
        if args.source != "ogol":
            print("--squad only supported with --source ogol")
            sys.exit(1)
        _fetch_squad(args.team, OGolScraper(), TransfermarktScraper(), store)
        return

    if args.player_stats:
        if args.source != "ogol":
            print("--player-stats only supported with --source ogol")
            sys.exit(1)
        _fetch_player_stats(args.team, args.limit, OGolScraper(), store)
        return

    if args.source == "ogol":
        scraper = OGolScraper()
        if args.stats:
            _fetch_stats(args.team, args.source, args.limit, scraper, store)
        else:
            _fetch_matches_ogol(args.team, scraper, store)
    else:
        scraper = TransfermarktScraper()
        if args.stats:
            _fetch_stats(args.team, args.source, args.limit, scraper, store)
        else:
            _fetch_matches_transfermarkt(args.team, scraper, store)


def _fetch_matches_ogol(team: str, scraper: OGolScraper, store: JsonStore) -> None:
    slug = TEAMS[team]["ogol"]["slug"]
    print(f"Fetching matches: {team} from OGol (slug={slug})")

    matches = scraper.get_matches(slug)
    if not matches:
        print("No matches found. Possible causes: wrong slug, site structure changed, or rate limited.")
        sys.exit(1)

    played = [m for m in matches if m.status == "played"]
    upcoming = [m for m in matches if m.status == "upcoming"]
    print(f"Found {len(matches)} matches ({len(played)} played, {len(upcoming)} upcoming)")

    path = store.save(f"{team}_ogol", matches)
    print(f"Saved → {path}")


def _fetch_matches_transfermarkt(team: str, scraper: TransfermarktScraper, store: JsonStore) -> None:
    cfg = TEAMS[team]["transfermarkt"]
    print(f"Fetching matches: {team} from Transfermarkt (id={cfg['id']})")

    matches = scraper.get_matches(cfg["slug"], cfg["id"])
    if not matches:
        print("No matches found. Possible causes: wrong team ID/slug, site structure changed, or rate limited.")
        sys.exit(1)

    played = [m for m in matches if m.status == "played"]
    upcoming = [m for m in matches if m.status == "upcoming"]
    print(f"Found {len(matches)} matches ({len(played)} played, {len(upcoming)} upcoming)")

    path = store.save(f"{team}_transfermarkt", matches)
    print(f"Saved → {path}")


def _fetch_squad(team: str, ogol_scraper: OGolScraper, tm_scraper: TransfermarktScraper, store: JsonStore) -> None:
    ogol_slug = TEAMS[team]["ogol"]["slug"]
    tm_cfg = TEAMS[team]["transfermarkt"]
    print(f"Fetching squad: {team} from OGol (slug={ogol_slug})")

    players, season_year, epoca_id = ogol_scraper.get_squad(ogol_slug)
    if not players:
        print(f"    OGol sem elenco para '{ogol_slug}'; utilizando elenco do Transfermarkt...")
        tm_players = tm_scraper.get_squad(tm_cfg["slug"], tm_cfg["id"])
        if not tm_players:
            raise ValueError(f"Nenhum atleta encontrado no OGol nem no Transfermarkt para {team}")

        from models.player import Player
        players = []
        for i, p in enumerate(tm_players):
            sp = Player(
                player_id=str(p.get("id") or (100000 + i)),
                name=p["name"],
                slug=p["name"].lower().replace(" ", "-"),
                position=p.get("position") or "Meio-Campo",
                position_detail=p.get("position"),
                jersey_number=None,
                age=p.get("age"),
                nationality=None,
                market_value_eur=p.get("market_value_eur"),
                photo_url=None,
                profile_url="",
                active=True,
                contract_until=p.get("contract_until"),
            )
            players.append(sp)
        season_year = "2024"
        epoca_id = 0
        matched = len(players)
    else:
        print(f"Fetching market value/contract from Transfermarkt (id={tm_cfg['id']})")
        try:
            tm_players = tm_scraper.get_squad(tm_cfg["slug"], tm_cfg["id"])
        except Exception as e:
            print(f"    Warning: Transfermarkt squad fetch failed ({e}); keeping OGol-only values")
            tm_players = []

        tm_by_name = {normalize_name(p["name"]): p for p in tm_players}
        matched = 0
        for player in players:
            tm_match = tm_by_name.get(normalize_name(player.name))
            if not tm_match:
                norm = normalize_name(player.name)
                tm_match = next(
                    (p for k, p in tm_by_name.items() if k in norm or norm in k),
                    None,
                )
            if tm_match:
                matched += 1
                player.position_detail = tm_match["position"]
                player.contract_until = tm_match["contract_until"]
                if tm_match["market_value_eur"] is not None:
                    player.market_value_eur = tm_match["market_value_eur"]

        if matched <= 2 and len(tm_players) >= 15:
            print(f"    OGol retornou clube homônimo/incompatível (apenas {matched} casamentos); utilizando elenco oficial do Transfermarkt...")
            from models.player import Player
            players = []
            for i, p in enumerate(tm_players):
                sp = Player(
                    player_id=str(p.get("id") or (100000 + i)),
                    name=p["name"],
                    slug=p["name"].lower().replace(" ", "-"),
                    position=p.get("position") or "Meio-Campo",
                    position_detail=p.get("position"),
                    jersey_number=None,
                    age=p.get("age"),
                    nationality=None,
                    market_value_eur=p.get("market_value_eur"),
                    photo_url=None,
                    profile_url="",
                    active=True,
                    contract_until=p.get("contract_until"),
                )
                players.append(sp)
            matched = len(players)

    active = [p for p in players if p.active]
    print(f"Found {len(players)} players in squad history ({len(active)} currently active), "
          f"{matched} matched to Transfermarkt")
    path = store.save_squad(team, players, season_year, epoca_id)
    print(f"Saved → {path}")


def _fetch_squad_sofascore(team: str, scraper: SofaScoreScraper, store: JsonStore) -> None:
    """Busca o elenco oficial com camisa, idade, contrato e valor de mercado via SofaScore."""
    cfg = TEAMS.get(team, {}).get("sofascore", {})
    team_id = cfg.get("team_id")
    if not team_id:
        print(f"No SofaScore team_id configured for '{team}'.")
        return
    print(f"Fetching official squad: {team} from SofaScore (team_id={team_id})")
    players = scraper.get_team_players(team_id)
    if not players:
        print(f"No squad returned by SofaScore for {team}")
        return

    existing = store.load_squad(team)
    if existing and existing.get("players"):
        from name_match import normalize_name

        ex_by_name = {normalize_name(p["name"]): p for p in existing.get("players", []) if p.get("name")}
        for p in players:
            m = ex_by_name.get(normalize_name(p.name))
            if m:
                if not m.get("jersey_number") and p.jersey_number:
                    m["jersey_number"] = p.jersey_number
                if not m.get("market_value_eur") and p.market_value_eur:
                    m["market_value_eur"] = p.market_value_eur
                if not m.get("contract_until") and p.contract_until:
                    m["contract_until"] = p.contract_until
                if not m.get("age") and p.age:
                    m["age"] = p.age
        from models.player import Player

        merged = [
            Player(**{k: v for k, v in p.items() if k in Player.__annotations__})
            for p in existing["players"]
        ]
        path = store.save_squad(team, merged, existing.get("season_year", "2026"), existing.get("epoca_id", "0"))
        print(f"Saved merged squad ({len(merged)} players) → {path}")
    else:
        path = store.save_squad(team, players, "2026", "0")
        print(f"Saved SofaScore squad ({len(players)} players) → {path}")


def _fetch_player_stats(team: str, limit: int | None, scraper: OGolScraper, store: JsonStore) -> None:
    squad = store.load_squad(team)
    players = squad["players"]
    if not players:
        print(f"No saved squad for '{team}'. Run --squad first.")
        sys.exit(1)

    active = [p for p in players if p.get("active")]
    if limit:
        active = active[:limit]

    print(f"Fetching season stats for {len(active)} active players...")
    all_stats = []
    for i, p in enumerate(active, 1):
        print(f"  [{i}/{len(active)}] {p['name']}")
        stats = scraper.get_player_season_stats(p["player_id"], p["name"], p["profile_url"], p["position"])
        if not stats:
            print(f"    Warning: no season stats parsed for {p['name']}")
            continue
        starts, subs, avg_rating = scraper.get_player_match_log(p["slug"], p["player_id"], squad["epoca_id"])
        # match_log não separa competições; se o atleta não somou minutos profissionais
        # (só jogou base: S20/Copinha/etc.), zera titularidades e nota.
        if (stats.total_minutes or 0) == 0:
            starts, subs, avg_rating = 0, 0, None
        stats.starts, stats.substitute_appearances, stats.avg_rating = starts, subs, avg_rating
        all_stats.append(stats)

    path = store.save_player_stats(team, all_stats, squad["season_year"])
    print(f"Saved {len(all_stats)} player stats → {path}")


def _discover_sofascore(team: str) -> None:
    scraper = SofaScoreScraper()
    cfg = TEAMS[team].get("sofascore")
    if cfg:
        team_id = cfg["team_id"]
        print(f"Configured SofaScore team_id for '{team}': {team_id}")
    else:
        hits = scraper.search_team(team)
        print(f"Search results for '{team}':")
        for h in hits[:10]:
            print(f"  id={h['id']:<8} {h['name']} ({h['country']})")
        if not hits:
            return
        team_id = hits[0]["id"]
        print(f"\nUsing top hit id={team_id}")
    print("\nSeasons with statistics:")
    for s in scraper.get_team_seasons(team_id):
        print(f"  tournament_id={s['tournament_id']:<6} season_id={s['season_id']:<8} "
              f"{s['tournament']} — {s['season']}")


def _rehydrate_advanced(d: dict):
    """Reconstruct MatchAdvancedStats from a saved dict (keys match dataclass fields).

    Tolerant of schema drift: JSON saved by an older version of the scraper can carry
    fields the current dataclasses have renamed or dropped (ex.: ``assist_name`` ->
    ``assist_player_name`` on Shot). Unknown keys are dropped instead of raising, so a
    stale cache entry never blocks an incremental fetch from picking up new matches.
    """
    from dataclasses import fields
    from models.player_match_stats import MatchAdvancedStats, PlayerMatchStats, Shot

    _SHOT_RENAMES = {"assist_name": "assist_player_name"}

    def _coerce(cls, raw: dict):
        raw = dict(raw)
        for old, new in _SHOT_RENAMES.items():
            if old in raw and new not in raw:
                raw[new] = raw.pop(old)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    d = dict(d)
    d["players"] = [_coerce(PlayerMatchStats, p) for p in d.get("players", [])]
    d["shots"] = [_coerce(Shot, s) for s in d.get("shots", [])]
    return MatchAdvancedStats(**d)


def _fetch_advanced(team: str, limit: int | None, scraper: SofaScoreScraper, store: JsonStore,
                    incremental: bool = False) -> None:
    cfg = TEAMS[team].get("sofascore")
    if not cfg:
        print(f"No 'sofascore' config for '{team}'. Run --discover to find ids, then add to config.py.")
        sys.exit(1)

    team_id = cfg["team_id"]
    seasons = _team_seasons(team)
    if not seasons:
        print(f"No SofaScore seasons for '{team}' (config or cache). Run --discover-seasons first.")
        sys.exit(1)
    season_ids = [s["season_id"] for s in seasons.values()]
    print(f"Listing SofaScore events: {team} (team_id={team_id}, seasons={season_ids})")
    events = scraper.get_season_events(team_id, season_ids)
    if not events:
        print("No finished events found for the configured seasons.")
        sys.exit(1)
    if limit:
        events = events[:limit]

    club_name = _club_name(events, team_id) or team

    existing = {}
    if incremental:
        for m in store.load_match_advanced(team).get("matches", []):
            existing[m["event_id"]] = m
        todo = [e for e in events if e["event_id"] not in existing]
        print(f"Incremental: {len(existing)} saved, {len(todo)} new to fetch.")
    else:
        todo = events

    matches = [_rehydrate_advanced(m) for m in existing.values()] if incremental else []
    for i, meta in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {meta['date']} {meta['home_team']} x {meta['away_team']} "
              f"({meta['competition']} r{meta['round']})")
        adv = scraper.get_match_advanced(meta)
        if adv:
            matches.append(adv)
        else:
            print("    Warning: no advanced stats (lineups unavailable)")

    matches.sort(key=lambda m: m.date or "")
    season_year = str((events[-1]["date"] or ""))[:4]
    path = store.save_match_advanced(team, matches, season_year)
    print(f"Saved {len(matches)} matches -> {path}")

    season_rows = aggregate_player_season(matches, club_name)
    path = store.save_advanced_season(team, season_rows, season_year)
    print(f"Aggregated {len(season_rows)} players -> {path}")


def _fetch_fixtures(team: str, scraper: SofaScoreScraper, store: JsonStore) -> None:
    cfg = TEAMS[team].get("sofascore")
    if not cfg:
        print(f"No 'sofascore' config for '{team}'.")
        return
    events = scraper.get_next_events(cfg["team_id"])
    if not events and store.load_fixtures(team).get("fixtures"):
        print("No upcoming fixtures fetched (likely blocked/rate-limited); keeping existing file.")
        return
    path = store.save_fixtures(team, events)
    print(f"Saved {len(events)} upcoming fixtures -> {path}")


def _fetch_standings(scraper: SofaScoreScraper, store: JsonStore) -> None:
    # Série B (tournament 390, season 89840)
    try:
        rows_b = scraper.get_standings(390, 89840)
        path_b = store.save_standings("serie_b_2026", rows_b)
        print(f"Saved {len(rows_b)} standings rows (Série B) -> {path_b}")
    except Exception as e:
        print(f"Failed to fetch Série B standings: {e}")

    # Série A (tournament 325, season 87678)
    try:
        rows_a = scraper.get_standings(325, 87678)
        path_a = store.save_standings("serie_a_2026", rows_a)
        print(f"Saved {len(rows_a)} standings rows (Série A) -> {path_a}")
    except Exception as e:
        print(f"Failed to fetch Série A standings: {e}")


def _fetch_ufmg(scraper: UFMGScraper, store: JsonStore) -> None:
    # Série B
    try:
        data_b = scraper.get_all_serie_b()
        n_b = len(data_b.get("probabilities", {}).get("rebaixamento", []))
        if n_b > 0:
            path_b = store.save_ufmg_data("serie_b_2026", data_b)
            print(f"Saved UFMG statistical data Série B ({n_b} teams) -> {path_b}")
        else:
            print("Warning: UFMG Série B returned empty probabilities; keeping existing file.")
    except Exception as e:
        print(f"Failed to scrape UFMG Série B: {e}")

    # Série A
    try:
        data_a = scraper.get_all_serie_a()
        n_a = len(data_a.get("probabilities", {}).get("rebaixamento", []))
        if n_a > 0:
            path_a = store.save_ufmg_data("serie_a_2026", data_a)
            print(f"Saved UFMG statistical data Série A ({n_a} teams) -> {path_a}")
        else:
            print("Warning: UFMG Série A returned empty probabilities; keeping existing file.")
    except Exception as e:
        print(f"Failed to scrape UFMG Série A: {e}")


def _build_derived(team: str, store: JsonStore) -> None:
    """Offline: player_metrics + team_metrics + match_reports from resolve + raw."""
    players_master = store.load_players_master(team)
    matches_master = store.load_matches_master(team)
    advanced_season = store.load_advanced_season(team)
    advanced_matches = store.load_match_advanced(team)
    ogol_stats = store.load_ogol_stats(team)
    player_stats = store.load_player_stats(team)
    season_year = matches_master.get("season_year") or advanced_matches.get("season_year") or ""

    tier = "sofascore" if advanced_matches.get("matches") else "ogol"
    print(f"Building derive layer for '{team}' (tier={tier})")
    pm = build_player_metrics(players_master, advanced_season, advanced_matches, player_stats)
    print(f"  player_metrics: {len(pm)} players -> {store.save_player_metrics(team, pm, season_year)}")

    tm = build_team_metrics(matches_master, advanced_matches, ogol_stats, team)
    print(f"  team_metrics: {tm['summary']['matches']} matches, "
          f"pts {tm['summary']['points_real']} real vs {tm['summary']['points_expected']} xpts "
          f"-> {store.save_team_metrics(team, tm, season_year)}")

    mr = build_match_reports(matches_master, advanced_matches, players_master, ogol_stats, team)
    print(f"  match_reports: {len(mr)} reports -> {store.save_match_reports(team, mr, season_year)}")

    an = build_analysis(tm, mr, pm, TEAMS.get(team, {}).get("name", team.title()))
    n_str = len(an["season"]["strengths"]); n_weak = len(an["season"]["weaknesses"])
    print(f"  analysis: temporada {n_str} fortes / {n_weak} fracos, {len(an['matches'])} jogos "
          f"-> {store.save_analysis(team, an, season_year)}")


def _run_all(team: str, store: JsonStore) -> None:
    """Full resilient pipeline: each source in its own try/except, then --build."""
    steps = [
        ("ogol matches", lambda: _fetch_matches_ogol(team, OGolScraper(), store)),
        ("squad", lambda: _fetch_squad(team, OGolScraper(), TransfermarktScraper(), store)),
        ("squad (sofascore)", lambda: _fetch_squad_sofascore(team, SofaScoreScraper(), store)),
        ("player stats", lambda: _fetch_player_stats(team, None, OGolScraper(), store)),
        ("advanced (incremental)", lambda: _fetch_advanced(team, None, SofaScoreScraper(), store, incremental=True)),
        ("fixtures", lambda: _fetch_fixtures(team, SofaScoreScraper(), store)),
        ("standings", lambda: _fetch_standings(SofaScoreScraper(), store)),
        ("ufmg", lambda: _fetch_ufmg(UFMGScraper(), store)),
    ]
    for name, fn in steps:
        print(f"\n=== {name} ===")
        try:
            fn()
        except SystemExit as e:
            print(f"    Step '{name}' exited ({e}); continuing.")
        except Exception as e:
            print(f"    Step '{name}' failed ({type(e).__name__}: {e}); continuing.")
    print("\n=== build derived ===")
    _build_resolve(team, store)
    _build_derived(team, store)


def _club_name(events: list, team_id: int) -> str | None:
    for e in events:
        if e.get("home_id") == team_id:
            return e["home_team"]
        if e.get("away_id") == team_id:
            return e["away_team"]
    return None


def _build_resolve(team: str, store: JsonStore) -> None:
    """Offline: build players_master + matches_master from raw source JSON."""
    squad = store.load_squad(team)
    player_stats = store.load_player_stats(team)
    advanced_season = store.load_advanced_season(team)
    advanced_matches = store.load_match_advanced(team)
    tm_matches = store.load(team)
    ogol_matches = store.load_ogol_matches(team)
    ogol_stats = store.load_ogol_stats(team)

    print(f"Building resolve layer for '{team}'")
    print(f"  sources: squad={len(squad.get('players', []))} "
          f"player_stats={len(player_stats.get('players', []))} "
          f"advanced_season={len(advanced_season.get('players', []))} "
          f"advanced_matches={len(advanced_matches.get('matches', []))} "
          f"tm_matches={len(tm_matches)} ogol_matches={len(ogol_matches)} "
          f"ogol_stats={len(ogol_stats)}")

    # pre-join ogol_stats onto ogol_matches by match_url (attendance/referee)
    stats_by_url = {s.get("match_url"): s for s in ogol_stats if s.get("match_url")}
    for m in ogol_matches:
        s = stats_by_url.get(m.get("match_url"))
        if s:
            m.setdefault("attendance", s.get("attendance"))
            m.setdefault("referee", s.get("referee"))

    players = build_players_master(squad, player_stats, advanced_season)
    with_both = sum(1 for p in players if p.get("sofascore_id") and p.get("ogol_id"))
    print(f"  players_master: {len(players)} rows "
          f"({with_both} with sofascore_id + ogol_id)")

    matches = build_matches_master(tm_matches, ogol_matches, advanced_matches, team)
    tm_hits = sum(1 for m in matches if m["tm_matched"])
    ogol_hits = sum(1 for m in matches if m["ogol_matched"])
    print(f"  matches_master: {len(matches)} rows "
          f"({tm_hits} tm-matched, {ogol_hits} ogol-matched)")

    season_year = (
        advanced_matches.get("season_year")
        or squad.get("season_year")
        or ""
    )
    path = store.save_players_master(team, players, season_year)
    print(f"Saved {len(players)} players -> {path}")
    path = store.save_matches_master(team, matches, season_year)
    print(f"Saved {len(matches)} matches -> {path}")


def _fetch_stats(team: str, source: str, limit: int | None, scraper, store: JsonStore) -> None:
    save_key = f"{team}_{source}"
    matches = store.load(save_key)
    if not matches:
        print(f"No saved matches for '{team}' ({source}). Run without --stats first.")
        sys.exit(1)

    played = [m for m in matches if m.get("status") == "played" and m.get("match_url")]
    if limit:
        played = played[:limit]

    print(f"Fetching stats for {len(played)} played matches ({source})...")
    all_stats = []
    for i, m in enumerate(played, 1):
        print(f"  [{i}/{len(played)}] {m['date']} vs {m['opponent']} ({m['score']})")
        stats = scraper.get_match_stats(m["match_url"])
        if stats:
            all_stats.append(stats)
        else:
            print(f"    Warning: no stats parsed for {m['match_url']}")

    path = store.save_stats(save_key, all_stats)
    print(f"Saved {len(all_stats)} match stats → {path}")


def _build_league(store: JsonStore) -> None:
    """Agrega player_metrics de todos os clubes cadastrados com dado já coletado."""
    data = build_league_player_metrics(store)
    path = store.save_league_player_metrics(data)
    n = len(data["players"])
    print(f"💾 League player metrics: {n} jogadores de {data['teams_covered']} clubes -> {path}")
    if data["teams_covered"] < len(TEAMS):
        faltam = len(TEAMS) - data["teams_covered"]
        print(f"   ⚠️ {faltam} clube(s) ainda sem player_metrics coletado (rode --batch-full).")


def _discover_all_seasons() -> None:
    """Discover 2026 Série A/B SofaScore seasons for every team and cache them.

    Writes data/sofascore_seasons.json = {team_key: {label: {tournament_id, season_id}}}.
    Only tournaments 325 (Série A) and 390 (Série B) with a 2026 season are kept.
    """
    scraper = SofaScoreScraper()
    cache = _load_season_cache()
    wanted_tournaments = {325, 390}

    targets = [k for k, v in TEAMS.items() if (v.get("sofascore") or {}).get("team_id")]
    print(f"\n🔎 Descobrindo temporadas 2026 (SofaScore) para {len(targets)} clubes...\n")

    for idx, team in enumerate(targets, 1):
        cfg = TEAMS[team]["sofascore"]
        if cfg.get("seasons"):
            print(f"[{idx}/{len(targets)}] {team}: já configurado em config.py, pulando.")
            continue
        team_id = cfg["team_id"]
        try:
            rows = scraper.get_team_seasons(team_id)
        except Exception as e:
            print(f"[{idx}/{len(targets)}] {team}: falha ({type(e).__name__}: {e})")
            continue
        found = {}
        for r in rows:
            if r["tournament_id"] not in wanted_tournaments:
                continue
            if str(r.get("year") or "") not in ("2026", "26", "25/26"):
                continue
            found[f"{r['tournament_id']}-{r['season_id']}"] = {
                "tournament_id": r["tournament_id"],
                "season_id": r["season_id"],
            }
        if found:
            cache[team] = found
            labels = ", ".join(f"t{v['tournament_id']}/s{v['season_id']}" for v in found.values())
            print(f"[{idx}/{len(targets)}] {team}: {labels}")
        else:
            print(f"[{idx}/{len(targets)}] {team}: nenhuma temporada 2026 Série A/B encontrada.")

    os.makedirs("data", exist_ok=True)
    with open(_SEASON_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Cache salvo -> {_SEASON_CACHE} ({len(cache)} clubes)\n")


def _matches_master_filled(team: str, store: JsonStore) -> bool:
    try:
        mm = store.load_matches_master(team)
    except Exception:
        return False
    rows = mm.get("matches") if isinstance(mm, dict) else mm
    return bool(rows)


def _run_batch_full(division: str, store: JsonStore, skip: set[str] | None = None,
                    skip_existing: bool = False, limit_teams: int | None = None) -> None:
    """Esteira analítica COMPLETA em lote (todas as fontes) para vários clubes."""
    skip = skip or set()
    div_map = {"serie-a": "Série A", "serie-b": "Série B"}
    target_div = div_map.get(division)
    if target_div:
        teams_to_run = [k for k, v in TEAMS.items() if v.get("division") == target_div]
    else:
        teams_to_run = list(TEAMS.keys())

    teams_to_run = [t for t in teams_to_run if t not in skip]
    if skip_existing:
        teams_to_run = [t for t in teams_to_run if not _matches_master_filled(t, store)]
    if limit_teams:
        teams_to_run = teams_to_run[:limit_teams]

    print(f"\n🚀 Batch-Full: {len(teams_to_run)} clubes ({division.upper()})"
          f"{' | pulando ' + ', '.join(sorted(skip)) if skip else ''}\n")

    ok = 0
    for idx, team in enumerate(teams_to_run, 1):
        name = TEAMS.get(team, {}).get("name", team.title())
        print(f"\n{'=' * 70}\n[{idx}/{len(teams_to_run)}] ⚽ {name} ({team})\n{'=' * 70}")

        steps = []
        if TEAMS.get(team, {}).get("ogol"):
            steps.extend([
                ("ogol matches", lambda t=team: _fetch_matches_ogol(t, OGolScraper(), store)),
                ("squad", lambda t=team: _fetch_squad(t, OGolScraper(), TransfermarktScraper(), store)),
                ("player stats", lambda t=team: _fetch_player_stats(t, None, OGolScraper(), store)),
                ("ogol match stats", lambda t=team: _fetch_stats(t, "ogol", None, OGolScraper(), store)),
            ])
        steps.append(
            ("squad (sofascore)", lambda t=team: _fetch_squad_sofascore(t, SofaScoreScraper(), store))
        )
        if _team_seasons(team):
            steps.append(
                ("advanced (incremental)",
                 lambda t=team: _fetch_advanced(t, None, SofaScoreScraper(), store, incremental=True))
            )
        else:
            print("   (sem temporada SofaScore — xG virá do fallback ogol_stats)")

        for sname, fn in steps:
            print(f"\n--- {sname} ---")
            try:
                fn()
            except SystemExit as e:
                print(f"    Step '{sname}' exited ({e}); continuing.")
            except Exception as e:
                print(f"    Step '{sname}' failed ({type(e).__name__}: {e}); continuing.")

        print("\n--- resolve + derived + análise ---")
        try:
            _build_resolve(team, store)
            _build_derived(team, store)
            ok += 1
            print(f"   ✓ {name} concluído.")
        except Exception as e:
            print(f"   ⚠️ {name}: build falhou ({type(e).__name__}: {e})")

    print(f"\n🎉 Batch-Full concluído: {ok}/{len(teams_to_run)} clubes.\n")


if __name__ == "__main__":
    main()
