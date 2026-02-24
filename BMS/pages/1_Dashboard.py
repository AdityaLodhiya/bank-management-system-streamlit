"""
Dashboard Page - Unified interface with role-based conditional rendering.
Shows customer features for CUSTOMER role, admin features for ADMIN role.
"""

import streamlit as st
from decimal import Decimal



from utils.auth_guard import require_login, get_current_user, is_admin, is_customer, get_user_role
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date

require_login()
render_sidebar()

sd = get_current_user()
role = get_user_role()

# Header
st.title("Dashboard Overview")
st.caption(f"Welcome, **{sd.get('username', 'User')}** ({role.replace('_', ' ').title()})")
st.markdown("---")

# ===============================================================
# CUSTOMER DASHBOARD
# ===============================================================
if is_customer():
    try:
        from core.services.account_service import AccountService
        from core.services.transaction_service import TransactionService

        acct_svc = AccountService()
        txn_svc = TransactionService()

        from core.repositories.customer_repository import CustomerRepository
        cust_repo = CustomerRepository()
        customer = cust_repo.find_customer_by_id(sd["user_id"])

        accounts = []
        if customer:
            user_id = customer.user_id
            accounts = acct_svc.get_customer_accounts(user_id)

            # Self-healing: If user is active but missing account row, create it now
            if not accounts and sd.get("registration_status") == "active":
                with st.spinner("Initializing your initial savings account..."):
                    init_res = acct_svc.initiate_savings_account(sd["user_id"])
                    if init_res.get("success"):
                        accounts = acct_svc.get_customer_accounts(sd["user_id"])
                        st.toast("Savings account auto-initialized.")

        if not accounts:
            if sd.get("registration_status") != "active":
                st.info("Your account is pending admin approval. Please wait for verification.")
            else:
                st.error("No active accounts found. Please contact support.")
                if not customer:
                    st.warning("Customer profile missing. Please complete your registration.")
        else:
            # Display primary account
            main_acct = accounts[0]

            # 1. Account Info Card
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Account Number", main_acct['account_number'])
                c2.metric("Type", main_acct['account_type'].title())
                c3.metric("Balance", format_currency(main_acct['balance']))
                c4.metric("Status", main_acct['status'].upper())

            st.markdown("---")

            # 2. Banking Operations (Side by Side)
            op_col1, op_col2 = st.columns([1, 1.5])

            with op_col1:
                st.subheader("Quick Transfer")
                st.caption("Transfer funds to another account.")
                st.info("Use the **Transactions** page to initiate a transfer.")
                st.page_link("pages/4_Transactions.py", label="Go to Transactions ->", use_container_width=True)

            with op_col2:
                st.subheader("Recent Transactions")
                history = txn_svc.get_transaction_history(
                    main_acct['account_id'],
                    performed_by=sd["user_id"],
                    limit=5
                )
                if not history:
                    st.info("No transactions logged for this account.")
                else:
                    import pandas as pd
                    df = pd.DataFrame(history)
                    df = df[['txn_time', 'txn_type', 'amount', 'balance_after_txn']]
                    df['amount'] = df['amount'].apply(lambda x: format_currency(x))
                    df['balance_after_txn'] = df['balance_after_txn'].apply(lambda x: format_currency(x))
                    df['txn_time'] = pd.to_datetime(df['txn_time']).dt.strftime('%Y-%m-%d %H:%M')
                    df.columns = ['Date', 'Type', 'Amount', 'Balance After']
                    st.table(df)

    except Exception as e:
        st.error(f"Error loading banking data: {e}")

