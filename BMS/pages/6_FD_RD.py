"""
FD & RD Page - Open, view, and manage Fixed Deposits and Recurring Deposits.
Roles: admin, customer

RBAC Rules:
  CUSTOMER -> sees only own FD/RD, user_id auto-set from session, no manual ID input
  ADMIN    -> sees all FD/RD, can open for any user
"""

import streamlit as st
from decimal import Decimal
from datetime import date

from utils.auth_guard import require_role, get_current_user, is_admin
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date, status_badge, to_decimal
from core.services.investment_service import (
    InvestmentService, ALLOWED_TENURES,
    FD_INTEREST_SLABS, FD_DEFAULT_RATE,
    RD_INTEREST_SLABS, RD_DEFAULT_RATE,
)

require_role(["admin", "customer"])
render_sidebar()

sd  = get_current_user()
_uid = sd["user_id"]   # Always the session user - never from UI input for customers

st.title("Fixed Deposits & Recurring Deposits")
st.markdown("---")

inv_svc = InvestmentService()

tab_fd, tab_rd, tab_active, tab_calc = st.tabs([
    "Open FD", "Open RD",
    "My Deposits" if not is_admin() else "All Deposits",
    "Interest Calculator"
])

# -----------------------------------------------------------------------
# TAB 1 - Open Fixed Deposit
# -----------------------------------------------------------------------
with tab_fd:
    st.subheader("Open Fixed Deposit")

    # Determine target user
    if is_admin():
        target_uid_fd = st.number_input(
            "Target User ID (the customer this FD is for)",
            min_value=1, step=1, key="fd_target_user"
        )
    else:
        target_uid_fd = _uid
        st.info(f"FD will be linked to your account (User ID: **{_uid}**)")

    # Fetch linked accounts
    try:
        from core.services.account_service import AccountService
        fd_accounts = AccountService().get_customer_accounts(int(target_uid_fd))
    except Exception:
        fd_accounts = []

    with st.form("open_fd_form"):
        fd_col1, fd_col2 = st.columns(2)

        with fd_col1:
            fd_amount = st.number_input(
                "Principal Amount (INR)", min_value=1000.0, max_value=5000000.0,
                step=1000.0, format="%.2f", key="fd_amount"
            )
            fd_payout = st.selectbox(
                "Payout Mode", ["on_maturity", "monthly", "quarterly"], key="fd_payout"
            )

        with fd_col2:
            # Account selector
            if fd_accounts:
                fd_acc_opts = {
                    f"#{a['account_id']} - {a['account_number']} ({a['account_type'].title()})": a["account_id"]
                    for a in fd_accounts
                }
                fd_acc_label = st.selectbox("Linked Account", list(fd_acc_opts.keys()), key="fd_acc_sel")
                fd_account_id = fd_acc_opts[fd_acc_label]
            elif is_admin():
                fd_account_id = st.number_input("Linked Account ID", min_value=1, step=1, key="fd_acc_id_admin")
            else:
                st.warning("No active accounts found.")
                fd_account_id = None

            # Tenure: predefined selectbox only
            fd_tenure = st.selectbox(
                "Tenure", ALLOWED_TENURES,
                format_func=lambda m: f"{m} months",
                key="fd_tenure"
            )

            # Rate: auto from slab, read-only
            fd_auto_rate = inv_svc.get_fd_rate(to_decimal(fd_amount))
            st.metric("Interest Rate (p.a.)", f"{fd_auto_rate}%",
                      help="Fixed by deposit amount slab. Not affected by tenure.")

        # Maturity preview
        if fd_amount > 0:
            fd_maturity_preview = inv_svc.calculate_fd_maturity(
                to_decimal(fd_amount), fd_auto_rate, int(fd_tenure)
            )
            st.info(
                f"Maturity Date: **{date.today().strftime('%Y-%m-%d')} + {fd_tenure} months** &nbsp;|&nbsp; "
                f"Maturity Amount: **{format_currency(fd_maturity_preview)}**"
            )

        fd_submitted = st.form_submit_button("Open Fixed Deposit", use_container_width=True)

    if fd_submitted:
        if fd_account_id is None:
            st.error("No linked account available.")
        else:
            try:
                fd_id = inv_svc.open_fd(
                    account_id=int(fd_account_id),
                    tenure_months=int(fd_tenure),
                    principal=to_decimal(fd_amount),
                    payout_mode=fd_payout,
                    created_by=_uid,
                )
                maturity = inv_svc.calculate_fd_maturity(to_decimal(fd_amount), fd_auto_rate, int(fd_tenure))
                st.success(f"FD opened! FD ID: **{fd_id}**")
                st.metric("Maturity Amount", format_currency(maturity))
            except Exception as e:
                st.error(f"{e}")

