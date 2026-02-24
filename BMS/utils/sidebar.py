"""
Shared sidebar renderer for all authenticated pages.
Displays user info, role badge, and logout button.
Conditionally shows navigation links based on user role.
"""

import streamlit as st
from utils.auth_guard import handle_logout, get_current_user, is_admin, is_customer


def render_sidebar():
    """Render the common sidebar on every authenticated page."""
    with st.sidebar:
        st.markdown("## 🏦 SecureCore Banking")
        st.markdown("---")

        sd = get_current_user()
        if sd:
            st.markdown(f"**{sd.get('username', 'User')}**")
            role = sd.get("role", "customer").replace("_", " ").title()
            st.caption(f"Role: {role}")

            # Show approval status badge if not active
            approval_status = sd.get("registration_status", "active")
            if approval_status != "active":
                status_label = {
                    "pending_verification": "[Pending Verification]",
                    "pending_kyc": "[Pending KYC]",
                    "blocked": "[Blocked]",
                    "rejected": "[Rejected]"
                }.get(approval_status, "[Unknown]")
                st.caption(f"Status: {approval_status.replace('_', ' ').title()} {status_label}")

            st.markdown("---")

            # Role-based navigation hints
            if is_customer():
                st.caption("Customer Portal")
            elif is_admin():
                st.caption("Admin Dashboard")

            st.markdown("---")

            if st.button("Logout", use_container_width=True, key="sidebar_logout"):
                handle_logout()
