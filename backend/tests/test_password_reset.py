"""Password reset: forgot-password never reveals accounts, links are single use."""

from src.core.security import hash_password, verify_password
from src.modules import password_reset as pr


def test_token_roundtrip_and_single_use(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    old_hash = hash_password("old-password-1")
    token = pr.create_reset_token("p-1", old_hash)
    claims = pr.read_reset_token(token)
    assert claims and claims["sub"] == "p-1"
    assert pr.token_matches_password(claims, old_hash)
    # Once the password changes, the same link must stop working.
    assert not pr.token_matches_password(claims, hash_password("new-password-2"))


def test_normal_login_token_is_not_a_reset_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    from src.core.security import create_access_token

    login_token = create_access_token({"sub": "p-1", "user_type": "passenger"})
    assert pr.read_reset_token(login_token) is None
    assert pr.read_reset_token("not-a-token") is None


def test_reset_token_cannot_authenticate(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    from src.core.security import decode_access_token

    claims = decode_access_token(pr.create_reset_token("p-1", None))
    assert claims.get("user_type") is None  # auth dependency requires it


def test_email_skipped_without_provider(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert pr.send_reset_email("a@b.co", None, "tok") is False
    assert verify_password("x", "bad") is False


def test_forgot_and_reset_flow_end_to_end(client, monkeypatch):
    sent = {}

    def fake_send(to_email, full_name, token):
        sent["to"] = to_email
        sent["token"] = token
        return True

    monkeypatch.setattr("src.main.send_reset_email", fake_send)
    client.post(
        "/auth/register",
        json={"email": "reset@example.com", "password": "first-password-1"},
    )

    # Unknown and known emails get the same answer; only the known one is emailed.
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    known = client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert sent["to"] == "reset@example.com"

    changed = client.post(
        "/auth/reset-password",
        json={"token": sent["token"], "password": "second-password-2"},
    )
    assert changed.status_code == 200
    old = client.post(
        "/auth/passenger/login",
        json={"email": "reset@example.com", "password": "first-password-1"},
    )
    new = client.post(
        "/auth/passenger/login",
        json={"email": "reset@example.com", "password": "second-password-2"},
    )
    assert old.status_code == 401 and new.status_code == 200

    # The same link cannot be used twice.
    again = client.post(
        "/auth/reset-password",
        json={"token": sent["token"], "password": "third-password-3"},
    )
    assert again.status_code == 400
