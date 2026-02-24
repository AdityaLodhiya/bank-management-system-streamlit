"""
Account Repository
Handles database operations for accounts table
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

from core.repositories.base_repository import BaseRepository
from core.models.entities import Account, AccountType, AccountStatus
from utils.exceptions import AccountNotFoundException, ValidationException, InsufficientFundsException

class AccountRepository(BaseRepository):
    """Repository for accounts table operations"""
    
    def __init__(self):
        super().__init__('accounts', 'account_id')
    
    def create_account(self, account: Account) -> int:
        """Create a new account"""
        if not account.user_id or not account.account_number:
            raise ValidationException("User ID and account number are required")
        
        account_data = {
            'user_id': account.user_id,
            'account_number': account.account_number,
            'account_type': account.account_type.value if isinstance(account.account_type, AccountType) else account.account_type,
            'opening_date': account.opening_date,
            'balance': account.balance,
            'min_balance': account.min_balance,
            'od_limit': account.od_limit,
            'od_interest_rate': account.od_interest_rate,
            'interest_rate': account.interest_rate,
            'status': account.status.value if isinstance(account.status, AccountStatus) else account.status,
            'branch_code': account.branch_code
        }
        
        return self.create(account_data)
    
    def find_account_by_id(self, account_id: int) -> Optional[Account]:
        """Find account by ID"""
        account_data = self.find_by_id(account_id)
        if not account_data:
            return None
        
        return self._dict_to_account(account_data)
    
    def find_by_account_number(self, account_number: str) -> Optional[Account]:
        """Find account by account number"""
        if not account_number:
            return None
        
        accounts = self.find_by_field('account_number', account_number)
        if not accounts:
            return None
        
        return self._dict_to_account(accounts[0])
    
    def find_by_customer(self, user_id: int) -> List[Account]:
        """Find all accounts for a customer"""
        accounts_data = self.find_by_field('user_id', user_id)
        return [self._dict_to_account(account_data) for account_data in accounts_data]
    
    def get_active_accounts_by_customer(self, user_id: int) -> List[Account]:
        """Get active accounts for a customer"""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE user_id = %s AND status = 'active'"
            results = self.db.execute_query(query, (user_id,), fetch_all=True)
            return [self._dict_to_account(account_data) for account_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting active accounts: {str(e)}")
    
    def update_balance(self, account_id: int, new_balance: Decimal) -> bool:
        """Update account balance"""
        return self.update(account_id, {'balance': new_balance})
    
    def get_account_balance(self, account_id: int) -> Decimal:
        """Get current account balance"""
        account_data = self.find_by_id(account_id)
        if not account_data:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        return account_data['balance']
    
    def freeze_account(self, account_id: int, reason: str, performed_by: int) -> bool:
        """Freeze an account"""
        # Update account status
        success = self.update(account_id, {'status': 'frozen'})
        
        if success:
            # Log the freeze action
            self._log_freeze_action(account_id, 'freeze', reason, performed_by)
        
        return success
    
    def unfreeze_account(self, account_id: int, reason: str, performed_by: int) -> bool:
        """Unfreeze an account"""
        # Update account status
        success = self.update(account_id, {'status': 'active'})
        
        if success:
            # Log the unfreeze action
            self._log_freeze_action(account_id, 'unfreeze', reason, performed_by)
        
        return success
    
    def close_account(self, account_id: int) -> bool:
        """Close an account"""
        return self.update(account_id, {'status': 'closed'})
    
    def validate_sufficient_funds(self, account_id: int, amount: Decimal) -> bool:
        """Validate if account has sufficient funds including overdraft"""
        account = self.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        if account.status != AccountStatus.ACTIVE:
            raise ValidationException(f"Account {account_id} is not active")
        
        available_balance = account.balance + account.od_limit
        return available_balance >= amount
    
    def get_available_balance(self, account_id: int) -> Decimal:
        """Get available balance including overdraft limit"""
        account = self.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        return account.balance + account.od_limit
    
    def is_account_active(self, account_id: int) -> bool:
        """Check if account is active"""
        account = self.find_account_by_id(account_id)
        return account and account.status == AccountStatus.ACTIVE
    
    def get_accounts_by_type(self, account_type: AccountType) -> List[Account]:
        """Get accounts by type"""
        accounts_data = self.find_by_field('account_type', account_type.value)
        return [self._dict_to_account(account_data) for account_data in accounts_data]
    
    def get_low_balance_accounts(self, threshold: Decimal = None) -> List[Account]:
        """Get accounts with balance below minimum or specified threshold"""
        try:
            if threshold:
                query = f"SELECT * FROM {self.table_name} WHERE balance < %s AND status = 'active'"
                params = (threshold,)
            else:
                query = f"SELECT * FROM {self.table_name} WHERE balance < min_balance AND status = 'active'"
                params = ()
            
            results = self.db.execute_query(query, params, fetch_all=True)
            return [self._dict_to_account(account_data) for account_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting low balance accounts: {str(e)}")
    
    def get_account_summary(self, account_id: int) -> Dict[str, Any]:
        """Get comprehensive account summary"""
        account = self.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        return {
            'account_id': account.account_id,
            'account_number': account.account_number,
            'account_type': account.account_type.value,
            'balance': account.balance,
            'available_balance': account.balance + account.od_limit,
            'min_balance': account.min_balance,
            'od_limit': account.od_limit,
            'status': account.status.value,
            'opening_date': account.opening_date,
            'branch_code': account.branch_code
        }
    
    def _log_freeze_action(self, account_id: int, action: str, reason: str, performed_by: int):
        """Log account freeze/unfreeze action"""
        try:
            query = """
                INSERT INTO account_freeze_log (account_id, action, reason, performed_by)
                VALUES (%s, %s, %s, %s)
            """
            self.db.execute_query(query, (account_id, action, reason, performed_by))
        except Exception as e:
            # Log error but don't fail the main operation
            import logging
            logging.error(f"Failed to log freeze action: {e}")
    
    def _dict_to_account(self, account_data: dict) -> Account:
        """Convert dictionary to Account object"""
        return Account(
            account_id=account_data['account_id'],
            user_id=account_data['user_id'],
            account_number=account_data['account_number'],
            account_type=AccountType(account_data['account_type'].lower()),
            opening_date=account_data.get('opening_date'),
            balance=account_data['balance'],
            min_balance=account_data['min_balance'],
            od_limit=account_data['od_limit'],
            od_interest_rate=account_data.get('od_interest_rate'),
            interest_rate=account_data.get('interest_rate'),
            status=AccountStatus(account_data['status'].lower()),
            branch_code=account_data.get('branch_code'),
            created_at=account_data.get('created_at')
        )