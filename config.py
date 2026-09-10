"""Configuração central de clubes, torneios e parâmetros de coleta.

Plataforma Fortaleza Analytics — cobertura de Fortaleza EC (principal) e Ceará SC,
com identificadores oficiais no SofaScore, OGol e Transfermarkt.
"""

SLEEP_SECONDS = 2

COMPETITIONS = {
    "serie-a": {
        "name": "Brasileirão Série A",
        "sofascore_tournament_id": 325,
        "ogol_slug": "brasileirao-serie-a",
    },
    "serie-b": {
        "name": "Brasileirão Série B",
        "sofascore_tournament_id": 390,
        "ogol_slug": "brasileirao-serie-b",
    },
    "copa-do-brasil": {
        "name": "Copa do Brasil",
        "sofascore_tournament_id": 373,
        "ogol_slug": "copa-do-brasil",
    },
    "copa-do-nordeste": {
        "name": "Copa do Nordeste",
        "sofascore_tournament_id": 2081,
        "ogol_slug": "copa-do-nordeste",
    },
}

TEAMS = {
    # =========================================================================
    # SÉRIE A (20 Clubes Oficiais)
    # =========================================================================
    "fortaleza": {
        "name": "Fortaleza EC",
        "division": "Série A",
        "state": "CE",
        "transfermarkt": {"id": 10870, "slug": "fortaleza-esporte-clube"},
        "ogol": {"slug": "fortaleza"},
        "sofascore": {
            "team_id": 2020,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "ceara": {
        "name": "Ceará SC",
        "division": "Série A",
        "state": "CE",
        "transfermarkt": {"id": 2029, "slug": "ceara-sporting-club"},
        "ogol": {"slug": "ceara"},
        "sofascore": {
            "team_id": 2001,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
}


def get_team_config(team_key: str) -> dict:
    """Retorna a configuração completa do clube a partir do slug."""
    return TEAMS.get(team_key, {})


def list_teams_by_division(division: str) -> dict:
    """Filtra equipes por divisão ('Série A', 'Série B')."""
    return {k: v for k, v in TEAMS.items() if v.get("division") == division}


def get_all_divisions() -> list:
    """Retorna lista de divisões cadastradas."""
    return ["Série A", "Série B"]

