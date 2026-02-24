"""
Transactions Page - Deposit, withdraw, transfer, and view statements.
Roles: admin, customer
"""

import streamlit as st
import uuid


from utils.auth_guard import require_role, get_current_user, is_admin
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date, to_decimal

require_role(["admin", "customer"])
render_sidebar()

sd = get_current_user()

st.title("Transactions")
st.markdown("---")

# Conditionally render tabs based on role
if is_admin():
    tab_titles = ["Deposit", "Withdraw", "Transfer", "Statement"]
    tab_list = st.tabs(tab_titles)
    tab_deposit, tab_withdraw, tab_transfer, tab_statement = tab_list
else:
    tab_titles = ["Transfer", "Statement"]
    tab_list = st.tabs(tab_titles)
    tab_transfer, tab_statement = tab_list
    tab_deposit = None
    tab_withdraw = None

# ===========================
# TAB 1 - Deposit (Admin Only)
# ===========================
if is_admin() and tab_deposit:
    with tab_deposit:
        st.subheader("Process Deposit")

        # Idempotency: Generate reference for this form load
        if "dep_ref" not in st.session_state:
            from utils.helpers import StringUtils
            st.session_state["dep_ref"] = StringUtils.generate_reference_number("DEP")

        with st.form("deposit_form"):
            dep_acc_id = st.number_input("Account ID", min_value=1, step=1, key="dep_acc_id")
            dep_amount = st.number_input("Amount (INR)", min_value=1.0, step=100.0, format="%.2f", key="dep_amount")
            dep_desc = st.text_input("Description / Narration", placeholder="Cash deposit", key="dep_desc")
            st.caption(f"Transaction ID: `{st.session_state['dep_ref']}`")
            dep_submitted = st.form_submit_button("Process Deposit", use_container_width=True)

        if dep_submitted:
            if dep_amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                try:
                    from core.services.transaction_service import TransactionService

                    txn_svc = TransactionService()
                    result = txn_svc.deposit(
                        account_id=int(dep_acc_id),
                        amount=to_decimal(dep_amount),
                        description=dep_desc or "Cash deposit",
                        performed_by=sd.get("user_id"),
                        reference=st.session_state["dep_ref"]
                    )
                    st.success(f"Deposit successful! Reference: **{result.get('reference', 'N/A')}**")
                    st.session_state.pop("dep_ref")
                    st.metric("New Balance", format_currency(result.get("balance_after", 0)))
                except Exception as e:
                    st.error(f"{e}")

# ===========================
# TAB 2 - Withdraw (Admin Only)
# ===========================
if is_admin() and tab_withdraw:
    with tab_withdraw:
        st.subheader("Process Withdrawal")

        # Idempotency: Generate reference for this form load
        if "wd_ref" not in st.session_state:
            from utils.helpers import StringUtils
            st.session_state["wd_ref"] = StringUtils.generate_reference_number("WDR")

        with st.form("withdraw_form"):
            wd_acc_id = st.number_input("Account ID", min_value=1, step=1, key="wd_acc_id")
            wd_amount = st.number_input("Amount (INR)", min_value=1.0, step=100.0, format="%.2f", key="wd_amount")
            wd_desc = st.text_input("Description / Narration", placeholder="Cash withdrawal", key="wd_desc")
            st.caption(f"Transaction ID: `{st.session_state['wd_ref']}`")
            wd_submitted = st.form_submit_button("Process Withdrawal", use_container_width=True)

        if wd_submitted:
            if wd_amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                try:
                    from core.services.transaction_service import TransactionService

                    txn_svc = TransactionService()
                    result = txn_svc.withdraw(
                        account_id=int(wd_acc_id),
                        amount=to_decimal(wd_amount),
                        description=wd_desc or "Cash withdrawal",
                        performed_by=sd.get("user_id"),
                        reference=st.session_state["wd_ref"]
                    )
                    st.success(f"Withdrawal successful! Reference: **{result.get('reference', 'N/A')}**")
                    st.session_state.pop("wd_ref")
                    st.metric("New Balance", format_currency(result.get("balance_after", 0)))
                except Exception as e:
                    st.error(f"{e}")

