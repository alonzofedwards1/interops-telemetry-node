"""Database persistence for transport events using SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from .models import TransportEvent


class Base(DeclarativeBase):
    """Base SQLAlchemy declarative class."""


class TransportEventRecord(Base):
    """Database model that stores normalized transport events."""

    __tablename__ = "transport_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(255), index=True)

    request_method: Mapped[str] = mapped_column(String(32))
    request_url: Mapped[str] = mapped_column(String(2048))
    request_headers: Mapped[dict] = mapped_column(JSON)

    response_status: Mapped[int] = mapped_column(Integer, index=True)
    response_duration_ms: Mapped[int] = mapped_column(Integer, index=True)

    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TransportEventStore:
    """SQLAlchemy-backed store for ``TransportEvent`` objects."""

    def __init__(self, database_url: str = "sqlite:///transport.db") -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        """Create DB tables if they do not already exist."""

        Base.metadata.create_all(self.engine)

    def upsert_event(self, event: TransportEvent) -> TransportEventRecord:
        """Insert or update one event keyed by ``transaction_id``."""

        with self.session_factory() as session:
            record = self._get_by_transaction_id(session, event.transaction_id)
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

    def _get_by_transaction_id(
        self,
        session: Session,
        transaction_id: str,
    ) -> TransportEventRecord | None:
        return (
            session.query(TransportEventRecord)
            .filter(TransportEventRecord.transaction_id == transaction_id)
            .one_or_none()
        )
