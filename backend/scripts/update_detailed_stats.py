"""
Batch update game_results with detailed box score stats using raw SQL.

Much faster than ORM row-by-row updates over a network connection. Loads
detailed CSV data into a temp staging table, then joins against game_results
to apply all box score columns in a single UPDATE.

When to run: one-time after seeding the DB, if detailed stats were not loaded
by seed_db.py, or after importing new detailed CSV files from Kaggle.

Run from backend/:
    python -m scripts.update_detailed_stats
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

DETAIL_FILES = [
    ("MRegularSeasonDetailedResults.csv", "regular", "M"),
    ("WRegularSeasonDetailedResults.csv", "regular", "W"),
    ("MNCAATourneyDetailedResults.csv", "tourney", "M"),
    ("WNCAATourneyDetailedResults.csv", "tourney", "W"),
]

CSV_TO_DB = {
    "WFGM": "w_fgm", "WFGA": "w_fga", "WFGM3": "w_fgm3", "WFGA3": "w_fga3",
    "WFTM": "w_ftm", "WFTA": "w_fta", "WOR": "w_or", "WDR": "w_dr",
    "WAst": "w_ast", "WTO": "w_to", "WStl": "w_stl", "WBlk": "w_blk", "WPF": "w_pf",
    "LFGM": "l_fgm", "LFGA": "l_fga", "LFGM3": "l_fgm3", "LFGA3": "l_fga3",
    "LFTM": "l_ftm", "LFTA": "l_fta", "LOR": "l_or", "LDR": "l_dr",
    "LAst": "l_ast", "LTO": "l_to", "LStl": "l_stl", "LBlk": "l_blk", "LPF": "l_pf",
}


def main():
    total = 0

    with engine.connect() as conn:
        # Create temp table
        conn.execute(text("""
            CREATE TEMP TABLE IF NOT EXISTS detail_staging (
                season INTEGER, day_num INTEGER,
                w_team_id INTEGER, l_team_id INTEGER,
                game_type VARCHAR(10), gender VARCHAR(1),
                w_fgm INT, w_fga INT, w_fgm3 INT, w_fga3 INT,
                w_ftm INT, w_fta INT, w_or INT, w_dr INT,
                w_ast INT, w_to INT, w_stl INT, w_blk INT, w_pf INT,
                l_fgm INT, l_fga INT, l_fgm3 INT, l_fga3 INT,
                l_ftm INT, l_fta INT, l_or INT, l_dr INT,
                l_ast INT, l_to INT, l_stl INT, l_blk INT, l_pf INT
            )
        """))
        conn.execute(text("TRUNCATE detail_staging"))

        for csv_file, game_type, gender in DETAIL_FILES:
            path = DATA_DIR / csv_file
            if not path.exists():
                print(f"  Skipping {csv_file} (not found)")
                continue

            df = pd.read_csv(path)
            print(f"  Loading {csv_file}: {len(df)} rows...")

            # Rename columns
            rename = {csv: db for csv, db in CSV_TO_DB.items()}
            df = df.rename(columns=rename)
            df = df.rename(columns={
                "Season": "season", "DayNum": "day_num",
                "WTeamID": "w_team_id", "LTeamID": "l_team_id",
                "WScore": "w_score", "LScore": "l_score",
            })
            df["game_type"] = game_type
            df["gender"] = gender

            # Select only the columns we need for staging
            staging_cols = [
                "season", "day_num", "w_team_id", "l_team_id", "game_type", "gender",
            ] + list(CSV_TO_DB.values())

            staging_df = df[staging_cols].copy()

            # Insert into staging in batches using raw SQL
            batch_size = 5000
            for i in range(0, len(staging_df), batch_size):
                batch = staging_df.iloc[i:i + batch_size]
                values_parts = []
                for _, row in batch.iterrows():
                    values_parts.append(
                        f"({row['season']}, {row['day_num']}, {row['w_team_id']}, {row['l_team_id']}, "
                        f"'{game_type}', '{gender}', "
                        + ", ".join(
                            str(int(row[c])) if pd.notna(row[c]) else "NULL"
                            for c in list(CSV_TO_DB.values())
                        )
                        + ")"
                    )

                if values_parts:
                    sql = f"INSERT INTO detail_staging ({', '.join(staging_cols)}) VALUES " + ", ".join(values_parts)
                    conn.execute(text(sql))

                if (i + batch_size) % 20000 == 0:
                    print(f"    Staged {min(i + batch_size, len(staging_df))}/{len(staging_df)}")

            total += len(staging_df)
            print(f"    Staged {len(staging_df)} rows")

        # Now batch update from staging
        print(f"\nBatch updating game_results from {total} staging rows...")
        set_clauses = ", ".join(f"{col} = s.{col}" for col in CSV_TO_DB.values())
        result = conn.execute(text(f"""
            UPDATE game_results g
            SET {set_clauses}
            FROM detail_staging s
            WHERE g.season = s.season
              AND g.day_num = s.day_num
              AND g.w_team_id = s.w_team_id
              AND g.l_team_id = s.l_team_id
              AND g.game_type = s.game_type
              AND g.gender = s.gender
        """))
        conn.commit()
        print(f"  Updated {result.rowcount} game_results rows with detailed stats")

        # Drop temp table
        conn.execute(text("DROP TABLE IF EXISTS detail_staging"))
        conn.commit()

    print("Done!")


if __name__ == "__main__":
    main()
