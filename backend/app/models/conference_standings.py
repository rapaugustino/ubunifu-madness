from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, Index

from app.database import Base


class ConferenceStanding(Base):
    __tablename__ = "conference_standings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)  # 'M' or 'W'
    conf_abbrev = Column(String(20), ForeignKey("conferences.abbrev"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    # ESPN data
    conf_seed = Column(Integer, nullable=True)  # playoff seed within conference
    conf_wins = Column(Integer, nullable=False, default=0)
    conf_losses = Column(Integer, nullable=False, default=0)
    conf_win_pct = Column(Float, nullable=True)
    overall_wins = Column(Integer, nullable=False, default=0)
    overall_losses = Column(Integer, nullable=False, default=0)
    overall_win_pct = Column(Float, nullable=True)
    home_wins = Column(Integer, nullable=False, default=0)
    home_losses = Column(Integer, nullable=False, default=0)
    away_wins = Column(Integer, nullable=False, default=0)
    away_losses = Column(Integer, nullable=False, default=0)
    streak = Column(String(10), nullable=True)  # e.g. "W3", "L2"
    games_behind = Column(Float, nullable=True)
    avg_points_for = Column(Float, nullable=True)
    avg_points_against = Column(Float, nullable=True)
    point_differential = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_conf_standing_team"),
        Index("ix_conf_standing_season_gender_conf", "season", "gender", "conf_abbrev"),
    )
