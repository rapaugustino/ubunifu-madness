from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)  # Kaggle TeamID; gender stored in gender column
    name = Column(String(100), nullable=False)
    gender = Column(String(1), nullable=False)  # 'M' or 'W'
    first_d1_season = Column(Integer, nullable=True)
    last_d1_season = Column(Integer, nullable=True)
    espn_id = Column(Integer, nullable=True)
    logo_url = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # hex e.g. "#002B5C"

    season_stats = relationship("TeamSeasonStats", back_populates="team")
    elo_ratings = relationship("EloRating", back_populates="team")
