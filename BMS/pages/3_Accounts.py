"""
Accounts Page - Create, search, and view bank accounts.
Roles: admin, customer
"""

import streamlit as st


from utils.auth_guard import require_role, get_current_user, is_admin
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date, status_badge, to_decimal

require_role(["admin", "customer"])
render_sidebar()

sd = get_current_user()

st.title("Account Management")
st.markdown("---")

# ---------- Tabs ----------
if is_admin():
    tab_titles = ["Create Account", "Search Account", "Account Details"]
    tab_list = st.tabs(tab_titles)
    tab_create, tab_search, tab_details = tab_list
else:
    tab_titles = ["My Accounts", "Open New Account"]
    tab_list = st.tabs(tab_titles)
    tab_search, tab_create = tab_list
    tab_details = None

# ========================================================
# TAB: Create Account (Admin) / Open New Account (Customer)
# ========================================================
with tab_create:
    if is_admin():
        st.subheader("Create New Bank Account")
        st.markdown("#### 1. Select Customer")
    else:
        st.subheader("Open New Bank Account")
        # Auto-select the current user for customers
        from core.repositories.customer_repository import CustomerRepository
        customer = CustomerRepository().find_customer_by_id(sd['user_id'])
        if customer:
            st.session_state["selected_customer"] = customer
        st.markdown("#### 1. Verify Your Information")
    if is_admin():
        cust_col1, cust_col2 = st.columns([3, 1])
        with cust_col1:
            cust_search = st.text_input(
                "Search customer by User ID, phone, or email",
                key="cust_search_input",
                placeholder="Enter user ID, phone, or email",
            )
        with cust_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            search_cust_btn = st.button("Search Customer", key="search_cust_btn")
    else:
        search_cust_btn = False

    if search_cust_btn and cust_search:
        try:
            from core.repositories.customer_repository import CustomerRepository

            repo = CustomerRepository()
            # Try numeric ID first, then fall back to search by phone/email
            customer = None
            if cust_search.isdigit():
                customer = repo.find_customer_by_id(int(cust_search))

            if customer:
                st.session_state["selected_customer"] = customer
                st.success(
                    f"Customer found: **{customer.full_name}** (User ID: {customer.user_id})"
                )
            else:
                st.warning("No customer found. Please check the search term.")
        except Exception as e:
            st.error(f"Search error: {e}")

    if "selected_customer" in st.session_state:
        c = st.session_state["selected_customer"]
        with st.expander("Selected Customer Details", expanded=True):
            mc1, mc2 = st.columns(2)
            mc1.markdown(f"**Name:** {c.full_name}")
            mc1.markdown(f"**Phone:** {c.phone or 'N/A'}")
            mc2.markdown(f"**Email:** {c.email or 'N/A'}")
            mc2.markdown(f"**Govt ID:** {c.govt_id or 'N/A'}")

    st.markdown("#### 2. Account Details")

    with st.form("create_account_form"):
        acc_type = st.selectbox("Account Type", ["savings", "current", "salary"])
        initial_deposit = st.number_input("Initial Deposit (INR)", min_value=0.0, step=500.0, format="%.2f")
        branch_code = st.text_input("Branch Code", value="MAIN001")

        # Show min-balance info
        min_bal_info = {
            "savings": "Minimum balance: INR 1,000 | Interest: 3.5% p.a.",
            "current": "Minimum balance: INR 10,000 | OD facility available",
            "salary": "Zero balance account | Requires employer linkage",
        }
        st.info(min_bal_info.get(acc_type, ''))

        create_submitted = st.form_submit_button("Create Account", use_container_width=True)

    if create_submitted:
        if "selected_customer" not in st.session_state:
            st.error("Please search and select a customer first.")
        elif initial_deposit < 0:
            st.error("Initial deposit cannot be negative.")
        else:
            try:
                from core.services.account_service import AccountService
                from core.models.entities import AccountType

                svc = AccountService()
                type_map = {
                    "savings": AccountType.SAVINGS,
                    "current": AccountType.CURRENT,
                    "salary": AccountType.SALARY,
                }
                result = svc.create_account(
                    user_id=st.session_state["selected_customer"].user_id,
                    account_type=type_map[acc_type],
                    initial_deposit=to_decimal(initial_deposit),
                    branch_code=branch_code or None,
                )
                st.success(f"Account created! Account Number: **{result.get('account_number', 'N/A')}**")
                st.balloons()
            except Exception as e:
                st.error(f"{e}")