# ===============================================================
# ADMIN DASHBOARD
# ===============================================================
elif is_admin():
    # Admin sees everything in tabs
    tab_overview, tab_users, tab_accounts, tab_audit, tab_system = st.tabs([
        "Overview",
        "User Management",
        "Account Actions",
        "Audit Logs",
        "System Health"
    ])

    # -------------------------------------------------------
    # TAB 1: Overview
    # -------------------------------------------------------
    with tab_overview:
        st.subheader("System Overview")

        c1, c2, c3, c4 = st.columns(4)

        try:
            from core.services.account_service import AccountService
            acct_svc = AccountService()
            low_bal = acct_svc.get_low_balance_accounts()
            low_count = len(low_bal) if low_bal else 0
        except Exception:
            low_count = 0

        c1.metric("System Role", role.replace("_", " ").title())
        c2.metric("Login Time", format_date(sd.get("login_time")))
        c3.metric("Low-Balance Alerts", low_count)
        c4.metric("System Status", "Online")

        st.markdown("---")

        # Quick actions row
        qa1, qa2, qa3, qa4 = st.columns(4)
        with qa1:
            st.page_link("pages/7_Reports.py", label="Detailed Reports", use_container_width=True)
        with qa2:
             if st.button("Refresh Overview", use_container_width=True):
                 st.rerun()

        st.markdown("---")
        st.subheader("Branch Cash Deposit")
        st.caption("Record a cash deposit for a customer at the branch.")

        # Idempotency: Generate reference for this form load
        if "admin_deposit_ref" not in st.session_state:
            from utils.helpers import StringUtils
            st.session_state["admin_deposit_ref"] = StringUtils.generate_reference_number("CSH")

        with st.form("admin_deposit_form", clear_on_submit=True):
            d_acc = st.text_input("Account Number", placeholder="e.g. SC-SAV-0001-1234")
            d_amt = st.number_input("Deposit Amount", min_value=1.0, step=500.0)
            d_nar = st.text_input("Narration", value="Cash deposit at branch")
            st.caption(f"Transaction ID: `{st.session_state['admin_deposit_ref']}`")
            d_sub = st.form_submit_button("Record Cash Deposit", use_container_width=True)

        if d_sub:
            try:
                from core.services.account_service import AccountService
                from core.services.transaction_service import TransactionService

                # Find account ID by account number
                acct_repo = AccountService().account_repo
                target_acct = acct_repo.find_by_account_number(d_acc)

                if not target_acct:
                    st.error("Account not found. Please verify account number.")
                else:
                    txn_svc = TransactionService()
                    res = txn_svc.deposit(
                        account_id=target_acct.account_id,
                        amount=Decimal(str(d_amt)),
                        description=d_nar,
                        performed_by=sd["user_id"],
                        txn_type="CASH_DEPOSIT",
                        reference=st.session_state["admin_deposit_ref"]
                    )
                    st.success(f"Cash deposit recorded! Ref: {res['reference']}")
                    st.session_state.pop("admin_deposit_ref")
                    st.balloons()
            except Exception as e:
                st.error(f"{e}")

    # -------------------------------------------------------
    # TAB 2: User Management (Consolidated)
    # -------------------------------------------------------
    with tab_users:
        # Pending section
        st.subheader("Pending Approvals")
        try:
            from core.services.authentication_service import AuthenticationService
            from core.repositories.customer_repository import CustomerRepository
            auth = AuthenticationService()
            pending_users = auth.user_repo.get_pending_registrations()

            if not pending_users:
                st.info("No pending approvals.")
            else:
                st.metric("Pending Approvals", len(pending_users))
                cust_repo = CustomerRepository()
                for user in pending_users:
                    customer = cust_repo.find_customer_by_id(user.user_id)
                    cust_name = customer.full_name if customer else "N/A"
                    with st.expander(f"Review: {cust_name} (@{user.username})"):
                        st.markdown(f"**Phone:** {user.phone} | **DOB:** {customer.dob if customer else 'N/A'}")
                        b1, b2 = st.columns(2)
                        if b1.button("Approve", key=f"apprv_{user.user_id}", use_container_width=True):
                            auth.approve_user(user.user_id, sd["user_id"])
                            st.rerun()
                        if b2.button("Reject", key=f"rej_{user.user_id}", use_container_width=True):
                            auth.reject_kyc(user.user_id, sd["user_id"], "Rejected by admin")
                            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("Quick Create User")
        with st.expander("New User Form", expanded=False):
            with st.form("create_user_form"):
                cu_col1, cu_col2 = st.columns(2)
                with cu_col1:
                    new_username = st.text_input("Username")
                    new_password = st.text_input("Password", type="password")
                with cu_col2:
                    new_role = st.selectbox("Role", ["customer", "admin"])
                    confirm_password = st.text_input("Confirm Password", type="password")

                create_submitted = st.form_submit_button("Create User", use_container_width=True)

            if create_submitted:
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        from core.models.entities import UserRole
                        auth = AuthenticationService()
                        auth.create_user(new_username, new_password, UserRole(new_role), sd["user_id"])
                        st.success(f"User {new_username} created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"{e}")

        st.markdown("---")
        st.subheader("All System Users")
        if st.button("Load User List", use_container_width=True):
            try:
                from core.repositories.user_repository import UserRepository
                repo = UserRepository()
                st.session_state["admin_user_list"] = repo.get_all()
            except Exception as e:
                st.error(f"{e}")

        if "admin_user_list" in st.session_state:
            for user in st.session_state["admin_user_list"]:
                status = user.registration_status
                role_label = user.role.value if hasattr(user.role, 'value') else str(user.role)
                with st.expander(f"{user.username} - {role_label.title()} ({status})"):
                    bc1, bc2 = st.columns(2)
                    if status == "blocked":
                        if bc1.button(f"Unblock {user.username}", key=f"unbl_{user.user_id}", use_container_width=True):
                            AuthenticationService().unblock_user(user.user_id, sd["user_id"])
                            st.session_state.pop("admin_user_list")
                            st.rerun()
                    else:
                        if bc1.button(f"Block {user.username}", key=f"bl_{user.user_id}", use_container_width=True):
                            AuthenticationService().block_user(user.user_id, sd["user_id"], "Admin action")
                            st.session_state.pop("admin_user_list")
                            st.rerun()
                    
                    if bc2.button(f"Force Logout {user.username}", key=f"flog_{user.user_id}", use_container_width=True):
                        AuthenticationService().force_logout(user.user_id, sd["user_id"])
                        st.toast(f"Sessions invalidated for {user.username}")

    # -------------------------------------------------------
    # TAB 3: Account Actions (Freeze/Unfreeze)
    # -------------------------------------------------------
    with tab_accounts:
        st.subheader("Account Operations")
        st.caption("Manage account availability and restrictions.")

        fcol1, fcol2 = st.columns(2)
        with fcol1:
            st.markdown("#### Freeze Account")
            with st.form("freeze_form"):
                acc_to_freeze = st.text_input("Account Number", placeholder="SC-SAV-...")
                freeze_reason = st.text_input("Reason", placeholder="Suspicious activity")
                if st.form_submit_button("Freeze Account", use_container_width=True):
                    try:
                        from core.services.account_service import AccountService
                        asvc = AccountService()
                        acct = asvc.account_repo.find_by_account_number(acc_to_freeze)
                        if not acct: st.error("Account not found")
                        else:
                            asvc.freeze_account(acct.account_id, freeze_reason, sd["user_id"])
                            st.success(f"Account {acc_to_freeze} frozen.")
                    except Exception as e: st.error(f"{e}")

        with fcol2:
            st.markdown("#### Unfreeze Account")
            with st.form("unfreeze_form"):
                acc_to_unfreeze = st.text_input("Account Number", placeholder="SC-SAV-...")
                unfreeze_reason = st.text_input("Reason", placeholder="Issue resolved")
                if st.form_submit_button("Unfreeze Account", use_container_width=True):
                    try:
                        from core.services.account_service import AccountService
                        asvc = AccountService()
                        acct = asvc.account_repo.find_by_account_number(acc_to_unfreeze)
                        if not acct: st.error("Account not found")
                        else:
                            asvc.unfreeze_account(acct.account_id, unfreeze_reason, sd["user_id"])
                            st.success(f"Account {acc_to_unfreeze} unfrozen.")
                    except Exception as e: st.error(f"{e}")

    # -------------------------------------------------------
    # TAB 4: Audit Logs
    # -------------------------------------------------------
    with tab_audit:
        st.subheader("System Audit Trail")
        st.caption("Review critical system events and administrative actions.")
        
        if st.button("Refresh Audit Logs", use_container_width=True):
            try:
                from core.services.audit_service import AuditService
                st.session_state["admin_audit_logs"] = AuditService().get_latest_activity(50)
            except Exception as e:
                st.error(f"{e}")

        if "admin_audit_logs" in st.session_state:
            import json
            import pandas as pd
            logs = st.session_state["admin_audit_logs"]
            log_data = []
            for l in logs:
                details = l['details']
                if isinstance(details, str):
                    try: details = json.loads(details)
                    except: pass
                log_data.append({
                    "Time": format_date(l['created_at']),
                    "Actor ID": l['actor_id'],
                    "Role": l['role'].upper(),
                    "Action": l['action'],
                    "Details": str(details)
                })
            st.table(pd.DataFrame(log_data))

    # -------------------------------------------------------
    # TAB 5: System Health
    # -------------------------------------------------------
    with tab_system:
        st.subheader("System Status & Maintenance")
        
        h1, h2, h3 = st.columns(3)
        try:
            from db.database import db_manager
            db_conn = "Connected" if db_manager.db_config.test_connection() else "Disconnected"
        except: db_conn = "Error"
        
        h1.metric("Database", db_conn)
        h2.metric("Application", "Online")
        h3.metric("Version", "1.0.0 Stable")

        st.markdown("---")
        st.markdown("#### Session Management")
        c_cl, c_act = st.columns(2)
        with c_cl:
            if st.button("Cleanup Expired Sessions", use_container_width=True):
                try:
                    from core.services.authentication_service import AuthenticationService
                    count = AuthenticationService().cleanup_expired_sessions()
                    st.success(f"Cleaned {count} sessions.")
                except Exception as e: st.error(f"{e}")
        
        with c_act:
            if st.button("View Active Sessions", use_container_width=True):
                try:
                    from core.services.authentication_service import AuthenticationService
                    st.session_state["admin_active_sessions"] = AuthenticationService().get_active_sessions()
                except Exception as e: st.error(f"{e}")

        if "admin_active_sessions" in st.session_state:
            for s in st.session_state["admin_active_sessions"]:
                st.write(f"- **{s['username']}** (ID: {s['user_id']}) from {s.get('ip_address', 'Unknown')} at {format_date(s['login_time'])}")


# Fallback - if no role matches
else:
    st.error("Access Denied")
    st.info("No banking services are available for your current role. Please contact the administrator.")

    if st.button("Logout"):
        from utils.auth_guard import handle_logout
        handle_logout()
