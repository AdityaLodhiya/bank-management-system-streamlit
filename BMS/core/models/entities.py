"""
Data Models for SecureCore Banking System
Dataclasses representing database entities
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum

# Enums for database constraints
class UserRole(Enum):
    ADMIN = 'admin'
    CUSTOMER = 'customer'

class AccountType(Enum):
    SAVINGS = 'savings'
    CURRENT = 'current'
    SALARY = 'salary'

class AccountStatus(Enum):
    ACTIVE = 'active'
    FROZEN = 'frozen'
    CLOSED = 'closed'

class EmploymentType(Enum):
    SALARIED = 'salaried'
    SELF_EMPLOYED = 'self_employed'
    STUDENT = 'student'
    UNEMPLOYED = 'unemployed'

class RiskProfile(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'

class PlanType(Enum):
    FD = 'FD'
    RD = 'RD'

class LoanType(Enum):
    PERSONAL = 'personal'
    HOME = 'home'
    EDUCATION = 'education'
    VEHICLE = 'vehicle'
    GOLD = 'gold'

class LoanStatus(Enum):
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    ACTIVE = 'active'
    CLOSED = 'closed'
    DEFAULTED = 'defaulted'
    REJECTED = 'rejected'

class RegistrationStatus(Enum):
    PENDING_VERIFICATION = 'pending_verification'
    PENDING_KYC = 'pending_kyc'
    APPROVED = 'active'  # Alias for ACTIVE for semantic clarity
    ACTIVE = 'active'
    REJECTED = 'rejected'
    BLOCKED = 'blocked'

@dataclass
class User:
    """User entity for system authentication"""
    user_id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    role: UserRole = UserRole.CUSTOMER
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    registration_status: str = "active"
    registered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class Customer:
    """Customer entity"""
    user_id: Optional[int] = None
    full_name: str = ""
    dob: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    govt_id: Optional[str] = None
    address: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    monthly_income: Optional[Decimal] = None
    risk_profile: Optional[RiskProfile] = None
    kyc_status: str = "not_started"
    kyc_verified_by: Optional[int] = None
    kyc_verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class Account:
    """Account entity"""
    account_id: Optional[int] = None
    user_id: int = 0
    account_number: str = ""
    account_type: AccountType = AccountType.SAVINGS
    opening_date: Optional[date] = None
    balance: Decimal = Decimal('0.00')
    min_balance: Decimal = Decimal('0.00')
    od_limit: Decimal = Decimal('0.00')
    od_interest_rate: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    status: AccountStatus = AccountStatus.ACTIVE
    branch_code: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class Transaction:
    """Transaction entity"""
    txn_id: Optional[int] = None
    account_id: int = 0
    related_account_id: Optional[int] = None
    txn_type: str = ""
    amount: Decimal = Decimal('0.00')
    balance_after_txn: Decimal = Decimal('0.00')
    currency: str = "INR"
    txn_time: Optional[datetime] = None
    reference: Optional[str] = None
    narration: Optional[str] = None
    created_by: Optional[int] = None

@dataclass
class DepositPlan:
    """Deposit plan entity for FD/RD products"""
    plan_id: Optional[int] = None
    plan_type: PlanType = PlanType.FD
    plan_name: str = ""
    tenure_months: int = 0
    interest_rate: Decimal = Decimal('0.00')
    min_amount: Decimal = Decimal('0.00')
    max_amount: Optional[Decimal] = None
    penalty_rate: Optional[Decimal] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

@dataclass
class LoanPlan:
    """Loan plan entity"""
    loan_plan_id: Optional[int] = None
    loan_type: LoanType = LoanType.PERSONAL
    loan_name: str = ""
    interest_rate_annual: Decimal = Decimal('0.00')
    min_amount: Decimal = Decimal('0.00')
    max_amount: Decimal = Decimal('0.00')
    max_tenure_months: int = 0
    processing_fee_rate: Optional[Decimal] = None
    min_credit_score: int = 650
    max_emi_ratio: Decimal = Decimal('50.0')
    is_active: bool = True
    created_at: Optional[datetime] = None

@dataclass
class FDAccount:
    """Fixed Deposit account entity"""
    fd_id: Optional[int] = None
    account_id: int = 0
    plan_id: int = 0
    principal_amount: Decimal = Decimal('0.00')
    interest_rate: Decimal = Decimal('0.00')
    start_date: Optional[date] = None
    maturity_date: Optional[date] = None
    maturity_amount: Optional[Decimal] = None
    payout_mode: str = "on_maturity"
    status: str = "active"
    created_at: Optional[datetime] = None

@dataclass
class RDAccount:
    """Recurring Deposit account entity"""
    rd_id: Optional[int] = None
    account_id: int = 0
    plan_id: int = 0
    installment_amount: Decimal = Decimal('0.00')
    total_installments: int = 0
    paid_installments: int = 0
    interest_rate: Decimal = Decimal('0.00')
    start_date: Optional[date] = None
    maturity_date: Optional[date] = None
    status: str = "active"
    next_due_date: Optional[date] = None
    created_at: Optional[datetime] = None

@dataclass
class Loan:
    """Loan entity"""
    loan_id: Optional[int] = None
    user_id: int = 0
    account_id: int = 0
    loan_plan_id: int = 0
    loan_type: LoanType = LoanType.PERSONAL
    principal_amount: Decimal = Decimal('0.00')
    interest_rate_annual: Decimal = Decimal('0.00')
    tenure_months: int = 0
    emi_amount: Decimal = Decimal('0.00')
    sanction_date: Optional[date] = None
    disbursement_date: Optional[date] = None
    status: LoanStatus = LoanStatus.PENDING_APPROVAL
    total_interest_payable: Optional[Decimal] = None
    remaining_principal: Optional[Decimal] = None
    credit_score_at_sanction: Optional[int] = None
    created_by: Optional[int] = None
    reference: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class CreditScore:
    """Credit score entity"""
    score_id: Optional[int] = None
    user_id: int = 0
    score: int = 0
    reason_summary: Optional[str] = None
    calculated_at: Optional[datetime] = None

@dataclass
class OTPLog:
    """OTP log entity"""
    otp_id: Optional[int] = None
    user_id: int = 0
    otp_code: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_used: bool = False
    used_at: Optional[datetime] = None

@dataclass
class Notification:
    """Notification entity"""
    notification_id: Optional[int] = None
    user_id: Optional[int] = None
    channel: str = "email"  # sms, email
    type: str = ""
    content: str = ""
    status: str = "sent"  # queued, sent, failed
    created_at: Optional[datetime] = None