# -----------------------------------------------------------------------
# TAB 2 - Open Recurring Deposit
# -----------------------------------------------------------------------
with tab_rd:
    st.subheader("Open Recurring Deposit")

    # Determine target user
    if is_admin():
        target_uid_rd = st.number_input(
            "Target User ID (the customer this RD is for)",
            min_value=1, step=1, key="rd_target_user"
        )
    else:
        target_uid_rd = _uid
        st.info(f"RD will be linked to your account (User ID: **{_uid}**)")

    # Fetch linked accounts
    try:
        from core.services.account_service import AccountService
        rd_accounts = AccountService().get_customer_accounts(int(target_uid_rd))
    except Exception:
        rd_accounts = []

    with st.form("open_rd_form"):
        rd_col1, rd_col2 = st.columns(2)

        with rd_col1:
            rd_installment = st.number_input(
                "Monthly Installment (INR)", min_value=100.0, max_value=500000.0,
                step=100.0, format="%.2f", key="rd_installment"
            )
            # Tenure: predefined selectbox only
            rd_tenure = st.selectbox(
                "Tenure", ALLOWED_TENURES,
                format_func=lambda m: f"{m} months",
                key="rd_tenure"
            )

        with rd_col2:
            # Account selector
            if rd_accounts:
                rd_acc_opts = {
                    f"#{a['account_id']} - {a['account_number']} ({a['account_type'].title()})": a["account_id"]
                    for a in rd_accounts
                }
                rd_acc_label = st.selectbox("Linked Account", list(rd_acc_opts.keys()), key="rd_acc_sel")
                rd_account_id = rd_acc_opts[rd_acc_label]
            elif is_admin():
                rd_account_id = st.number_input("Linked Account ID", min_value=1, step=1, key="rd_acc_id_admin")
            else:
                st.warning("No active accounts found.")
                rd_account_id = None

            # Rate: auto from slab, read-only
            rd_auto_rate = inv_svc.get_rd_rate(to_decimal(rd_installment))
            st.metric("Interest Rate (p.a.)", f"{rd_auto_rate}%",
                      help="Fixed by monthly installment slab. Not affected by tenure.")

        # Maturity preview
        if rd_installment > 0:
            rd_maturity_preview = inv_svc.calculate_rd_maturity(
                to_decimal(rd_installment), rd_auto_rate, int(rd_tenure)
            )
            total_deposited = to_decimal(rd_installment) * rd_tenure
            st.info(
                f"Total Deposited: **{format_currency(total_deposited)}** &nbsp;|&nbsp; "
                f"Maturity Amount: **{format_currency(rd_maturity_preview)}**"
            )

        rd_submitted = st.form_submit_button("Open Recurring Deposit", use_container_width=True)

    if rd_submitted:
        if rd_account_id is None:
            st.error("No linked account available.")
        else:
            try:
                rd_id = inv_svc.open_rd(
                    account_id=int(rd_account_id),
                    tenure_months=int(rd_tenure),
                    installment=to_decimal(rd_installment),
                    created_by=_uid,
                )
                st.success(f"RD opened! RD ID: **{rd_id}**")
            except Exception as e:
                st.error(f"{e}")

# -----------------------------------------------------------------------
# TAB 3 - View Deposits
# -----------------------------------------------------------------------
with tab_active:
    if is_admin():
        st.subheader("All Deposits in System")
        _, col_btn = st.columns([4, 1])
        with col_btn:
            if st.button("Refresh", key="refresh_all_deps"):
                st.session_state.pop("all_fds_cache", None)
                st.session_state.pop("all_rds_cache", None)

        if "all_fds_cache" not in st.session_state:
            try:
                st.session_state["all_fds_cache"] = inv_svc.get_all_fds()
                st.session_state["all_rds_cache"] = inv_svc.get_all_rds()
            except Exception as e:
                st.error(f"{e}")
                st.session_state["all_fds_cache"] = []
                st.session_state["all_rds_cache"] = []

        all_fds = st.session_state.get("all_fds_cache", [])
        all_rds = st.session_state.get("all_rds_cache", [])

        if all_fds:
            st.markdown("#### Fixed Deposits")
            st.caption(f"{len(all_fds)} FD(s)")
            for fd in all_fds:
                fid     = getattr(fd, "fd_id", "N/A")
                fstatus = str(getattr(fd, "status", "active"))
                facc    = getattr(fd, "account_id", "N/A")
                with st.expander(f"FD #{fid} - Account #{facc} - {status_badge(fstatus)}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Principal",  format_currency(getattr(fd, "principal_amount", 0)))
                    c2.metric("Rate",       f"{getattr(fd, 'interest_rate', 'N/A')}%")
                    c3.metric("Maturity",   format_currency(getattr(fd, "maturity_amount", 0)))
                    st.markdown(f"**Maturity Date:** {format_date(getattr(fd, 'maturity_date', None))}")
        else:
            st.info("No FDs in the system.")

        if all_rds:
            st.markdown("#### Recurring Deposits")
            st.caption(f"{len(all_rds)} RD(s)")
            for rd in all_rds:
                rid     = getattr(rd, "rd_id", "N/A")
                rstatus = str(getattr(rd, "status", "active"))
                racc    = getattr(rd, "account_id", "N/A")
                with st.expander(f"RD #{rid} - Account #{racc} - {status_badge(rstatus)}"):
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Installment", format_currency(getattr(rd, "installment_amount", 0)))
                    r2.metric("Progress",    f"{getattr(rd, 'paid_installments', 0)}/{getattr(rd, 'total_installments', 0)}")
                    r3.metric("Rate",        f"{getattr(rd, 'interest_rate', 'N/A')}%")
                    st.markdown(f"**Next Due:** {format_date(getattr(rd, 'next_due_date', None))}")
        else:
            st.info("No RDs in the system.")

    else:
        # CUSTOMER: auto-load own deposits - no account_id input
        st.subheader("My Deposits")
        _, col_btn = st.columns([4, 1])
        with col_btn:
            if st.button("Refresh", key="refresh_my_deps"):
                st.session_state.pop("my_fds_cache", None)
                st.session_state.pop("my_rds_cache", None)

        if "my_fds_cache" not in st.session_state:
            try:
                st.session_state["my_fds_cache"] = inv_svc.get_fds_for_user(_uid)
                st.session_state["my_rds_cache"] = inv_svc.get_rds_for_user(_uid)
            except Exception as e:
                st.error(f"{e}")
                st.session_state["my_fds_cache"] = []
                st.session_state["my_rds_cache"] = []

        my_fds = st.session_state.get("my_fds_cache", [])
        my_rds = st.session_state.get("my_rds_cache", [])

        if my_fds:
            st.markdown("#### My Fixed Deposits")
            for fd in my_fds:
                fid     = getattr(fd, "fd_id", "N/A")
                fstatus = str(getattr(fd, "status", "active"))
                with st.expander(f"FD #{fid} - {status_badge(fstatus)}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Principal",  format_currency(getattr(fd, "principal_amount", 0)))
                    c2.metric("Rate",       f"{getattr(fd, 'interest_rate', 'N/A')}%")
                    c3.metric("Maturity",   format_currency(getattr(fd, "maturity_amount", 0)))
                    st.markdown(f"**Maturity Date:** {format_date(getattr(fd, 'maturity_date', None))}")
        else:
            st.info("No Fixed Deposits on record.")

        if my_rds:
            st.markdown("#### My Recurring Deposits")
            for rd in my_rds:
                rid     = getattr(rd, "rd_id", "N/A")
                rstatus = str(getattr(rd, "status", "active"))
                with st.expander(f"RD #{rid} - {status_badge(rstatus)}"):
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Installment", format_currency(getattr(rd, "installment_amount", 0)))
                    r2.metric("Progress",    f"{getattr(rd, 'paid_installments', 0)}/{getattr(rd, 'total_installments', 0)}")
                    r3.metric("Rate",        f"{getattr(rd, 'interest_rate', 'N/A')}%")
                    st.markdown(f"**Next Due:** {format_date(getattr(rd, 'next_due_date', None))}")
        else:
            st.info("No Recurring Deposits on record.")

