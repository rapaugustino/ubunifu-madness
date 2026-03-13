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

    # Adjusted efficiency (opponent-adjusted, KenPom-style)
    adj_off_eff = Column(Float, nullable=True)   # Adjusted offensive efficiency (pts/100 poss)
    adj_def_eff = Column(Float, nullable=True)   # Adjusted defensive efficiency (pts/100 poss)
    adj_net_eff = Column(Float, nullable=True)    # AdjOE - AdjDE (net efficiency margin)
    barthag = Column(Float, nullable=True)        # Win prob vs average D1 team (0-1)

    # Pythagorean / luck
    pyth_win_pct = Column(Float, nullable=True)   # Expected W% from points scored/allowed
    luck = Column(Float, nullable=True)           # Actual W% - Pythagorean W%

    # Additional shooting & style metrics
    true_shooting_pct = Column(Float, nullable=True)   # PTS / (2 * (FGA + 0.44*FTA))
    three_pt_rate = Column(Float, nullable=True)       # 3PA / FGA
    ast_to_ratio = Column(Float, nullable=True)        # AST / TOV
    drb_pct = Column(Float, nullable=True)             # DRB / (DRB + Opp_ORB)
    stl_pct = Column(Float, nullable=True)             # STL / Opp possessions
    blk_pct = Column(Float, nullable=True)             # BLK / Opp 2PA
    opp_true_shooting_pct = Column(Float, nullable=True)  # Defensive TS%

    # Consistency & volatility
    margin_stdev = Column(Float, nullable=True)        # Stdev of scoring margin
    off_eff_stdev = Column(Float, nullable=True)       # Stdev of offensive efficiency
    floor_eff = Column(Float, nullable=True)           # 10th percentile net efficiency
    ceiling_eff = Column(Float, nullable=True)         # 90th percentile net efficiency
    upset_vulnerability = Column(Float, nullable=True) # Composite upset risk (0-100)

    # Close games & clutch
    close_wins = Column(Integer, default=0)            # Wins in games decided by <=5
    close_losses = Column(Integer, default=0)          # Losses in games decided by <=5
    close_game_win_pct = Column(Float, nullable=True)  # Close-game W%

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

    # Composite power rating (blended ranking score)
    power_rating = Column(Float, nullable=True)

    team = relationship("Team", back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_team_stats_season"),
        Index("ix_team_stats_season", "season"),
    )
