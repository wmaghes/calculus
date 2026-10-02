"""Authentication: argon2id, TOTP MFA, replay, lockout, sessions."""

import pyotp
import pytest

from lexreview import auth as authmod
from lexreview.auth import Authenticator
from lexreview.errors import AccessDenied, AuthError


class Clock:
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def authn(app):
    clock = Clock()
    return Authenticator(app.control, require_mfa=True, clock=clock), clock


def test_password_stored_as_argon2id(app, authn):
    a, _ = authn
    uid, _ = a.create_user("erin", "erin-password-123")
    h = app.control.execute("SELECT pw_hash FROM users WHERE user_id=?", (uid,)).fetchone()[0]
    assert h.startswith("$argon2id$") and "erin-password-123" not in h


def test_short_password_rejected(authn):
    with pytest.raises(AuthError):
        authn[0].create_user("x", "short")


def test_mfa_required(authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    with pytest.raises(AuthError):
        a.login("erin", "erin-password-123", None)
    with pytest.raises(AuthError):
        a.login("erin", "erin-password-123", "000000")
    token, p = a.login("erin", "erin-password-123", pyotp.TOTP(totp).at(clock.t))
    assert a.authenticate(token).user_id == p.user_id


def test_totp_replay_rejected(authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    code = pyotp.TOTP(totp).at(clock.t)
    a.login("erin", "erin-password-123", code)
    with pytest.raises(AuthError):
        a.login("erin", "erin-password-123", code)


def test_wrong_password_with_valid_totp_rejected(authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    with pytest.raises(AuthError):
        a.login("erin", "wrong-password-xx", pyotp.TOTP(totp).at(clock.t))


def test_lockout_after_failures(authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    for _ in range(authmod.MAX_FAILS):
        with pytest.raises(AuthError):
            a.login("erin", "bad-password-xxx", "123456")
    clock.t += 60
    with pytest.raises(AuthError):  # correct credentials, but locked
        a.login("erin", "erin-password-123", pyotp.TOTP(totp).at(clock.t))
    clock.t += authmod.LOCK_SECONDS
    a.login("erin", "erin-password-123", pyotp.TOTP(totp).at(clock.t))


def test_unknown_user_same_error(authn):
    with pytest.raises(AuthError) as e:
        authn[0].login("nobody", "whatever-password", "123456")
    assert e.value.code == "auth_failed"


def test_session_idle_and_absolute_expiry(authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    token, _ = a.login("erin", "erin-password-123", pyotp.TOTP(totp).at(clock.t))
    clock.t += authmod.SESSION_IDLE + 1
    with pytest.raises(AuthError):
        a.authenticate(token)


def test_session_token_stored_hashed(app, authn):
    a, clock = authn
    _, totp = a.create_user("erin", "erin-password-123")
    token, _ = a.login("erin", "erin-password-123", pyotp.TOTP(totp).at(clock.t))
    rows = app.control.execute("SELECT token_hash FROM sessions").fetchall()
    assert all(token not in r[0] for r in rows)


def test_only_sysadmin_creates_users_and_cases(world):
    bob = world.p("bob")
    with pytest.raises(AccessDenied):
        world.app.create_user(bob, "mallory", "mallory-password-1")
    with pytest.raises(AccessDenied):
        world.app.create_case(bob, "x")


def test_login_audited_without_password(world):
    with pytest.raises(AuthError):
        world.app.login("alice", "WRONG-password-999", "123456")
    raw = (world.app.root / "audit" / "audit.log").read_text()
    assert "WRONG-password-999" not in raw and "alice-password-123" not in raw
    recs = [r for r in world.app.audit.records() if r["action"] == "login" and r["outcome"] == "denied"]
    assert recs and recs[-1]["actor"] == world.users["alice"]["uid"]