# -----------------------------------------------------------------------
# TAB 4 - Interest Calculator
# -----------------------------------------------------------------------
with tab_calc:
    st.subheader("Deposit Interest Calculator")

    calc_type = st.radio(
        "Deposit Type", ["Fixed Deposit", "Recurring Deposit"],
        horizontal=True, key="calc_dep_type"
    )

    if calc_type == "Fixed Deposit":
        ic1, ic2 = st.columns(2)
        with ic1:
            fd_p = st.number_input(
                "Principal (INR)", min_value=1000.0, value=100000.0,
                step=1000.0, format="%.2f", key="calc_fd_p"
            )
            # Tenure: predefined selectbox only
            fd_t = st.selectbox(
                "Tenure", ALLOWED_TENURES,
                format_func=lambda m: f"{m} months",
                key="calc_fd_t"
            )
            # Rate: auto from slab, read-only
            fd_r = inv_svc.get_fd_rate(to_decimal(fd_p))
            st.metric("Interest Rate (p.a.)", f"{fd_r}%", help="Fixed by deposit amount slab.")

        with ic2:
            maturity       = inv_svc.calculate_fd_maturity(to_decimal(fd_p), fd_r, int(fd_t))
            interest_earned = maturity - to_decimal(fd_p)
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.metric("Maturity Amount",  format_currency(maturity))
            st.metric("Interest Earned",  format_currency(interest_earned))

    else:
        ic1, ic2 = st.columns(2)
        with ic1:
            rd_inst = st.number_input(
                "Monthly Installment (INR)", min_value=100.0, value=5000.0,
                step=100.0, format="%.2f", key="calc_rd_inst"
            )
            # Tenure: predefined selectbox only
            rd_t = st.selectbox(
                "Tenure", ALLOWED_TENURES,
                format_func=lambda m: f"{m} months",
                key="calc_rd_t"
            )
            # Rate: auto from slab, read-only
            rd_r = inv_svc.get_rd_rate(to_decimal(rd_inst))
            st.metric("Interest Rate (p.a.)", f"{rd_r}%", help="Fixed by installment amount slab.")

        with ic2:
            rd_maturity      = inv_svc.calculate_rd_maturity(to_decimal(rd_inst), rd_r, int(rd_t))
            rd_total_deposit = to_decimal(rd_inst) * rd_t
            rd_interest      = rd_maturity - rd_total_deposit
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.metric("Maturity Amount",  format_currency(rd_maturity))
            st.metric("Interest Earned",  format_currency(rd_interest))
            st.metric("Total Deposited",  format_currency(rd_total_deposit))
