"""
Investment Service — Logic for Fixed Deposits (FD) and Recurring Deposits (RD).

Interest Rules:
  FD: Fixed rate based on principal amount slab (tenure-independent)
  RD: Fixed rate based on monthly installment amount slab (tenure-independent)

Tenure: Must be one of ALLOWED_TENURES = [6, 12, 24, 36] months.
"""
from decimal import Decimal
from datetime import date
from typing import List
from dateutil.relativedelta import relativedelta

from core.models.entities import FDAccount, RDAccount
from core.repositories.fd_account_repository import FDAccountRepository
from core.repositories.rd_account_repository import RDAccountRepository
from core.repositories.deposit_plan_repository import DepositPlanRepository
from core.services.audit_service import AuditService
from utils.exceptions import ValidationException

# ─── Allowed Tenure Options (shared with Loan module) ─────────────────────────
ALLOWED_TENURES = [6, 12, 24, 36]

# ─── FD Interest Slabs (principal-based, tenure-independent) ──────────────────
FD_INTEREST_SLABS = [
    (Decimal("50000"),   Decimal("6.50")),   # ≤ ₹50,000  → 6.5% p.a.
    (Decimal("200000"),  Decimal("7.00")),   # ≤ ₹2,00,000 → 7.0% p.a.
    (Decimal("500000"),  Decimal("7.50")),   # ≤ ₹5,00,000 → 7.5% p.a.
]
FD_DEFAULT_RATE = Decimal("8.00")            # > ₹5,00,000 → 8.0% p.a.

# ─── RD Interest Slabs (installment-based, tenure-independent) ────────────────
RD_INTEREST_SLABS = [
    (Decimal("5000"),   Decimal("6.00")),    # ≤ ₹5,000/mo  → 6.0% p.a.
    (Decimal("20000"),  Decimal("6.50")),    # ≤ ₹20,000/mo → 6.5% p.a.
]
RD_DEFAULT_RATE = Decimal("7.00")            # > ₹20,000/mo → 7.0% p.a.


