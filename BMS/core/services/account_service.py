"""
Account Service
Business logic for account management operations
"""

from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from core.repositories.account_repository import AccountRepository
from core.repositories.customer_repository import CustomerRepository
from core.models.entities import Account, AccountType, AccountStatus
from utils.exceptions import (
    ValidationException, AccountNotFoundException, 
    InsufficientFundsException, AccountFrozenException
)
from utils.validators import BankingValidator, BusinessRuleValidator
from utils.helpers import StringUtils, NumberUtils, LoggingUtils
from core.services.audit_service import AuditService

class AccountService:
    """Service class for account management operations"""
    
    def __init__(self):
        self.account_repo = AccountRepository()
        self.customer_repo = CustomerRepository()
    
    def create_account(self, user_id: int, account_type: AccountType, 
                      initial_deposit: Decimal = Decimal('0.00'), 
                      branch_code: str = None) -> Dict[str, Any]:
        """Create a new bank account"""
        try:
            # Validate customer exists
            customer = self.customer_repo.find_customer_by_id(user_id)
            if not customer:
                raise ValidationException(f"Customer {user_id} not found")
            
            # Validate initial deposit
            BankingValidator.validate_amount(initial_deposit, Decimal('0.00'))
            
            # Get account type configuration
            config = self._get_account_type_config(account_type, customer.monthly_income)
            
            # Validate minimum deposit requirement
            if initial_deposit < config['min_balance']:
                raise ValidationException(
                    f"Initial deposit must be at least {config['min_balance']} for {account_type.value} account"
                )
            
            # Generate unique account number
            account_number = StringUtils.generate_account_number(account_type.value[:3].upper())
            
            # Create account entity
            account = Account(
                user_id=user_id,
                account_number=account_number,
                account_type=account_type,
                opening_date=date.today(),
                balance=initial_deposit,
                min_balance=config['min_balance'],
                od_limit=config['od_limit'],
                od_interest_rate=config['od_interest_rate'],
                interest_rate=config['interest_rate'],
                status=AccountStatus.ACTIVE,
                branch_code=branch_code or "MAIN001"
            )
            
            # Save to database
            account_id = self.account_repo.create_account(account)
            
            # Log account creation
            LoggingUtils.log_business_event(
                "account_created",
                "account",
                account_id,
                details={
                    'user_id': user_id,
                    'account_type': account_type.value,
                    'initial_deposit': str(initial_deposit)
                }
            )

            # Log to Audit
            AuditService().log(
                actor_id=user_id, # Or performed_by if we had it
                role='system',
                action='ACCOUNT_CREATE',
                details={'account_id': account_id, 'type': account_type.value}
            )
            
            return {
                'account_id': account_id,
                'account_number': account_number,
                'account_type': account_type.value,
                'balance': initial_deposit,
                'min_balance': config['min_balance'],
                'od_limit': config['od_limit'],
                'interest_rate': config['interest_rate'],
                'status': 'active'
            }
            
        except Exception as e:
            LoggingUtils.log_business_event(
                "account_creation_failed",
                "account",
                0,
                details={'error': str(e), 'user_id': user_id}
            )
            raise

    def initiate_savings_account(self, user_id: int) -> Dict[str, Any]:
        """Automatically create a basic savings account for an approved user"""
        try:
            # 1. Get customer and validate
            customer = self.customer_repo.find_by_user_id(user_id)
            if not customer:
                raise ValidationException(f"No customer profile found for user ID {user_id}")

            # 2. Check for existing accounts (prevent duplicates — check ALL statuses)
            existing_accounts = self.get_customer_accounts(user_id, active_only=False)
            if existing_accounts:
                return {
                    'success': False,
                    'message': 'Account already exists for this user',
                    'accounts': existing_accounts
                }

            # 3. Create unique account number
            import random
            random_part = random.randint(1000, 9999)
            account_number = f"SC-SAV-{user_id:04d}-{random_part}"

            # 4. Create Savings account entity (Balance = 0, Status = ACTIVE)
            config = self._get_account_type_config(AccountType.SAVINGS)
            
            account = Account(
                user_id=user_id,
                account_number=account_number,
                account_type=AccountType.SAVINGS,
                opening_date=date.today(),
                balance=Decimal('0.00'),
                min_balance=config['min_balance'],
                interest_rate=config['interest_rate'],
                status=AccountStatus.ACTIVE,
                branch_code="MAIN001"
            )

            # 5. Save to database
            account_id = self.account_repo.create_account(account)

            LoggingUtils.log_business_event(
                "auto_account_created",
                "account",
                account_id,
                details={'user_id': user_id, 'type': 'savings'}
            )

            # Log to Audit
            AuditService().log(
                actor_id=user_id,
                role='system',
                action='ACCOUNT_AUTO_CREATE',
                details={'account_id': account_id}
            )

            return {
                'success': True,
                'account_id': account_id,
                'account_number': account_number,
                'message': 'Initial Savings account created successfully'
            }

        except Exception as e:
            LoggingUtils.log_business_event(
                "auto_account_creation_failed",
                "account",
                0,
                details={'error': str(e), 'user_id': user_id}
            )
            return {'success': False, 'error': str(e)}

    
    def get_account_details(self, account_id: int) -> Dict[str, Any]:
        """Get comprehensive account details"""
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        customer = self.customer_repo.find_customer_by_id(account.user_id)
        
        return {
            'account_id': account.account_id,
            'account_number': account.account_number,
            'account_type': account.account_type.value,
            'customer_name': customer.full_name if customer else "Unknown",
            'balance': account.balance,
            'available_balance': account.balance + account.od_limit,
            'min_balance': account.min_balance,
            'od_limit': account.od_limit,
            'od_interest_rate': account.od_interest_rate,
            'interest_rate': account.interest_rate,
            'status': account.status.value,
            'opening_date': account.opening_date,
            'branch_code': account.branch_code,
            'created_at': account.created_at
        }
    
    def get_customer_accounts(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get accounts for a customer. By default returns only ACTIVE accounts."""
        if active_only:
            accounts = self.account_repo.get_active_accounts_by_customer(user_id)
        else:
            accounts = self.account_repo.find_by_customer(user_id)
        
        account_list = []
        for account in accounts:
            account_list.append({
                'account_id': account.account_id,
                'account_number': account.account_number,
                'account_type': account.account_type.value,
                'balance': account.balance,
                'available_balance': account.balance + account.od_limit,
                'status': account.status.value,
                'opening_date': account.opening_date
            })
        
        return account_list
    
    def check_balance(self, account_id: int) -> Dict[str, Any]:
        """Check account balance and available funds"""
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        return {
            'account_id': account_id,
            'account_number': account.account_number,
            'current_balance': account.balance,
            'available_balance': account.balance + account.od_limit,
            'min_balance': account.min_balance,
            'od_limit': account.od_limit,
            'balance_status': self._get_balance_status(account)
        }
    
    def validate_sufficient_funds(self, account_id: int, amount: Decimal) -> Dict[str, Any]:
        """Validate if account has sufficient funds for transaction"""
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.status != AccountStatus.ACTIVE:
            raise AccountFrozenException(f"Account {account_id} is {account.status.value}")
        
        available_balance = account.balance + account.od_limit
        sufficient = available_balance >= amount
        
        return {
            'sufficient_funds': sufficient,
            'current_balance': account.balance,
            'available_balance': available_balance,
            'requested_amount': amount,
            'shortfall': max(Decimal('0.00'), amount - available_balance) if not sufficient else Decimal('0.00'),
            'will_use_overdraft': account.balance < amount <= available_balance
        }
    
    def freeze_account(self, account_id: int, reason: str, performed_by: int) -> bool:
        """Freeze an account"""
        from core.repositories.user_repository import UserRepository
        user = UserRepository().find_by_id(performed_by)
        role = str(user.get('role', '')).upper() if user else ''
        if role != 'ADMIN':
            raise ValidationException("Unauthorized: Only Admins can freeze accounts")

        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.status == AccountStatus.FROZEN:
            raise ValidationException("Account is already frozen")
        
        success = self.account_repo.freeze_account(account_id, reason, performed_by)
        
        if success:
            LoggingUtils.log_business_event(
                "account_frozen",
                "account",
                account_id,
                user_id=performed_by,
                details={'reason': reason}
            )
            
            # Log to Audit
            AuditService().log(
                actor_id=performed_by,
                role='admin',
                action='ACCOUNT_FREEZE',
                details={'account_id': account_id, 'reason': reason}
            )
        
        return success
    
    def unfreeze_account(self, account_id: int, reason: str, performed_by: int) -> bool:
        """Unfreeze an account"""
        from core.repositories.user_repository import UserRepository
        user = UserRepository().find_by_id(performed_by)
        role = str(user.get('role', '')).upper() if user else ''
        if role != 'ADMIN':
            raise ValidationException("Unauthorized: Only Admins can unfreeze accounts")

        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.status != AccountStatus.FROZEN:
            raise ValidationException("Account is not frozen")
        
        success = self.account_repo.unfreeze_account(account_id, reason, performed_by)
        
        if success:
            LoggingUtils.log_business_event(
                "account_unfrozen",
                "account",
                account_id,
                user_id=performed_by,
                details={'reason': reason}
            )
            
            # Log to Audit
            AuditService().log(
                actor_id=performed_by,
                role='admin',
                action='ACCOUNT_UNFREEZE',
                details={'account_id': account_id, 'reason': reason}
            )
        
        return success
    
    def close_account(self, account_id: int, performed_by: int) -> Dict[str, Any]:
        """Close an account"""
        from core.repositories.user_repository import UserRepository
        user = UserRepository().find_by_id(performed_by)
        role = str(user.get('role', '')).upper() if user else ''
        if role != 'ADMIN':
            raise ValidationException("Unauthorized: Only Admins can close accounts")

        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.status == AccountStatus.CLOSED:
            raise ValidationException("Account is already closed")
        
        # Check if account has balance
        if account.balance != Decimal('0.00'):
            raise ValidationException("Cannot close account with non-zero balance")
        
        # TODO: Check for pending transactions, active loans, etc.
        
        success = self.account_repo.close_account(account_id)
        
        if success:
            LoggingUtils.log_business_event(
                "account_closed",
                "account",
                account_id,
                user_id=performed_by,
                details={'final_balance': str(account.balance)}
            )

            # Log to Audit
            AuditService().log(
                actor_id=performed_by,
                role='admin',
                action='ACCOUNT_CLOSE',
                details={'account_id': account_id, 'final_balance': str(account.balance)}
            )
        
        return {
            'account_id': account_id,
            'account_number': account.account_number,
            'closed': success,
            'final_balance': account.balance
        }
    
    def apply_low_balance_penalty(self, account_id: int) -> Dict[str, Any]:
        """Apply penalty for low balance"""
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.balance >= account.min_balance:
            return {'penalty_applied': False, 'reason': 'Balance above minimum'}
        
        # Calculate penalty based on account type
        penalty_amount = self._calculate_low_balance_penalty(account)
        
        if penalty_amount > Decimal('0.00'):
            new_balance = account.balance - penalty_amount
            self.account_repo.update_balance(account_id, new_balance)
            
            LoggingUtils.log_business_event(
                "low_balance_penalty_applied",
                "account",
                account_id,
                details={
                    'penalty_amount': str(penalty_amount),
                    'old_balance': str(account.balance),
                    'new_balance': str(new_balance)
                }
            )
            
            return {
                'penalty_applied': True,
                'penalty_amount': penalty_amount,
                'old_balance': account.balance,
                'new_balance': new_balance
            }
        
        return {'penalty_applied': False, 'reason': 'No penalty applicable'}
    
    def get_low_balance_accounts(self) -> List[Dict[str, Any]]:
        """Get accounts with balance below minimum"""
        accounts = self.account_repo.get_low_balance_accounts()
        
        low_balance_accounts = []
        for account in accounts:
            customer = self.customer_repo.find_customer_by_id(account.user_id)
            
            low_balance_accounts.append({
                'account_id': account.account_id,
                'account_number': account.account_number,
                'customer_name': customer.full_name if customer else "Unknown",
                'account_type': account.account_type.value,
                'current_balance': account.balance,
                'min_balance': account.min_balance,
                'shortfall': account.min_balance - account.balance,
                'days_below_minimum': self._calculate_days_below_minimum(account)
            })
        
        return low_balance_accounts
    
    def _get_account_type_config(self, account_type: AccountType, monthly_income: Decimal = None) -> Dict[str, Any]:
        """Get configuration for account type"""
        configs = {
            AccountType.SAVINGS: {
                'min_balance': Decimal('500.00'),
                'od_limit': Decimal('0.00'),
                'od_interest_rate': None,
                'interest_rate': Decimal('4.0')
            },
            AccountType.CURRENT: {
                'min_balance': Decimal('1000.00'),
                'od_limit': BusinessRuleValidator.validate_overdraft_limit('current', monthly_income),
                'od_interest_rate': Decimal('12.0'),
                'interest_rate': Decimal('0.0')
            },
            AccountType.SALARY: {
                'min_balance': Decimal('0.00'),
                'od_limit': Decimal('0.00'),
                'od_interest_rate': None,
                'interest_rate': Decimal('3.5')
            }
        }
        
        return configs.get(account_type, configs[AccountType.SAVINGS])
    
    def _get_balance_status(self, account: Account) -> str:
        """Get balance status description"""
        if account.balance < Decimal('0.00'):
            return "Overdrawn"
        elif account.balance < account.min_balance:
            return "Below Minimum"
        elif account.balance >= account.min_balance * 10:
            return "High Balance"
        else:
            return "Normal"
    
    def _calculate_low_balance_penalty(self, account: Account) -> Decimal:
        """Calculate penalty for low balance"""
        penalty_rates = {
            AccountType.SAVINGS: Decimal('50.00'),  # Flat penalty
            AccountType.CURRENT: Decimal('100.00'),
            AccountType.SALARY: Decimal('0.00')  # No penalty for salary accounts
        }
        
        return penalty_rates.get(account.account_type, Decimal('50.00'))
    
    def _calculate_days_below_minimum(self, account: Account) -> int:
        """Calculate days account has been below minimum balance"""
        # This would require transaction history analysis
        # For now, return a placeholder
        return 0