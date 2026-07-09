import jwt
import bcrypt
from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import request, redirect, url_for, g, current_app, flash


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def issue_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "name": user["name"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str):
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def load_current_user():
    """Populates g.user from the session cookie's JWT, if present and valid."""
    token = request.cookies.get("access_token")
    g.user = decode_token(token) if token else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not getattr(g, "user", None):
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if g.user.get("role") != role:
                flash("You don't have access to that page.", "error")
                return redirect(url_for("main.index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator
