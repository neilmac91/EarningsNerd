"""Durable, project-owned job attempts; maintenance runs use distinct logical names."""
from sqlalchemy import JSON, Column, DateTime, Index, String

from app.database import Base


class JobRun(Base):
    __tablename__ = "earningsnerd_job_runs"
    __table_args__ = (Index("ix_earningsnerd_job_runs_job_started", "job_name", "started_at"),)

    id = Column(String(36), primary_key=True)
    job_name = Column(String(80), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False)
    error_type = Column(String(120), nullable=True)
    counters = Column(JSON, nullable=True)
