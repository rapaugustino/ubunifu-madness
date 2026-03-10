from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class Player(Base):
    """NCAA D1 basketball player."""

    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    espn_id = Column(Integer, nullable=False, unique=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    name = Column(String(100), nullable=False)
    jersey = Column(String(5), nullable=True)
    position = Column(String(5), nullable=True)  # G, F, C
    position_full = Column(String(30), nullable=True)
    height = Column(String(10), nullable=True)  # e.g. "6' 9\""
    weight = Column(String(10), nullable=True)  # e.g. "250 lbs"
    experience = Column(String(20), nullable=True)  # Freshman, Sophomore, etc.
    headshot_url = Column(String(500), nullable=True)
    gender = Column(String(1), nullable=False, default="M")

    # Injury status (updated from ESPN when available)
    injury_status = Column(String(20), nullable=True)  # "Out", "Day-To-Day", "Probable", None=healthy
    injury_detail = Column(String(200), nullable=True)  # e.g. "Knee - Out indefinitely"

    season_stats = relationship("PlayerSeasonStats", back_populates="player")

    __table_args__ = (
        Index("ix_player_team", "team_id"),
        Index("ix_player_espn", "espn_id"),
    )


class PlayerSeasonStats(Base):
    """Aggregated season stats for a player, computed from game box scores."""

    __tablename__ = "player_season_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    games_played = Column(Integer, default=0)
    minutes_total = Column(Float, default=0.0)

    # Scoring
    points_total = Column(Integer, default=0)
    fgm = Column(Integer, default=0)
    fga = Column(Integer, default=0)
    fgm3 = Column(Integer, default=0)
    fga3 = Column(Integer, default=0)
    ftm = Column(Integer, default=0)
    fta = Column(Integer, default=0)

    # Rebounds
    oreb_total = Column(Integer, default=0)
    dreb_total = Column(Integer, default=0)
    reb_total = Column(Integer, default=0)

    # Other
    ast_total = Column(Integer, default=0)
    to_total = Column(Integer, default=0)
    stl_total = Column(Integer, default=0)
    blk_total = Column(Integer, default=0)
    pf_total = Column(Integer, default=0)

    # Computed averages (updated after each game sync)
    ppg = Column(Float, default=0.0)  # points per game
    rpg = Column(Float, default=0.0)  # rebounds per game
    apg = Column(Float, default=0.0)  # assists per game
    mpg = Column(Float, default=0.0)  # minutes per game
    fg_pct = Column(Float, nullable=True)
    fg3_pct = Column(Float, nullable=True)
    ft_pct = Column(Float, nullable=True)

    # Player importance (computed)
    minutes_share = Column(Float, nullable=True)  # % of team's total minutes
    usage_rate = Column(Float, nullable=True)  # estimated usage rate
    importance_score = Column(Float, nullable=True)  # 0-1, how much team depends on this player

    player = relationship("Player", back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint("season", "player_id", name="uq_player_stats_season"),
        Index("ix_player_stats_team_season", "team_id", "season"),
    )


class PlayerGameLog(Base):
    """Individual game stats for a player (from ESPN box scores)."""

    __tablename__ = "player_game_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    espn_game_id = Column(String(20), nullable=False)
    game_date = Column(String(10), nullable=False)  # YYYYMMDD
    season = Column(Integer, nullable=False)

    minutes = Column(Float, default=0.0)
    points = Column(Integer, default=0)
    fgm = Column(Integer, default=0)
    fga = Column(Integer, default=0)
    fgm3 = Column(Integer, default=0)
    fga3 = Column(Integer, default=0)
    ftm = Column(Integer, default=0)
    fta = Column(Integer, default=0)
    oreb = Column(Integer, default=0)
    dreb = Column(Integer, default=0)
    reb = Column(Integer, default=0)
    ast = Column(Integer, default=0)
    to = Column(Integer, default=0)
    stl = Column(Integer, default=0)
    blk = Column(Integer, default=0)
    pf = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("player_id", "espn_game_id", name="uq_player_game"),
        Index("ix_pgl_game", "espn_game_id"),
        Index("ix_pgl_player_season", "player_id", "season"),
    )
