"""Map Kaggle team IDs to ESPN team IDs using team name fuzzy matching.

Fetches the ESPN teams API, matches against Kaggle team names and spelling
variants, then updates the Team table with espn_id, logo_url, and color.
Also writes a JSON mapping file to data/espn_team_map.json.

When to run: one-time setup after seeding the DB, or when ESPN adds/renames teams.

Run from backend/:
    python -m scripts.map_espn_ids
"""

import csv
import json
import re
import ssl
import urllib.request

# macOS Python often lacks system certs
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

from app.database import SessionLocal  # noqa: E402
from app.models import Team  # noqa: E402

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball"
SPORTS = {
    "M": "mens-college-basketball",
    "W": "womens-college-basketball",
}
DATA_DIR = "../data/raw"


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower().strip())


def fetch_espn_teams(gender: str) -> list[dict]:
    sport = SPORTS[gender]
    url = f"{ESPN_BASE}/{sport}/teams?limit=500"
    with urllib.request.urlopen(url, context=_ctx) as resp:
        data = json.loads(resp.read())
    teams = []
    for t in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        team = t["team"]
        logos = team.get("logos", [])
        logo_url = logos[0]["href"] if logos else None
        color = team.get("color", "")
        teams.append({
            "espn_id": int(team["id"]),
            "displayName": team["displayName"],
            "location": team.get("location", ""),
            "abbreviation": team.get("abbreviation", ""),
            "nickname": team.get("nickname", ""),
            "shortDisplayName": team.get("shortDisplayName", ""),
            "logo_url": logo_url,
            "color": f"#{color}" if color and not color.startswith("#") else color,
        })
    return teams


def load_spellings(gender: str) -> dict[str, int]:
    """Load team name spelling variants -> Kaggle ID."""
    prefix = "M" if gender == "M" else "W"
    path = f"{DATA_DIR}/{prefix}TeamSpellings.csv"
    spellings = {}
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row[0] == "TeamNameSpelling":
                    continue
                spellings[normalize(row[0])] = int(row[1])
    except FileNotFoundError:
        print(f"  Warning: {path} not found, using team names only")
    return spellings


def load_kaggle_teams(gender: str) -> dict[int, str]:
    prefix = "M" if gender == "M" else "W"
    path = f"{DATA_DIR}/{prefix}Teams.csv"
    teams = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            teams[int(row["TeamID"])] = row["TeamName"]
    return teams


def match_teams(gender: str) -> dict[int, dict]:
    """Returns {kaggle_id: {espn_id, logo_url, color}}."""
    espn_teams = fetch_espn_teams(gender)
    spellings = load_spellings(gender)
    kaggle = load_kaggle_teams(gender)

    # Build ESPN lookup: normalized name -> team info
    espn_lookup = {}
    for t in espn_teams:
        for key in [t["displayName"], t["location"], t["nickname"], t["shortDisplayName"]]:
            if key:
                espn_lookup[normalize(key)] = t

    matched = {}

    # Match via spellings file first (most reliable)
    for spelling, kid in spellings.items():
        if kid in matched:
            continue
        if spelling in espn_lookup:
            t = espn_lookup[spelling]
            matched[kid] = {
                "espn_id": t["espn_id"],
                "logo_url": t["logo_url"],
                "color": t["color"],
                "espn_name": t["displayName"],
            }

    # Fallback: direct Kaggle name match
    for kid, kname in kaggle.items():
        if kid in matched:
            continue
        norm = normalize(kname)
        if norm in espn_lookup:
            t = espn_lookup[norm]
            matched[kid] = {
                "espn_id": t["espn_id"],
                "logo_url": t["logo_url"],
                "color": t["color"],
                "espn_name": t["displayName"],
            }

    return matched


def main():
    all_mappings = {}

    for gender in ["M", "W"]:
        label = "Men's" if gender == "M" else "Women's"
        print(f"\n--- {label} Teams ---")
        kaggle = load_kaggle_teams(gender)
        matched = match_teams(gender)
        print(f"  Kaggle teams: {len(kaggle)}")
        print(f"  Matched to ESPN: {len(matched)}")

        unmatched = [kaggle[k] for k in kaggle if k not in matched]
        if unmatched:
            print(f"  Unmatched ({len(unmatched)}): {', '.join(unmatched[:10])}...")

        for kid, info in matched.items():
            all_mappings[kid] = info

    # Save to JSON
    out_path = "../data/espn_team_map.json"
    with open(out_path, "w") as f:
        json.dump(all_mappings, f, indent=2)
    print(f"\nSaved {len(all_mappings)} mappings to {out_path}")

    # Update database
    db = SessionLocal()
    updated = 0
    for kid, info in all_mappings.items():
        team = db.query(Team).filter(Team.id == kid).first()
        if team:
            team.espn_id = info["espn_id"]
            team.logo_url = info["logo_url"]
            team.color = info["color"]
            updated += 1

    db.commit()
    db.close()
    print(f"Updated {updated} teams in database")


if __name__ == "__main__":
    main()