# ===========================
# TAB 2 - Search Account
# ===========================
with tab_search:
    if is_admin():
        st.subheader("Search Accounts")
        s_col1, s_col2 = st.columns([3, 1])
        with s_col1:
            acc_query = st.text_input(
                "Enter account number or user ID",
                key="acc_search_query",
                placeholder="Account number or user ID",
            )
        with s_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            search_acc_btn = st.button("Search", key="search_acc_btn")
    else:
        st.subheader("My Accounts")
        search_acc_btn = True
        acc_query = str(sd['user_id'])

    if search_acc_btn and acc_query:
        try:
            from core.services.account_service import AccountService
            svc = AccountService()
            accounts = []

            if is_admin():
                if acc_query.isdigit():
                    # Try as user ID - admins see ALL accounts (active, frozen, closed)
                    accts = svc.get_customer_accounts(int(acc_query), active_only=False)
                    if accts:
                        accounts = accts if isinstance(accts, list) else [accts]

                if not accounts:
                    # Try as account number - get details
                    try:
                        detail = svc.get_account_details(int(acc_query)) if acc_query.isdigit() else None
                        if detail:
                            accounts = [detail]
                    except Exception:
                        pass
            else:
                # Customer only sees their own active accounts
                accounts = svc.get_customer_accounts(sd['user_id'])

            if accounts:
                st.session_state["search_results"] = accounts
                if is_admin():
                    st.success(f"Found {len(accounts)} account(s).")
            else:
                st.warning("No accounts found.")
        except Exception as e:
            st.error(f"Search error: {e}")

    if "search_results" in st.session_state:
        results = st.session_state["search_results"]
        for acc in results:
            if isinstance(acc, dict):
                acc_num = acc.get("account_number", "N/A")
                acc_id = acc.get("account_id", "")
                bal = acc.get("balance", 0)
                available = acc.get("available_balance", bal)
                atype = acc.get("account_type", "")
                astatus = acc.get("status", "active")

                # Extra details for enrichment
                interest = acc.get("interest_rate", "N/A")
                branch = acc.get("branch_code", "N/A")
                opened = acc.get("opening_date", "N/A")
            else:
                acc_num = getattr(acc, "account_number", "N/A")
                acc_id = getattr(acc, "account_id", "")
                bal = getattr(acc, "balance", 0)
                available = getattr(acc, "available_balance", bal)
                atype = getattr(acc, "account_type", "")
                if hasattr(atype, "value"):
                    atype = atype.value
                astatus = getattr(acc, "status", "active")
                if hasattr(astatus, "value"):
                    astatus = astatus.value

                # Extra details for enrichment
                od_limit = getattr(acc, "od_limit", 0)
                interest = getattr(acc, "interest_rate", "N/A")
                branch = getattr(acc, "branch_code", "N/A")
                opened = getattr(acc, "opening_date", "N/A")

            with st.expander(f"Account {acc_num}  -  {status_badge(str(astatus))}"):
                r1, r2, r3 = st.columns(3)
                r1.metric("Current Balance", format_currency(bal))
                r2.metric("Available Funds", format_currency(available if 'available' in locals() else bal))
                r3.markdown(f"**Type:** {str(atype).title()}")

                st.markdown("---")
                if not is_admin():
                    d1, d2, d3 = st.columns(3)
                    d1.markdown(f"**Status:** {status_badge(str(astatus))}")
                    d2.markdown(f"**Branch:** `{branch if 'branch' in locals() else 'N/A'}`")
                    d3.markdown(f"**Interest Rate:** {interest if 'interest' in locals() else 'N/A'}%")

                    e1, e2 = st.columns(2)
                    e1.markdown(f"**Opening Date:** {format_date(opened) if 'opened' in locals() and opened != 'N/A' else 'N/A'}")
                    e2.caption(f"Internal ID: {acc_id}")
                else:
                    d1, d2 = st.columns(2)
                    d1.markdown(f"**Status:** {status_badge(str(astatus))}")
                    d2.caption(f"Internal ID: {acc_id}")
                    st.info("For full details and actions, use the Account Details tab.")

