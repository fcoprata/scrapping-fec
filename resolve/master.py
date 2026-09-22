"""Resolve layer: unify player ids across sources and join matches best-effort.

Pure functions only. No network calls, no DataFrame use. Dict/loop style
mirroring ``models/aggregate.py``. Joins are by key, never by list index.
"""

import re

from name_match import normalize_name

# Extract the numeric OGol player id from a profile_url whose path looks like
# /jogador/<slug>/<digits>
_OGOL_ID_RE = re.compile(r"/jogador/[^/]+/(\d+)")

# Match result -> points
_POINTS = {"W": 3, "D": 1, "L": 0}

# Known player aliases between SofaScore and OGol/Transfermarkt
_PLAYER_ALIASES = {
    "mauricio lima": "mauricio mucuri",
    "mauricio mucuri": "mauricio lima",
}


def _ogol_id_from_url(url):
    if not url:
        return None
    m = _OGOL_ID_RE.search(url)
    return m.group(1) if m else None


def _fuzzy_lookup(by_name, norm):
    """Exact-then-alias-then-substring lookup."""
    hit = by_name.get(norm)
    if hit is not None:
        return hit

    # Check aliases
    alias = _PLAYER_ALIASES.get(norm)
    if alias and alias in by_name:
        return by_name[alias]

    return next(
        (v for k, v in by_name.items() if k in norm or norm in k),
        None,
    )


def _longest(*names):
    best = ""
    for n in names:
        if n and len(n) > len(best):
            best = n
    return best


# ---------------------------------------------------------------------------
# players_master
# ---------------------------------------------------------------------------
def build_players_master(squad: dict, player_stats: dict, advanced_season: dict) -> list:
    """One row per normalized name, unioning squad / player_stats / advanced_season."""
    squad_players = (squad or {}).get("players", []) or []
    pstats_players = (player_stats or {}).get("players", []) or []
    adv_players = (advanced_season or {}).get("players", []) or []

    squad_by_name = {normalize_name(p["name"]): p for p in squad_players if p.get("name")}
    pstats_by_name = {normalize_name(p["name"]): p for p in pstats_players if p.get("name")}
    adv_by_name = {normalize_name(p["name"]): p for p in adv_players if p.get("name")}

    squad_by_id = {str(p["player_id"]): p for p in squad_players if p.get("player_id")}
    adv_by_id = {str(p["player_id"]): p for p in adv_players if p.get("player_id")}

    rows = []
    seen_keys = set()

    # union of normalized names across the three sources, squad first
    ordered_keys = list(squad_by_name)
    for k in list(pstats_by_name) + list(adv_by_name):
        if k not in squad_by_name:
            ordered_keys.append(k)

    for key in ordered_keys:
        if key in seen_keys:
            continue

        sq = _fuzzy_lookup(squad_by_name, key)
        ps = _fuzzy_lookup(pstats_by_name, key)
        adv = _fuzzy_lookup(adv_by_name, key)

        # Fallback de cruzamento por SofaScore player_id caso o nome varie ligeiramente
        if sq is None and adv is not None and adv.get("player_id"):
            sq = squad_by_id.get(str(adv.get("player_id")))
        if adv is None and sq is not None and sq.get("player_id"):
            adv = adv_by_id.get(str(sq.get("player_id")))

        # avoid emitting a second row when a non-squad name matched a
        # squad row already produced under its own key
        if sq is not None and key not in squad_by_name:
            sq_key = normalize_name(sq["name"])
            if sq_key in seen_keys:
                continue

        seen_keys.add(key)

        ogol_id = None
        if sq is not None:
            ogol_id = _ogol_id_from_url(sq.get("profile_url"))
        if ogol_id is None and ps is not None:
            ogol_id = _ogol_id_from_url(ps.get("profile_url"))

        sofascore_id = adv.get("player_id") if adv is not None else None
        if not sofascore_id and sq is not None and sq.get("player_id"):
            sofascore_id = str(sq.get("player_id"))

        name = _longest(
            sq.get("name") if sq is not None else "",
            ps.get("name") if ps is not None else "",
            adv.get("name") if adv is not None else "",
        ) or key

        rows.append(
            {
                "key": key,
                "name": name,
                "sofascore_id": sofascore_id,
                "ogol_id": ogol_id,
                "position_group": (
                    (sq.get("position") if sq is not None else None)
                    or (adv.get("position_group") if adv is not None else None)
                ),
                "position_detail": sq.get("position_detail") if sq is not None else None,
                "jersey_number": sq.get("jersey_number") if sq is not None else None,
                "age": sq.get("age") if sq is not None else None,
                "nationality": sq.get("nationality") if sq is not None else "Brasil",
                "market_value_eur": sq.get("market_value_eur") if sq is not None else None,
                "contract_until": sq.get("contract_until") if sq is not None else None,
                "active": sq.get("active") if sq is not None else (True if not squad_players else None),
                "in_squad": sq is not None if squad_players else True,
                "in_ogol_stats": ps is not None,
                "in_advanced": adv is not None,
            }
        )

    return rows


