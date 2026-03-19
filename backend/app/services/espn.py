"""ESPN API client with in-memory TTL cache."""

import json
import ssl
import time
import urllib.request
from typing import Any

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/v2/sports/basketball"

SPORTS = {
    "M": "mens-college-basketball",
    "W": "womens-college-basketball",
}

# SSL context for macOS
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

# Simple TTL cache: {key: (data, expires_at)}
_cache: dict[str, tuple[Any, float]] = {}


def _fetch(url: str, ttl: int = 30) -> Any:
    """Fetch URL with TTL cache. Returns parsed JSON."""
    now = time.time()
    if url in _cache:
        data, expires = _cache[url]
        if now < expires:
            return data

    req = urllib.request.Request(url, headers={"User-Agent": "UbunifuMadness/1.0"})
    with urllib.request.urlopen(req, context=_ctx, timeout=10) as resp:
        data = json.loads(resp.read())

    _cache[url] = (data, now + ttl)
    return data


def get_scoreboard(date: str | None = None, gender: str = "M") -> list[dict]:
    """Get today's games. date format: YYYYMMDD.

    Fetches both regular-season (groups=50) and conference tournament
    (no group filter) games, deduplicating by event ID.
    """
    sport = SPORTS.get(gender, SPORTS["M"])

    # Fetch regular-season D1 games
    url_regular = f"{ESPN_BASE}/{sport}/scoreboard?groups=50&limit=100"
    if date:
        url_regular += f"&dates={date}"
    data_regular = _fetch(url_regular, ttl=30)

    # Fetch conf tournament / postseason games (no group filter)
    url_all = f"{ESPN_BASE}/{sport}/scoreboard?limit=200"
    if date:
        url_all += f"&dates={date}"
    data_all = _fetch(url_all, ttl=30)

    # Merge and deduplicate by event ID
    seen_ids: set[str] = set()
    all_events = []
    for event in data_regular.get("events", []) + data_all.get("events", []):
        eid = event["id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            all_events.append(event)

    games = []

    for event in all_events:
        comp = event["competitions"][0]
        status = comp["status"]["type"]

        teams_data = []
        for competitor in comp["competitors"]:
            t = competitor["team"]
            records = competitor.get("records", [])
            overall_record = records[0]["summary"] if records else None
            logos = t.get("logos", [])
            logo = t.get("logo") or (logos[0]["href"] if logos else None)
            teams_data.append({
                "espnId": int(t["id"]),
                "name": t.get("displayName", t.get("shortDisplayName", "")),
                "abbreviation": t.get("abbreviation", ""),
                "logo": logo,
                "color": f"#{t['color']}" if t.get("color") else None,
                "score": int(competitor.get("score", 0)),
                "homeAway": competitor.get("homeAway", ""),
                "record": overall_record,
                "rank": competitor.get("curatedRank", {}).get("current"),
            })

        # Sort so home team is second
        home = next((t for t in teams_data if t["homeAway"] == "home"), teams_data[-1] if teams_data else None)
        away = next((t for t in teams_data if t["homeAway"] == "away"), teams_data[0] if teams_data else None)

        broadcasts = comp.get("broadcasts", [])
        tv = broadcasts[0]["names"][0] if broadcasts and broadcasts[0].get("names") else None

        # Detect game type: regular, conf_tourney, or tourney (NCAA)
        notes = comp.get("notes", [])
        headline = notes[0].get("headline", "") if notes else ""
        tournament_id = comp.get("tournamentId")
        season_type = event.get("season", {}).get("type")
        headline_upper = headline.upper()
        if ("NCAA" in headline_upper or "MARCH MADNESS" in headline_upper
                or "FIRST FOUR" in headline_upper):
            game_type = "tourney"
        elif season_type == 3:
            # ESPN postseason type — NCAA tournament, NIT, etc.
            game_type = "tourney"
        elif tournament_id or "Tournament" in headline:
            game_type = "conf_tourney"
        else:
            game_type = "regular"

        games.append({
            "id": event["id"],
            "date": event["date"],
            "venue": comp.get("venue", {}).get("fullName"),
            "status": status["name"],  # STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_FINAL
            "statusDetail": comp["status"].get("type", {}).get("shortDetail", status.get("description", "")),
            "clock": comp["status"].get("displayClock"),
            "period": comp["status"].get("period"),
            "broadcast": tv,
            "away": away,
            "home": home,
            "gameType": game_type,
            "headline": headline or None,
        })

    return games


def get_game_summary(game_id: str, gender: str = "M") -> dict:
    """Get box score for a specific game."""
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"{ESPN_BASE}/{sport}/summary?event={game_id}"
    data = _fetch(url, ttl=60)

    result = {
        "gameId": game_id,
        "teams": [],
        "players": [],
    }

    # Box score teams
    boxscore = data.get("boxscore", {})
    for team_data in boxscore.get("teams", []):
        team = team_data.get("team", {})
        stats = {s["label"]: s["displayValue"] for s in team_data.get("statistics", [])}
        result["teams"].append({
            "name": team.get("displayName", ""),
            "abbreviation": team.get("abbreviation", ""),
            "logo": team.get("logo", ""),
            "stats": stats,
        })

    # Player stats
    for team_players in boxscore.get("players", []):
        team = team_players.get("team", {})
        for stat_group in team_players.get("statistics", []):
            labels = stat_group.get("labels", [])
            for athlete in stat_group.get("athletes", []):
                player = athlete.get("athlete", {})
                stat_values = athlete.get("stats", [])
                player_stats = dict(zip(labels, stat_values))
                result["players"].append({
                    "espnId": int(player["id"]) if player.get("id") else None,
                    "team": team.get("abbreviation", ""),
                    "name": player.get("displayName", ""),
                    "position": player.get("position", {}).get("abbreviation", ""),
                    "stats": player_stats,
                })

    return result


def get_rankings(gender: str = "M") -> list[dict]:
    """Get AP Top 25 rankings."""
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"{ESPN_BASE}/{sport}/rankings"
    data = _fetch(url, ttl=3600)  # 1 hour cache

    rankings = []
    for ranking_group in data.get("rankings", []):
        if "AP" not in ranking_group.get("name", "").upper():
            continue

        for entry in ranking_group.get("ranks", []):
            team = entry.get("team", {})
            logos = team.get("logos", [])
            # In rankings, displayName is missing; combine location + name
            full_name = team.get("displayName") or f"{team.get('location', '')} {team.get('name', '')}".strip()
            rankings.append({
                "rank": entry["current"],
                "previousRank": entry.get("previous"),
                "points": entry.get("points"),
                "firstPlaceVotes": entry.get("firstPlaceVotes"),
                "record": entry.get("recordSummary", ""),
                "trend": entry.get("trend", ""),
                "team": {
                    "espnId": int(team["id"]),
                    "name": full_name,
                    "abbreviation": team.get("abbreviation", ""),
                    "logo": logos[0]["href"] if logos else None,
                },
            })
        break  # Only AP poll

    return rankings


def get_team_schedule(espn_id: int, gender: str = "M") -> list[dict]:
    """Get team schedule from ESPN."""
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"{ESPN_BASE}/{sport}/teams/{espn_id}/schedule"
    data = _fetch(url, ttl=3600)

    schedule = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {})

        opponent = None
        team_score = None
        opp_score = None
        home_away = None

        for c in comp.get("competitors", []):
            if int(c["team"]["id"]) == espn_id:
                team_score = c.get("score", {}).get("value") if isinstance(c.get("score"), dict) else c.get("score")
                home_away = c.get("homeAway", "")
            else:
                opp = c["team"]
                logos = opp.get("logos", [])
                opponent = {
                    "espnId": int(opp["id"]),
                    "name": opp.get("displayName", ""),
                    "abbreviation": opp.get("abbreviation", ""),
                    "logo": logos[0]["href"] if logos else None,
                }
                opp_score = c.get("score", {}).get("value") if isinstance(c.get("score"), dict) else c.get("score")

        schedule.append({
            "date": event.get("date", ""),
            "opponent": opponent,
            "homeAway": home_away,
            "teamScore": team_score,
            "opponentScore": opp_score,
            "status": status.get("name", ""),
            "statusDetail": status.get("shortDetail", ""),
            "result": status.get("completed", False),
        })

    return schedule


