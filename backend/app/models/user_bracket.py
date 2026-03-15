from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint, func

from app.database import Base


class UserBracket(Base):
    __tablename__ = "user_brackets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    season = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)
    picks = Column(JSON, nullable=False)  # slotId -> teamId, same format as localStorage
    is_ai_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "season", "gender", name="uq_user_bracket"),
    )
