"""Persistence layer for transport events using SQLAlchemy."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .models import TransportEvent


class Base(DeclarativeBase):
    """Declarative base for transport persistence models."""


class TransportEventRecord(Base):
    """SQLAlchemy model representing a persisted transport event."""

    __tablename__ = "transport_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(255), index=True)
    request_method: Mapped[str] = mapped_column(String(32))
    request_url: Mapped[str] = mapped_column(String(2048))
    request_headers: Mapped[dict[str, Any]] = mapped_column(JSON)
    response_status: Mapped[int] = mapped_column(Integer)
    response_duration_ms: Mapped[int] = mapped_column(Integer)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def create_tables(database_url: str) -> None:
    """Create transport tables if they do not already exist."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


class TransportEventStore:
    """Store wrapper for writing and querying TransportEvents."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def upsert_event(self, event: TransportEvent) -> TransportEventRecord:
        """Insert or update an event by transaction ID."""
        with self.session_factory() as session:
            record = self._find_by_transaction_id(session, event.transaction_id)
            if record is None:
                record = TransportEventRecord(transaction_id=event.transaction_id)
                session.add(record)

            record.channel = event.channel
            record.request_method = event.request.method
            record.request_url = event.request.url
            record.request_headers = event.request.headers
            record.response_status = event.response.status
            record.response_duration_ms = event.response.duration_ms
            record.source_ip = event.source_ip
            record.timestamp = event.timestamp

            session.commit()
            session.refresh(record)
            return record

    def _find_by_transaction_id(self, session: Session, transaction_id: str) -> TransportEventRecord | None:
        stmt = select(TransportEventRecord).where(TransportEventRecord.transaction_id == transaction_id)
        return session.execute(stmt).scalar_one_or_none()