# ---------------------------------------------------------------------------
# matches_master
# ---------------------------------------------------------------------------
def _iso_date(raw):
    """Normalize a date string to YYYY-MM-DD.

    Handles ISO (``2026-03-21``) and Transfermarkt (``sáb 21/03/2026``).
    """
    if not raw:
        return None
    token = raw.strip().split()[-1]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", token):
        return token
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", token)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return token


_KNOWN_TEAM_ALIASES = {
    "crb": {"clube de regatas brasil", "regatas brasil", "crb"},
    "athletico": {"athletico paranaense", "atletico paranaense", "cap"},
    "atletico-mineiro": {"atletico mineiro", "atlético mineiro", "cam", "galo"},
    "atletico-goianiense": {"atletico goianiense", "atlético goianiense", "acg"},
    "botafogo-sp": {"botafogo sp", "botafogo-sp", "botafogo futebol clube"},
    "red-bull-bragantino": {"bragantino", "red bull bragantino", "rb bragantino"},
    "sport-recife": {"sport recife", "sport club do recife", "sport"},
    "vila-nova-fc": {"vila nova", "vila nova fc", "vila nova go"},
    "america-mineiro": {"america mineiro", "américa mineiro", "america mg"},
    "operario-pr": {"operario pr", "operário pr", "operario ferrovario"},
}


def _team_aliases(team: str) -> set:
    """Lowercase substrings that identify a team in a home/away name string."""
    from config import TEAMS

    out = {team.lower().replace("-", " "), team.lower()}
    cfg = TEAMS.get(team, {})
    name = (cfg.get("name") or "").lower()
    for al in cfg.get("aliases", []):
        out.add(al.lower())
    for al in _KNOWN_TEAM_ALIASES.get(team, []):
        out.add(al.lower())
    # drop common club-type suffixes/prefixes so "Ceará SC" -> "ceará"
    _STOPWORDS = {"club", "clube", "esporte", "futebol", "football", "sporting", "de", "do", "da", "para", "fc", "ec", "sc", "ac"}
    for noise in (" ec", " fc", " sc", " ac", " sac", "ec ", "fc ", "sc ",
                  " esporte clube", " futebol clube", " sporting club",
                  " sporting", " clube", "-"):
        name = name.replace(noise, " ")
    for tok in name.split():
        if len(tok) >= 3 and tok not in _STOPWORDS:
            out.add(tok)
    ogol_slug = (cfg.get("ogol") or {}).get("slug")
    if ogol_slug:
        out.add(ogol_slug.lower().replace("-", " "))
    return {a.strip() for a in out if a.strip() and a.strip() not in _STOPWORDS}


def _is_home_side(home_team: str, aliases: set) -> bool:
    hs = (home_team or "").lower()
    return any(a in hs for a in aliases)


def _opponent(home_team, away_team, aliases):
    home_team = home_team or ""
    away_team = away_team or ""
    if _is_home_side(home_team, aliases):
        return away_team
    if _is_home_side(away_team, aliases):
        return home_team
    return away_team


def _parse_score(score, is_home):
    """Return (goals_for, goals_against, points, formatted_score) or (None, None, None, None)."""
    if not score:
        return None, None, None, None
    parts = re.split(r"[:\-x]", str(score).strip())
    if len(parts) != 2:
        return None, None, None, None
    try:
        a, b = int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None, None, None, None
    home_goals, away_goals = a, b
    if is_home:
        gf, ga = home_goals, away_goals
    else:
        gf, ga = away_goals, home_goals
    if gf > ga:
        pts = _POINTS["W"]
    elif gf == ga:
        pts = _POINTS["D"]
    else:
        pts = _POINTS["L"]
    return gf, ga, pts, f"{home_goals}:{away_goals}"


def _fuzzy_opp_lookup(opponents_by_date, date, opp_norm):
    candidates = opponents_by_date.get(date, [])
    if not candidates:
        return None
    for opp_name, obj in candidates:
        if opp_name == opp_norm or opp_name in opp_norm or opp_norm in opp_name:
            return obj
        # token overlap match
        if set(opp_name.split()) & set(opp_norm.split()):
            return obj
    if len(candidates) == 1:
        return candidates[0][1]
    return None


def _ogol_spine(ogol_matches: list, aliases: set) -> list:
    """Build matches_master rows straight from OGol when no SofaScore advanced data.

    OGol match ``score`` is home-away formatted; ``home_away`` ('H'/'A') gives the side.
    No xG (OGol has none) — those columns are None and downstream degrades gracefully.
    """
    rows = []
    for m in ogol_matches:
        if m.get("status") != "played":
            continue
        date = _iso_date(m.get("date"))
        ha = str(m.get("home_away") or "").upper()
        is_home = ha.startswith("H")
        gf, ga, points, score = _parse_score(m.get("score"), is_home)
        rows.append({
            "event_id": m.get("match_url"),
            "date": date,
            "competition": m.get("competition"),
            "round": m.get("round"),
            "is_home": is_home,
            "opponent": m.get("opponent"),
            "score": score,
            "goals_for": gf,
            "goals_against": ga,
            "points": points,
            "xg_for": None,
            "xg_against": None,
            "xgot_for": None,
            "xgot_against": None,
            "tm_matched": False,
            "ogol_matched": True,
            "ogol_url": m.get("match_url"),
            "attendance": m.get("attendance"),
            "referee": m.get("referee"),
        })
    rows.sort(key=lambda r: r.get("date") or "")
    return rows


