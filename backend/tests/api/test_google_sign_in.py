import pytest

from app.api.features.auth.domain.google_identity import GoogleIdentity
from app.api.features.auth.services import google_tokens
from app.infrastructure.config import get_settings
from tests.api.support import PASSWORD

NEW_PASSWORD = "a much better password"


@pytest.fixture
def google(monkeypatch):
    """Credentials the fake Google accepts, by token string."""
    issued: dict[str, GoogleIdentity] = {}

    async def verify(credential: str) -> GoogleIdentity | None:
        return issued.get(credential)

    monkeypatch.setattr(google_tokens, "verify", verify)
    return issued


def credential(google, subject, email, *, verified=True, name="Alice Liddell"):
    token = f"token-{len(google)}"
    google[token] = GoogleIdentity(subject=subject, email=email, email_verified=verified, name=name)
    return token


def sign_in(anon, token):
    return anon.post("/auth/google", json={"credential": token})


def test_the_browser_learns_the_client_id_from_the_server(anon):
    response = anon.get("/auth/google")

    assert response.json() == {"clientId": get_settings().google_client_id}


def test_a_new_google_identity_gets_a_confirmed_account_without_password(anon, google, mails):
    response = sign_in(anon, credential(google, "g-1", "alice@gmail.com"))
    anon.adopt(response)

    assert anon.user["emailVerified"] is True
    assert anon.user["hasPassword"] is False
    assert anon.user["googleLinked"] is True
    assert anon.user["username"] == "alice"
    assert anon.user["displayName"] == "Alice Liddell"
    assert anon.own_entry()["name"] == "Alice Liddell"
    assert mails == []


def test_the_same_identity_signs_in_to_the_same_account(anon, google):
    first = sign_in(anon, credential(google, "g-1", "alice@gmail.com")).json()["user"]
    again = sign_in(anon, credential(google, "g-1", "renamed@gmail.com")).json()["user"]

    assert again["id"] == first["id"]
    assert again["email"] == "alice@gmail.com"


def test_a_taken_handle_gets_the_next_free_number(register, anon, google):
    register("alice")
    register("alice2")

    response = sign_in(anon, credential(google, "g-1", "alice@gmail.com"))

    assert response.json()["user"]["username"] == "alice3"


def test_a_short_address_and_no_name_still_make_valid_names(anon, google):
    user = sign_in(anon, credential(google, "g-1", "jo@gmail.com", name=None)).json()["user"]

    assert user["username"] == "joplayer"
    assert user["displayName"] == "jo"


def test_a_confirmed_account_with_the_address_is_linked_and_keeps_its_password(
    register, anon, session, google
):
    alice = register("alice")
    session.sql("UPDATE users SET email_verified_at = now() WHERE id = :id", id=alice.id)

    user = sign_in(anon, credential(google, "g-1", "alice@darts.example.org")).json()["user"]

    assert user["id"] == alice.id
    assert user["googleLinked"] is True
    assert user["hasPassword"] is True
    assert anon.post("/auth/refresh", refresh=alice.refresh_token).status_code == 200
    login = anon.post("/auth/login", json={"identifier": "alice", "password": PASSWORD})
    assert login.status_code == 200


def test_an_unconfirmed_account_loses_its_password_and_sessions_when_linked(register, anon, google):
    squatter = register("alice")

    user = sign_in(anon, credential(google, "g-1", "alice@darts.example.org")).json()["user"]

    assert user["id"] == squatter.id
    assert user["emailVerified"] is True
    assert user["hasPassword"] is False
    assert anon.post("/auth/refresh", refresh=squatter.refresh_token).status_code == 401
    login = anon.post("/auth/login", json={"identifier": "alice", "password": PASSWORD})
    assert login.status_code == 401


def test_an_address_linked_to_another_google_identity_is_not_taken_over(anon, google):
    sign_in(anon, credential(google, "g-1", "alice@gmail.com"))

    response = sign_in(anon, credential(google, "g-2", "alice@gmail.com"))

    assert response.status_code == 409


def test_an_unconfirmed_google_address_makes_no_account(anon, session, google):
    response = sign_in(anon, credential(google, "g-1", "alice@gmail.com", verified=False))

    assert response.status_code == 403
    assert session.sql("SELECT id FROM users") == []


def test_a_credential_google_does_not_vouch_for_is_refused(anon, google):
    assert sign_in(anon, "forged").status_code == 401


def test_a_google_account_has_no_password_to_sign_in_with(anon, google):
    sign_in(anon, credential(google, "g-1", "alice@gmail.com"))

    for password in ("", PASSWORD):
        login = anon.post("/auth/login", json={"identifier": "alice", "password": password})
        assert login.status_code == 401


def test_a_google_account_confirms_changes_with_a_fresh_google_sign_in(anon, google):
    anon.adopt(sign_in(anon, credential(google, "g-1", "alice@gmail.com")))

    stranger = credential(google, "g-2", "mallory@gmail.com")
    assert anon.delete("/auth/me", json={"googleCredential": stranger}).status_code == 403
    assert anon.delete("/auth/me", json={"currentPassword": ""}).status_code == 403
    assert anon.delete("/auth/me", json={}).status_code == 403

    own = credential(google, "g-1", "alice@gmail.com")
    assert anon.delete("/auth/me", json={"googleCredential": own}).status_code == 204
    assert anon.get("/auth/me").status_code == 401


def test_a_google_account_sets_a_password_and_can_then_use_it(anon, google):
    anon.adopt(sign_in(anon, credential(google, "g-1", "alice@gmail.com")))

    response = anon.put(
        "/auth/me/password",
        json={"googleCredential": credential(google, "g-1", "alice@gmail.com"), "newPassword": NEW_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["user"]["hasPassword"] is True
    login = anon.post("/auth/login", json={"identifier": "alice", "password": NEW_PASSWORD})
    assert login.status_code == 200


def test_a_linked_account_confirms_with_either_proof(register, anon, session, google, mails):
    alice = register("alice")
    session.sql("UPDATE users SET email_verified_at = now() WHERE id = :id", id=alice.id)
    sign_in(anon, credential(google, "g-1", "alice@darts.example.org"))

    by_password = alice.put(
        "/auth/me/email", json={"newEmail": "a@darts.example.org", "currentPassword": PASSWORD}
    )
    by_google = alice.put(
        "/auth/me/email",
        json={
            "newEmail": "b@darts.example.org",
            "googleCredential": credential(google, "g-1", "alice@darts.example.org"),
        },
    )

    assert (by_password.status_code, by_google.status_code) == (204, 204)
