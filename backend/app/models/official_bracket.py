from sqlalchemy import (
    Column, Integer, String, DateTime, JSON, UniqueConstraint, func,
)

from app.database import Base


class OfficialBracket(Base):
    """Stores locked model and agent brackets.

    These are generated once per season/gender/bracket_type and never modified.
    bracket_type is either 'model' or 'agent'.
    """

    __tablename__ = "official_brackets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)
    bracket_type = Column(String(10), nullable=False)  # 'model' or 'agent'
    picks = Column(JSON, nullable=False)  # slotId -> teamId
    metadata_ = Column("metadata", JSON, nullable=True)  # extra info (strategy, notes)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "season", "gender", "bracket_type",
            name="uq_official_bracket",
        ),
    )
