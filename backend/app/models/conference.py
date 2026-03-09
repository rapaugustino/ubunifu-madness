from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index

from app.database import Base


class Conference(Base):
    __tablename__ = "conferences"

    abbrev = Column(String(20), primary_key=True)
    description = Column(String(200), nullable=False)


class TeamConference(Base):
    __tablename__ = "team_conferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    conf_abbrev = Column(String(20), ForeignKey("conferences.abbrev"), nullable=False)

    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_team_conf_season"),
        Index("ix_team_conf_season_team", "season", "team_id"),
    )
