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
    role:    str = "broker"


def require_role(*allowed_roles: str):
    """FastAPI dependency that checks the current user has one of the allowed roles.

    Usage: `user: CurrentUser = Depends(require_role("admin"))`
    or:    `user: CurrentUser = Depends(require_role("admin", "broker"))`
    """
    def _check(user: CurrentUser = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Krever rolle: {', '.join(allowed_roles)}. Din rolle: {user.role}",
            )
        return user
    return _check


def _get_jwks(tenant_id: str) -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_google_jwks_cache: dict | None = None


def _get_google_jwks() -> dict:
    global _google_jwks_cache
    if _google_jwks_cache:
        return _google_jwks_cache
    resp = requests.get(_GOOGLE_JWKS_URL, timeout=10)
    resp.raise_for_status()
    _google_jwks_cache = resp.json()
    return _google_jwks_cache


def _detect_provider(token: str) -> str:
    """Peek at the unverified payload to determine if this is a Google or Azure token."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        iss = payload.get("iss", "")
        if "accounts.google.com" in iss:
            return "google"
    except Exception:
        pass
    return "azure"


def _validate_token(token: str) -> dict:
    provider = _detect_provider(token)

    if provider == "google":
        return _validate_google_token(token)
    return _validate_azure_token(token)


def _validate_google_token(token: str) -> dict:
    """Validate a Google OAuth2 id_token."""
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID must be set for Google auth")

    jwks = _get_google_jwks()
    header = jwt.get_unverified_header(token)
    try:
        matching = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    except StopIteration:
        raise jwt.InvalidTokenError("No matching Google key found in JWKS")
    key = jwt.algorithms.RSAAlgorithm.from_jwk(matching)

    return jwt.decode(
        token, key,
        algorithms=["RS256"],
        audience=google_client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"],
    )


def _validate_azure_token(token: str) -> dict:
    """Validate an Azure AD / Entra ID JWT."""
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    audience = os.getenv("AUTH_AUDIENCE") or os.getenv("AZURE_CLIENT_ID", "")
    if not tenant_id or not audience:
        raise ValueError("AZURE_TENANT_ID and AUTH_AUDIENCE must be set for JWT validation")

    multi_tenant = tenant_id.lower() == "common"
    jwks_tenant = "common" if multi_tenant else tenant_id
    jwks = _get_jwks(jwks_tenant)
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


# Synthetic dev user used when AUTH_DISABLED=1. The same triple is used by
# both `get_optional_user` and `get_current_user` so a single User row in the
# database satisfies both code paths. Without provisioning this row, every
# router that does `db.query(User).filter(User.azure_oid == user.oid).first()`
# returns 404 in dev mode (notifications, saved_searches, etc).
_DEV_USER_OID   = "dev-oid"
_DEV_USER_EMAIL = "dev@local"
_DEV_USER_NAME  = "Dev User"


def _ensure_dev_user_provisioned(db: Session) -> CurrentUser:
    """Idempotently insert the dev@local row into the users table.

    Called from get_current_user / get_optional_user when AUTH_DISABLED=1.
    Without this, every router that resolves the current user via
    `User.azure_oid` lookup returns 404 in dev mode (UI audit F01, 2026-04-09).
    UserService.get_or_create is itself idempotent — does nothing if the row
    already exists.
    """
    from api.services.user_service import UserService
    svc = UserService(db)
    user = svc.get_or_create(
        oid=_DEV_USER_OID, email=_DEV_USER_EMAIL, name=_DEV_USER_NAME,
    )
    # Reconcile firm_id: if the dev user row predates the demo seed (or the
    # DB was partially reset), it may point at a non-existent firm. Force it
    # back to the default firm so seeded demo data (policies, IDD, insurers,
    # renewals) is always visible in dev mode. MVP polish 2026-04-12.
    _DEFAULT_FIRM_ID = 1
    if user.firm_id != _DEFAULT_FIRM_ID:
        user.firm_id = _DEFAULT_FIRM_ID
        db.commit()
        db.refresh(user)
    # Dev user always gets admin role so all endpoints are accessible in dev mode
    return CurrentUser(
        email=_DEV_USER_EMAIL, name=_DEV_USER_NAME,
        oid=_DEV_USER_OID, firm_id=user.firm_id, role="admin",
    )


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[CurrentUser]:
    """Like get_current_user but returns None instead of 401 when no token is present."""
    if _is_auth_disabled():
        return _ensure_dev_user_provisioned(db)
    if not creds:
        return None
    try:
        claims = _validate_token(creds.credentials)
    except Exception:
        return None
    oid   = claims.get("oid", "")
    email = claims.get("preferred_username") or claims.get("email", "")
    name  = claims.get("name", "")
    firm_id = _resolve_sso_firm(claims, db)
    from api.services.user_service import UserService
    user = UserService(db).get_or_create(oid=oid, email=email, name=name, firm_id=firm_id)
    return CurrentUser(email=email, name=name, oid=oid, firm_id=user.firm_id,
                       role=user.role.value if hasattr(user.role, "value") else str(user.role))


def _validate_and_extract_claims(creds: Optional[HTTPAuthorizationCredentials]) -> dict:
    """Validate JWT token and return claims, or raise 401."""
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing Authorization header", headers={"WWW-Authenticate": "Bearer"})
    try:
        return _validate_token(creds.credentials)
    except Exception as exc:
        _log.debug("Token validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})


def _resolve_sso_firm(claims: dict, db: Session) -> int | None:
    """Try to map Azure AD tenant to a BrokerFirm. Returns firm_id or None."""
    try:
        from api.services.sso_service import SsoService
        return SsoService().resolve_firm_from_token(claims, db).id
    except Exception as exc:
        _log.debug("SSO firm resolution failed (non-fatal): %s", exc)
        return None


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency — validates bearer token, provisions user, returns CurrentUser."""
    if _is_auth_disabled():
        return _ensure_dev_user_provisioned(db)
    claims = _validate_and_extract_claims(creds)
    oid   = claims.get("oid", "")
    email = claims.get("preferred_username") or claims.get("email", "")
    name  = claims.get("name", "")
    firm_id = _resolve_sso_firm(claims, db)
    from api.services.user_service import UserService
    user = UserService(db).get_or_create(oid=oid, email=email, name=name, firm_id=firm_id)
    return CurrentUser(email=email, name=name, oid=oid, firm_id=user.firm_id,
                       role=user.role.value if hasattr(user.role, "value") else str(user.role))
