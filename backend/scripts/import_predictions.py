"""
Import model predictions from a submission CSV into the PostgreSQL predictions table.

Parses rows like "2026_1101_1102,0.678" into the predictions table, replacing
any existing predictions for the same model version.

When to run: after generating a new submission CSV from the notebook, to make
predictions available to the app's lookup-based prediction path.

Run from backend/:
    python -m scripts.import_predictions
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Prediction

SUBMISSION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "notebooks"
    / "submissions"
    / "stage2_submission_v6.csv"
)


def main():
    if not SUBMISSION_PATH.exists():
        print(f"Submission file not found: {SUBMISSION_PATH}")
        return

    session = SessionLocal()

    try:
        # Clear existing v6 predictions
        deleted = session.query(Prediction).filter(Prediction.model_version == "v6").delete()
        session.commit()
        if deleted:
            print(f"Cleared {deleted} existing v6 predictions")

        print(f"Loading predictions from {SUBMISSION_PATH}...")
        df = pd.read_csv(SUBMISSION_PATH)
        print(f"  {len(df)} rows in CSV")

        records = []
        for _, row in df.iterrows():
            parts = row["ID"].split("_")
            season = int(parts[0])
            team_a = int(parts[1])
            team_b = int(parts[2])
            prob = float(row["Pred"])

            # Determine gender from team_a_id
            gender = "M" if team_a < 2000 else "W"

            records.append(
                Prediction(
                    season=season,
                    team_a_id=team_a,
                    team_b_id=team_b,
                    win_prob_a=prob,
                    model_version="v6",
                    gender=gender,
                )
            )

        # Bulk insert in batches
        batch_size = 10000
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            session.bulk_save_objects(batch)
            session.commit()
            print(f"  Inserted {min(i + batch_size, len(records))}/{len(records)}")

        print(f"\nDone! {len(records)} predictions imported.")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