# ===========================
# TAB: Account Details (Admin Only)
# ===========================
if is_admin() and tab_details:
    with tab_details:
        st.subheader("Account Details & Actions")

        acc_id_input = st.number_input("Enter Account ID", min_value=1, step=1, key="detail_acc_id")
        load_btn = st.button("Load Details", key="load_details_btn")

        if load_btn:
            try:
                from core.services.account_service import AccountService

                svc = AccountService()
                detail = svc.get_account_details(int(acc_id_input))
                if detail:
                    st.session_state["account_detail"] = detail
                else:
                    st.warning("Account not found.")
            except Exception as e:
                st.error(f"{e}")

        if "account_detail" in st.session_state:
            det = st.session_state["account_detail"]

            # Security check for customers (though tab is admin-only, good for safety)
            det_user_id = det.get("user_id") if isinstance(det, dict) else getattr(det, "user_id", None)
            if not is_admin() and det_user_id != sd['user_id']:
                st.error("You are not authorized to view this account.")
                st.session_state.pop("account_detail", None)
                st.rerun()

            if isinstance(det, dict):
                st.markdown(f"### Account: {det.get('account_number', 'N/A')}")
                d1, d2, d3 = st.columns(3)
                d1.metric("Balance", format_currency(det.get("balance", 0)))
                d2.markdown(f"**Type:** {str(det.get('account_type', 'N/A')).title()}")
                d3.markdown(f"**Status:** {status_badge(str(det.get('status', 'active')))}")
            else:
                st.markdown(f"### Account: {getattr(det, 'account_number', 'N/A')}")
                d1, d2, d3 = st.columns(3)
                d1.metric("Balance", format_currency(getattr(det, "balance", 0)))
                atype = getattr(det, "account_type", "N/A")
                d2.markdown(f"**Type:** {str(atype.value if hasattr(atype, 'value') else atype).title()}")
                astatus = getattr(det, "status", "active")
                d3.markdown(f"**Status:** {status_badge(astatus.value if hasattr(astatus, 'value') else str(astatus))}")

            st.markdown("---")

            # Freeze / Unfreeze / Close actions
            if is_admin():
                st.markdown("#### Admin Actions")
                act1, act2, act3 = st.columns(3)

                with act1:
                    if st.button("Freeze Account", key="freeze_btn"):
                        st.session_state["show_freeze_form"] = True

                with act2:
                    if st.button("Unfreeze Account", key="unfreeze_btn"):
                        st.session_state["show_unfreeze_form"] = True

                with act3:
                    if st.button("Close Account", key="close_btn"):
                        st.session_state["show_close_confirm"] = True

                det_id = det.get("account_id") if isinstance(det, dict) else getattr(det, "account_id", None)

                if st.session_state.get("show_freeze_form"):
                    reason = st.text_area("Reason for freezing", key="freeze_reason")
                    if st.button("Confirm Freeze", key="confirm_freeze"):
                        try:
                            from core.services.account_service import AccountService
                            AccountService().freeze_account(det_id, reason, sd["user_id"])
                            st.success("Account frozen.")
                            st.session_state.pop("show_freeze_form", None)
                            st.session_state.pop("account_detail", None)
                        except Exception as e:
                            st.error(f"{e}")

                if st.session_state.get("show_unfreeze_form"):
                    reason = st.text_area("Reason for unfreezing", key="unfreeze_reason")
                    if st.button("Confirm Unfreeze", key="confirm_unfreeze"):
                        try:
                            from core.services.account_service import AccountService
                            AccountService().unfreeze_account(det_id, reason, sd["user_id"])
                            st.success("Account unfrozen.")
                            st.session_state.pop("show_unfreeze_form", None)
                            st.session_state.pop("account_detail", None)
                        except Exception as e:
                            st.error(f"{e}")

                if st.session_state.get("show_close_confirm"):
                    st.warning("This action is irreversible!")
                    confirm = st.checkbox("I confirm I want to close this account", key="close_confirm_check")
                    if confirm and st.button("Close Account Permanently", key="confirm_close"):
                        try:
                            from core.services.account_service import AccountService
                            AccountService().close_account(det_id, sd["user_id"])
                            st.success("Account closed.")
                            st.session_state.pop("show_close_confirm", None)
                            st.session_state.pop("account_detail", None)
                        except Exception as e:
                            st.error(f"{e}")
