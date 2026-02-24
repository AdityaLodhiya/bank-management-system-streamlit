"""
Authentication guard utilities for Streamlit pages.
Provides login-required and role-based access control.
"""

import streamlit as st
from datetime import datetime, timedelta


SESSION_TIMEOUT_MINUTES = 30


def require_login():
    """Stop page execution if user is not logged in."""
    if "session_data" not in st.session_state:
        st.warning("Please log in to continue.")
        st.stop()
    _check_session_timeout()


def require_role(allowed_roles: list):
    """Stop page execution if user role is not in allowed_roles."""
    require_login()
    user_role = get_user_role()
    if any(role.lower() == user_role for role in allowed_roles):
        return
    st.error("You do not have permission to access this page.")
    st.stop()


def get_current_user() -> dict:
    """Return current session_data or empty dict."""
    return st.session_state.get("session_data", {})


def get_user_role() -> str:
    """Return current user role string in lowercase."""
    role = get_current_user().get("role", "customer")
    return role.lower() if isinstance(role, str) else str(role).lower()


def is_logged_in() -> bool:
    """Check whether a user session exists."""
    return "session_data" in st.session_state


def handle_logout():
    """Logout the current user and rerun."""
    from core.services.authentication_service import AuthenticationService

    auth = AuthenticationService()
    token = st.session_state.get("session_data", {}).get("session_token")
    if token:
        try:
            auth.logout(token)
        except Exception:
            pass
    if "session_data" in st.session_state:
        del st.session_state["session_data"]
    
    # Ensure all auth-related state is cleared
    for key in list(st.session_state.keys()):
        del st.session_state[key]
            
    st.rerun()


def _check_session_timeout():
    """Auto-logout if session has been idle too long."""
    sd = st.session_state.get("session_data")
    if not sd:
        return
    last_activity = sd.get("last_activity")
    if last_activity and datetime.now() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        handle_logout()
    else:
        sd["last_activity"] = datetime.now()


def is_admin() -> bool:
    """Check if current user is an admin."""
    return get_user_role() == "admin"


def is_customer() -> bool:
    """Check if current user is a customer."""
    return get_user_role() == "customer"
