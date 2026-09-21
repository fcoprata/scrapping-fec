"""Scraper para dados estatísticos e probabilidades do Departamento de Matemática da UFMG.

Fontes:
- Série B: https://www.mat.ufmg.br/futebol/serie-b/
- Série A: https://www.mat.ufmg.br/futebol/serie-a/
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from name_match import normalize_name
from scrapers.base import BaseScraper


class UFMGScraper(BaseScraper):
    """Coleta estatísticas avançadas e probabilidades calculadas pela UFMG para as Séries A e B."""

    BASE_URL = "https://www.mat.ufmg.br/futebol"

    ENDPOINTS_SERIE_B = {
        "rebaixamento": "/rebaixamento-serie-b/",
        "campeao": "/campeao-serie-b/",
        "acesso": "/classificacao-para-primeira-divisao/",
        "pts_rebaixamento": "/rebaixamento-por-pontuacao-serie-b/",
        "pts_acesso": "/classificacao-para-primeira-divisao-serie-b/",
        "pts_campeao": "/campeao-por-pontuacao-serie-b/",
        "mandante": "/classificacao-como-mandante-serie-b/",
        "visitante": "/classificacao-como-visitante-serie-b/",
        "ultimas_10": "/classificacao-das-ultimas-10-rodadas-serie-b/",
        "turno": "/classificacao-do-turno-serie-b/",
        "returno": "/classificacao-do-returno-serie-b/",
        "ataque": "/melhor-ataque-serie-b/",
        "defesa": "/melhor-defesa-serie-b/",
    }

    ENDPOINTS_SERIE_A = {
        "rebaixamento": "/rebaixamento_seriea/",
        "campeao": "/campeao_seriea/",
        "sulamericana": "/classificacao-para-sulamericana_seriea/",
        "mandante": "/classificacao-como-mandante_seriea/",
        "visitante": "/classificacao-como-visitante_seriea/",
        "ultimas_10": "/classificacao-das-ultimas-10-rodadas_seriea/",
        "turno": "/classificacao-do-turno_seriea/",
        "returno": "/classificacao-do-returno_seriea/",
        "ataque": "/melhor-ataque_seriea/",
        "defesa": "/melhor-defesa_seriea/",
    }

    # Compatibilidade retroativa
    ENDPOINTS = ENDPOINTS_SERIE_B

    def __init__(self):
        super().__init__()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False

        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_soup(self, endpoint_key: str, endpoints_dict: Optional[dict] = None) -> Optional[BeautifulSoup]:
        endpoints = endpoints_dict or self.ENDPOINTS
        path = endpoints.get(endpoint_key, "")
        if not path:
            return None
        url = f"{self.BASE_URL}{path}"
        try:
            resp = self._get(url, timeout=20)
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"    ⚠️ Aviso UFMG: falha ao requisitar '{endpoint_key}' ({url}): {e}")
            return None

    @staticmethod
    def _parse_table(table) -> tuple[str, List[str], List[List[str]]]:
        caption_el = table.find("caption")
        caption = caption_el.get_text(" ", strip=True) if caption_el else ""
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                rows.append(cells)
        return caption, headers, rows

    @staticmethod
    def _to_float(val: str, default: float = 0.0) -> float:
        try:
            cleaned = val.replace("%", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _to_int(val: str, default: int = 0) -> int:
        try:
            return int(val.strip())
        except (ValueError, TypeError):
            return default

    def get_probabilities(self, endpoint_key: str, endpoints_dict: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Extrai tabela de probabilidade simples por time (N, Times, Prob(%))."""
        soup = self._get_soup(endpoint_key, endpoints_dict)
        if not soup:
            return []
        table = soup.find("table")
        if not table:
            return []

        _, _, rows = self._parse_table(table)
        results = []
        for r in rows:
            if len(r) >= 3:
                rank = self._to_int(r[0])
                team_name = r[1]
                prob = self._to_float(r[2])
                results.append({
                    "rank": rank,
                    "team": team_name,
                    "norm_team": normalize_name(team_name),
                    "prob": prob,
                })
        return results

    def get_access_probabilities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extrai as 2 tabelas da página de classificação da Série B: Acesso Direto (Top 2) e Playoffs."""
        soup = self._get_soup("acesso")
        if not soup:
            return {"direct": [], "playoffs": []}
        tables = soup.find_all("table")
        output = {"direct": [], "playoffs": []}
        for i, table in enumerate(tables):
            caption, _, rows = self._parse_table(table)
            cap_lower = caption.lower()
            key = "direct" if ("diretamente" in cap_lower or i == 0) else "playoffs"
            parsed = []
            for r in rows:
                if len(r) >= 3:
                    rank = self._to_int(r[0])
                    team_name = r[1]
                    prob = self._to_float(r[2])
                    parsed.append({
                        "rank": rank,
                        "team": team_name,
                        "norm_team": normalize_name(team_name),
                        "prob": prob,
                    })
            output[key] = parsed
        return output

    def get_points_probabilities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extrai tabelas de corte por pontuação (pontos necessários vs probabilidade)."""
        output = {"rebaixamento": [], "direct": [], "playoffs": [], "campeao": []}

        # 1. Rebaixamento
        try:
            soup_reb = self._get_soup("pts_rebaixamento")
            if soup_reb:
                table_reb = soup_reb.find("table")
                if table_reb:
                    _, _, rows = self._parse_table(table_reb)
                    output["rebaixamento"] = [
                        {"points": self._to_int(r[0]), "prob": self._to_float(r[1])}
                        for r in rows if len(r) >= 2
                    ]
        except Exception as e:
            print(f"Warning: erro ao coletar pts_rebaixamento: {e}")

        # 2. Acesso Direto e Playoffs
        try:
            soup_acc = self._get_soup("pts_acesso")
            if soup_acc:
                tables_acc = soup_acc.find_all("table")
                for i, t in enumerate(tables_acc):
                    cap, _, rows = self._parse_table(t)
                    cap_lower = cap.lower()
                    key = "direct" if ("primeiros" in cap_lower or i == 0) else "playoffs"
                    output[key] = [
                        {"points": self._to_int(r[0]), "prob": self._to_float(r[1])}
                        for r in rows if len(r) >= 2
                    ]
        except Exception as e:
            print(f"Warning: erro ao coletar pts_acesso: {e}")

        # 3. Campeão
        try:
            soup_camp = self._get_soup("pts_campeao")
            if soup_camp:
                table_camp = soup_camp.find("table")
                if table_camp:
                    _, _, rows = self._parse_table(table_camp)
                    output["campeao"] = [
                        {"points": self._to_int(r[0]), "prob": self._to_float(r[1])}
                        for r in rows if len(r) >= 2
                    ]
        except Exception as e:
            print(f"Warning: erro ao coletar pts_campeao: {e}")

        return output

    def get_standings_table(self, endpoint_key: str, endpoints_dict: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Extrai tabelas completas de classificação (mandante, visitante, ultimas 10, turno, returno).

        Headers típicos: N, Times, PG, J, V, E, D, GF, GC, S, R
        """
        soup = self._get_soup(endpoint_key, endpoints_dict)
        if not soup:
            return []
        table = soup.find("table")
        if not table:
            return []

        _, headers, rows = self._parse_table(table)
        results = []
        for r in rows:
            if len(r) >= 11:
                team_name = r[1]
                results.append({
                    "position": self._to_int(r[0]),
                    "team": team_name,
                    "norm_team": normalize_name(team_name),
                    "points": self._to_int(r[2]),
                    "played": self._to_int(r[3]),
                    "wins": self._to_int(r[4]),
                    "draws": self._to_int(r[5]),
                    "losses": self._to_int(r[6]),
                    "goals_for": self._to_int(r[7]),
                    "goals_against": self._to_int(r[8]),
                    "goal_diff": self._to_int(r[9]),
                    "efficiency": self._to_float(r[10]),
                })
        return results

    def get_all_serie_b(self) -> Dict[str, Any]:
        """Coleta e estrutura todos os dados disponíveis da Série B na UFMG."""
        print("Scraping UFMG Série B...")
        eps = self.ENDPOINTS_SERIE_B
        relegation = self.get_probabilities("rebaixamento", eps)
        champion = self.get_probabilities("campeao", eps)
        access = self.get_access_probabilities()
        points_cutoffs = self.get_points_probabilities()

        home_standings = self.get_standings_table("mandante", eps)
        away_standings = self.get_standings_table("visitante", eps)
        last_10 = self.get_standings_table("ultimas_10", eps)
        turno = self.get_standings_table("turno", eps)
        returno = self.get_standings_table("returno", eps)

        # Compilar mapa consolidado por time
        teams_map = {}
        for row in relegation:
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_rebaixamento"] = row["prob"]

        for row in champion:
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_campeao"] = row["prob"]

        for row in access.get("direct", []):
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_acesso_direto"] = row["prob"]

        for row in access.get("playoffs", []):
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_playoffs"] = row["prob"]

        return {
            "season_year": "2026",
            "competition": "serie-b",
            "scraped_at": datetime.now().isoformat(),
            "teams_summary": list(teams_map.values()),
            "probabilities": {
                "rebaixamento": relegation,
                "campeao": champion,
                "acesso_direto": access.get("direct", []),
                "playoffs": access.get("playoffs", []),
            },
            "points_cutoffs": points_cutoffs,
            "standings": {
                "home": home_standings,
                "away": away_standings,
                "last_10_rounds": last_10,
                "first_half": turno,
                "second_half": returno,
            },
        }

    def get_all_serie_a(self) -> Dict[str, Any]:
        """Coleta e estrutura todos os dados disponíveis da Série A na UFMG."""
        print("Scraping UFMG Série A...")
        eps = self.ENDPOINTS_SERIE_A
        relegation = self.get_probabilities("rebaixamento", eps)
        champion = self.get_probabilities("campeao", eps)
        sulamericana = self.get_probabilities("sulamericana", eps)

        home_standings = self.get_standings_table("mandante", eps)
        away_standings = self.get_standings_table("visitante", eps)
        last_10 = self.get_standings_table("ultimas_10", eps)
        turno = self.get_standings_table("turno", eps)
        returno = self.get_standings_table("returno", eps)

        teams_map = {}
        for row in relegation:
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_rebaixamento"] = row["prob"]

        for row in champion:
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_campeao"] = row["prob"]

        for row in sulamericana:
            nt = row["norm_team"]
            teams_map.setdefault(nt, {"team": row["team"], "norm_team": nt})
            teams_map[nt]["prob_sulamericana"] = row["prob"]

        return {
            "season_year": "2026",
            "competition": "serie-a",
            "scraped_at": datetime.now().isoformat(),
            "teams_summary": list(teams_map.values()),
            "probabilities": {
                "rebaixamento": relegation,
                "campeao": champion,
                "sulamericana": sulamericana,
            },
            "standings": {
                "home": home_standings,
                "away": away_standings,
                "last_10_rounds": last_10,
                "first_half": turno,
                "second_half": returno,
            },
        }
