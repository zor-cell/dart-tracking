from datetime import timedelta

import pytest
import time_machine

from tests.api.support import PASSWORD, token_in

NEW_PASSWORD = "a much better password"


def login(anon, identifier, password=PASSWORD):
    return anon.post("/auth/login", json={"identifier": identifier, "password": password})


def test_register_opens_a_session_and_asks_to_confirm_the_address(register, mails):
    alice = register("alice")

    assert alice.user["emailVerified"] is False
    assert alice.own_entry()["name"] == "Alice"
    assert [mail["To"] for mail in mails] == ["alice@darts.example.org"]


@pytest.mark.parametrize(
    ("email", "username", "taken"),
    [
        ("ALICE@darts.example.org", "someone", "email"),
        ("other@darts.example.org", "ALICE", "username"),
    ],
)
def test_register_refuses_a_taken_address_or_handle_in_any_case(register, anon, email, username, taken):
    register("alice")

    response = anon.post(
        "/auth/register",
        json={"email": email, "username": username, "displayName": "X", "password": PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == f"{taken} already in use"


def test_username_cannot_look_like_an_address(anon):
    response = anon.post(
        "/auth/register",
        json={"email": "a@darts.example.org", "username": "a@b", "displayName": "A", "password": PASSWORD},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("identifier", ["alice", "ALICE", "Alice@Darts.Example.org"])
def test_login_by_handle_or_address_in_any_case(register, anon, identifier):
    register("alice")
    assert login(anon, identifier).status_code == 200


def test_login_does_not_reveal_which_accounts_exist(register, anon):
    register("alice")

    wrong_password = login(anon, "alice", "not the password")
    unknown = login(anon, "nobody")

    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json()


def test_failed_logins_lock_the_account_until_the_window_ends(register, anon):
    register("alice")
    for _ in range(10):
        login(anon, "alice@darts.example.org", "wrong")

    response = login(anon, "alice", PASSWORD)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_a_successful_login_clears_the_failures(register, anon):
    register("alice")
    for _ in range(9):
        login(anon, "alice", "wrong")
    assert login(anon, "alice").status_code == 200

    for _ in range(9):
        login(anon, "alice", "wrong")
    assert login(anon, "alice").status_code == 200


def test_refresh_rotates_the_token(register, anon):
    alice = register("alice")
    first = alice.refresh_token

    rotated = anon.post("/auth/refresh", refresh=first)
    replayed = anon.post("/auth/refresh", refresh=first)

    assert rotated.status_code == 200
    assert rotated.cookies.get("refresh_token") not in (None, first)
    assert replayed.status_code == 401
    assert "refresh_token" in replayed.headers["set-cookie"]


def test_refresh_without_a_cookie(anon):
    assert anon.post("/auth/refresh").status_code == 401


def test_logout_ends_the_session_on_the_server(register, anon):
    alice = register("alice")

    assert alice.post("/auth/logout", refresh=alice.refresh_token).status_code == 204
    assert anon.post("/auth/refresh", refresh=alice.refresh_token).status_code == 401


def test_password_change_signs_out_every_other_device(register, anon):
    alice = register("alice")
    phone = login(anon, "alice").cookies.get("refresh_token")

    response = alice.put(
        "/auth/me/password", json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD}
    )

    assert response.status_code == 200
    assert anon.post("/auth/refresh", refresh=phone).status_code == 401
    assert anon.post("/auth/refresh", refresh=alice.refresh_token).status_code == 401
    assert anon.post("/auth/refresh", refresh=response.cookies.get("refresh_token")).status_code == 200
    assert login(anon, "alice").status_code == 401
    assert login(anon, "alice", NEW_PASSWORD).status_code == 200


def test_wrong_current_password_is_forbidden_not_unauthorized(register):
    alice = register("alice")

    response = alice.put(
        "/auth/me/password", json={"currentPassword": "wrong", "newPassword": NEW_PASSWORD}
    )

    assert response.status_code == 403


def test_verify_email_link_works_once(register, anon, mails):
    alice = register("alice")
    token = token_in(mails[-1])

    assert anon.post("/auth/verify-email", json={"token": token}).json()["emailVerified"] is True
    assert anon.post("/auth/verify-email", json={"token": token}).status_code == 400
    assert alice.post("/auth/verify-email/resend").status_code == 409


def test_resending_voids_the_earlier_link(register, anon, mails):
    alice = register("alice")
    first = token_in(mails[-1])

    assert alice.post("/auth/verify-email/resend").status_code == 204

    assert anon.post("/auth/verify-email", json={"token": first}).status_code == 400
    assert anon.post("/auth/verify-email", json={"token": token_in(mails[-1])}).status_code == 200


def test_resend_is_limited(register):
    alice = register("alice")
    statuses = [alice.post("/auth/verify-email/resend").status_code for _ in range(4)]
    assert statuses == [204, 204, 204, 429]


def test_password_reset_for_an_unknown_address_looks_the_same(anon, mails):
    response = anon.post("/auth/password-reset", json={"email": "nobody@darts.example.org"})

    assert response.status_code == 204
    assert mails == []


def test_password_reset_sets_the_password_confirms_the_address_and_signs_out(register, anon, mails):
    alice = register("alice")
    anon.post("/auth/password-reset", json={"email": "ALICE@darts.example.org"})
    token = token_in(mails[-1])

    response = anon.post("/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD})

    assert response.status_code == 204
    assert anon.post("/auth/refresh", refresh=alice.refresh_token).status_code == 401
    assert login(anon, "alice", NEW_PASSWORD).json()["user"]["emailVerified"] is True
    again = anon.post("/auth/password-reset/confirm", json={"token": token, "password": PASSWORD})
    assert again.status_code == 400


def test_a_newer_reset_link_voids_the_older_one(register, anon, mails):
    register("alice")
    anon.post("/auth/password-reset", json={"email": "alice@darts.example.org"})
    older = token_in(mails[-1])
    anon.post("/auth/password-reset", json={"email": "alice@darts.example.org"})

    response = anon.post("/auth/password-reset/confirm", json={"token": older, "password": NEW_PASSWORD})

    assert response.status_code == 400


def change_email(api, email, password=PASSWORD):
    return api.put("/auth/me/email", json={"newEmail": email, "currentPassword": password})


def test_email_change_takes_effect_with_the_link(register, anon, mails):
    alice = register("alice")

    assert change_email(alice, "New@darts.example.org").status_code == 204
    assert alice.get("/auth/me").json()["email"] == "alice@darts.example.org"
    assert mails[-1]["To"] == "new@darts.example.org"

    confirmed = anon.post("/auth/email-change/confirm", json={"token": token_in(mails[-1])})
    assert confirmed.json()["email"] == "new@darts.example.org"
    assert confirmed.json()["emailVerified"] is True


@pytest.mark.parametrize(
    ("email", "password", "status"),
    [
        ("alice@darts.example.org", PASSWORD, 409),
        ("bob@darts.example.org", PASSWORD, 409),
        ("free@darts.example.org", "wrong", 403),
    ],
)
def test_email_change_refusals(register, email, password, status):
    alice = register("alice")
    register("bob")
    assert change_email(alice, email, password).status_code == status


def test_address_taken_before_the_link_is_opened(register, anon, mails):
    alice = register("alice")
    change_email(alice, "wanted@darts.example.org")
    token = token_in(mails[-1])
    register("wanted")

    response = anon.post("/auth/email-change/confirm", json={"token": token})

    assert response.status_code == 409
    assert alice.get("/auth/me").json()["email"] == "alice@darts.example.org"


def test_profile_rename_carries_into_the_own_entry(register):
    alice = register("alice")

    response = alice.put("/auth/me", json={"username": "ALICE", "displayName": "  Ali  "})

    assert response.status_code == 200
    assert response.json()["displayName"] == "Ali"
    assert alice.own_entry()["name"] == "Ali"


@pytest.mark.parametrize(
    ("username", "display_name", "detail"),
    [
        ("BOB", "Alice", "username already in use"),
        ("alice", "carol", "display name in address book"),
    ],
)
def test_profile_rename_refusals(register, username, display_name, detail):
    alice = register("alice")
    register("bob")
    alice.add_player("Carol")

    response = alice.put("/auth/me", json={"username": username, "displayName": display_name})

    assert response.status_code == 409
    assert response.json()["detail"] == detail


@pytest.mark.parametrize("path", ["/settings", "/games"])
def test_a_bad_token_is_an_error_even_where_anonymous_is_allowed(anon, path):
    response = anon.request(
        "GET" if path == "/settings" else "POST",
        path,
        headers={"Authorization": "Bearer not-a-token"},
        json={"mode": 301, "players": [{"name": "Guest"}]},
    )
    assert response.status_code == 401


def test_an_expired_token_is_refused(register):
    alice = register("alice")

    with time_machine.travel(timedelta(minutes=16)):
        assert alice.get("/auth/me").status_code == 401
