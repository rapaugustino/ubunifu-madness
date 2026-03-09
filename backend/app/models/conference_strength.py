from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, Index

from app.database import Base


class ConferenceStrength(Base):
    __tablename__ = "conference_strength"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)
    conf_abbrev = Column(String(20), ForeignKey("conferences.abbrev"), nullable=False)
    avg_elo = Column(Float, nullable=True)
    elo_depth = Column(Float, nullable=True)
    top5_elo = Column(Float, nullable=True)
    nc_winrate = Column(Float, nullable=True)
    tourney_hist_winrate = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("season", "gender", "conf_abbrev", name="uq_conf_str"),
        Index("ix_conf_str_season_gender", "season", "gender"),
    )
