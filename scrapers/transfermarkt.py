import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from scrapers.base import BaseScraper
from models.match import Match
from models.match_stats import CardEvent, GoalEvent, MatchStats, SubEvent


BASE_URL = "https://www.transfermarkt.com.br"
_RANK_RE = re.compile(r"\(\d+\.\)$")
_WAPPEN_ID_RE = re.compile(r"/wappen/\w+/(\d+)\.png")
# Skip tables that are not match schedules (season selector, balance, last games)
_SKIP_HEADINGS = {"informação", "balanço", "os últimos", "selecionar"}


class TransfermarktScraper(BaseScraper):
    def get_matches(self, team_slug: str, team_id: int) -> List[Match]:
        url = f"{BASE_URL}/{team_slug}/spielplan/verein/{team_id}/plus/1"
        response = self._get(url)
        return self._parse_matches(response.text)

    def get_squad(self, team_slug: str, team_id: int) -> List[dict]:
        url = f"{BASE_URL}/{team_slug}/kader/verein/{team_id}"
        response = self._get(url)
        return self._parse_squad(response.text)

    def _parse_squad(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", class_="items")
        if not table or not table.find("tbody"):
            return []

        players = []
        for row in table.find("tbody").find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 6:
                continue
            posrela = cells[1]
            inline_table = posrela.find("table", class_="inline-table")
            if not inline_table:
                continue
            link = inline_table.find("a")
            name = link.get_text(strip=True) if link else None
            position_rows = inline_table.find_all("tr")
            position = position_rows[1].get_text(strip=True) if len(position_rows) > 1 else None
            if not name:
                continue

            jersey_number = cells[0].get_text(strip=True) or None
            age_m = re.search(r"\d+", cells[2].get_text(strip=True))
            age = int(age_m.group()) if age_m else None
            flag = cells[3].find("img")
            nationality = flag.get("alt") if flag else None
            contract_until = cells[4].get_text(strip=True) or None
            market_value_eur = _parse_market_value(cells[5].get_text(strip=True))

            players.append({
                "name": name,
                "position": position,
                "jersey_number": jersey_number,
                "age": age,
                "nationality": nationality,
                "contract_until": contract_until,
                "market_value_eur": market_value_eur,
            })
        return players

    def _parse_matches(self, html: str) -> List[Match]:
        soup = BeautifulSoup(html, "lxml")
        matches: List[Match] = []

        for box in soup.find_all("div", class_="box"):
            h2 = box.find("h2")
            competition = h2.get_text(strip=True) if h2 else "Unknown"

            if any(competition.lower().startswith(skip) for skip in _SKIP_HEADINGS):
                continue

            table = box.find("table")
            if not table:
                continue

            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 11:
                    continue

                match = self._parse_row(cells, competition)
                if match:
                    matches.append(match)

        return matches

    def _parse_row(self, cells: List[Tag], competition: str) -> Optional[Match]:
        try:
            date = cells[1].get_text(strip=True) or None
            home_name = cells[4].get_text(strip=True)
            away_name = cells[6].get_text(strip=True)

            if not home_name or not away_name:
                return None

            # hauptlink class marks the team we're viewing
            home_is_ours = "hauptlink" in cells[4].get("class", [])
            if home_is_ours:
                opponent = _RANK_RE.sub("", away_name).strip()
                home_away = "H"
            else:
                opponent = _RANK_RE.sub("", home_name).strip()
                home_away = "A"

            score, match_url = self._extract_score(cells[10])

            return Match(
                date=date,
                opponent=opponent,
                score=score,
                home_away=home_away,
                competition=competition,
                status="played" if score else "upcoming",
                match_url=match_url,
            )
        except (IndexError, AttributeError):
            return None

    def _extract_score(self, cell: Tag) -> Tuple[Optional[str], Optional[str]]:
        text = cell.get_text(strip=True)
        if not text or not re.search(r"\d:\d", text):
            return None, None
        link = cell.find("a")
        match_url = BASE_URL + link["href"] if link and link.get("href") else None
        return text, match_url

    def get_match_stats(self, match_url: str) -> Optional[MatchStats]:
        response = self._get(match_url)
        return self._parse_match_stats(response.text, match_url)

    def _parse_match_stats(self, html: str, match_url: str) -> Optional[MatchStats]:
        soup = BeautifulSoup(html, "lxml")

        home_id, away_id, home_name, away_name = self._extract_team_ids(soup)
        if not home_id or not away_id:
            return None

        referee, stadium, attendance, round_name = self._extract_match_info(soup)

        stats = MatchStats(
            match_url=match_url,
            home_team=home_name,
            away_team=away_name,
            referee=referee,
            stadium=stadium,
            attendance=attendance,
            round=round_name,
        )

        for h2 in soup.find_all("h2"):
            heading = h2.get_text(strip=True)
            box = h2.find_parent("div", class_="box")
            if not box:
                continue
            if heading == "Gols":
                stats.goals = self._parse_goals(box, home_id)
            elif heading == "Ação disciplinar":
                stats.cards = self._parse_cards(box, home_id)
            elif heading == "Substituições":
                stats.substitutions = self._parse_subs(box, home_id)

        return stats

    def _extract_team_ids(self, soup: BeautifulSoup):
        seen = []
        for a in soup.find_all("a", href=re.compile(r"/startseite/verein/\d+")):
            m = re.search(r"/startseite/verein/(\d+)", a["href"])
            name = a.get_text(strip=True)
            if m and name and m.group(1) not in [t[0] for t in seen]:
                seen.append((m.group(1), name))
            if len(seen) == 2:
                break
        if len(seen) < 2:
            return None, None, "", ""
        return seen[0][0], seen[1][0], seen[0][1], seen[1][1]

    def _wappen_to_side(self, action: Tag, home_id: str) -> str:
        wappen = action.find("div", class_="sb-aktion-wappen")
        if not wappen:
            return "home"
        img = wappen.find("img")
        if not img:
            return "home"
        m = _WAPPEN_ID_RE.search(img.get("src", ""))
        if m and m.group(1) == home_id:
            return "home"
        return "away"

    def _parse_goals(self, box: Tag, home_id: str) -> List[GoalEvent]:
        goals = []
        for action in box.find_all("div", class_="sb-aktion"):
            minute = action.find("div", class_="sb-aktion-uhr")
            score_el = action.find("div", class_="sb-aktion-spielstand")
            aktion = action.find("div", class_="sb-aktion-aktion")
            if not aktion or not score_el:
                continue
            links = aktion.find_all("a", class_="wichtig")
            if not links:
                continue
            scorer = links[0].get_text(strip=True)
            assist = links[1].get_text(strip=True) if len(links) > 1 else None
            goals.append(GoalEvent(
                minute=minute.get_text(strip=True) or None if minute else None,
                cumulative_score=score_el.get_text(strip=True),
                scorer=scorer,
                assist=assist,
                team=self._wappen_to_side(action, home_id),
            ))
        return goals

    def _parse_cards(self, box: Tag, home_id: str) -> List[CardEvent]:
        cards = []
        for action in box.find_all("div", class_="sb-aktion"):
            minute = action.find("div", class_="sb-aktion-uhr")
            aktion = action.find("div", class_="sb-aktion-aktion")
            if not aktion:
                continue
            player_link = aktion.find("a", class_="wichtig")
            if not player_link:
                continue
            player = player_link.get_text(strip=True)
            # Card type and reason are in text nodes after the <br>
            raw = aktion.get_text(" ", strip=True)
            card_type = "yellow"
            if "vermelho" in raw.lower():
                if "amarelo" in raw.lower():
                    card_type = "yellow_red"
                else:
                    card_type = "red"
            reason_m = re.search(r",\s*(.+)$", raw)
            reason = reason_m.group(1).strip() if reason_m else None
            cards.append(CardEvent(
                minute=minute.get_text(strip=True) or None if minute else None,
                player=player,
                card_type=card_type,
                reason=reason,
                team=self._wappen_to_side(action, home_id),
            ))
        return cards

    def _parse_subs(self, box: Tag, home_id: str) -> List[SubEvent]:
        subs = []
        for action in box.find_all("div", class_="sb-aktion"):
            minute = action.find("div", class_="sb-aktion-uhr")
            player_in_el = action.find("span", class_="sb-aktion-wechsel-ein")
            player_out_el = action.find("span", class_="sb-aktion-wechsel-aus")
            if not player_in_el or not player_out_el:
                continue
            player_in = player_in_el.get_text(strip=True)
            out_raw = player_out_el.get_text(strip=True)
            # Format: "PlayerName, Reason" or just "PlayerName"
            out_parts = out_raw.split(",", 1)
            player_out = out_parts[0].strip()
            reason = out_parts[1].strip() if len(out_parts) > 1 else None
            subs.append(SubEvent(
                minute=minute.get_text(strip=True) or None if minute else None,
                player_in=player_in,
                player_out=player_out,
                reason=reason,
                team=self._wappen_to_side(action, home_id),
            ))
        return subs

    def _extract_match_info(self, soup: BeautifulSoup):
        referee = stadium = attendance = round_name = None
        spieldaten = soup.find("div", class_="sb-spieldaten")
        if not spieldaten:
            return referee, stadium, attendance, round_name
        text = spieldaten.get_text(" ", strip=True)
        # Round: "N. rodada" at start
        round_m = re.search(r"(\d+\.\s*rodada)", text, re.IGNORECASE)
        if round_m:
            round_name = round_m.group(1)
        # Stadium: after score block, before pipe or "torcedores"
        stadium_m = re.search(r"Estádio\s+([^|]+?)(?:\||$|\d)", text)
        if stadium_m:
            stadium = stadium_m.group(1).strip()
        else:
            # Generic: text after last ")" and before "|torcedores"
            stadium_m2 = re.search(r"\)\s+([^|]+?)\|\s*[\d.]", text)
            if stadium_m2:
                stadium = stadium_m2.group(1).strip()
        # Attendance
        att_m = re.search(r"([\d.]+)\s*torcedores", text)
        if att_m:
            attendance = int(att_m.group(1).replace(".", ""))
        # Referee
        ref_m = re.search(r"Árbitro:\s*(.+?)(?:\s*$|\s*\|)", text)
        if ref_m:
            referee = ref_m.group(1).strip()
        return referee, stadium, attendance, round_name


def _parse_market_value(text: str) -> Optional[int]:
    # Formats: "€ 300 mil", "€ 1.20 mi.", "-"
    m = re.search(r"([\d.,]+)\s*(mil|mi\.)", text)
    if not m:
        return None
    amount, unit = m.group(1), m.group(2)
    if unit == "mi.":
        return int(float(amount.replace(",", ".")) * 1_000_000)
    return int(float(amount.replace(".", "").replace(",", ".")) * 1_000)
