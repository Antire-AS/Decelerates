"""Azure AD JWT authentication — get_current_user FastAPI dependency.

Auth gate: ENVIRONMENT=production blocks all bypass attempts. In dev/staging,
set AUTH_DISABLED=1 to skip token validation entirely. Tokens are validated
against AZURE_TENANT_ID / AUTH_AUDIENCE. AUTH_AUDIENCE is the App ID URI for
the frontend App Registration, e.g. api://514e4f92-...
(AZURE_CLIENT_ID is reserved for the managed identity — do NOT use it as the JWT audience.)

Usage in routers:
    from api.auth import get_current_user, CurrentUser
    from fastapi import Depends

    @router.get("/protected")
    def my_endpoint(user: CurrentUser = Depends(get_current_user)):
        ...
"""
import logging
import os
from dataclasses import dataclass
from typing import Optional

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.dependencies import get_db

_log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

# ── Auth toggle ───────────────────────────────────────────────────────────────
# Auth is ON by default everywhere. To bypass JWT validation in dev/staging:
#     ENVIRONMENT=development AUTH_DISABLED=1 uv run uvicorn api.main:app
# Production safety: when ENVIRONMENT=production, AUTH_DISABLED is IGNORED —
# auth cannot be disabled in prod regardless of the env var. This is enforced
# in tests/unit/test_auth_safety.py.
def _is_auth_disabled() -> bool:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        return False
    return os.getenv("AUTH_DISABLED", "").lower() in ("true", "1", "yes")
# ─────────────────────────────────────────────────────────────────────────────

# JWKS cache — populated lazily on first token validation, one entry per worker
_jwks_cache: Optional[dict] = None


@dataclass
class CurrentUser:
    email:   str
    name:    str
    oid:     str
    firm_id: int = 1


def _get_jwks(tenant_id: str) -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


def _validate_token(token: str) -> dict:
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    # AUTH_AUDIENCE = App Registration client ID (the Next.js frontend's
    # NextAuth Azure AD app — used to issue id_tokens that the API validates).
    # Falls back to AZURE_CLIENT_ID only if AUTH_AUDIENCE is absent (legacy / local dev).
    audience  = os.getenv("AUTH_AUDIENCE") or os.getenv("AZURE_CLIENT_ID", "")
    if not tenant_id or not audience:
        raise ValueError("AZURE_TENANT_ID and AUTH_AUDIENCE must be set for JWT validation")

    # Multi-tenant mode: AZURE_TENANT_ID=common accepts tokens from any Microsoft tenant.
    # In this mode we validate the signature and audience but skip the issuer check,
    # since each external user's token will carry their own tenant in the issuer claim.
    multi_tenant = tenant_id.lower() == "common"
    jwks_tenant  = "common" if multi_tenant else tenant_id
    jwks   = _get_jwks(jwks_tenant)
    header = jwt.get_unverified_header(token)
    try:
        matching = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    except StopIteration:
        raise jwt.InvalidTokenError("No matching key found in JWKS")
    key = jwt.algorithms.RSAAlgorithm.from_jwk(matching)

    decode_kwargs: dict = {"algorithms": ["RS256"], "audience": audience}
    if multi_tenant:
        decode_kwargs["options"] = {"verify_iss": False}
    else:
        decode_kwargs["issuer"] = f"https://login.microsoftonline.com/{tenant_id}/v2.0"

    return jwt.decode(token, key, **decode_kwargs)


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[CurrentUser]:
    """Like get_current_user but returns None instead of 401 when no token is present."""
    if _is_auth_disabled():
        return CurrentUser(email="dev@local", name="Dev User", oid="dev-oid", firm_id=1)
    if not creds:
        return None
    try:
        claims = _validate_token(creds.credentials)
    except Exception:
        return None
    oid   = claims.get("oid", "")
    email = claims.get("preferred_username") or claims.get("email", "")
    name  = claims.get("name", "")
    from api.services.user_service import UserService
    user = UserService(db).get_or_create(oid=oid, email=email, name=name)
    return CurrentUser(email=email, name=name, oid=oid, firm_id=user.firm_id)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency — validates the bearer token and returns the current user.

    With ENVIRONMENT != "production" AND AUTH_DISABLED=1 returns a dev user
    without hitting Azure AD. In production, AUTH_DISABLED is ignored.
    On first login, auto-provisions the user in the users table.
    """
    if _is_auth_disabled():
        return CurrentUser(email="dev@local", name="Dev User", oid="dev-oid", firm_id=1)

    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = _validate_token(creds.credentials)
    except Exception as exc:
        _log.debug("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    oid   = claims.get("oid", "")
    email = claims.get("preferred_username") or claims.get("email", "")
    name  = claims.get("name", "")

    from api.services.user_service import UserService
    user = UserService(db).get_or_create(oid=oid, email=email, name=name)
    return CurrentUser(email=email, name=name, oid=oid, firm_id=user.firm_id)
