"""
Loans Page - Apply, view, calculate EMI, and manage loans.
Roles: admin, customer

RBAC Rules:
  CUSTOMER -> sees only own loans, user_id auto-set from session, no manual ID input
  ADMIN    -> sees all loans, can apply for any user
"""

import streamlit as st
from decimal import Decimal

from utils.auth_guard import require_role, get_current_user, is_admin
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date, status_badge, to_decimal
from core.services.loan_service import LoanService, ALLOWED_TENURES

require_role(["admin", "customer"])
render_sidebar()

sd = get_current_user()
_uid = sd["user_id"]  # Always the session user - never from UI input for customers

st.title("Loan Management")
st.markdown("---")

tabs = ["Apply for Loan", "My Loans" if not is_admin() else "All Loans", "EMI Calculator"]
if is_admin():
    tabs.append("Approvals")

tab_list = st.tabs(tabs)
tab_apply  = tab_list[0]
tab_active = tab_list[1]
tab_calc   = tab_list[2]
tab_approval = tab_list[3] if is_admin() else None

loan_svc = LoanService()

# -----------------------------------------------------------------------
# TAB 1 - Apply for Loan
# -----------------------------------------------------------------------
with tab_apply:
    st.subheader("New Loan Application")

    # Determine target user_id
    if is_admin():
        target_user_id = st.number_input(
            "Target User ID (the customer this loan is for)",
            min_value=1, step=1, key="loan_target_user"
        )
    else:
        # Customer: always their own ID - no input field
        target_user_id = _uid
        st.info(f"Loan will be linked to your account (User ID: **{_uid}**)")

    # Fetch linked account
    try:
        from core.services.account_service import AccountService
        acct_svc = AccountService()
        user_accounts = acct_svc.get_customer_accounts(int(target_user_id))
    except Exception:
        user_accounts = []

    account_id = None  # always initialized before form renders
    with st.form("loan_application_form"):
        la_col1, la_col2 = st.columns(2)

        with la_col1:
            loan_type = st.selectbox(
                "Loan Type", ["personal"], key="loan_type",
                help="Only Personal Loans are available for online application."
            )

            # Account selector
            if user_accounts:
                acc_options = {
                    f"#{a['account_id']} - {a['account_number']} ({a['account_type'].title()})": a["account_id"]
                    for a in user_accounts
                }
                acc_label = st.selectbox("Linked Account", list(acc_options.keys()), key="loan_acc_select")
                account_id = acc_options[acc_label]
            elif is_admin():
                # Admin fallback: manual entry if no accounts found for that user
                account_id = st.number_input("Linked Account ID", min_value=1, step=1, key="loan_acc_id_admin")
            else:
                st.warning("No active accounts found. Please contact support.")
                account_id = None

        with la_col2:
            principal = st.number_input(
                "Loan Amount (INR)", min_value=1000.0, max_value=2000000.0,
                step=1000.0, format="%.2f", key="loan_principal"
            )

            # Tenure: predefined options only - no free text
            tenure = st.selectbox(
                "Loan Tenure", ALLOWED_TENURES,
                format_func=lambda m: f"{m} months",
                key="loan_tenure"
            )

            # Interest rate: auto-calculated from slab, read-only
            auto_rate = loan_svc.get_interest_rate_for_amount(to_decimal(principal))
            st.metric("Interest Rate (p.a.)", f"{auto_rate}%", help="Fixed by loan amount slab. Not affected by tenure.")

        purpose = st.text_area(
            "Purpose / Remarks", key="loan_purpose",
            placeholder="Describe the purpose of the loan"
        )

        # EMI preview
        if principal > 0 and tenure > 0:
            preview_emi = loan_svc.calculate_emi(to_decimal(principal), auto_rate, int(tenure))
            st.info(f"Estimated Monthly EMI: **{format_currency(preview_emi)}**")

        # Idempotency reference
        if "loan_app_ref" not in st.session_state:
            from utils.helpers import StringUtils
            st.session_state["loan_app_ref"] = StringUtils.generate_reference_number("LON")
        st.caption(f"Application Ref: `{st.session_state['loan_app_ref']}`")

        loan_submitted = st.form_submit_button("Submit Application", use_container_width=True)

    if loan_submitted:
        if account_id is None:
            st.error("No linked account available. Cannot submit loan.")
        else:
            try:
                from core.models.entities import LoanType
                type_map = {"personal": LoanType.PERSONAL}

                created_id = loan_svc.apply_for_loan(
                    user_id=int(target_user_id),
                    account_id=int(account_id),
                    loan_type=type_map[loan_type],
                    principal=to_decimal(principal),
                    tenure_months=int(tenure),
                    created_by=_uid,
                    reference=st.session_state["loan_app_ref"],
                )
                st.session_state.pop("loan_app_ref")

                emi = loan_svc.calculate_emi(to_decimal(principal), auto_rate, int(tenure))
                st.success(f"Loan application submitted! Loan ID: **{created_id}**")
                st.metric("Monthly EMI", format_currency(emi))
            except Exception as e:
                st.error(f"{e}")