def get_roster(espn_id: int, gender: str = "M") -> dict:
    """Get team roster with players and coach from ESPN."""
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"{ESPN_BASE}/{sport}/teams/{espn_id}/roster"
    try:
        data = _fetch(url, ttl=3600)
    except Exception:
        return {"players": [], "coach": None}

    players = []
    for athlete in data.get("athletes", []):
        pos = athlete.get("position", {})
        headshot = athlete.get("headshot", {})
        players.append({
            "id": athlete.get("id"),
            "name": athlete.get("displayName", ""),
            "jersey": athlete.get("jersey", ""),
            "position": pos.get("abbreviation", ""),
            "positionFull": pos.get("displayName", pos.get("name", "")),
            "height": athlete.get("displayHeight", ""),
            "weight": athlete.get("displayWeight", ""),
            "experience": athlete.get("experience", {}).get("displayValue", "")
                          if isinstance(athlete.get("experience"), dict)
                          else str(athlete.get("experience", {}).get("displayValue", "")) if athlete.get("experience") else "",
            "headshot": headshot.get("href") if isinstance(headshot, dict) else headshot,
        })

    # Coach info from the roster endpoint
    coach_data = data.get("coach", [])
    coach = None
    if coach_data:
        c = coach_data[0] if isinstance(coach_data, list) else coach_data
        coach = {
            "id": c.get("id"),
            "name": c.get("firstName", "") + " " + c.get("lastName", ""),
            "experience": c.get("experience", 0),
            "headshot": c.get("headshot", {}).get("href") if isinstance(c.get("headshot"), dict) else None,
        }

    return {"players": players, "coach": coach}


