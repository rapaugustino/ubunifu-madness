from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, func

from app.database import Base


class GamePrediction(Base):
    """Stores locked pre-game predictions and outcomes for every game we cover.

    The locked prediction is frozen before tipoff and never modified.
    This allows honest performance tracking — we can't retroactively
    improve our record by updating predictions during or after games.
    """

    __tablename__ = "game_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    espn_game_id = Column(String(20), nullable=False)
    game_date = Column(String(10), nullable=False)  # YYYYMMDD
    season = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)

    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    away_name = Column(String(100), nullable=True)
    home_name = Column(String(100), nullable=True)

    # Locked pre-game prediction (frozen before tipoff, never updated)
    locked_prob_away = Column(Float, nullable=False)  # P(away wins) at lock time
    locked_at = Column(DateTime, server_default=func.now(), nullable=False)
    prediction_source = Column(String(20), nullable=False)  # "model_v2", "elo_fallback"

    # Outcome (filled after game ends)
    away_score = Column(Integer, nullable=True)
    home_score = Column(Integer, nullable=True)
    winner_team_id = Column(Integer, nullable=True)
    model_correct = Column(Boolean, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("espn_game_id", name="uq_game_pred_espn"),
        Index("ix_game_pred_date", "game_date"),
        Index("ix_game_pred_season_gender", "season", "gender"),
    )
