import re
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services.auth_service import hash_password


class CasdoorAuthError(Exception):
    pass


def is_enabled() -> bool:
    return bool(
        settings.casdoor_endpoint
        and settings.casdoor_client_id
        and settings.casdoor_client_secret
    )


def public_config() -> dict[str, Any]:
    enabled = is_enabled()
    return {
        "enabled": enabled,
        "endpoint": _endpoint() if enabled else "",
        "client_id": settings.casdoor_client_id if enabled else "",
        "redirect_uri": settings.casdoor_redirect_uri if enabled else "",
        "scope": settings.casdoor_scope,
    }


def build_authorization_url(state: str | None = None, redirect_uri: str | None = None) -> str:
    config = public_config()
    if not config["enabled"]:
        raise CasdoorAuthError("Casdoor is not configured")

    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": redirect_uri or config["redirect_uri"],
        "scope": config["scope"],
    }
    if state:
        params["state"] = state
    return f"{config['endpoint']}/login/oauth/authorize?{urlencode(params)}"


def exchange_code_and_sync_user(
    db: Session,
    code: str,
    redirect_uri: str | None = None,
) -> User:
    if not is_enabled():
        raise CasdoorAuthError("Casdoor is not configured")

    token_data = _exchange_code(code, redirect_uri)
    access_token = token_data.get("access_token")
    if not access_token:
        raise CasdoorAuthError("Casdoor did not return an access token")

    token_claims = _decode_without_verification(access_token)
    id_claims = _decode_without_verification(token_data.get("id_token"))
    account = _fetch_account(access_token)
    identity = _identity_from_sources(account, id_claims, token_claims)

    user = _upsert_user(db, identity)
    db.commit()
    db.refresh(user)
    return user


def _endpoint() -> str:
    return settings.casdoor_endpoint.rstrip("/")


def _exchange_code(code: str, redirect_uri: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "grant_type": "authorization_code",
        "client_id": settings.casdoor_client_id,
        "client_secret": settings.casdoor_client_secret,
        "code": code,
    }
    callback_uri = redirect_uri or settings.casdoor_redirect_uri
    if callback_uri:
        payload["redirect_uri"] = callback_uri

    with httpx.Client(timeout=10.0) as client:
        response = client.post(f"{_endpoint()}/api/login/oauth/access_token", json=payload)
        if response.status_code >= 400:
            response = client.post(
                f"{_endpoint()}/api/login/oauth/access_token",
                data=payload,
                auth=(settings.casdoor_client_id, settings.casdoor_client_secret),
            )

    if response.status_code >= 400:
        raise CasdoorAuthError("Casdoor token exchange failed")
    return _unwrap_casdoor_response(response.json())


def _fetch_account(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=10.0) as client:
        for path in ("/api/get-account", "/api/userinfo"):
            response = client.get(f"{_endpoint()}{path}", headers=headers)
            if response.status_code < 400:
                data = _unwrap_casdoor_response(response.json())
                if isinstance(data, dict):
                    return data
    return {}


def _unwrap_casdoor_response(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    if isinstance(data, dict):
        return data
    return {}


def _decode_without_verification(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    try:
        return jwt.get_unverified_claims(token)
    except (JWTError, ValueError):
        return {}


def _identity_from_sources(*sources: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        merged.update({k: v for k, v in source.items() if v not in (None, "")})

    owner = _first_value(merged, "owner", "Owner", "organization", "org")
    name = _first_value(merged, "name", "Name", "preferred_username", "username", "sub", "id")
    casdoor_id = _first_value(merged, "id", "Id", "sub")
    if owner and name:
        casdoor_id = f"{owner}/{name}"
    if not casdoor_id:
        raise CasdoorAuthError("Casdoor account is missing a stable identity")

    display_name = _first_value(merged, "displayName", "display_name", "DisplayName", "name", "Name")
    email = _first_value(merged, "email", "Email")
    avatar = _first_value(merged, "avatar", "Avatar", "picture")

    return {
        "casdoor_id": str(casdoor_id),
        "username": _safe_username(_first_value(merged, "preferred_username", "name", "Name", "username", "sub") or str(casdoor_id)),
        "email": str(email) if email else "",
        "display_name": str(display_name)[:100] if display_name else None,
        "avatar": str(avatar)[:500] if avatar else None,
        "role": _map_role(merged),
    }


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _map_role(data: dict[str, Any]) -> str:
    if data.get("isAdmin") is True or data.get("IsAdmin") is True:
        return "admin"

    values = _collect_role_values(data)
    admin_roles = _configured_values(settings.casdoor_admin_roles)
    editor_roles = _configured_values(settings.casdoor_editor_roles)
    if values & admin_roles:
        return "admin"
    if values & editor_roles:
        return "editor"
    return "viewer"


def _configured_values(raw: str) -> set[str]:
    return {_normalize_role_value(part) for part in raw.split(",") if part.strip()}


def _collect_role_values(data: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("role", "Role", "roles", "Roles", "groups", "Groups", "permissions", "Permissions", "tags", "type", "Type"):
        _collect_value(data.get(key), values)
    expanded = set(values)
    for value in values:
        if "/" in value:
            expanded.add(value.rsplit("/", 1)[-1])
    return expanded


def _collect_value(value: Any, values: set[str]) -> None:
    if value in (None, ""):
        return
    if isinstance(value, str):
        values.add(_normalize_role_value(value))
        return
    if isinstance(value, dict):
        for key in ("name", "Name", "displayName", "DisplayName", "role", "Role"):
            _collect_value(value.get(key), values)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_value(item, values)


def _normalize_role_value(value: str) -> str:
    return value.strip().strip("/").lower()


def _upsert_user(db: Session, identity: dict[str, Any]) -> User:
    user = db.query(User).filter(User.casdoor_id == identity["casdoor_id"]).first()
    if not user and identity["email"]:
        user = db.query(User).filter(User.email == identity["email"]).first()

    if not user:
        username = _unique_username(db, identity["username"])
        email = _unique_email(db, identity["email"] or f"{username}@casdoor.local")
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            role=identity["role"],
            casdoor_id=identity["casdoor_id"],
            display_name=identity["display_name"],
            avatar=identity["avatar"],
            is_active=True,
        )
        db.add(user)
        return user

    user.casdoor_id = identity["casdoor_id"]
    user.role = identity["role"]
    user.display_name = identity["display_name"]
    user.avatar = identity["avatar"]
    user.is_active = True
    if identity["email"] and not _email_taken_by_other(db, identity["email"], user.id):
        user.email = identity["email"]
    return user


def _unique_username(db: Session, username: str) -> str:
    base = username[:50] or "casdoor-user"
    candidate = base
    suffix = 2
    while db.query(User).filter(User.username == candidate).first():
        tail = f"-{suffix}"
        candidate = f"{base[:50 - len(tail)]}{tail}"
        suffix += 1
    return candidate


def _unique_email(db: Session, email: str) -> str:
    local, sep, domain = email.partition("@")
    if not sep:
        local, domain = email, "casdoor.local"
    candidate = f"{local}@{domain}"
    suffix = 2
    while db.query(User).filter(User.email == candidate).first():
        candidate = f"{local}+{suffix}@{domain}"
        suffix += 1
    return candidate


def _email_taken_by_other(db: Session, email: str, user_id: str) -> bool:
    return db.query(User).filter(User.email == email, User.id != user_id).first() is not None


def _safe_username(value: str) -> str:
    username = value.split("@", 1)[0]
    username = re.sub(r"[^a-zA-Z0-9._-]+", "-", username).strip(".-_").lower()
    return username[:50] or "casdoor-user"
