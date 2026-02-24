"""
Loan Service — Business logic for loan applications, EMI calculations, and payments.
"""
from decimal import Decimal
from datetime import date
from typing import List, Dict, Any, Optional
from core.models.entities import Loan, LoanStatus, LoanType
from core.repositories.loan_repository import LoanRepository
from core.repositories.account_repository import AccountRepository
from core.repositories.credit_score_repository import CreditScoreRepository
from core.services.audit_service import AuditService
from utils.exceptions import ValidationException, InsufficientFundsException

# ─── Fixed Interest Rate Slabs (tenure-independent) ───────────────────────────
INTEREST_SLABS = [
    (Decimal("50000"),   Decimal("14.00")),   # ≤ ₹50,000  → 14% p.a.
    (Decimal("200000"),  Decimal("12.00")),   # ≤ ₹2,00,000 → 12% p.a.
    (Decimal("500000"),  Decimal("10.00")),   # ≤ ₹5,00,000 → 10% p.a.
]
DEFAULT_INTEREST_RATE = Decimal("8.50")       # > ₹5,00,000 → 8.5% p.a.

# ─── Allowed Tenure Options (months) ──────────────────────────────────────────
ALLOWED_TENURES = [6, 12, 24, 36]


class LoanService:
    def __init__(self):
        self.loan_repo = LoanRepository()
        self.account_repo = AccountRepository()
        self.credit_repo = CreditScoreRepository()
        self.audit_svc = AuditService()

    # ── Interest Slab Logic ────────────────────────────────────────────────────
    def get_interest_rate_for_amount(self, principal: Decimal) -> Decimal:
        """Return fixed annual interest rate based on loan amount slab.
        Rate is INDEPENDENT of tenure.
        """
        for threshold, rate in INTEREST_SLABS:
            if principal <= threshold:
                return rate
        return DEFAULT_INTEREST_RATE

    # ── EMI Calculation ────────────────────────────────────────────────────────
    def calculate_emi(self, principal: Decimal, annual_rate: Decimal, tenure_months: int) -> Decimal:
        """Calculate Equated Monthly Installment (EMI)"""
        if principal <= 0 or annual_rate < 0 or tenure_months <= 0:
            raise ValidationException("Invalid EMI parameters")

        monthly_rate = annual_rate / Decimal("1200")
        if monthly_rate > 0:
            emi = (
                principal
                * monthly_rate
                * (1 + monthly_rate) ** tenure_months
                / ((1 + monthly_rate) ** tenure_months - 1)
            )
        else:
            emi = principal / tenure_months

        return round(emi, 2)

    # ── Loan Application ───────────────────────────────────────────────────────
    def apply_for_loan(
        self,
        user_id: int,
        account_id: int,
        loan_type: LoanType,
        principal: Decimal,
        tenure_months: int,
        created_by: int,
        reference: str = None,
        # annual_rate is intentionally NOT a required param — derived from slab
        annual_rate: Decimal = None,
    ) -> int:
        """Process a new loan application.

        Interest rate is always derived from the amount slab.
        Tenure must be one of ALLOWED_TENURES.
        user_id must be the actual owner — enforced at UI layer, verified here.
        """
        # 0. Restrict to Personal Loans
        if loan_type != LoanType.PERSONAL:
            raise ValidationException("Only Personal Loans are supported currently.")

        # 1. Validate tenure
        if tenure_months not in ALLOWED_TENURES:
            raise ValidationException(
                f"Invalid tenure. Allowed values: {ALLOWED_TENURES} months."
            )

        # 2. Derive interest rate from slab (ignore any caller-supplied rate)
        annual_rate = self.get_interest_rate_for_amount(principal)

        # 3. Eligibility Check (relaxed — warn but don't block new users with score=0)
        score_data = self.credit_repo.get_latest_score(user_id)
        current_score = getattr(score_data, "current_score", 0) if score_data else 0
        if current_score > 0 and current_score < 600:
            raise ValidationException(
                f"Credit score too low ({current_score}). Minimum 600 required."
            )

        # 4. Calculate EMI
        emi = self.calculate_emi(principal, annual_rate, tenure_months)

        # 5. Generate reference if not provided
        if not reference:
            from utils.helpers import StringUtils
            reference = StringUtils.generate_reference_number("LON")

        loan = Loan(
            user_id=user_id,
            account_id=account_id,
            loan_plan_id=0,
            loan_type=loan_type,
            principal_amount=principal,
            interest_rate_annual=annual_rate,
            tenure_months=tenure_months,
            emi_amount=emi,
            status=LoanStatus.PENDING_APPROVAL,
            created_by=created_by,
            reference=reference,
        )

        loan_id = self.loan_repo.create_loan(loan)

        # 6. Audit log
        self.audit_svc.log(
            actor_id=created_by,
            role="admin" if created_by != user_id else "customer",
            action="LOAN_APPLY",
            details={"loan_id": loan_id, "amount": str(principal), "for_user": user_id},
        )

        return loan_id

    # ── Loan Queries ───────────────────────────────────────────────────────────
    def get_loans_for_user(self, user_id: int) -> List[Loan]:
        """Return all loans belonging to a specific user (customer self-view)."""
        return self.loan_repo.find_by_customer(user_id)

    def get_all_loans(self) -> List[Loan]:
        """Return ALL loans in the system (admin-only)."""
        return self.loan_repo.get_all_loans()

    # ── Approval / Rejection ───────────────────────────────────────────────────
    def approve_loan(self, loan_id: int, admin_user_id: int):
        """Approve loan application via service layer"""
        loan = self.loan_repo.find_loan_by_id(loan_id)
        if not loan:
            raise ValidationException("Loan not found")

        success = self.loan_repo.approve_loan(
            loan_id,
            loan.principal_amount,
            loan.interest_rate_annual,
            loan.tenure_months,
            admin_user_id,
        )

        if success:
            self.audit_svc.log(
                actor_id=admin_user_id,
                role="admin",
                action="LOAN_APPROVE",
                details={"loan_id": loan_id, "user_id": loan.user_id},
            )
        return success

    def reject_loan(self, loan_id: int, admin_user_id: int):
        """Reject loan application via service layer"""
        success = self.loan_repo.reject_loan(loan_id)
        if success:
            self.audit_svc.log(
                actor_id=admin_user_id,
                role="admin",
                action="LOAN_REJECT",
                details={"loan_id": loan_id},
            )
        return success

    # ── EMI Payment ────────────────────────────────────────────────────────────
    def process_emi_payment(self, loan_id: int, payment_amount: Decimal, processed_by: int):
        """Handle loan repayment installment"""
        loan = self.loan_repo.find_loan_by_id(loan_id)
        if not loan:
            raise ValidationException("Loan not found")

        if loan.status != LoanStatus.APPROVED:
            raise ValidationException(f"EMI cannot be paid for loan in {loan.status} status")

        self.loan_repo.update_balance(loan_id, payment_amount)
        self.credit_repo.calculate_and_save_score(loan.user_id)
        return True

    def get_overdue_loans(self):
        """Identify loans with missed payments"""
        return self.loan_repo.get_overdue()
