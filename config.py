"""Configuração central de clubes, torneios e parâmetros de coleta.

Plataforma de análise do Campeonato Brasileiro — Série A e Série B completas (40 clubes),
com identificadores oficiais no SofaScore (fonte primária de dados avançados/xG/eventos)
e, para Fortaleza EC/Ceará SC, também OGol e Transfermarkt (elenco e valores de mercado).
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
    # SÉRIE A 2026 (20 clubes) — sofascore_tournament_id 325 / season_id 87678
    # =========================================================================
    "athletico": {
        "name": "Athletico",
        "division": "Série A",
        "state": "PR",
        "sofascore": {
            "team_id": 1967,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "atletico-mineiro": {
        "name": "Atlético Mineiro",
        "division": "Série A",
        "state": "MG",
        "sofascore": {
            "team_id": 1977,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "bahia": {
        "name": "Bahia",
        "division": "Série A",
        "state": "BA",
        "sofascore": {
            "team_id": 1955,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "botafogo": {
        "name": "Botafogo",
        "division": "Série A",
        "state": "RJ",
        "sofascore": {
            "team_id": 1958,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "chapecoense": {
        "name": "Chapecoense",
        "division": "Série A",
        "state": "SC",
        "sofascore": {
            "team_id": 21845,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "corinthians": {
        "name": "Corinthians",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 1957,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "coritiba": {
        "name": "Coritiba",
        "division": "Série A",
        "state": "PR",
        "sofascore": {
            "team_id": 1982,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "cruzeiro": {
        "name": "Cruzeiro",
        "division": "Série A",
        "state": "MG",
        "sofascore": {
            "team_id": 1954,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "flamengo": {
        "name": "Flamengo",
        "division": "Série A",
        "state": "RJ",
        "sofascore": {
            "team_id": 5981,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "fluminense": {
        "name": "Fluminense",
        "division": "Série A",
        "state": "RJ",
        "sofascore": {
            "team_id": 1961,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "gremio": {
        "name": "Grêmio",
        "division": "Série A",
        "state": "RS",
        "sofascore": {
            "team_id": 5926,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "internacional": {
        "name": "Internacional",
        "division": "Série A",
        "state": "RS",
        "sofascore": {
            "team_id": 1966,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "mirassol": {
        "name": "Mirassol",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 21982,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "palmeiras": {
        "name": "Palmeiras",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 1963,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "red-bull-bragantino": {
        "name": "Red Bull Bragantino",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 1999,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "remo": {
        "name": "Remo",
        "division": "Série A",
        "state": "PA",
        "sofascore": {
            "team_id": 2012,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "santos": {
        "name": "Santos",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 1968,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "sao-paulo": {
        "name": "São Paulo",
        "division": "Série A",
        "state": "SP",
        "sofascore": {
            "team_id": 1981,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "vasco-da-gama": {
        "name": "Vasco da Gama",
        "division": "Série A",
        "state": "RJ",
        "sofascore": {
            "team_id": 1974,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    "vitoria": {
        "name": "Vitória",
        "division": "Série A",
        "state": "BA",
        "sofascore": {
            "team_id": 1962,
            "seasons": {
                "serie-a-2026": {"tournament_id": 325, "season_id": 87678},
            },
        },
    },
    # =========================================================================
    # SÉRIE B 2026 (20 clubes) — sofascore_tournament_id 390 / season_id 89840
    # Fortaleza EC e Ceará SC (foco principal da plataforma) têm cobertura extra
    # via OGol e Transfermarkt (elenco, valores de mercado).
    # =========================================================================
    "america-mineiro": {
        "name": "América Mineiro",
        "division": "Série B",
        "state": "MG",
        "sofascore": {
            "team_id": 1973,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "athletic-club": {
        "name": "Athletic Club",
        "division": "Série B",
        "state": "MG",
        "sofascore": {
            "team_id": 342775,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "atletico-goianiense": {
        "name": "Atlético Goianiense",
        "division": "Série B",
        "state": "GO",
        "sofascore": {
            "team_id": 7314,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "avai": {
        "name": "Avaí",
        "division": "Série B",
        "state": "SC",
        "sofascore": {
            "team_id": 7315,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "botafogo-sp": {
        "name": "Botafogo-SP",
        "division": "Série B",
        "state": "SP",
        "sofascore": {
            "team_id": 1979,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "ceara": {
        "name": "Ceará SC",
        "division": "Série B",
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
    "crb": {
        "name": "CRB",
        "division": "Série B",
        "state": "AL",
        "aliases": ["Clube De Regatas Brasil", "Regatas Brasil", "CRB"],
        "sofascore": {
            "team_id": 22032,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "criciuma": {
        "name": "Criciúma",
        "division": "Série B",
        "state": "SC",
        "sofascore": {
            "team_id": 1984,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "cuiaba": {
        "name": "Cuiabá",
        "division": "Série B",
        "state": "MT",
        "sofascore": {
            "team_id": 49202,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "fortaleza": {
        "name": "Fortaleza EC",
        "division": "Série B",
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
    "goias": {
        "name": "Goiás",
        "division": "Série B",
        "state": "GO",
        "sofascore": {
            "team_id": 1960,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "gremio-novorizontino": {
        "name": "Grêmio Novorizontino",
        "division": "Série B",
        "state": "SP",
        "sofascore": {
            "team_id": 135514,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "juventude": {
        "name": "Juventude",
        "division": "Série B",
        "state": "RS",
        "sofascore": {
            "team_id": 1980,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "londrina": {
        "name": "Londrina",
        "division": "Série B",
        "state": "PR",
        "sofascore": {
            "team_id": 2022,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "nautico": {
        "name": "Náutico",
        "division": "Série B",
        "state": "PE",
        "sofascore": {
            "team_id": 2011,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "operario-pr": {
        "name": "Operário-PR",
        "division": "Série B",
        "state": "PR",
        "sofascore": {
            "team_id": 39634,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "ponte-preta": {
        "name": "Ponte Preta",
        "division": "Série B",
        "state": "SP",
        "sofascore": {
            "team_id": 1969,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "sao-bernardo": {
        "name": "São Bernardo",
        "division": "Série B",
        "state": "SP",
        "sofascore": {
            "team_id": 47504,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "sport-recife": {
        "name": "Sport Recife",
        "division": "Série B",
        "state": "PE",
        "sofascore": {
            "team_id": 1959,
            "seasons": {
                "serie-b-2026": {"tournament_id": 390, "season_id": 89840},
            },
        },
    },
    "vila-nova-fc": {
        "name": "Vila Nova FC",
        "division": "Série B",
        "state": "GO",
        "sofascore": {
            "team_id": 2021,
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
