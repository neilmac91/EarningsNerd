"""One fleet SEC admission/cooldown row, seeded by migrations only. create_all creates the table empty where they have
not run, and admission fails closed until the seed row exists."""
from sqlalchemy import CheckConstraint, Column, DateTime, SmallInteger, func

from app.database import Base


class SECRequestGate(Base):
    __tablename__ = "earningsnerd_sec_request_gate"
    __table_args__ = (CheckConstraint("id = 1"),)

    id = Column(SmallInteger, primary_key=True)
    next_admission_at = Column(DateTime(timezone=True), nullable=False)
    cooldown_until = Column(DateTime(timezone=True), nullable=False, server_default=func.to_timestamp(0))
