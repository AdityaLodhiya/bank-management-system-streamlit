"""
Registration Page - SecureCore Banking
Multi-step sign-up with OTP verification
"""

import streamlit as st
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.authentication_service import AuthenticationService
from utils.exceptions import ValidationException, InvalidOTPException
from utils.auth_guard import is_logged_in



# Redirect if already logged in
if is_logged_in():
    st.switch_page("pages/1_Dashboard.py")

# Initialise session state
for key, default in {
    "reg_step": 1,           # 1=form, 2=otp, 3=done
    "reg_user_id": None,
    "reg_phone": None,
    "reg_otp_dev": None,     # dev-mode OTP display
    "reg_otp_attempts": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


auth_service = AuthenticationService()


# Header
st.markdown("""
<div style="text-align:center; padding:1.5rem 0 0.5rem;">
    <h1 style="margin:0;">SecureCore Banking</h1>
    <p style="color:#888; margin-top:.25rem;">Create Your Account</p>
</div>
""", unsafe_allow_html=True)

# Step indicator
cols = st.columns(3)
steps = ["(1) Details", "(2) Verify OTP", "(3) Complete"]
for i, (col, label) in enumerate(zip(cols, steps), 1):
    if i < st.session_state.reg_step:
        col.success(label)
    elif i == st.session_state.reg_step:
        col.info(label)
    else:
        col.markdown(f"<div style='text-align:center;color:#aaa'>{label}</div>",
                     unsafe_allow_html=True)

st.divider()


# STEP 1 - Registration Form
if st.session_state.reg_step == 1:

    with st.form("registration_form", clear_on_submit=False):
        st.subheader("Personal Details")
        col1, col2 = st.columns(2)
        full_name = col1.text_input("Full Name *", max_chars=100,
                                     placeholder="As per government ID")
        phone = col2.text_input("Phone Number *", max_chars=10,
                                 placeholder="10-digit mobile")
        col3, col4 = st.columns(2)
        email = col3.text_input("Email", placeholder="Optional")
        dob = col4.date_input("Date of Birth *",
                               min_value=date(1920, 1, 1),
                               max_value=date.today() - timedelta(days=365*18),
                               value=date(2000, 1, 1))

        st.subheader("Login Credentials")
        col5, col6 = st.columns(2)
        username = col5.text_input("Username *", max_chars=30,
                                    placeholder="4-30 chars, letters/digits/_")
        # empty column for spacing
        col6.markdown("")

        col7, col8 = st.columns(2)
        password = col7.text_input("Password *", type="password",
                                    placeholder="Min 8 chars, mixed case+digit+special")
        confirm_password = col8.text_input("Confirm Password *", type="password")

        st.caption("Password: 8+ chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character")

        submitted = st.form_submit_button("Register & Send OTP", use_container_width=True)

    if submitted:
        # Client-side confirm-password check
        if password != confirm_password:
            st.error("Passwords do not match.")
        else:
            try:
                result = auth_service.register_user(
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    dob=dob,
                    username=username,
                    password=password
                )

                st.session_state.reg_user_id = result['user_id']
                st.session_state.reg_phone = result['phone']
                st.session_state.reg_otp_dev = result.get('otp_code')
                st.session_state.reg_otp_attempts = 0
                st.session_state.reg_step = 2
                st.rerun()

            except (ValidationException, Exception) as e:
                import traceback
                error_detail = f"\n\nDetails: {str(e)}" if str(e) else ""
                st.error(f"Registration failed.{error_detail}")
                if os.getenv("DEBUG") == "True":
                    st.exception(e)




# STEP 2 - OTP Verification
elif st.session_state.reg_step == 2:

    masked = st.session_state.reg_phone
    if masked and len(masked) >= 4:
        masked = masked[:2] + "XXXX" + masked[-4:]
    st.info(f"OTP sent to **{masked}**. Valid for 5 minutes.")

    # Dev mode: show OTP on screen
    if st.session_state.reg_otp_dev:
        st.warning(f"[Dev Mode] OTP: `{st.session_state.reg_otp_dev}` "
                   f"(In production this is sent via SMS)")

    with st.form("otp_form"):
        otp_input = st.text_input("Enter 6-digit OTP", max_chars=6,
                                   placeholder="e.g. 123456")
        verify_btn = st.form_submit_button("Verify", use_container_width=True)

    if verify_btn:
        if not otp_input or len(otp_input) != 6:
            st.error("Please enter a valid 6-digit OTP.")
        else:
            try:
                result = auth_service.verify_registration_otp(
                    user_id=st.session_state.reg_user_id,
                    otp_code=otp_input
                )
                st.session_state.reg_step = 3
                st.rerun()

            except InvalidOTPException:
                st.session_state.reg_otp_attempts += 1
                if st.session_state.reg_otp_attempts >= 3:
                    st.error("Too many wrong attempts. Please request a new OTP.")
                else:
                    remaining = 3 - st.session_state.reg_otp_attempts
                    st.error(f"Invalid or expired OTP. {remaining} attempt(s) left.")
            except Exception as e:
                st.error(str(e))

    # Resend OTP
    st.markdown("")
    if st.button("Resend OTP"):
        try:
            new_otp = auth_service.generate_otp(
                st.session_state.reg_user_id, "registration"
            )
            st.session_state.reg_otp_dev = new_otp
            st.session_state.reg_otp_attempts = 0
            st.success("New OTP sent!")
            st.rerun()
        except Exception as e:
            st.error(str(e))


# STEP 3 - Registration Complete
elif st.session_state.reg_step == 3:

    st.balloons()

    st.success("### Registration Successful!")

    st.markdown("""
    Your phone number has been verified.  
    **What happens next:**

    1. A bank officer will review and verify your identity (**KYC**)
    2. You may be contacted for document verification
    3. Once approved, you can log in and access banking services

    > Your account is currently in **Pending KYC** state.  
    > You will be able to log in after an authorized officer activates your account.
    """)

    if st.button("<- Back to Login", use_container_width=True):
        # Reset registration state
        for key in ["reg_step", "reg_user_id", "reg_phone", "reg_otp_dev", "reg_otp_attempts"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
