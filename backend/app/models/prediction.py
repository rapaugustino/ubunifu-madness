from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, Index

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    team_a_id = Column(Integer, ForeignKey("teams.id"), nullable=False)  # lower ID
    team_b_id = Column(Integer, ForeignKey("teams.id"), nullable=False)  # higher ID
    win_prob_a = Column(Float, nullable=False)  # P(team_a wins)
    model_version = Column(String(20), default="v6")
    gender = Column(String(1), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "season", "team_a_id", "team_b_id", "model_version", name="uq_pred"
        ),
        Index("ix_pred_season_gender", "season", "gender"),
        Index("ix_pred_team_a", "team_a_id"),
        Index("ix_pred_team_b", "team_b_id"),
    )
