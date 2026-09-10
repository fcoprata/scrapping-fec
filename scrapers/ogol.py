import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from scrapers.base import BaseScraper
from models.match import Match
from models.match_stats import GoalEvent, MatchStats
from models.player import Player
from models.player_stats import CompetitionStats, PlayerSeasonStats


BASE_URL = "https://www.ogol.com.br"
_RESULT_MAP = {"V": "played", "D": "played", "E": "played", "h2h": "upcoming"}
_JOGADOR_RE = re.compile(r"^/jogador/([^/]+)/(\d+)")
_AGE_RE = re.compile(r"(\d+)\s*anos")
_SEASON_YEAR_RE = re.compile(r"Resumo da Temporada\((\d{4})\)")
_EPOCA_ID_RE = re.compile(r"epoca_id=(\d+)")


class OGolScraper(BaseScraper):
    def get_squad(self, team_slug: str) -> Tuple[List[Player], str, str]:
        """Returns (players, season_year, epoca_id)."""
        url = f"{BASE_URL}/equipe/{team_slug}"
        response = self._get(url)
        soup = BeautifulSoup(response.text, "lxml")

        year_h2 = next((h for h in soup.find_all("h2") if _SEASON_YEAR_RE.search(h.get_text(strip=True))), None)
        season_year = _SEASON_YEAR_RE.search(year_h2.get_text(strip=True)).group(1) if year_h2 else ""

        epoca_link = soup.find("a", href=re.compile(r"todos-os-jogos.*epoca_id=(\d+)"))
        epoca_id = _EPOCA_ID_RE.search(epoca_link["href"]).group(1) if epoca_link else ""

        players = self._parse_squad(soup)
        return players, season_year, epoca_id

    def get_player_match_log(self, slug: str, player_id: str, epoca_id: str) -> Tuple[int, int, Optional[float]]:
        """Returns (starts, substitute_appearances, avg_rating) for the given season."""
        url = f"{BASE_URL}/jogador/{slug}/{player_id}/jogos?epoca_id={epoca_id}"
        response = self._get(url)
        return self._parse_match_log(response.text)

    def _parse_match_log(self, html: str) -> Tuple[int, int, Optional[float]]:
        soup = BeautifulSoup(html, "lxml")
        h2 = next((h for h in soup.find_all("h2") if h.get_text(strip=True) == "Jogos"), None)
        if not h2:
            return 0, 0, None
        card = h2.find_parent("div", class_="card-data")
        box = card.find("div", class_="box_table") if card else None
        table = box.find("table") if box else None
        if not table or not table.find("tbody"):
            return 0, 0, None

        starts = subs = 0
        ratings: List[float] = []
        for row in table.find("tbody").find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 10:
                continue
            appearance_span = row.find("span", class_="icn_zerozero")
            if appearance_span:
                classes = appearance_span.get("class") or []
                if "green" in classes:
                    starts += 1
                elif "red" in classes:
                    subs += 1
            else:
                # Goalkeepers: no starter/sub badge, just raw minutes. Treat any
                # minutes played as a start (keepers are essentially never subbed).
                minutes_cell = cells[8]
                if re.fullmatch(r"\d+", minutes_cell.get_text(strip=True) or ""):
                    starts += 1
            rating_cell = cells[-2]
            rating_div = rating_cell.find("div")
            if rating_div:
                rm = re.search(r"[\d.]+", rating_div.get_text(strip=True))
                if rm:
                    ratings.append(float(rm.group()))

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        return starts, subs, avg_rating

    def get_player_season_stats(
        self, player_id: str, name: str, profile_url: str, position: str
    ) -> Optional[PlayerSeasonStats]:
        response = self._get(profile_url)
        return self._parse_player_season_stats(response.text, player_id, name, profile_url, position)

    def get_matches(self, team_slug: str) -> List[Match]:
        epoca_id = self._get_current_epoca(team_slug)
        url = f"{BASE_URL}/equipe/{team_slug}/todos-os-jogos?grp=1&epoca_id={epoca_id}"
        response = self._get(url)
        return self._parse_matches(response.text)

    def get_match_stats(self, match_url: str) -> Optional[MatchStats]:
        response = self._get(match_url)
        stats = self._parse_match_stats(response.text, match_url)
        # 2026 match pages dropped "Faltas" from the summary table; the per-player
        # breakdown page still has it. Fetch + sum when the summary lacked it.
        if stats is not None and stats.fouls_home is None:
            fh, fa = self._fetch_match_fouls(match_url)
            stats.fouls_home, stats.fouls_away = fh, fa
        return stats

    def _fetch_match_fouls(self, match_url: str) -> Tuple[Optional[int], Optional[int]]:
        m = re.search(r"/(\d+)/?$", match_url or "")
        if not m:
            return None, None
        match_id = m.group(1)
        url = f"{BASE_URL}/match_player_stats.php?id={match_id}&one_stat=sfaltas"
        try:
            response = self._get(url)
        except Exception:
            return None, None
        return self._parse_player_stat_totals(response.text)

    @staticmethod
    def _parse_player_stat_totals(html: str) -> Tuple[Optional[int], Optional[int]]:
        """Sum a per-player two-column stat table into (home_total, away_total).

        Rows look like ``['', '2 César Martins', '', 'Luiz Fernando 3', '']`` —
        home cell has the count prefixed, away cell has it suffixed; '-' = none.
        """
        soup = BeautifulSoup(html, "lxml")
        home_total = away_total = None
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            hsum = asum = 0
            counted = False
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue
                hm = re.match(r"\s*(\d+)", cells[1].get_text(strip=True))
                am = re.search(r"(\d+)\s*$", cells[3].get_text(strip=True))
                if hm:
                    hsum += int(hm.group(1)); counted = True
                if am:
                    asum += int(am.group(1)); counted = True
            if counted:
                home_total, away_total = hsum, asum
                break
        return home_total, away_total

    def _get_current_epoca(self, team_slug: str) -> str:
        url = f"{BASE_URL}/equipe/{team_slug}"
        response = self._get(url)
        soup = BeautifulSoup(response.text, "lxml")
        # The team landing page links the *current* season via its
        # "todos-os-jogos?...epoca_id=N" link. A bare epoca_id= match instead
        # grabs the previous (completed) season from the history dropdown.
        epoca_link = soup.find("a", href=re.compile(r"todos-os-jogos.*epoca_id=(\d+)"))
        if epoca_link:
            m = _EPOCA_ID_RE.search(epoca_link["href"])
            if m:
                return m.group(1)
        # Fallback: highest epoca_id anywhere on the page (newest season).
        ids = [int(x) for x in _EPOCA_ID_RE.findall(response.text)]
        return str(max(ids)) if ids else "155"

    def _parse_matches(self, html: str) -> List[Match]:
        soup = BeautifulSoup(html, "lxml")
        matches: List[Match] = []

        tables = soup.find_all("table", class_="zztable")
        # Second table is the matches list (first is competition summary)
        match_table = tables[1] if len(tables) > 1 else (tables[0] if tables else None)
        if not match_table:
            return matches

        for row in match_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            result_code = cells[0].get_text(strip=True)
            status = _RESULT_MAP.get(result_code, "played")
            date = cells[1].get_text(strip=True) or None
            home_away_raw = cells[3].get_text(strip=True)  # "(C)" or "(F)"
            home_away = "H" if home_away_raw == "(C)" else "A"
            opponent = cells[5].get_text(strip=True)
            score_raw = cells[6].get_text(strip=True)
            score = score_raw if re.search(r"\d-\d", score_raw) else None
            competition = cells[7].get_text(strip=True)

            link = row.find("a", href=re.compile(r"/jogo/"))
            match_url = BASE_URL + link["href"] if link else None

            if not opponent:
                continue

            matches.append(Match(
                date=date,
                opponent=opponent,
                score=score,
                home_away=home_away,
                competition=competition,
                status=status,
                match_url=match_url,
            ))

        return matches

    def _parse_match_stats(self, html: str, match_url: str) -> Optional[MatchStats]:
        soup = BeautifulSoup(html, "lxml")

        home_team, away_team = self._extract_teams(soup)
        if not home_team or not away_team:
            return None

        referee, stadium, attendance = self._extract_match_info(soup)
        goals = self._parse_goals(soup)
        stat_map = self._parse_stats_table(soup)

        return MatchStats(
            match_url=match_url,
            home_team=home_team,
            away_team=away_team,
            referee=referee,
            stadium=stadium,
            attendance=attendance,
            goals=goals,
            possession_home_pct=stat_map.get("possession_home_pct"),
            possession_away_pct=stat_map.get("possession_away_pct"),
            shots_home=stat_map.get("shots_home"),
            shots_away=stat_map.get("shots_away"),
            shots_on_target_home=stat_map.get("shots_on_target_home"),
            shots_on_target_away=stat_map.get("shots_on_target_away"),
            corners_home=stat_map.get("corners_home"),
            corners_away=stat_map.get("corners_away"),
            fouls_home=stat_map.get("fouls_home"),
            fouls_away=stat_map.get("fouls_away"),
        )

    def _extract_teams(self, soup: BeautifulSoup) -> Tuple[str, str]:
        home_el = soup.find("div", class_=lambda c: c and "match-header-team" in c and "right" in c)
        away_el = soup.find("div", class_=lambda c: c and "match-header-team" in c and "left" in c)
        home = home_el.get_text(strip=True) if home_el else ""
        away = away_el.get_text(strip=True) if away_el else ""
        return home, away

    def _parse_goals(self, soup: BeautifulSoup) -> List[GoalEvent]:
        goals: List[GoalEvent] = []
        for side, team_key in [("right", "home"), ("left", "away")]:
            scorers_div = soup.find(
                "div",
                class_=lambda c: c and "match-header-scorers" in c and side in c,
            )
            if not scorers_div:
                continue
            # Alternate between <a> (player) and <span.time> (minute)
            links = scorers_div.find_all("a")
            times = scorers_div.find_all("span", class_="time")
            for player_tag, time_tag in zip(links, times):
                goals.append(GoalEvent(
                    minute=time_tag.get_text(strip=True) or None,
                    cumulative_score="",  # not available in this section
                    scorer=player_tag.get_text(strip=True),
                    assist=None,
                    team=team_key,
                ))
        return goals

    def _parse_stats_table(self, soup: BeautifulSoup) -> dict:
        result = {}
        for table in soup.find_all("table"):
            if "Posse" not in table.get_text():
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [th.get_text(strip=True) for th in rows[0].find_all(["td", "th"])]
            for header, cell in zip(headers, rows[1].find_all(["td", "th"])):
                # Values are NavigableString children of the font-size span, split by team color circles
                span = cell.find("span", style=lambda s: s and "font-size: 17px" in s)
                texts = [str(c).strip() for c in span.children if isinstance(c, NavigableString) and str(c).strip()] if span else []
                result.update(_parse_stat_value(header, texts))
            break
        return result

    def _extract_match_info(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        referee = stadium = attendance = None
        for card in soup.find_all("div", class_="card-data"):
            h2 = card.find("h2")
            if not h2:
                continue
            title = h2.get_text(strip=True)
            if "rbitro" in title:
                a = card.find("a", href=re.compile(r"referee\.php"))
                if a:
                    referee = a.get_text(strip=True)
            elif title == "Estádio":
                stadium_div = card.find("div", id="stadium")
                if stadium_div:
                    a = stadium_div.find("div", class_="name")
                    if a:
                        link = a.find("a")
                        stadium = link.get_text(strip=True) if link else None
        for div in soup.find_all("div"):
            m = re.search(r"([\d.]+)\s*espectadores", div.get_text(strip=True), re.IGNORECASE)
            if m:
                attendance = int(m.group(1).replace(".", ""))
                break
        return referee, stadium, attendance


    def _parse_player_season_stats(
        self, html: str, player_id: str, name: str, profile_url: str, position: str
    ) -> Optional[PlayerSeasonStats]:
        soup = BeautifulSoup(html, "lxml")
        h2 = next((h for h in soup.find_all("h2") if "resumo da temporada" in h.get_text(strip=True)), None)
        card = h2.find_parent("div", class_="card-data") if h2 else None
        competitions: List[CompetitionStats] = []
        total_appearances = total_minutes = total_goals = total_assists = 0
        total_goals_conceded = None
        table = card.find("table", class_="zztable") if card else None
        if table:
            # 3rd stat column is "GM" (gols marcados) for outfield players but
            # "GC" (gols sofridos) for goalkeepers — same position, different meaning.
            header_cells = table.find("thead").find_all(["td", "th"])
            third_col_label = header_cells[3].get_text(strip=True) if len(header_cells) > 3 else "GM"
            is_conceded = third_col_label == "GC"

            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                label_cell = cells[0]
                values = [_to_int(c.get_text(strip=True)) for c in cells[1:5]]
                appearances, minutes, third_stat, assists = values
                goals = 0 if is_conceded else third_stat
                conceded = third_stat if is_conceded else None
                if "totals" in (label_cell.get("class") or []):
                    total_appearances, total_minutes, total_assists = appearances, minutes, assists
                    total_goals = goals
                    total_goals_conceded = conceded
                else:
                    link = label_cell.find("a")
                    competition = link.get_text(strip=True) if link else label_cell.get_text(strip=True)
                    competitions.append(CompetitionStats(
                        competition=competition,
                        appearances=appearances,
                        minutes=minutes,
                        goals=goals,
                        assists=assists,
                        goals_conceded=conceded,
                    ))

        return PlayerSeasonStats(
            player_id=player_id,
            name=name,
            profile_url=profile_url,
            position=position,
            total_appearances=total_appearances,
            total_minutes=total_minutes,
            total_goals=total_goals,
            total_assists=total_assists,
            total_goals_conceded=total_goals_conceded,
            competitions=competitions,
        )

    def _parse_squad(self, soup: BeautifulSoup) -> List[Player]:
        players: List[Player] = []

        h2 = next((h for h in soup.find_all("h2") if h.get_text(strip=True) == "elenco"), None)
        if not h2:
            return players
        card = h2.find_parent("div", class_="card-data")
        if not card:
            return players
        body = card.find("div", class_="card-data__body")
        if not body:
            return players

        position = "Desconhecido"
        for child in body.find_all(recursive=False):
            classes = child.get("class") or []
            if "section" in classes:
                position = child.get_text(strip=True)
            elif "staff_line" in classes:
                for staff in child.find_all("div", class_="staff", recursive=False):
                    player = self._parse_staff_entry(staff, position)
                    if player:
                        players.append(player)
        return players

    def _parse_staff_entry(self, staff: Tag, position: str) -> Optional[Player]:
        link = staff.find("a", href=_JOGADOR_RE)
        if not link:
            return None
        m = _JOGADOR_RE.search(link["href"])
        slug, player_id = m.group(1), m.group(2)
        active = "inactive" not in (staff.get("class") or [])

        number_el = staff.find("div", class_="number")
        jersey_number = number_el.get_text(strip=True) if number_el else None
        jersey_number = jersey_number if jersey_number and jersey_number != "-" else None

        photo_el = staff.find("div", class_="photo")
        photo_url = None
        if photo_el and photo_el.get("style"):
            pm = re.search(r"url\('([^']+)'\)", photo_el["style"])
            photo_url = pm.group(1) if pm else None

        nat_flag = staff.find("span", class_=re.compile(r"^flag:"))
        nationality = None
        if nat_flag:
            flag_link = nat_flag.find_parent("a")
            if flag_link and flag_link.get("title"):
                nationality = flag_link["title"]

        name_div = staff.find("div", class_="name")
        age = market_value_eur = None
        if name_div:
            info_span = name_div.find("span", recursive=False)
            if info_span:
                info_text = info_span.get_text(strip=True)
                age_m = _AGE_RE.search(info_text)
                age = int(age_m.group(1)) if age_m else None
                market_value_eur = _parse_market_value(info_text)

        return Player(
            player_id=player_id,
            slug=slug,
            name=link.get_text(strip=True),
            position=position,
            jersey_number=jersey_number,
            age=age,
            nationality=nationality,
            market_value_eur=market_value_eur,
            photo_url=photo_url,
            profile_url=BASE_URL + link["href"],
            active=active,
        )


def _to_int(text: str) -> int:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else 0


def _parse_market_value(text: str) -> Optional[int]:
    m = re.search(r"([\d.]+)\s*(mil|M)\s*€", text)
    if not m:
        return None
    unit = m.group(2)
    if unit == "M":
        # e.g. "3.00 M" -> "." is a decimal separator here
        return int(float(m.group(1)) * 1_000_000)
    # e.g. "300 mil" -> "." would be a thousands separator (rare at this scale)
    return int(float(m.group(1).replace(".", "")) * 1_000)


def _parse_stat_value(header: str, texts: list) -> dict:
    """Parse [home_text, away_text] pair from stat cell NavigableStrings."""
    if len(texts) < 2:
        return {}
    home_raw, away_raw = texts[0], texts[1]
    h = header.lower()
    if "posse" in h:
        hm = re.search(r"(\d+)", home_raw)
        am = re.search(r"(\d+)", away_raw)
        if hm and am:
            return {"possession_home_pct": int(hm.group(1)), "possession_away_pct": int(am.group(1))}
    if "chute" in h or "remate" in h:
        # Format: "(on_target) total" per side
        hm = re.search(r"\((\d+)\)\s*(\d+)", home_raw)
        am = re.search(r"(\d+)\s*\((\d+)\)", away_raw)
        if hm and am:
            return {
                "shots_home": int(hm.group(2)), "shots_away": int(am.group(1)),
                "shots_on_target_home": int(hm.group(1)), "shots_on_target_away": int(am.group(2)),
            }
    if "escanteio" in h or "canto" in h:
        hm = re.search(r"\d+", home_raw)
        am = re.search(r"\d+", away_raw)
        if hm and am:
            return {"corners_home": int(hm.group()), "corners_away": int(am.group())}
    if "falta" in h:
        hm = re.search(r"\d+", home_raw)
        am = re.search(r"\d+", away_raw)
        if hm and am:
            return {"fouls_home": int(hm.group()), "fouls_away": int(am.group())}
    return {}
