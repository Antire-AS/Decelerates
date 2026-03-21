"""Entra ID authentication helpers for Streamlit on Azure Container Apps Easy Auth.

Container Apps Easy Auth intercepts all requests and injects user claims.
The /.auth/me endpoint returns the current user's claims as JSON.
We fetch it client-side via a hidden iframe/JS component and cache in session_state.
"""
import json
import streamlit as st
import streamlit.components.v1 as components


_AUTH_ME_JS = """
<script>
(function() {
  fetch('/.auth/me')
    .then(r => r.json())
    .then(data => {
      const user = data && data[0];
      if (!user) return;
      const claims = {};
      (user.user_claims || []).forEach(c => { claims[c.typ] = c.val; });
      const result = {
        user_id:      user.user_id || '',
        provider:     user.provider_name || '',
        name:         claims['name'] || claims['preferred_username'] || user.user_id || '',
        email:        claims['preferred_username'] || claims['email'] || '',
        roles:        user.user_roles || [],
      };
      window.parent.postMessage({type: 'auth_me', data: result}, '*');
    })
    .catch(() => {
      window.parent.postMessage({type: 'auth_me', data: null}, '*');
    });
})();
</script>
"""


def get_user() -> dict | None:
    """Return cached user info dict or None if not authenticated / not on Azure."""
    return st.session_state.get("_auth_user")


def is_manager() -> bool:
    user = get_user()
    if not user:
        return False
    return "Manager" in (user.get("roles") or [])


def render_auth_bootstrap() -> None:
    """Call once at app startup to fetch /.auth/me and cache user in session_state.
    No-ops if already loaded or running outside Azure Easy Auth.
    """
    if "_auth_loaded" in st.session_state:
        return

    # Use a tiny hidden component to fetch /.auth/me from the browser
    result = components.declare_component(
        "auth_me_fetcher",
        path=None,
        url=None,
    ) if False else None  # placeholder — use html component instead

    # Simpler: inject JS that posts to parent, read via query params workaround
    # For now, try a direct server-side fetch of /.auth/me via requests
    # (works when Streamlit server and Easy Auth sidecar are co-located)
    try:
        import requests as _req
        import os
        # In Container Apps, /.auth/me is served on the same host
        host = os.getenv("WEBSITE_HOSTNAME") or "localhost"
        r = _req.get(f"http://localhost:8501/.auth/me", timeout=2)
        if r.ok:
            data = r.json()
            if data and len(data) > 0:
                user = data[0]
                claims = {c["typ"]: c["val"] for c in (user.get("user_claims") or [])}
                st.session_state["_auth_user"] = {
                    "user_id": user.get("user_id", ""),
                    "name":    claims.get("name") or claims.get("preferred_username") or user.get("user_id", ""),
                    "email":   claims.get("preferred_username") or claims.get("email") or "",
                    "roles":   user.get("user_roles") or [],
                }
            else:
                st.session_state["_auth_user"] = None
        else:
            st.session_state["_auth_user"] = None
    except Exception:
        st.session_state["_auth_user"] = None

    st.session_state["_auth_loaded"] = True


def render_user_badge() -> None:
    """Show logged-in user name + role badge in the sidebar."""
    render_auth_bootstrap()
    user = get_user()
    if not user:
        return
    name  = user.get("name") or user.get("email") or "Bruker"
    email = user.get("email", "")
    roles = user.get("roles") or []
    role_badge = " 🔑 Manager" if "Manager" in roles else ""
    with st.sidebar:
        st.markdown(f"**👤 {name}**{role_badge}")
        if email:
            st.caption(email)
        if st.button("Logg ut", key="logout_btn"):
            st.markdown('<meta http-equiv="refresh" content="0;url=/.auth/logout">', unsafe_allow_html=True)
