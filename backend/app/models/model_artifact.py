from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary, JSON, func

from app.database import Base


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # e.g. "lr_final", "lgb_final", "calibrator"
    version = Column(String(20), nullable=False)  # e.g. "v2"
    artifact_blob = Column(LargeBinary, nullable=True)  # joblib.dumps() output
    metadata_json = Column(JSON, nullable=True)  # weights, feature_cols, etc.
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
