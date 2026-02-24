"""
Profile Page - View user info and change password.
"""

import streamlit as st


from utils.auth_guard import require_role, get_current_user
from utils.sidebar import render_sidebar
from utils.formatters import format_date

require_role(["admin", "customer"])
render_sidebar()

sd = get_current_user()

st.title("My Profile")
st.markdown("---")

# ---- User information ----
col1, col2 = st.columns(2)
with col1:
    st.markdown("### Account Information")
    st.markdown(f"**Username:** {sd.get('username', 'N/A')}")
    st.markdown(f"**Role:** {sd.get('role', 'N/A').replace('_', ' ').title()}")
    st.markdown(f"**User ID:** {sd.get('user_id', 'N/A')}")

    # Fetch additional customer info
    try:
        from core.repositories.customer_repository import CustomerRepository
        customer = CustomerRepository().find_customer_by_id(sd["user_id"])
        if customer:
            st.markdown("---")
            st.markdown("### Personal Details")
            st.markdown(f"**Full Name:** {customer.full_name}")
            st.markdown(f"**Email:** {customer.email or 'N/A'}")
            st.markdown(f"**Phone:** {customer.phone or 'N/A'}")
            st.markdown(f"**Date of Birth:** {format_date(customer.dob)}")
            st.markdown(f"**KYC Status:** {customer.kyc_status.upper()}")
    except Exception:
        pass

with col2:
    st.markdown("### Session Information")
    st.markdown(f"**Login Time:** {format_date(sd.get('login_time'))}")
    st.markdown(f"**Last Activity:** {format_date(sd.get('last_activity'))}")
    st.markdown(f"**Session Token:** `{str(sd.get('session_token', ''))[:16]}...`")

st.markdown("---")

# ---- Change password ----
st.subheader("Change Password")

with st.form("change_password_form"):
    old_pwd = st.text_input("Current Password", type="password")
    new_pwd = st.text_input("New Password", type="password")
    confirm_pwd = st.text_input("Confirm New Password", type="password")
    change_submitted = st.form_submit_button("Update Password", use_container_width=True)

if change_submitted:
    if not old_pwd or not new_pwd or not confirm_pwd:
        st.error("All fields are required.")
    elif new_pwd != confirm_pwd:
        st.error("New passwords do not match.")
    elif len(new_pwd) < 6:
        st.error("Password must be at least 6 characters.")
    else:
        try:
            from core.services.authentication_service import AuthenticationService
            auth = AuthenticationService()
            auth.change_password(sd["user_id"], old_pwd, new_pwd)
            st.success("Password changed successfully!")
        except Exception as e:
            st.error(f"{e}")
