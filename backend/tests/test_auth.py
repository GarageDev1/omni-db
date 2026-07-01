def test_login_success(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert "access_token" in r.json()["data"]

def test_login_wrong_password(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

def test_register(client):
    r = client.post("/api/v1/auth/register",
                    json={"username": "newuser", "email": "new@test.com", "password": "pass123"})
    assert r.status_code == 201
    assert r.json()["data"]["username"] == "newuser"

def test_register_duplicate(client, admin_user):
    r = client.post("/api/v1/auth/register",
                    json={"username": "admin", "email": "other@test.com", "password": "pass123"})
    assert r.status_code == 409

def test_profile_requires_auth(client):
    r = client.get("/api/v1/auth/profile")
    assert r.status_code == 403

def test_profile_with_token(client, auth_headers):
    r = client.get("/api/v1/auth/profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "admin"

def test_change_password(client, auth_headers):
    r = client.put("/api/v1/auth/password",
                   json={"current_password": "admin123", "new_password": "newpass456"},
                   headers=auth_headers)
    assert r.status_code == 200

def test_change_password_wrong_current(client, auth_headers):
    r = client.put("/api/v1/auth/password",
                   json={"current_password": "wrong", "new_password": "newpass"},
                   headers=auth_headers)
    assert r.status_code == 400

def test_casdoor_config_disabled(client):
    r = client.get("/api/v1/auth/casdoor/config")
    assert r.status_code == 200
    assert r.json()["data"]["enabled"] is False

def test_casdoor_callback_issues_local_jwt(client, db, monkeypatch):
    from app.models.user import User
    from app.routers import auth
    from app.services.auth_service import hash_password

    def fake_exchange(db_session, code, redirect_uri=None):
        user = User(
            username="sso-user",
            email="sso@example.com",
            password_hash=hash_password("unused"),
            role="admin",
            casdoor_id="garage/sso-user",
            display_name="SSO User",
            avatar="https://example.com/avatar.png",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    monkeypatch.setattr(auth.casdoor_service, "exchange_code_and_sync_user", fake_exchange)

    r = client.post(
        "/api/v1/auth/casdoor/callback",
        json={"code": "oauth-code", "state": "state-1", "redirect_uri": "http://localhost:5173/auth/callback"},
    )
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    profile = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["data"]["role"] == "admin"
    assert profile.json()["data"]["display_name"] == "SSO User"

def test_casdoor_role_mapping_from_groups(monkeypatch):
    from app.services import casdoor_service

    monkeypatch.setattr(casdoor_service.settings, "casdoor_admin_roles", "admin,omni-admin")
    monkeypatch.setattr(casdoor_service.settings, "casdoor_editor_roles", "editor,omni-editor")

    assert casdoor_service._map_role({"groups": [{"name": "/garage/omni-admin"}]}) == "admin"
    assert casdoor_service._map_role({"roles": ["omni-editor"]}) == "editor"
    assert casdoor_service._map_role({"roles": ["member"]}) == "viewer"
