"""Accounts: password hashing, sessions, and the /api/auth routes.

Passwords
    PBKDF2-HMAC-SHA256 with a random 16-byte salt per user and 600,000 iterations
    (OWASP 2023 guidance), stored as  pbkdf2_sha256$<iterations>$<salt>$<hex digest>.
    Seed users use the older  pbkdf2_sha256$<salt>$<hex digest>  format (120,000
    iterations); those hashes still verify. Plaintext passwords are never stored or logged.

Sessions
    A random 256-bit token goes to the browser in an HttpOnly, SameSite=Lax cookie.
    The database stores only its SHA-256 hash, so a leaked DB can't be used to log in.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from db import connect
from models import ShopperProfile, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

PBKDF2_ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000  # seed-data hashes have no iteration field
SESSION_COOKIE = "cc_session"
SESSION_TTL = timedelta(days=7)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # set to 1 behind HTTPS

MAX_FAILED_LOGINS = 5
LOCKOUT_WINDOW = 15 * 60  # seconds

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_RULES = [
    (lambda p: len(p) >= 8, "at least 8 characters"),
    (lambda p: re.search(r"[A-Z]", p), "an uppercase letter"),
    (lambda p: re.search(r"[a-z]", p), "a lowercase letter"),
    (lambda p: re.search(r"\d", p), "a number"),
    (lambda p: re.search(r"[^A-Za-z0-9]", p), "a special character"),
]


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 4:
        algorithm, iterations, salt, expected = parts[0], int(parts[1]), parts[2], parts[3]
    elif len(parts) == 3:
        algorithm, salt, expected = parts
        iterations = LEGACY_ITERATIONS
    else:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return hmac.compare_digest(digest.hex(), expected)


# Used when the email doesn't exist, so a failed login takes the same time either
# way and response timing doesn't reveal which emails have accounts.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def password_problems(password: str) -> list[str]:
    return [msg for check, msg in PASSWORD_RULES if not check(password)]


# ---------- Brute-force protection ----------

_failures: dict[str, deque[float]] = defaultdict(deque)


def _too_many_failures(key: str) -> bool:
    attempts = _failures[key]
    while attempts and attempts[0] < time.time() - LOCKOUT_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_FAILED_LOGINS


# ---------- Sessions ----------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + SESSION_TTL
    with closing(connect(readonly=False)) as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, _token_hash(token), expires.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
        conn.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,  # JavaScript (and any injected script) can't read it
        samesite="lax",  # not sent on cross-site POSTs (CSRF protection)
        secure=COOKIE_SECURE,
        path="/",
    )


def _to_user(row) -> User:
    first, last = row["first_name"], row["last_name"]
    if not first:  # older rows may only have the combined name
        first, _, last = (row["name"] or "").partition(" ")
    return User(id=row["id"], first_name=first or "", last_name=last or "", email=row["email"])


def current_user_optional(cc_session: str | None = Cookie(default=None)) -> User | None:
    if not cc_session:
        return None
    with closing(connect()) as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (_token_hash(cc_session),),
        ).fetchone()
    return _to_user(row) if row else None


def shopper_profile(user_id: int) -> ShopperProfile | None:
    """Fresh name/email for the agent, read from the users table for the session's own account."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    u = _to_user(row)
    return ShopperProfile(
        user_id=u.id,
        first_name=u.first_name,
        last_name=u.last_name,
        email=u.email,
        member_since=(row["created_at"] or "")[:10],
    )


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


# ---------- Routes ----------

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register", response_model=User, status_code=201)
def register(req: RegisterRequest, response: Response) -> User:
    first, last, email = req.first_name.strip(), req.last_name.strip(), req.email.strip().lower()
    errors: dict[str, str] = {}
    if not first:
        errors["first_name"] = "First name is required."
    if not last:
        errors["last_name"] = "Last name is required."
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if problems := password_problems(req.password):
        errors["password"] = "Password needs " + ", ".join(problems) + "."
    if req.password != req.confirm_password:
        errors["confirm_password"] = "Passwords don't match."
    if errors:
        raise HTTPException(status_code=422, detail={"fields": errors})

    with closing(connect(readonly=False)) as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(
                status_code=409,
                detail={"fields": {"email": "An account with this email already exists. Try logging in."}},
            )
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (f"{first} {last}", email, hash_password(req.password), first, last),
        )
        conn.commit()
        user_id = cur.lastrowid

    _start_session(response, user_id)
    return User(id=user_id, first_name=first, last_name=last, email=email)


@router.post("/login", response_model=User)
def login(req: LoginRequest, request: Request, response: Response) -> User:
    email = req.email.strip().lower()
    key = f"{request.client.host if request.client else '?'}|{email}"
    if _too_many_failures(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait 15 minutes and try again.")

    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()

    ok = verify_password(req.password, row["password_hash"] if row else _DUMMY_HASH)
    if not (row and ok):
        _failures[key].append(time.time())
        # Same message whether the email or the password was wrong.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    _failures.pop(key, None)
    _start_session(response, row["id"])
    return _to_user(row)


@router.post("/logout", status_code=204)
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> None:
    if cc_session:
        with closing(connect(readonly=False)) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
            conn.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=User)
def me(user: User = Depends(current_user)) -> User:
    return user
