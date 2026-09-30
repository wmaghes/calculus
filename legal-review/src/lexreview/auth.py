"""Authentication: argon2id passwords, TOTP MFA, server-side sessions.

* Passwords: argon2id (argon2-cffi defaults), minimum length 12.
* MFA: RFC 6238 TOTP. Required unless LEXREVIEW_REQUIRE_MFA=0 (dev only;
  config refuses that in production). A TOTP code can be used only once
  (replay protection via the last accepted time step).
* Lockout: 5 consecutive failures lock the account for 15 minutes.
* Sessions: 256-bit random bearer tokens. Only a SHA-256 of the token is
  stored. Absolute lifetime 8 h, idle timeout 30 min.
* Login failures return one generic error. Unknown users still pay the
  argon2 cost so timing does not reveal which usernames exist.

Production should delegate to the firm's IdP (OIDC/SAML) with MFA enforced
there. That adapter is an open item (SECURITY.md).
"""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from .errors import AuthError

MIN_PASSWORD = 12
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
SESSION_ABSOLUTE = 8 * 3600
SESSION_IDLE = 30 * 60

_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("dummy-password-for-timing")


@dataclass(frozen=True)
class Principal:
    user_id: str
    is_sysadmin: bool
    session_id: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Authenticator:
    def __init__(self, conn, require_mfa: bool, clock=time.time):
        self._db = conn
        self._require_mfa = require_mfa
        self._clock = clock

    # ---- user management (callers must check sysadmin rights) -----------
    def create_user(self, username: str, password: str, is_sysadmin: bool = False, enroll_totp: bool = True) -> tuple[str, str | None]:
        if len(password) < MIN_PASSWORD:
            raise AuthError("password_too_short")
        user_id = "u_" + uuid.uuid4().hex[:16]
        totp = pyotp.random_base32() if enroll_totp else None
        self._db.execute(
            "INSERT INTO users (user_id, username, pw_hash, totp_secret, is_sysadmin, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, username, _ph.hash(password), totp, int(is_sysadmin), self._clock()),
        )
        return user_id, totp

    def user_id_for(self, username: str) -> str | None:
        row = self._db.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
        return row[0] if row else None

    # ---- login ------------------------------------------------------------
    def login(self, username: str, password: str, totp_code: str | None) -> tuple[str, Principal]:
        now = self._clock()
        row = self._db.execute(
            "SELECT user_id, pw_hash, totp_secret, last_totp_step, is_sysadmin, is_active, failed_attempts, locked_until "
            "FROM users WHERE username=?", (username,)).fetchone()
        if row is None:
            try:
                _ph.verify(_DUMMY_HASH, password + "x")
            except VerificationError:
                pass
            raise AuthError()
        user_id, pw_hash, totp_secret, last_step, is_sysadmin, active, fails, locked_until = row
        if not active or locked_until > now:
            raise AuthError()
        try:
            _ph.verify(pw_hash, password)
            pw_ok = True
        except (VerifyMismatchError, VerificationError):
            pw_ok = False
        mfa_ok = False
        step = None
        if totp_secret and totp_code:
            totp = pyotp.TOTP(totp_secret)
            for offset in (0, -1, 1):  # allow one step of clock drift
                t = now + offset * totp.interval
                if secrets.compare_digest(totp.at(t), str(totp_code)):
                    step = int(t // totp.interval)
                    mfa_ok = step > last_step  # replay protection
                    break
        mfa_needed = self._require_mfa or bool(totp_secret)
        if not pw_ok or (mfa_needed and not mfa_ok):
            fails += 1
            self._db.execute(
                "UPDATE users SET failed_attempts=?, locked_until=? WHERE user_id=?",
                (fails, now + LOCK_SECONDS if fails >= MAX_FAILS else 0, user_id))
            raise AuthError()
        self._db.execute(
            "UPDATE users SET failed_attempts=0, locked_until=0, last_totp_step=? WHERE user_id=?",
            (step if step is not None else last_step, user_id))
        token = secrets.token_urlsafe(32)
        session_id = "s_" + uuid.uuid4().hex[:16]
        self._db.execute(
            "INSERT INTO sessions (token_hash, session_id, user_id, created_at, last_seen, expires_at, mfa_verified) VALUES (?,?,?,?,?,?,?)",
            (_token_hash(token), session_id, user_id, now, now, now + SESSION_ABSOLUTE, int(mfa_ok)))
        return token, Principal(user_id, bool(is_sysadmin), session_id)

    def authenticate(self, token: str) -> Principal:
        now = self._clock()
        row = self._db.execute(
            "SELECT s.session_id, s.user_id, s.last_seen, s.expires_at, u.is_sysadmin, u.is_active "
            "FROM sessions s JOIN users u ON u.user_id = s.user_id WHERE s.token_hash=?",
            (_token_hash(token or ""),)).fetchone()
        if row is None:
            raise AuthError()
        session_id, user_id, last_seen, expires_at, is_sysadmin, active = row
        if not active or now > expires_at or now - last_seen > SESSION_IDLE:
            self._db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            raise AuthError()
        self._db.execute("UPDATE sessions SET last_seen=? WHERE session_id=?", (now, session_id))
        return Principal(user_id, bool(is_sysadmin), session_id)

    def logout(self, token: str) -> None:
        self._db.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token or ""),))
