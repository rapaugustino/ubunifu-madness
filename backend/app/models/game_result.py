from sqlalchemy import Column, Integer, String, Index

from app.database import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    day_num = Column(Integer, nullable=False)
    w_team_id = Column(Integer, nullable=False)
    w_score = Column(Integer, nullable=False)
    l_team_id = Column(Integer, nullable=False)
    l_score = Column(Integer, nullable=False)
    w_loc = Column(String(1), nullable=True)  # H, A, N
    num_ot = Column(Integer, default=0)
    game_type = Column(String(10), nullable=False)  # 'regular' or 'tourney'
    gender = Column(String(1), nullable=False)  # 'M' or 'W'

    # Detailed stats (nullable — compact results don't have these)
    w_fgm = Column(Integer, nullable=True)
    w_fga = Column(Integer, nullable=True)
    w_fgm3 = Column(Integer, nullable=True)
    w_fga3 = Column(Integer, nullable=True)
    w_ftm = Column(Integer, nullable=True)
    w_fta = Column(Integer, nullable=True)
    w_or = Column(Integer, nullable=True)
    w_dr = Column(Integer, nullable=True)
    w_ast = Column(Integer, nullable=True)
    w_to = Column(Integer, nullable=True)
    w_stl = Column(Integer, nullable=True)
    w_blk = Column(Integer, nullable=True)
    w_pf = Column(Integer, nullable=True)
    l_fgm = Column(Integer, nullable=True)
    l_fga = Column(Integer, nullable=True)
    l_fgm3 = Column(Integer, nullable=True)
    l_fga3 = Column(Integer, nullable=True)
    l_ftm = Column(Integer, nullable=True)
    l_fta = Column(Integer, nullable=True)
    l_or = Column(Integer, nullable=True)
    l_dr = Column(Integer, nullable=True)
    l_ast = Column(Integer, nullable=True)
    l_to = Column(Integer, nullable=True)
    l_stl = Column(Integer, nullable=True)
    l_blk = Column(Integer, nullable=True)
    l_pf = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_game_season", "season"),
        Index("ix_game_teams", "w_team_id", "l_team_id"),
        Index("ix_game_season_type", "season", "game_type"),
    )