# -----------------------------------------------------------------------
# TAB 2 - Loans View
# -----------------------------------------------------------------------
with tab_active:
    if is_admin():
        st.subheader("All Loans in System")
        col_r, col_b = st.columns([4, 1])
        with col_b:
            refresh = st.button("Refresh", key="refresh_all_loans")

        if refresh or "all_loans_cache" not in st.session_state:
            try:
                st.session_state["all_loans_cache"] = loan_svc.get_all_loans()
            except Exception as e:
                st.error(f"{e}")
                st.session_state["all_loans_cache"] = []

        loans = st.session_state.get("all_loans_cache", [])
        if not loans:
            st.info("No loans found in the system.")
        else:
            st.caption(f"Showing {len(loans)} loan(s)")
            for loan in loans:
                lid     = getattr(loan, "loan_id", "N/A")
                lamt    = getattr(loan, "principal_amount", 0)
                lstatus = getattr(loan, "status", "")
                if hasattr(lstatus, "value"):
                    lstatus = lstatus.value
                lemi    = getattr(loan, "emi_amount", 0)
                ltenure = getattr(loan, "tenure_months", 0)
                luser   = getattr(loan, "user_id", "N/A")
                lrate   = getattr(loan, "interest_rate_annual", "N/A")

                with st.expander(f"Loan #{lid} - User {luser} - {format_currency(lamt)} - {status_badge(lstatus)}"):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Principal", format_currency(lamt))
                    m2.metric("EMI", format_currency(lemi))
                    m3.metric("Tenure", f"{ltenure} months")
                    st.markdown(f"**Rate:** {lrate}% p.a. &nbsp;|&nbsp; **Status:** {status_badge(lstatus)}")

    else:
        # CUSTOMER: auto-load own loans - no user_id input
        st.subheader("My Loans")
        col_r, col_b = st.columns([4, 1])
        with col_b:
            refresh = st.button("Refresh", key="refresh_my_loans")

        if refresh or "my_loans_cache" not in st.session_state:
            try:
                st.session_state["my_loans_cache"] = loan_svc.get_loans_for_user(_uid)
            except Exception as e:
                st.error(f"{e}")
                st.session_state["my_loans_cache"] = []

        loans = st.session_state.get("my_loans_cache", [])
        if not loans:
            st.info("You have no loans on record.")
        else:
            st.caption(f"Showing {len(loans)} loan(s)")
            for loan in loans:
                lid     = getattr(loan, "loan_id", "N/A")
                lamt    = getattr(loan, "principal_amount", 0)
                lstatus = getattr(loan, "status", "")
                if hasattr(lstatus, "value"):
                    lstatus = lstatus.value
                lemi    = getattr(loan, "emi_amount", 0)
                ltenure = getattr(loan, "tenure_months", 0)
                lrate   = getattr(loan, "interest_rate_annual", "N/A")

                with st.expander(f"Loan #{lid} - {format_currency(lamt)} - {status_badge(lstatus)}"):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Principal", format_currency(lamt))
                    m2.metric("EMI", format_currency(lemi))
                    m3.metric("Tenure", f"{ltenure} months")
                    st.markdown(f"**Rate:** {lrate}% p.a. &nbsp;|&nbsp; **Status:** {status_badge(lstatus)}")

