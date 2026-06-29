import json
import logging
import os
import sqlite3
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///triagebot.db")
    return url.removeprefix("sqlite:///")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d


def create_ticket(title: str, description: str, category: str, priority: str, tags: list) -> dict:
    logger.debug("create_ticket: title=%.80s category=%s priority=%s", title, category, priority)
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tickets"
            " (title, description, category, priority, tags, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 'open', ?, ?)",
            (title, description, category, priority, json.dumps(tags), now, now),
        )
        row_id = cursor.lastrowid
    return get_ticket(row_id)


def get_ticket(ticket_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_tickets(
    category: str | None = None, priority: str | None = None, status: str | None = None
) -> list[dict]:
    logger.debug("list_tickets: category=%s priority=%s status=%s", category, priority, status)
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if status:
        query += " AND status = ?"
        params.append(status)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_ticket(ticket_id: int, **kwargs) -> dict | None:
    logger.debug("update_ticket: id=%s fields=%s", ticket_id, list(kwargs.keys()))
    if not kwargs:
        return get_ticket(ticket_id)
    now = datetime.now(UTC).isoformat()
    kwargs["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [ticket_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", values)  # noqa: S608
    return get_ticket(ticket_id)


def delete_ticket(ticket_id: int) -> bool:
    logger.debug("delete_ticket: id=%s", ticket_id)
    with get_connection() as conn:
        result = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    return result.rowcount > 0