def build_matches_master(
    tm_matches: list, ogol_matches: list, advanced_matches: dict, team: str = "fortaleza"
) -> list:
    """Canonical match rows for ``team``.

    Spine is SofaScore advanced matches when present (full xG tier); otherwise
    OGol played matches (score/points tier). ``tm_matches`` / ``ogol_matches`` are
    joined to the advanced spine by ``(date, normalized opponent)``.
    """
    adv_matches = (advanced_matches or {}).get("matches", []) or []
    tm_matches = tm_matches or []
    ogol_matches = ogol_matches or []
    aliases = _team_aliases(team)

    if not adv_matches:
        return _ogol_spine(ogol_matches, aliases)

    tm_by_date = {}
    for m in tm_matches:
        d = _iso_date(m.get("date"))
        tm_by_date.setdefault(d, []).append((normalize_name(m.get("opponent") or ""), m))

    ogol_by_date = {}
    for m in ogol_matches:
        d = _iso_date(m.get("date"))
        ogol_by_date.setdefault(d, []).append((normalize_name(m.get("opponent") or ""), m))

    rows = []
    for adv in adv_matches:
        home_team = adv.get("home_team") or ""
        away_team = adv.get("away_team") or ""
        is_home = _is_home_side(home_team, aliases)
        opponent = _opponent(home_team, away_team, aliases)
        date = _iso_date(adv.get("date"))
        opp_norm = normalize_name(opponent)

        xg_home = adv.get("xg_home")
        xg_away = adv.get("xg_away")
        xgot_home = adv.get("xgot_home")
        xgot_away = adv.get("xgot_away")
        if is_home:
            xg_for, xg_against = xg_home, xg_away
            xgot_for, xgot_against = xgot_home, xgot_away
        else:
            xg_for, xg_against = xg_away, xg_home
            xgot_for, xgot_against = xgot_away, xgot_home

        tm = _fuzzy_opp_lookup(tm_by_date, date, opp_norm)
        ogol = _fuzzy_opp_lookup(ogol_by_date, date, opp_norm)

        score = None
        goals_for = goals_against = points = None

        if tm is not None and tm.get("score"):
            goals_for, goals_against, points, score = _parse_score(tm.get("score"), is_home)
        elif ogol is not None and ogol.get("score"):
            goals_for, goals_against, points, score = _parse_score(ogol.get("score"), is_home)

        # 1st Fallback: official SofaScore match score if present in advanced match
        if (goals_for is None or goals_against is None) and adv.get("home_score") is not None and adv.get("away_score") is not None:
            hs = int(adv["home_score"])
            aws = int(adv["away_score"])
            gf = hs if is_home else aws
            ga = aws if is_home else hs
            goals_for, goals_against = gf, ga
            score = f"{hs}:{aws}"
            if gf > ga:
                points = _POINTS["W"]
            elif gf == ga:
                points = _POINTS["D"]
            else:
                points = _POINTS["L"]

        # 2nd Fallback: derive exact match result from shots / goals when TM/OGol don't have score
        if goals_for is None or goals_against is None:
            shots = adv.get("shots", [])
            gf = sum(
                1 for s in shots
                if s.get("is_goal") and (
                    (s.get("is_home") and is_home) or (not s.get("is_home") and not is_home)
                )
            )
            ga = sum(
                1 for s in shots
                if s.get("is_goal") and (
                    (s.get("is_home") and not is_home) or (not s.get("is_home") and is_home)
                )
            )
            goals_for, goals_against = gf, ga
            home_g = gf if is_home else ga
            away_g = ga if is_home else gf
            score = f"{home_g}:{away_g}"
            if goals_for > goals_against:
                points = _POINTS["W"]
            elif goals_for == goals_against:
                points = _POINTS["D"]
            else:
                points = _POINTS["L"]

        attendance = ogol.get("attendance") if ogol is not None else None
        referee = ogol.get("referee") if ogol is not None else None
        ogol_url = ogol.get("match_url") if ogol is not None else None

        rows.append(
            {
                "event_id": adv.get("event_id"),
                "date": date,
                "competition": adv.get("competition"),
                "round": adv.get("round"),
                "is_home": is_home,
                "opponent": opponent,
                "score": score,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "points": points,
                "xg_for": xg_for,
                "xg_against": xg_against,
                "xgot_for": xgot_for,
                "xgot_against": xgot_against,
                "tm_matched": tm is not None,
                "ogol_matched": ogol is not None,
                "ogol_url": ogol_url,
                "attendance": attendance,
                "referee": referee,
            }
        )

    return rows
