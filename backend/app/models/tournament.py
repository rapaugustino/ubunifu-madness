from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index

from app.database import Base


class TourneySeed(Base):
    __tablename__ = "tourney_seeds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    seed = Column(String(4), nullable=False)  # raw e.g. "W01", "X16a"
    seed_number = Column(Integer, nullable=False)  # parsed: 1-16
    region = Column(String(1), nullable=False)  # W, X, Y, Z

    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_seed_season_team"),
        Index("ix_seed_season", "season"),
    )
