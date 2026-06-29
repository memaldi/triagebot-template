import logging
from hmac import compare_digest

from fastapi import HTTPException, Request

from app import db

logger = logging.getLogger(__name__)


def validate_credentials(username: str, password: str) -> bool:
    """Validate username and password against persisted users in the database."""
    user = db.get_user(username)
    if not user:
        return False
    expected_hash = user["password_hash"]
    actual_hash = db.hash_password(password)
    return compare_digest(expected_hash, actual_hash)


def is_admin(username: str) -> bool:
    """Check if username has admin role in database."""
    user = db.get_user(username)
    return bool(user and user.get("role") == "admin")


def get_current_user(request: Request) -> str | None:
    """Extract current user from session cookie. Returns None if not authenticated."""
    try:
        cookies = request.cookies.get("session_user")
        return cookies
    except Exception:
        return None


def get_current_user_required(request: Request) -> str:
    """Extract current user from session cookie. Raises 403 if not authenticated."""
    user = get_current_user(request)
    if not user:
        logger.warning("Unauthorized access attempt")
        raise HTTPException(status_code=403, detail="Not authenticated")
    return user


def require_owner_or_admin(ticket_author: str, current_user: str) -> None:
    """Check if current user is the owner or admin. Raises 403 if not."""
    if current_user != ticket_author and not is_admin(current_user):
        logger.warning(
            "Unauthorized modification attempt: user=%s attempting to modify ticket by author=%s",
            current_user,
            ticket_author,
        )
        raise HTTPException(status_code=403, detail="Not authorized to modify this ticket")
