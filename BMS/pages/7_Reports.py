"""
Reports Page - Transaction summaries, account statistics, and exports.
Roles: admin
"""

import streamlit as st
import pandas as pd


from utils.auth_guard import require_role, get_current_user
from utils.sidebar import render_sidebar
from utils.formatters import format_currency, format_date

require_role(["admin"])
render_sidebar()

sd = get_current_user()

st.title("Reports & Analytics")
st.markdown("---")

tab_txn, tab_acct, tab_alerts = st.tabs(
    ["Transaction Summary", "Account Statistics", "Alerts"]
)

# ===========================
# TAB 1 - Transaction Summary
# ===========================
with tab_txn:
    st.subheader("Transaction Summary")

    tc1, tc2 = st.columns(2)
    with tc1:
        rpt_acc_id = st.number_input("Account ID", min_value=1, step=1, key="rpt_acc_id")
    with tc2:
        rpt_days = st.selectbox("Select Report Period", [7, 30, 60, 90, 180, 365], index=1, key="rpt_days",
                                 format_func=lambda d: f"Last {d} Days")

    if st.button("Generate Report", key="gen_txn_rpt"):
        try:
            from core.services.transaction_service import TransactionService

            svc = TransactionService()
            summary = svc.get_transaction_summary(int(rpt_acc_id), days=int(rpt_days), performed_by=sd["user_id"])

            if summary:
                if isinstance(summary, dict):
                    sm1, sm2, sm3 = st.columns(3)
                    sm1.metric("Total Deposits", format_currency(summary.get("total_deposits", 0)))
                    sm2.metric("Total Withdrawals", format_currency(summary.get("total_withdrawals", 0)))
                    sm3.metric("Net Change", format_currency(summary.get("net_change", 0)))

                    if "transactions" in summary:
                        df = pd.DataFrame(summary["transactions"])
                        st.dataframe(df, use_container_width=True)
                else:
                    st.json(summary if isinstance(summary, dict) else vars(summary))
            else:
                st.info("No transaction data for the selected period.")

            # Also get full history for chart
            history = svc.get_transaction_history(int(rpt_acc_id), performed_by=sd["user_id"], limit=100)
            if history and isinstance(history, list) and len(history) > 0:
                if isinstance(history[0], dict):
                    df = pd.DataFrame(history)
                else:
                    df = pd.DataFrame([vars(t) for t in history])

                if "amount" in df.columns and "txn_type" in df.columns:
                    st.markdown("#### Transaction Distribution")
                    type_summary = df.groupby("txn_type")["amount"].sum()
                    st.bar_chart(type_summary)

                csv = df.to_csv(index=False)
                st.download_button("Download Full Report (CSV)", csv, file_name="transaction_report.csv", mime="text/csv")

        except Exception as e:
            st.error(f"{e}")

# ===========================
# TAB 2 - Account Statistics
# ===========================
with tab_acct:
    st.subheader("Account Statistics")

    if st.button("Load Statistics", key="load_acct_stats"):
        try:
            from core.services.account_service import AccountService

            svc = AccountService()
            low_bal = svc.get_low_balance_accounts() or []

            st.metric("Low Balance Accounts", len(low_bal))

            if low_bal:
                st.markdown("#### Low Balance Account Details")
                rows = []
                for acc in low_bal:
                    if isinstance(acc, dict):
                        rows.append(acc)
                    else:
                        rows.append({
                            "Account ID": getattr(acc, "account_id", "N/A"),
                            "Account #": getattr(acc, "account_number", "N/A"),
                            "Balance": str(getattr(acc, "balance", 0)),
                            "Min Balance": str(getattr(acc, "min_balance", 0)),
                            "Type": str(getattr(acc, "account_type", "").value if hasattr(getattr(acc, "account_type", ""), "value") else getattr(acc, "account_type", "")),
                        })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"{e}")

# ===========================
# TAB 3 - Alerts
# ===========================
with tab_alerts:
    st.subheader("System Alerts")

    try:
        from core.services.account_service import AccountService

        svc = AccountService()
        low_bal = svc.get_low_balance_accounts() or []

        if low_bal:
            st.warning(f"**{len(low_bal)} account(s)** are below minimum balance requirement.")
            for acc in low_bal:
                acc_num = getattr(acc, "account_number", "N/A") if not isinstance(acc, dict) else acc.get("account_number", "N/A")
                bal = getattr(acc, "balance", 0) if not isinstance(acc, dict) else acc.get("balance", 0)
                st.markdown(f"- Account **{acc_num}** - Balance: {format_currency(bal)}")
        else:
            st.success("No alerts. All accounts are in good standing.")

    except Exception:
        st.info("Unable to load alerts. Database may not be connected.")
