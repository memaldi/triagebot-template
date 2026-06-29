import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256

logger = logging.getLogger(__name__)

_ALLOWED_UPDATE_FIELDS = {
    "title",
    "description",
    "category",
    "priority",
    "tags",
    "status",
}


def hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def _seed_default_users(conn: sqlite3.Connection) -> None:
    # Seed demo users from environment defaults for local workshop usage.
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    user_user = os.getenv("USER_USER", "user")
    user_pass = os.getenv("USER_PASS", "user123")
    users = [
        (admin_user, hash_password(admin_pass), "admin"),
        (user_user, hash_password(user_pass), "user"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        users,
    )


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
            author TEXT NOT NULL DEFAULT 'anonymous',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
            created_at TEXT NOT NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE tickets ADD COLUMN author TEXT NOT NULL DEFAULT 'anonymous'")
    except sqlite3.OperationalError:
        pass
    _seed_default_users(conn)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d


def create_user(username: str, password: str, role: str = "user") -> dict:
    now = datetime.now(UTC).isoformat()
    role = "admin" if role == "admin" else "user"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, now),
        )
    return get_user(username)


def get_user(username: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT username, password_hash, role, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None



def create_ticket(
    title: str,
    description: str,
    category: str,
    priority: str,
    tags: list,
    author: str = "anonymous",
) -> dict:
    logger.debug(
        "create_ticket: title=%.80s category=%s priority=%s author=%s",
        title,
        category,
        priority,
        author,
    )
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tickets"
            " (title, description, category, priority, tags, status,"
            " author, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
            (title, description, category, priority, json.dumps(tags), author, now, now),
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
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    author: str | None = None,
) -> list[dict]:
    logger.debug(
        "list_tickets: category=%s priority=%s status=%s author=%s",
        category,
        priority,
        status,
        author,
    )
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list = []
    if author:
        query += " AND author = ?"
        params.append(author)
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
    invalid_fields = [key for key in kwargs if key not in _ALLOWED_UPDATE_FIELDS]
    if invalid_fields:
        logger.warning("update_ticket: ignored unsupported fields=%s", invalid_fields)
    safe_kwargs = {key: value for key, value in kwargs.items() if key in _ALLOWED_UPDATE_FIELDS}
    if not safe_kwargs:
        return get_ticket(ticket_id)
    now = datetime.now(UTC).isoformat()
    if "tags" in safe_kwargs and isinstance(safe_kwargs["tags"], list):
        safe_kwargs["tags"] = json.dumps(safe_kwargs["tags"])
    safe_kwargs["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in safe_kwargs)
    values = list(safe_kwargs.values()) + [ticket_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", values)
    return get_ticket(ticket_id)


def delete_ticket(ticket_id: int) -> bool:
    logger.debug("delete_ticket: id=%s", ticket_id)
    with get_connection() as conn:
        result = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    return result.rowcount > 0
