import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="SecureCore Banking System",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ensure logs directory exists
import os
if not os.path.exists("logs"):
    os.makedirs("logs")

from utils.auth_guard import is_logged_in, is_admin, get_current_user

# --- PAGE DEFINITIONS ---
def login_page():
    # Centered login card
    col_left, col_center, col_right = st.columns([1, 2, 1])

    with col_center:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="text-align:center">
                <h1 style="color:#1B4F72">🏦 SecureCore Banking</h1>
                <p style="color:#5D6D7E; font-size:1.1rem">Secure - Reliable - Trusted</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # --- Login form ---
        with st.form("login_form", clear_on_submit=False):
            st.subheader("Secure Login")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                with st.spinner("Authenticating..."):
                    try:
                        from core.services.authentication_service import AuthenticationService
                        auth = AuthenticationService()
                        result = auth.login(username, password, ip_address="127.0.0.1")

                        if result.get("success"):
                            st.session_state["session_data"] = {
                                "user_id": result.get("user_id"),
                                "username": result.get("username", username),
                                "role": result.get("role", "customer"),
                                "registration_status": result.get("registration_status", "active"),
                                "session_token": result.get("session_token"),
                                "login_time": datetime.now(),
                                "last_activity": datetime.now(),
                            }
                            st.success("Login successful! Redirecting...")
                            st.rerun()
                        else:
                            st.error("Login failed. Please check your credentials.")
                    except Exception as e:
                        st.error(f"Authentication error: {e}")

        st.markdown("---")
        st.caption("(c) 2026 SecureCore Banking System")


# --- NAVIGATION SETUP ---
if not is_logged_in():
    # Define pages for non-logged-in users
    auth_pages = [
        st.Page(login_page, title="Login", default=True),
        st.Page("pages/0_Register.py", title="Register"),
    ]

    pg = st.navigation(auth_pages)
    pg.run()

else:
    # Define pages based on role
    common_pages = [
        st.Page("pages/1_Dashboard.py", title="Dashboard", default=True),
        st.Page("pages/2_Profile.py", title="My Profile"),
    ]

    customer_pages = [
        st.Page("pages/3_Accounts.py", title="Accounts"),
        st.Page("pages/4_Transactions.py", title="Transactions"),
        st.Page("pages/5_Loans.py", title="Loans"),
        st.Page("pages/6_FD_RD.py", title="FD/RD"),
    ]

    admin_pages = [
        st.Page("pages/7_Reports.py", title="Reports"),
    ]

    # Selection based on role
    if is_admin():
        # Admin can see everything
        pg = st.navigation({
            "Main": common_pages,
            "Banking Ops": customer_pages,
            "Administration": admin_pages
        })
    else:
        # Customers see only common + banking
        pg = st.navigation({
            "Main": common_pages,
            "Banking": customer_pages
        })

    pg.run()
