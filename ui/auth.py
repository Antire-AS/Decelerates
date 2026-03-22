"""Entra ID authentication helpers for Streamlit on Azure Container Apps Easy Auth.

Container Apps Easy Auth intercepts all incoming requests and injects the
authenticated user's claims as the `X-MS-CLIENT-PRINCIPAL` header (base64 JSON).
Streamlit 1.37+ exposes headers via `st.context.headers`.

Locally (no Easy Auth) the header is absent → user is None → no auth shown.
"""
import base64
import json
import logging

import streamlit as st

log = logging.getLogger(__name__)


def _parse_principal(header_value: str) -> dict | None:
    """Decode the X-MS-CLIENT-PRINCIPAL base64 JSON and return a clean user dict."""
    try:
        data = json.loads(base64.b64decode(header_value + "=="))
        claims = {c["typ"]: c["val"] for c in (data.get("claims") or [])}
        return {
            "user_id": data.get("userId") or claims.get("oid", ""),
            "name":    claims.get("name") or claims.get("preferred_username") or data.get("userDetails", ""),
            "email":   claims.get("preferred_username") or claims.get("email") or data.get("userDetails", ""),
            "roles":   data.get("userRoles") or [],
        }
    except Exception as exc:
        log.debug("auth: failed to parse principal header — %s", exc)
        return None


def _load_user() -> dict | None:
    """Read the current user from Easy Auth headers injected by Container Apps runtime."""
    try:
        headers = st.context.headers
        principal = headers.get("X-Ms-Client-Principal", "")
        if principal:
            return _parse_principal(principal)
        # Simplified fallback — name-only header
        name = headers.get("X-Ms-Client-Principal-Name", "")
        if name:
            return {"user_id": name, "name": name, "email": name, "roles": []}
    except Exception:
        pass
    return None


def get_user() -> dict | None:
    """Return cached user info dict, or None if running locally without Easy Auth."""
    if "_auth_user" not in st.session_state:
        st.session_state["_auth_user"] = _load_user()
    return st.session_state["_auth_user"]


def get_access_token() -> str | None:
    """Return the Azure AD access token injected by Easy Auth, or None when running locally.

    Azure Container Apps Easy Auth injects the user's AAD access token as the
    X-MS-TOKEN-AAD-ACCESS-TOKEN header on every authenticated request to the UI container.
    Streamlit 1.37+ exposes this via st.context.headers (normalised to title-case).
    Locally (no Easy Auth) this header is absent → returns None → API uses AUTH_DISABLED bypass.
    """
    try:
        return st.context.headers.get("X-Ms-Token-Aad-Access-Token") or None
    except Exception:
        return None


def is_manager() -> bool:
    user = get_user()
    if not user:
        return False
    return "Manager" in (user.get("roles") or [])


def render_user_badge() -> None:
    """Render logged-in user name, role, and logout link in the sidebar."""
    user = get_user()
    if not user:
        return  # Running locally or Easy Auth not yet configured

    name  = user.get("name") or user.get("email") or "Bruker"
    email = user.get("email", "")
    roles = [r for r in (user.get("roles") or []) if r not in ("anonymous", "authenticated")]
    role_badge = " 🔑 Manager" if "Manager" in roles else ""

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"**👤 {name}**{role_badge}")
        if email and email != name:
            st.caption(email)
        st.markdown(
            '<a href="/.auth/logout" target="_self" style="font-size:0.8rem;color:#888;">Logg ut</a>',
            unsafe_allow_html=True,
        )