# -----------------------------------------------------------------------
# TAB 3 - EMI Calculator
# -----------------------------------------------------------------------
with tab_calc:
    st.subheader("EMI Calculator")
    st.markdown("Calculate your Equated Monthly Installment before applying.")

    ec1, ec2 = st.columns(2)
    with ec1:
        calc_principal = st.number_input(
            "Loan Amount (INR)", min_value=1000.0, max_value=2000000.0,
            step=1000.0, value=100000.0, format="%.2f", key="calc_principal"
        )
        # Tenure: predefined options only
        calc_tenure = st.selectbox(
            "Tenure", ALLOWED_TENURES,
            format_func=lambda m: f"{m} months",
            key="calc_tenure"
        )
        # Rate: auto from slab, shown read-only
        calc_rate = loan_svc.get_interest_rate_for_amount(to_decimal(calc_principal))
        st.metric("Interest Rate (p.a.)", f"{calc_rate}%", help="Fixed by loan amount slab.")

    with ec2:
        p = to_decimal(calc_principal)
        n = int(calc_tenure)

        emi           = loan_svc.calculate_emi(p, calc_rate, n)
        total_payment = emi * n
        total_interest = total_payment - p

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("Monthly EMI",    format_currency(emi))
        st.metric("Total Payment",  format_currency(total_payment))
        st.metric("Total Interest", format_currency(total_interest))

# -----------------------------------------------------------------------
# TAB 4 - Loan Approvals (Admin only)
# -----------------------------------------------------------------------
if is_admin() and tab_approval:
    with tab_approval:
        st.subheader("Pending Loan Approvals")

        if st.button("Refresh Pending", key="refresh_pending_loans"):
            st.session_state.pop("pending_loans", None)

        if "pending_loans" not in st.session_state:
            try:
                pending = loan_svc.loan_repo.get_pending_approvals()
                st.session_state["pending_loans"] = pending
            except Exception as e:
                st.error(f"{e}")

        pending = st.session_state.get("pending_loans", [])
        if not pending:
            st.info("No pending loan applications.")
        else:
            for loan in pending:
                lid   = getattr(loan, "loan_id", "N/A")
                lamt  = getattr(loan, "principal_amount", 0)
                luser = getattr(loan, "user_id", "N/A")

                with st.expander(f"Loan #{lid} - User {luser} - {format_currency(lamt)}"):
                    st.markdown(f"**EMI:** {format_currency(getattr(loan, 'emi_amount', 0))}")
                    st.markdown(f"**Tenure:** {getattr(loan, 'tenure_months', 0)} months")
                    st.markdown(f"**Rate:** {getattr(loan, 'interest_rate_annual', 'N/A')}% p.a.")

                    ap1, ap2 = st.columns(2)
                    with ap1:
                        if st.button(f"Approve #{lid}", key=f"approve_{lid}"):
                            try:
                                loan_svc.approve_loan(lid, _uid)
                                st.success(f"Loan #{lid} approved!")
                                st.session_state.pop("pending_loans", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"{e}")
                    with ap2:
                        if st.button(f"Reject #{lid}", key=f"reject_{lid}"):
                            try:
                                loan_svc.reject_loan(lid, _uid)
                                st.success(f"Loan #{lid} rejected.")
                                st.session_state.pop("pending_loans", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"{e}")
