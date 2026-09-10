"""Pacote de Inteligência Tática e Análise de Desempenho.

Contém:
- engine: Motor de regras determinísticas táticas (offline).
- narrative: Gerador de sínteses executivas determinísticas (temporada e partida).
"""

from analysis.engine import (
    build_analysis,
    build_season_analysis,
    build_match_analysis,
)
from analysis.narrative import (
    generate_match_narrative,
    generate_season_narrative,
    narrate,
)

__all__ = [
    "build_analysis",
    "build_season_analysis",
    "build_match_analysis",
    "generate_match_narrative",
    "generate_season_narrative",
    "narrate",
]
