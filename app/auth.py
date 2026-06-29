import logging
import os

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def validate_credentials(username: str, password: str) -> bool:
    """Validate username and password against hardcoded credentials from environment."""
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    user_user = os.getenv("USER_USER", "user")
    user_pass = os.getenv("USER_PASS", "user123")

    valid_creds = {admin_user: admin_pass, user_user: user_pass}
    return valid_creds.get(username) == password


def is_admin(username: str) -> bool:
    """Check if username is an admin."""
    admin_user = os.getenv("ADMIN_USER", "admin")
    return username == admin_user


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
