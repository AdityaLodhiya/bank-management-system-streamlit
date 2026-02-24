"""
Formatting helpers shared across Streamlit pages.
Currency formatting, status badges, date helpers.
"""

from decimal import Decimal
from datetime import datetime, date
from typing import Union


def format_currency(amount: Union[int, float, Decimal, str]) -> str:
    """Format amount as Indian Rupee currency string."""
    try:
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        return f"₹{amount:,.2f}"
    except Exception:
        return f"₹{amount}"


def format_date(dt: Union[datetime, date, None]) -> str:
    """Format date for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%d %b %Y, %I:%M %p")
    return dt.strftime("%d %b %Y")


def status_badge(status: str) -> str:
    """Return an emoji + text badge for account/loan status values."""
    badges = {
        "active": "Active",
        "frozen": "Frozen",
        "closed": "Closed",
        "pending_approval": "Pending Approval",
        "approved": "Approved",
        "rejected": "Rejected",
        "defaulted": "Defaulted",
        "sent": "Sent",
        "queued": "Queued",
        "failed": "Failed",
    }
    return badges.get(status, status.replace("_", " ").title())


def to_decimal(value: Union[float, int, str]) -> Decimal:
    """Safely convert a Streamlit number_input value to Decimal."""
    return Decimal(str(value))
