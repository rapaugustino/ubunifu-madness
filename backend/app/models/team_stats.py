from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class TeamSeasonStats(Base):
    __tablename__ = "team_season_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    # Record
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_pct = Column(Float, default=0.0)

    # Box score averages (Four Factors + efficiency)
    avg_efg_pct = Column(Float, nullable=True)
    avg_to_pct = Column(Float, nullable=True)
    avg_or_pct = Column(Float, nullable=True)
    avg_ft_rate = Column(Float, nullable=True)
    avg_opp_efg_pct = Column(Float, nullable=True)
    avg_opp_to_pct = Column(Float, nullable=True)
    avg_off_eff = Column(Float, nullable=True)
    avg_def_eff = Column(Float, nullable=True)
    avg_tempo = Column(Float, nullable=True)

    # Strength of schedule (average opponent Elo)
    sos = Column(Float, nullable=True)

    # Massey ordinals
    massey_avg_rank = Column(Float, nullable=True)
    massey_disagreement = Column(Float, nullable=True)

    # Momentum (last 10 games)
    last_n_winpct = Column(Float, nullable=True)
    last_n_mov = Column(Float, nullable=True)
    efg_trend = Column(Float, nullable=True)

    # Conference tournament
    conf_tourney_wins = Column(Integer, default=0)

    # Coach experience
    coach_name = Column(String(100), nullable=True)
    coach_tenure = Column(Integer, nullable=True)
    coach_tourney_appearances = Column(Integer, nullable=True)
    coach_march_winrate = Column(Float, nullable=True)

    team = relationship("Team", back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_team_stats_season"),
        Index("ix_team_stats_season", "season"),
    )