def get_team_record(espn_id: int, gender: str = "M") -> dict | None:
    """Get a single team's current record from ESPN."""
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"{ESPN_BASE}/{sport}/teams/{espn_id}"
    try:
        data = _fetch(url, ttl=3600)
    except Exception:
        return None

    team = data.get("team", {})
    record_items = team.get("record", {}).get("items", [])
    overall = None
    for item in record_items:
        if item.get("type") == "total" or item.get("description") == "Overall Record":
            overall = item
            break
    if not overall and record_items:
        overall = record_items[0]

    if not overall:
        return None

    stats = {s["name"]: s["value"] for s in overall.get("stats", [])}
    wins = int(stats.get("wins", 0))
    losses = int(stats.get("losses", 0))
    return {
        "espnId": espn_id,
        "wins": wins,
        "losses": losses,
        "record": overall.get("summary", f"{wins}-{losses}"),
    }


def get_all_team_records(gender: str = "M") -> list[dict]:
    """Get current records for all ranked/notable teams via ESPN standings.

    Uses the conference standings endpoint to get records for all D1 teams.
    """
    sport = SPORTS.get(gender, SPORTS["M"])
    # Standings endpoint gives us all teams grouped by conference
    url = f"{ESPN_WEB_BASE}/{sport}/standings?season=2026&group=50"
    try:
        data = _fetch(url, ttl=3600)
    except Exception:
        return []

    records = []
    for group in data.get("children", []):
        for entry in group.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            espn_id = int(team.get("id", 0))
            if not espn_id:
                continue

            stats = {s["name"]: s["value"] for s in entry.get("stats", [])}
            wins = int(stats.get("wins", stats.get("overall.wins", 0)))
            losses = int(stats.get("losses", stats.get("overall.losses", 0)))

            records.append({
                "espnId": espn_id,
                "wins": wins,
                "losses": losses,
            })

    return records


def get_conference_standings(gender: str = "M", season: int = 2026) -> list[dict]:
    """Get conference standings for all D1 conferences from ESPN.

    Returns list of dicts with conference name, and entries containing
    team ESPN ID, seed, conference/overall records, home/away splits,
    streak, and point stats.
    """
    sport = SPORTS.get(gender, SPORTS["M"])
    url = f"https://site.api.espn.com/apis/v2/sports/basketball/{sport}/standings?season={season}"
    data = _fetch(url, ttl=3600)

    conferences = []
    for group in data.get("children", []):
        conf_name = group.get("name", "")
        entries = []
        for entry in group.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            espn_id = int(team.get("id", 0))
            if not espn_id:
                continue

            # Build stats dicts keyed by type (unique) and name+type for display values
            stats: dict[str, Any] = {}
            display: dict[str, str] = {}
            for s in entry.get("stats", []):
                key = s.get("type", s.get("name", ""))
                stats[key] = s.get("value")
                display[key] = s.get("displayValue", "")

            entries.append({
                "espnId": espn_id,
                "name": team.get("displayName", ""),
                "confSeed": int(stats.get("playoffseed", 0) or 0),
                "confWins": int(stats.get("vsconf_wins", 0) or 0),
                "confLosses": int(stats.get("vsconf_losses", 0) or 0),
                "confWinPct": float(stats.get("vsconf_winpercent", stats.get("leaguewinpercent", 0)) or 0),
                "overallWins": int(stats.get("wins", 0) or 0),
                "overallLosses": int(stats.get("losses", 0) or 0),
                "overallWinPct": float(stats.get("winpercent", 0) or 0),
                "homeWins": int(stats.get("home_wins", 0) or 0),
                "homeLosses": int(stats.get("home_losses", 0) or 0),
                "awayWins": int(stats.get("road_wins", 0) or 0),
                "awayLosses": int(stats.get("road_losses", 0) or 0),
                "streak": display.get("streak", ""),
                "gamesBehind": float(stats.get("vsconf_gamesbehind", 0) or 0),
                "avgPointsFor": float(stats.get("avgpointsfor", 0) or 0),
                "avgPointsAgainst": float(stats.get("avgpointsagainst", 0) or 0),
                "pointDifferential": int(stats.get("pointdifferential", 0) or 0),
            })

        conferences.append({
            "name": conf_name,
            "entries": entries,
        })

    return conferences


