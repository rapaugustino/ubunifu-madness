from sqlalchemy import Column, Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class EloRating(Base):
    __tablename__ = "elo_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    elo = Column(Float, nullable=False)
    snapshot_day = Column(Integer, default=154)  # end-of-season snapshot

    team = relationship("Team", back_populates="elo_ratings")

    __table_args__ = (
        UniqueConstraint(
            "season", "team_id", "snapshot_day", name="uq_elo_season_team_day"
        ),
        Index("ix_elo_season", "season"),
    )
