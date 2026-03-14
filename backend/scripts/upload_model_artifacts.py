"""
Upload trained model artifacts (joblib files) to the model_artifacts DB table.

This enables the ml_ensemble prediction path in predictor.py, which builds
features from LIVE DB state instead of using stale CSV predictions.

Run from backend/:
    python -m scripts.upload_model_artifacts [--version v5] [--artifact-dir ../notebooks/artifacts]
"""

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import ModelArtifact

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks" / "artifacts"


def main():
    parser = argparse.ArgumentParser(description="Upload model artifacts to DB")
    parser.add_argument("--version", default="v5", help="Model version label (default: v5)")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR,
                        help="Directory containing joblib files and metadata JSON")
    args = parser.parse_args()

    version = args.version
    artifact_dir = args.artifact_dir

    if not artifact_dir.exists():
        print(f"Artifact directory not found: {artifact_dir}")
        print("Run the notebook first to generate artifacts.")
        return

    # Load metadata
    meta_path = artifact_dir / f"model_metadata_{version}.json"
    if not meta_path.exists():
        print(f"Metadata not found: {meta_path}")
        return

    with open(meta_path) as f:
        metadata = json.load(f)

    print(f"Uploading model version: {version}")
    print(f"Features: {len(metadata.get('feature_cols', []))}")
    print(f"Weights: {metadata.get('weights', {})}")

    session = SessionLocal()

    try:
        # Deactivate all existing active artifacts
        deactivated = (
            session.query(ModelArtifact)
            .filter(ModelArtifact.is_active == True)  # noqa: E712
            .update({ModelArtifact.is_active: False})
        )
        if deactivated:
            print(f"Deactivated {deactivated} existing artifact(s)")

        artifacts_to_upload = [
            ("lr_final", f"lr_{version}.joblib"),
            ("lgb_final", f"lgb_{version}.joblib"),
            ("calibrator", f"calibrator_{version}.joblib"),
        ]

        for name, filename in artifacts_to_upload:
            filepath = artifact_dir / filename
            if not filepath.exists():
                print(f"  SKIP {name}: {filename} not found")
                continue

            blob = filepath.read_bytes()
            size_kb = len(blob) / 1024

            # Check if this artifact already exists
            existing = (
                session.query(ModelArtifact)
                .filter(ModelArtifact.name == name, ModelArtifact.version == version)
                .first()
            )

            if existing:
                existing.artifact_blob = blob
                existing.metadata_json = metadata
                existing.is_active = True
                print(f"  UPDATED {name}: {size_kb:.1f} KB")
            else:
                session.add(ModelArtifact(
                    name=name,
                    version=version,
                    artifact_blob=blob,
                    metadata_json=metadata,
                    is_active=True,
                ))
                print(f"  INSERTED {name}: {size_kb:.1f} KB")

        session.commit()
        print(f"\nDone! Model {version} artifacts uploaded and activated.")
        print("The predictor will use ml_ensemble path on next prediction.")
        print("\nIMPORTANT: Restart the server to clear the cached model bundle.")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
