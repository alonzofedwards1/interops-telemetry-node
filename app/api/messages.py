from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import get_connection, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_CERT_STATUSES = {"Valid", "Expired", "Expiring Soon"}


class MessageMonitorRow(BaseModel):
    transaction_id: str | None = None
    channel: str | None = None
    response_status: int | None = None
    transport_timestamp: datetime | None = None
    endpoint_id: int | None = None
    host: str | None = None
    port: int | None = None
    scheme: str | None = None
    cert_id: int | None = None
    subject_cn: str | None = None
    issuer_cn: str | None = None
    fingerprint_sha1: str | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_self_signed: bool | None = None
    days_until_expiration: float | None = None
    certificate_status: str
    cert_age_years: float | None = None
    detected_via: str


class MessageMonitorPagination(BaseModel):
    total: int
    limit: int
    offset: int


class MessageMonitorResponse(BaseModel):
    data: list[MessageMonitorRow]
    pagination: MessageMonitorPagination


def _normalize_transport_status(response_status: int | None) -> str:
    if response_status is None:
        return "Warning"
    if 200 <= response_status <= 299:
        return "Success"
    if 400 <= response_status <= 599:
        return "Error"
    return "Warning"


def _certificate_status(cert_not_after: datetime | None) -> str:
    now = datetime.now(timezone.utc)
    if cert_not_after is None:
        return "Valid"

    if cert_not_after.tzinfo is None:
        cert_not_after = cert_not_after.replace(tzinfo=timezone.utc)

    if cert_not_after < now:
        return "Expired"
    if cert_not_after <= now + timedelta(days=30):
        return "Expiring Soon"
    return "Valid"


def _parse_limit(limit_raw: str) -> int:
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer") from exc

    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return limit


def _parse_offset(offset_raw: str) -> int:
    try:
        offset = int(offset_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="offset must be an integer") from exc

    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    return offset


def _parse_iso_timestamp(value: str, field_name: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        return datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid ISO timestamp") from exc


@router.get("/api/message-monitor", response_model=MessageMonitorResponse)
async def get_message_monitor(
    limit: str = Query(default="25"),
    offset: str = Query(default="0"),
    start_time: str | None = Query(default=None, alias="startTime"),
    end_time: str | None = Query(default=None, alias="endTime"),
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    db: Any = Depends(get_db),
) -> MessageMonitorResponse:

    parsed_limit = _parse_limit(limit)
    parsed_offset = _parse_offset(offset)

    if status is not None and status not in _ALLOWED_CERT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status must be one of: Valid, Expired, Expiring Soon",
        )

    start_dt = _parse_iso_timestamp(start_time, "startTime") if start_time else None
    end_dt = _parse_iso_timestamp(end_time, "endTime") if end_time else None

    filter_values: list[Any] = []
    where_clauses: list[str] = []

    def add_filter(clause_template: str, value: Any) -> None:
        filter_values.append(value)
        where_clauses.append(clause_template.format(param=f"${len(filter_values)}"))

    if start_dt is not None:
        add_filter("t.timestamp >= {param}", start_dt)

    if end_dt is not None:
        add_filter("t.timestamp <= {param}", end_dt)

    if status is not None:
        add_filter(
            """
            CASE
                WHEN c.not_after IS NULL THEN 'Expired'
                WHEN NOW() > c.not_after THEN 'Expired'
                WHEN c.not_after - NOW() <= INTERVAL '30 days' THEN 'Expiring Soon'
                ELSE 'Valid'
            END = {param}
            """,
            status,
        )

    if channel:
        add_filter("t.channel = {param}", channel)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    from_sql = """
        FROM transport_events t
        LEFT JOIN endpoints e ON t.endpoint_id = e.endpoint_id
        LEFT JOIN certificates c ON t.cert_id = c.cert_id
        LEFT JOIN (
            SELECT cert_id, MAX(source) AS source
            FROM endpoint_cert_observations
            GROUP BY cert_id
        ) o ON c.cert_id = o.cert_id
    """

    data_sql = f"""
        SELECT DISTINCT ON (t.transaction_id)
            t.transaction_id,
            t.channel,
            t.response_status,
            t.timestamp AS transport_timestamp,
            e.endpoint_id,
            e.host,
            e.port,
            e.scheme,
            c.cert_id,
            c.subject_cn,
            c.issuer_cn,
            c.fingerprint_sha1,
            c.not_before,
            c.not_after,
            c.first_seen_at,
            c.last_seen_at,
            (c.subject_cn = c.issuer_cn) AS is_self_signed,
            CASE
                WHEN c.not_after IS NOT NULL
                THEN DATE_PART('day', c.not_after - NOW())
                ELSE NULL
            END AS days_until_expiration,
            CASE
                WHEN c.not_after IS NULL THEN 'Expired'
                WHEN NOW() > c.not_after THEN 'Expired'
                WHEN c.not_after - NOW() <= INTERVAL '30 days' THEN 'Expiring Soon'
                ELSE 'Valid'
            END AS certificate_status,
            DATE_PART('year', AGE(NOW(), c.not_before)) AS cert_age_years,
            COALESCE(o.source, 'unknown') AS detected_via
        {from_sql}
        {where_sql}
        ORDER BY t.transaction_id, t.timestamp DESC
        LIMIT ${len(filter_values) + 1}
        OFFSET ${len(filter_values) + 2}
    """

    count_sql = f"""
        SELECT COUNT(DISTINCT t.transaction_id) AS total
        {from_sql}
        {where_sql}
    """

    try:
        data_rows = await db.fetch(
            data_sql,
            *(filter_values + [parsed_limit, parsed_offset]),
        )

        total = await db.fetchval(count_sql, *filter_values)

    except Exception:
        logger.exception("Failed to fetch message monitor data")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch message monitor data",
        )

    return MessageMonitorResponse(
        data=[MessageMonitorRow(**dict(row)) for row in data_rows],
        pagination=MessageMonitorPagination(
            total=int(total or 0),
            limit=parsed_limit,
            offset=parsed_offset,
        ),
    )