class InvestmentService:
    def __init__(self):
        self.fd_repo  = FDAccountRepository()
        self.rd_repo  = RDAccountRepository()
        self.plan_repo = DepositPlanRepository()
        self.audit_svc = AuditService()

    # ── Slab Rate Helpers ──────────────────────────────────────────────────────
    def get_fd_rate(self, principal: Decimal) -> Decimal:
        """Return fixed FD annual rate based on principal slab. Tenure-independent."""
        for threshold, rate in FD_INTEREST_SLABS:
            if principal <= threshold:
                return rate
        return FD_DEFAULT_RATE

    def get_rd_rate(self, installment: Decimal) -> Decimal:
        """Return fixed RD annual rate based on monthly installment slab. Tenure-independent."""
        for threshold, rate in RD_INTEREST_SLABS:
            if installment <= threshold:
                return rate
        return RD_DEFAULT_RATE

    # ── Maturity Calculations ──────────────────────────────────────────────────
    def calculate_fd_maturity(self, principal: Decimal, rate: Decimal, tenure_months: int) -> Decimal:
        """FD maturity: compound interest, annual compounding.
        A = P * (1 + r/100) ^ (months/12)
        """
        maturity = principal * (1 + rate / 100) ** (Decimal(str(tenure_months)) / 12)
        return round(maturity, 2)

    def calculate_rd_maturity(self, installment: Decimal, rate: Decimal, tenure_months: int) -> Decimal:
        """RD maturity: each installment earns compound interest for remaining months.
        Standard RD formula.
        """
        monthly_rate = rate / Decimal("1200")
        n = tenure_months
        if monthly_rate > 0:
            maturity = installment * ((1 + monthly_rate) ** n - 1) / monthly_rate * (1 + monthly_rate)
        else:
            maturity = installment * n
        return round(maturity, 2)

    # ── Open FD ────────────────────────────────────────────────────────────────
    def open_fd(
        self,
        account_id: int,
        tenure_months: int,
        principal: Decimal,
        payout_mode: str,
        created_by: int,
        plan_id: int = 1,
    ) -> int:
        """Open a new Fixed Deposit.

        Interest rate is always derived from the principal slab.
        Tenure must be one of ALLOWED_TENURES.
        """
        if tenure_months not in ALLOWED_TENURES:
            raise ValidationException(f"Invalid tenure. Allowed: {ALLOWED_TENURES} months.")

        rate = self.get_fd_rate(principal)
        maturity_amount = self.calculate_fd_maturity(principal, rate, tenure_months)
        start = date.today()
        maturity_date = start + relativedelta(months=tenure_months)

        fd = FDAccount(
            account_id=account_id,
            plan_id=plan_id,
            principal_amount=principal,
            interest_rate=rate,
            start_date=start,
            maturity_date=maturity_date,
            maturity_amount=maturity_amount,
            payout_mode=payout_mode,
            status="active",
        )

        fd_id = self.fd_repo.create_fd_account(fd)

        self.audit_svc.log(
            actor_id=created_by,
            role="admin" if created_by != self._get_account_owner(account_id) else "customer",
            action="FD_OPEN",
            details={"fd_id": fd_id, "principal": str(principal), "rate": str(rate)},
        )
        return fd_id

    # ── Open RD ────────────────────────────────────────────────────────────────
    def open_rd(
        self,
        account_id: int,
        tenure_months: int,
        installment: Decimal,
        created_by: int,
        plan_id: int = 2,
    ) -> int:
        """Open a new Recurring Deposit.

        Interest rate is always derived from the installment slab.
        Tenure must be one of ALLOWED_TENURES.
        """
        if tenure_months not in ALLOWED_TENURES:
            raise ValidationException(f"Invalid tenure. Allowed: {ALLOWED_TENURES} months.")

        rate = self.get_rd_rate(installment)
        start = date.today()
        maturity_date = start + relativedelta(months=tenure_months)

        rd = RDAccount(
            account_id=account_id,
            plan_id=plan_id,
            installment_amount=installment,
            total_installments=tenure_months,
            paid_installments=0,
            interest_rate=rate,
            start_date=start,
            maturity_date=maturity_date,
            status="active",
            next_due_date=start + relativedelta(months=1),
        )

        rd_id = self.rd_repo.create_rd_account(rd)

        self.audit_svc.log(
            actor_id=created_by,
            role="admin" if created_by != self._get_account_owner(account_id) else "customer",
            action="RD_OPEN",
            details={"rd_id": rd_id, "installment": str(installment), "rate": str(rate)},
        )
        return rd_id

    # ── Ownership Queries ──────────────────────────────────────────────────────
    def get_fds_for_user(self, user_id: int) -> List[FDAccount]:
        """Return all FDs belonging to a specific user."""
        return self.fd_repo.find_by_user(user_id)

    def get_rds_for_user(self, user_id: int) -> List[RDAccount]:
        """Return all RDs belonging to a specific user."""
        return self.rd_repo.find_by_user(user_id)

    def get_all_fds(self) -> List[FDAccount]:
        """Return ALL FDs in the system (admin-only)."""
        return self.fd_repo.get_all_fds()

    def get_all_rds(self) -> List[RDAccount]:
        """Return ALL RDs in the system (admin-only)."""
        return self.rd_repo.get_all_rds()

    # ── Internal Helpers ───────────────────────────────────────────────────────
    def _get_account_owner(self, account_id: int) -> int:
        """Return user_id for an account (used for audit role labeling)."""
        try:
            from core.repositories.account_repository import AccountRepository
            acct = AccountRepository().find_by_id(account_id)
            return acct.get("user_id") if isinstance(acct, dict) else getattr(acct, "user_id", 0)
        except Exception:
            return 0

    def process_maturities(self):
        """Scan and credit matured investments (to be called by InterestEngine)"""
        today = date.today()
        try:
            matured_fds = self.fd_repo.get_matured_fds()
        except Exception:
            matured_fds = []
        return len(matured_fds)