# ===========================
# TAB 3 - Transfer (two-step)
# ===========================
with tab_transfer:
    st.subheader("Transfer Between Accounts")

    # Step 1: Collect transfer details
    if "transfer_pending" not in st.session_state:
        # Pre-fetch accounts for customers to use in form
        customer_accounts = {}
        if not is_admin():
            try:
                from core.services.account_service import AccountService
                my_accounts = AccountService().get_customer_accounts(sd.get("user_id"))
                if my_accounts:
                    customer_accounts = {f"{a['account_number']} ({format_currency(a['balance'])})": a['account_id'] for a in my_accounts}
            except Exception:
                pass

        with st.form("transfer_form"):
            if is_admin():
                tf_from = st.number_input("From Account ID", min_value=1, step=1, key="tf_from")
            else:
                if customer_accounts:
                    tf_from_str = st.selectbox("From Account", options=list(customer_accounts.keys()), key="tf_from_select")
                    tf_from = customer_accounts.get(tf_from_str)
                else:
                    st.warning("No accounts found to transfer from.")
                    tf_from = None

            tf_to = st.number_input("To Account ID", min_value=1, step=1, key="tf_to")
            tf_amount = st.number_input("Amount (INR)", min_value=1.0, step=100.0, format="%.2f", key="tf_amount")
            tf_desc = st.text_input("Description", placeholder="Fund transfer", key="tf_desc")
            tf_submitted = st.form_submit_button("Review Transfer", use_container_width=True)

        if tf_submitted:
            if not tf_from:
                st.error("Please select a valid source account.")
            elif tf_from == tf_to:
                st.error("From and To accounts must be different.")
            elif tf_amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                st.session_state["transfer_pending"] = {
                    "from_account": int(tf_from),
                    "to_account": int(tf_to),
                    "amount": tf_amount,
                    "description": tf_desc or "Fund transfer",
                    "txn_key": str(uuid.uuid4()),
                }
                st.rerun()

    # Step 2: Confirm
    if "transfer_pending" in st.session_state:
        tp = st.session_state["transfer_pending"]
        st.warning("Please review the transfer details below before confirming.")

        st.markdown(f"""
        | Detail | Value |
        |--------|-------|
        | **From Account** | {tp['from_account']} |
        | **To Account** | {tp['to_account']} |
        | **Amount** | {format_currency(tp['amount'])} |
        | **Description** | {tp['description']} |
        """)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm Transfer", use_container_width=True, key="confirm_transfer"):
                try:
                    from core.services.transaction_service import TransactionService

                    txn_svc = TransactionService()
                    result = txn_svc.transfer(
                        from_account_id=tp["from_account"],
                        to_account_id=tp["to_account"],
                        amount=to_decimal(tp["amount"]),
                        description=tp["description"],
                        performed_by=sd.get("user_id"),
                        reference=tp["txn_key"]
                    )
                    st.success(f"Transfer successful! Reference: **{result.get('reference', 'N/A')}**")
                    del st.session_state["transfer_pending"]
                except Exception as e:
                    st.error(f"{e}")
                    del st.session_state["transfer_pending"]

        with c2:
            if st.button("Cancel", use_container_width=True, key="cancel_transfer"):
                del st.session_state["transfer_pending"]
                st.rerun()

# ===========================
# TAB 4 - Statement
# ===========================
with tab_statement:
    st.subheader("Account Statement")

    st_col1, st_col2 = st.columns([2, 1])

    selected_acc_id = None

    with st_col1:
        if is_admin():
            stmt_acc_id = st.number_input("Account ID", min_value=1, step=1, key="stmt_acc_id")
            selected_acc_id = stmt_acc_id
        else:
            # For customers, show dropdown of their accounts
            from core.services.account_service import AccountService
            try:
                my_accounts = AccountService().get_customer_accounts(sd.get("user_id"))
                if my_accounts:
                    # Create options list: "Account Number (Balance)"
                    acc_options = {f"{a['account_number']} ({format_currency(a['balance'])})": a['account_id'] for a in my_accounts}
                    selected_option = st.selectbox("Select Account", options=list(acc_options.keys()), key="stmt_acc_select")
                    selected_acc_id = acc_options[selected_option]
                else:
                    st.warning("No accounts found.")
            except Exception as e:
                st.error(f"Error fetching accounts: {e}")

    with st_col2:
        stmt_limit = st.number_input("Max records", min_value=10, max_value=500, value=50, step=10, key="stmt_limit")

    load_stmt = st.button("Load Statement", key="load_stmt_btn", disabled=(selected_acc_id is None))

    if load_stmt and selected_acc_id:
        try:
            from core.services.transaction_service import TransactionService

            txn_svc = TransactionService()
            history = txn_svc.get_transaction_history(
                account_id=int(selected_acc_id),
                performed_by=sd.get("user_id"),
                limit=int(stmt_limit)
            )

            if history:
                st.session_state["statement_data"] = history
            else:
                st.info("No transactions found for this account.")
        except Exception as e:
            st.error(f"{e}")

    if "statement_data" in st.session_state:
        data = st.session_state["statement_data"]
        if isinstance(data, list) and len(data) > 0:
            import pandas as pd

            if isinstance(data[0], dict):
                df = pd.DataFrame(data)
            else:
                # Convert dataclass objects to dicts
                df = pd.DataFrame([vars(t) for t in data])

            display_cols = [c for c in ["txn_id", "txn_type", "amount", "balance_after_txn", "narration", "reference", "txn_time"] if c in df.columns]
            if display_cols:
                st.dataframe(df[display_cols], use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)

            # Download button
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, file_name="statement.csv", mime="text/csv")
        else:
            st.info("No transaction data available.")

    # ---- Search by reference ----
    st.markdown("---")
    st.markdown("#### Search Transaction by Reference")
    ref_input = st.text_input("Reference Number", key="txn_ref_input", placeholder="TXN-XXXXXXXX")
    if st.button("Search", key="search_ref_btn") and ref_input:
        try:
            from core.services.transaction_service import TransactionService

            txn_svc = TransactionService()
            txn = txn_svc.get_transaction_by_reference(ref_input)
            if txn:
                if isinstance(txn, dict):
                    st.json(txn)
                else:
                    st.json(vars(txn))
            else:
                st.warning("Transaction not found.")
        except Exception as e:
            st.error(f"{e}")
