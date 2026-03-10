"""
Load Kaggle CSV data into PostgreSQL.

Seeding order (FK constraints):
1. Teams (MTeams + WTeams)
2. Conferences
3. TeamConferences (M + W)
4. TourneySeeds (M + W)
5. GameResults (compact + detailed, regular + tourney, M + W)

Run from backend/:
    python -m scripts.seed_db
"""

import sys
from pathlib import Path

import pandas as pd

# Add parent to path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Team, Conference, TeamConference, TourneySeed, GameResult

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def seed_teams(session):
    print("Loading teams...")
    # Men's
    men = pd.read_csv(DATA_DIR / "MTeams.csv")
    count = 0
    for _, row in men.iterrows():
        session.merge(
            Team(
                id=int(row["TeamID"]),
                name=row["TeamName"],
                gender="M",
                first_d1_season=int(row["FirstD1Season"]),
                last_d1_season=int(row["LastD1Season"]),
            )
        )
        count += 1

    # Women's
    women = pd.read_csv(DATA_DIR / "WTeams.csv")
    for _, row in women.iterrows():
        session.merge(
            Team(
                id=int(row["TeamID"]),
                name=row["TeamName"],
                gender="W",
            )
        )
        count += 1

    session.commit()
    print(f"  {count} teams loaded")


def seed_conferences(session):
    print("Loading conferences...")
    df = pd.read_csv(DATA_DIR / "Conferences.csv")
    count = 0
    for _, row in df.iterrows():
        session.merge(
            Conference(
                abbrev=row["ConfAbbrev"],
                description=row["Description"],
            )
        )
        count += 1
    session.commit()
    print(f"  {count} conferences loaded")


def seed_team_conferences(session):
    print("Loading team conferences...")
    count = 0
    for csv_file in ["MTeamConferences.csv", "WTeamConferences.csv"]:
        path = DATA_DIR / csv_file
        if not path.exists():
            continue
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            tc = TeamConference(
                season=int(row["Season"]),
                team_id=int(row["TeamID"]),
                conf_abbrev=row["ConfAbbrev"],
            )
            session.merge(tc)
            count += 1
    session.commit()
    print(f"  {count} team-conference records loaded")


def seed_tourney_seeds(session, season_filter: int | None = None):
    """Load tourney seeds. If season_filter is set, only load that season
    (useful for adding new bracket without re-seeding everything)."""
    print("Loading tourney seeds...")
    count = 0
    for csv_file in ["MNCAATourneySeeds.csv", "WNCAATourneySeeds.csv"]:
        path = DATA_DIR / csv_file
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if season_filter:
            df = df[df["Season"] == season_filter]
        for _, row in df.iterrows():
            seed_str = row["Seed"]  # e.g. "W01", "X16a"
            region = seed_str[0]
            seed_num = int(seed_str[1:3])
            # Delete existing seed for this team/season to avoid duplicates
            session.query(TourneySeed).filter(
                TourneySeed.season == int(row["Season"]),
                TourneySeed.team_id == int(row["TeamID"]),
            ).delete()
            session.add(
                TourneySeed(
                    season=int(row["Season"]),
                    team_id=int(row["TeamID"]),
                    seed=seed_str,
                    seed_number=seed_num,
                    region=region,
                )
            )
            count += 1
    session.commit()
    print(f"  {count} tourney seeds loaded")


def seed_game_results(session):
    print("Loading game results (compact)...")
    count = 0

    compact_files = [
        ("MRegularSeasonCompactResults.csv", "regular", "M"),
        ("WRegularSeasonCompactResults.csv", "regular", "W"),
        ("MNCAATourneyCompactResults.csv", "tourney", "M"),
        ("WNCAATourneyCompactResults.csv", "tourney", "W"),
    ]

    for csv_file, game_type, gender in compact_files:
        path = DATA_DIR / csv_file
        if not path.exists():
            continue
        df = pd.read_csv(path)
        records = []
        for _, row in df.iterrows():
            records.append(
                GameResult(
                    season=int(row["Season"]),
                    day_num=int(row["DayNum"]),
                    w_team_id=int(row["WTeamID"]),
                    w_score=int(row["WScore"]),
                    l_team_id=int(row["LTeamID"]),
                    l_score=int(row["LScore"]),
                    w_loc=row.get("WLoc", None),
                    num_ot=int(row.get("NumOT", 0)),
                    game_type=game_type,
                    gender=gender,
                )
            )
        session.bulk_save_objects(records)
        session.commit()
        count += len(records)
        print(f"  {csv_file}: {len(records)} games")

    print(f"  Total compact: {count} games")

    # Now load detailed results and update the matching compact rows
    print("Loading detailed stats...")
    detail_files = [
        ("MRegularSeasonDetailedResults.csv", "regular", "M"),
        ("WRegularSeasonDetailedResults.csv", "regular", "W"),
        ("MNCAATourneyDetailedResults.csv", "tourney", "M"),
        ("WNCAATourneyDetailedResults.csv", "tourney", "W"),
    ]

    detail_cols = [
        "WFGM", "WFGA", "WFGM3", "WFGA3", "WFTM", "WFTA",
        "WOR", "WDR", "WAst", "WTO", "WStl", "WBlk", "WPF",
        "LFGM", "LFGA", "LFGM3", "LFGA3", "LFTM", "LFTA",
        "LOR", "LDR", "LAst", "LTO", "LStl", "LBlk", "LPF",
    ]
    db_cols = [
        "w_fgm", "w_fga", "w_fgm3", "w_fga3", "w_ftm", "w_fta",
        "w_or", "w_dr", "w_ast", "w_to", "w_stl", "w_blk", "w_pf",
        "l_fgm", "l_fga", "l_fgm3", "l_fga3", "l_ftm", "l_fta",
        "l_or", "l_dr", "l_ast", "l_to", "l_stl", "l_blk", "l_pf",
    ]

    updated = 0
    for csv_file, game_type, gender in detail_files:
        path = DATA_DIR / csv_file
        if not path.exists():
            continue
        df = pd.read_csv(path)
        # Build batch updates
        for _, row in df.iterrows():
            update_vals = {}
            for csv_col, db_col in zip(detail_cols, db_cols):
                if csv_col in row and pd.notna(row[csv_col]):
                    update_vals[db_col] = int(row[csv_col])

            if update_vals:
                session.query(GameResult).filter(
                    GameResult.season == int(row["Season"]),
                    GameResult.day_num == int(row["DayNum"]),
                    GameResult.w_team_id == int(row["WTeamID"]),
                    GameResult.l_team_id == int(row["LTeamID"]),
                    GameResult.game_type == game_type,
                    GameResult.gender == gender,
                ).update(update_vals)
                updated += 1

            if updated % 10000 == 0 and updated > 0:
                session.commit()
                print(f"  Updated {updated} rows with detailed stats...")

        session.commit()
        print(f"  {csv_file}: detailed stats applied")

    print(f"  Total detailed updates: {updated}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed database from Kaggle CSVs")
    parser.add_argument(
        "--seeds-only",
        type=int,
        metavar="SEASON",
        help="Only load tourney seeds for a specific season (e.g. 2026)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.seeds_only:
            print(f"Loading tourney seeds for season {args.seeds_only} only...")
            seed_tourney_seeds(session, season_filter=args.seeds_only)
        else:
            seed_teams(session)
            seed_conferences(session)
            seed_team_conferences(session)
            seed_tourney_seeds(session)
            seed_game_results(session)
        print("\nDone! Database seeded successfully.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
