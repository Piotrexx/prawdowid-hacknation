"""Konta moderatorów, opinie, audyt i przełącznik modelu."""

from __future__ import annotations

API = "/api/v1"
PASSWORD = "BardzoTajne123!x"


def _login(client, email: str = "admin@example.com", password: str = PASSWORD):
    return client.post(
        f"{API}/admin/auth/login", json={"email": email, "password": password}
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap(client):
    store = client.app.state.moderator_store
    account, created, generated = store.bootstrap_superuser(
        "admin@example.com", PASSWORD, "Admin Testowy"
    )
    assert created is True and generated is None
    return account


def test_login_profile_and_notification_settings(client):
    _bootstrap(client)
    assert client.get(f"{API}/admin/auth/me").status_code == 401

    response = _login(client)
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    assert response.json()["moderator"]["role"] == "superuser"

    me = client.get(f"{API}/admin/auth/me", headers=_bearer(token))
    assert me.status_code == 200, me.text
    assert me.json()["moderator"]["email"] == "admin@example.com"
    assert me.json()["push_available"] is True
    assert me.json()["email_available"] is False

    public_key = client.get(f"{API}/admin/auth/me/push-public-key", headers=_bearer(token))
    assert public_key.status_code == 200
    assert public_key.json()["configured"] is True
    assert len(public_key.json()["public_key"]) > 60

    subscribed = client.post(
        f"{API}/admin/auth/me/push-subscription",
        headers=_bearer(token),
        json={
            "endpoint": "https://push.example.com/subscription/abc",
            "keys": {"p256dh": "x" * 40, "auth": "y" * 20},
        },
    )
    assert subscribed.status_code == 204
    removed = client.delete(
        f"{API}/admin/auth/me/push-subscription",
        headers=_bearer(token),
        params={"endpoint": "https://push.example.com/subscription/abc"},
    )
    assert removed.status_code == 204

    updated = client.patch(
        f"{API}/admin/auth/me",
        headers=_bearer(token),
        json={"notify_email": True, "comment_notify_threshold": 3},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["moderator"]["notify_email"] is True
    assert updated.json()["moderator"]["comment_notify_threshold"] == 3

    # Hasło startowe ma przejść walidację, a zmiana wylogowuje sesję.
    changed = client.post(
        f"{API}/admin/auth/me/password",
        headers=_bearer(token),
        json={"current_password": PASSWORD, "new_password": "NoweHaslo123!x"},
    )
    assert changed.status_code == 200, changed.text
    assert client.get(f"{API}/admin/auth/me", headers=_bearer(token)).status_code == 401


def test_superuser_creates_accounts_and_switches_llm(client):
    _bootstrap(client)
    token = _login(client).json()["token"]
    headers = _bearer(token)

    created = client.post(
        f"{API}/admin/moderators",
        headers=headers,
        json={"email": "mod@example.com", "display_name": "Moderator", "role": "moderator"},
    )
    assert created.status_code == 201, created.text
    generated = created.json()["generated_password"]
    assert generated
    assert len(client.get(f"{API}/admin/moderators", headers=headers).json()) == 2

    mod_token = _login(client, "mod@example.com", generated).json()["token"]
    providers = client.get(f"{API}/admin/llm/providers", headers=_bearer(mod_token))
    assert providers.status_code == 200
    assert {item["key"] for item in providers.json()} >= {
        "deepseek",
        "openai",
        "anthropic",
        "gemini",
        "openrouter",
        "local",
    }

    forbidden = client.put(
        f"{API}/admin/llm/settings",
        headers=_bearer(mod_token),
        json={"provider": "local", "model": "test", "base_url": "http://localhost:11434/v1"},
    )
    assert forbidden.status_code == 403

    saved = client.put(
        f"{API}/admin/llm/settings",
        headers=headers,
        json={
            "provider": "local",
            "model": "test-local",
            "base_url": "http://localhost:11434/v1",
            "price_input": 0,
            "price_output": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["provider"] == "local"
    assert saved.json()["configured"] is True  # model lokalny nie wymaga klucza

    current = client.get(f"{API}/admin/llm/settings", headers=headers)
    assert current.json()["model"] == "test-local"
    assert client.app.state.service._provider.model == "test-local"


def test_case_comments_and_moderator_history(client):
    _bootstrap(client)
    token = _login(client).json()["token"]
    headers = _bearer(token)
    store = client.app.state.store
    case = store.create_case("Twierdzenie do sprawdzenia", "standard", "web", "a" * 32)

    first = client.post(
        f"{API}/admin/cases/{case.id}/comments",
        headers=headers,
        json={"body": "Sprawdziłem źródło, twierdzenie jest nieaktualne."},
    )
    assert first.status_code == 201, first.text
    assert first.json()["author_email"] == "admin@example.com"

    listed = client.get(f"{API}/admin/cases/{case.id}/comments", headers=headers)
    assert listed.status_code == 200
    assert [item["body"] for item in listed.json()] == [
        "Sprawdziłem źródło, twierdzenie jest nieaktualne."
    ]

    patched = client.patch(
        f"{API}/admin/cases/{case.id}",
        headers=headers,
        json={
            "status": "resolved",
            "claim_text": "Poprawiona treść twierdzenia",
            "risk": "high",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["claim_text"] == "Poprawiona treść twierdzenia"
    assert patched.json()["comments_count"] == 1

    profile = client.get(f"{API}/admin/auth/me", headers=headers).json()
    assert profile["stats"]["comments"] == 1
    assert profile["stats"]["status_changes"] == 1
    assert profile["stats"]["edits"] >= 2  # treść i waga
    assert profile["comments"][0]["case_id"] == case.id
    assert any(action["action"] == "status_change" for action in profile["actions"])
    assert any(action["field"] == "claim_text" for action in profile["actions"])

    deleted = client.delete(
        f"{API}/admin/comments/{first.json()['id']}", headers=headers
    )
    assert deleted.status_code == 200
    assert client.get(f"{API}/admin/cases/{case.id}/comments", headers=headers).json() == []


def test_legacy_admin_token_still_works(client):
    response = client.get(f"{API}/admin/metrics", headers={"X-Admin-Token": "test-token"})
    assert response.status_code == 200


def test_login_link_connects_automatically(client):
    account = _bootstrap(client)
    link = client.app.state.moderator_store.login_link(
        account.id, base_url="http://localhost:3000", hours=1
    )
    assert link.startswith("http://localhost:3000/moderator#token=")
    token = link.split("#token=", 1)[1]
    me = client.get(f"{API}/admin/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["moderator"]["email"] == "admin@example.com"