def get_tournament_teams(gender: str = "M") -> list[dict]:
    """Get NCAA tournament teams with seeds and regions from ESPN.

    Available after Selection Sunday. Fetches tournament scoreboard (groups=100)
    and parses seed numbers from curatedRank and regions from event names
    (e.g. "South Region - 1st Round").

    Returns list of {espnId, name, seed, region, logo, abbreviation}.
    """
    sport = SPORTS.get(gender, SPORTS["M"])
    # ESPN groups=100 is March Madness tournament.
    # Fetch multiple date ranges since ESPN populates games gradually
    # across First Four (3/18-19), R1 (3/20-21), R2 (3/22-23), etc.
    tournament_dates = [
        "20260318", "20260319", "20260320", "20260321",
        "20260322", "20260323",  # Round of 32
        "20260327", "20260328",  # Sweet 16
        "20260329", "20260330",  # Elite Eight
        "20260404", "20260406",  # Final Four + Championship
    ]

    # Map ESPN region names to our single-letter codes.
    # Men's use named regions (East, West, South, Midwest).
    # Women's use numbered regionals (Regional 1-4).
    # Order matters: check "midwest" before "west" to avoid substring match.
    region_checks = [
        ("midwest", "Z"),
        ("southeast", "Y"),
        ("south", "Y"),
        ("east", "W"),
        ("west", "X"),
        # Women's numbered regionals -- map to W/X/Y/Z in order
        ("regional 1", "W"),
        ("regional 2", "X"),
        ("regional 3", "Y"),
        ("regional 4", "Z"),
    ]

    # For women's, also try to extract region from "Regional N" pattern
    import re
    def _parse_region(text):
        """Parse region code from headline text."""
        text_lower = text.lower()
        # Check numbered regionals first (women's)
        m = re.search(r"regional\s+(\d)", text_lower)
        if m:
            num = int(m.group(1))
            return {1: "W", 2: "X", 3: "Y", 4: "Z"}.get(num)
        # Named regions (men's)
        for name, code in region_checks:
            if name in text_lower:
                return code
        return None

    teams = {}

    # Process dated URLs first (have correct regional info), then undated
    # as fallback. Dated URLs are authoritative for region assignment.
    base_url = f"{ESPN_BASE}/{sport}/scoreboard?groups=100&limit=200"
    urls = [f"{base_url}&dates={d}" for d in tournament_dates] + [base_url]

    for url in urls:
        try:
            data = _fetch(url, ttl=300)
        except Exception:
            continue

        for event in data.get("events", []):
            # Parse region from event name (e.g. "South Region - 1st Round")
            event_name = event.get("name", "")
            headline = ""
            for note in event.get("competitions", [{}])[0].get("notes", []):
                headline = note.get("headline", "")
                break
            # Region is in the headline or event status type detail
            region_code = None
            for text in [headline, event_name]:
                if text:
                    region_code = _parse_region(text)
                    if region_code:
                        break

            comp = event.get("competitions", [{}])[0]
            for c in comp.get("competitors", []):
                t = c.get("team", {})
                tid = t.get("id")
                if not tid or int(tid) < 0:
                    continue  # Skip TBD placeholders
                espn_id = int(tid)
                if espn_id in teams:
                    # Update region if we now have a better one
                    if region_code and not teams[espn_id].get("region"):
                        teams[espn_id]["region"] = region_code
                    continue

                # Seed from curatedRank.current or direct seed field
                seed = c.get("curatedRank", {}).get("current") or c.get("seed")
                if seed == 99:
                    continue  # ESPN placeholder rank

                logos = t.get("logos", [])
                logo = t.get("logo") or (logos[0]["href"] if logos else None)
                teams[espn_id] = {
                    "espnId": espn_id,
                    "name": t.get("displayName", ""),
                    "abbreviation": t.get("abbreviation", ""),
                    "logo": logo,
                    "seed": seed,
                    "region": region_code,
                }

    return list(teams.values())
