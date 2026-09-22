"""Camada League: ranking/comparação de jogadores na liga inteira (40 clubes).

O merge de transferência de clube e o cálculo de percentil por posição agora
vivem em SQL (storage/db.py::query_league_player_metrics, via PERCENT_RANK())
— é exatamente o tipo de agregação que faz sentido rodar no banco em vez de
pandas em Python a cada carregamento de página. Este módulo fica só com o
filtro/ordenação de exibição (top_by_metric/find_player) e o wrapper que
mantém `python main.py --league` exportando o JSON de auditoria.
"""

from datetime import datetime, timezone
from typing import List, Optional

from storage import db as _db

_MIN_MINUTES = _db.MIN_MINUTES


def load_all_player_metrics(store, divisions: Optional[List[str]] = None) -> List[dict]:
    """Dataset da liga inteira, direto do banco (fonte de verdade) — `store`
    fica só pra manter a assinatura estável pros chamadores existentes."""
    return _db.query_league_player_metrics(divisions=divisions)


def build_league_player_metrics(store) -> dict:
    """Monta o payload de export (usado por `--league` / league_player_metrics.json,
    mantido como artefato de auditoria — o scout consulta o banco direto)."""
    rows = load_all_player_metrics(store)
    n_teams = len({r["team_key"] for r in rows if r.get("team_key")})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "teams_covered": n_teams,
        "players": rows,
    }


def top_by_metric(
    league_rows: List[dict], metric: str, position_group: Optional[str] = None,
    division: Optional[str] = None, min_minutes: int = _MIN_MINUTES, n: int = 20,
) -> List[dict]:
    """Ranking simples da liga por uma métrica per-90 (ou %), com filtros comuns
    de posição/divisão/minutagem mínima — usado pela página de scout."""
    out = [
        r for r in league_rows
        if (r.get(metric) is not None)
        and (r.get("minutes") or 0) >= min_minutes
        and (position_group is None or r.get("position_group") == position_group)
        and (division is None or r.get("division") == division)
    ]
    out.sort(key=lambda r: r[metric], reverse=True)
    return out[:n]


def find_player(league_rows: List[dict], name_query: str) -> List[dict]:
    """Busca case-insensitive por substring no nome — para a página de scout."""
    q = name_query.strip().lower()
    if not q:
        return []
    return [r for r in league_rows if q in (r.get("name") or "").lower()]
