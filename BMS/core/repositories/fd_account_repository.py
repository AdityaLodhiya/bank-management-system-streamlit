"""
Fixed Deposit Account Repository
Handles database operations for fd_accounts table
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date

from core.repositories.base_repository import BaseRepository
from core.models.entities import FDAccount
from utils.exceptions import ValidationException

class FDAccountRepository(BaseRepository):
    """Repository for fd_accounts table operations"""
    
    def __init__(self):
        super().__init__('fd_accounts', 'fd_id')
    
    def create_fd_account(self, fd_account: FDAccount) -> int:
        """Create a new FD account"""
        if not fd_account.account_id or fd_account.plan_id is None or fd_account.principal_amount <= 0:
            raise ValidationException("Account ID, Plan ID, and positive principal amount are required")
        
        fd_data = {
            'account_id': fd_account.account_id,
            'plan_id': fd_account.plan_id,
            'principal_amount': fd_account.principal_amount,
            'interest_rate': fd_account.interest_rate,
            'start_date': fd_account.start_date or date.today(),
            'maturity_date': fd_account.maturity_date,
            'maturity_amount': fd_account.maturity_amount,
            'payout_mode': fd_account.payout_mode,
            'status': fd_account.status
        }
        
        return self.create(fd_data)
    
    def find_fd_by_id(self, fd_id: int) -> Optional[FDAccount]:
        """Find FD account by ID"""
        fd_data = self.find_by_id(fd_id)
        if not fd_data:
            return None
        
        return self._dict_to_fd_account(fd_data)
    
    def find_by_account(self, account_id: int) -> List[FDAccount]:
        """Find all FD accounts for a customer account"""
        fd_accounts_data = self.find_by_field('account_id', account_id)
        return [self._dict_to_fd_account(fd_data) for fd_data in fd_accounts_data]

    def find_by_user(self, user_id: int) -> List[FDAccount]:
        """Find all FD accounts belonging to a user (via accounts JOIN)"""
        try:
            query = f"""
                SELECT f.* FROM {self.table_name} f
                JOIN accounts a ON f.account_id = a.account_id
                WHERE a.user_id = %s
                ORDER BY f.start_date DESC
            """
            results = self.db.execute_query(query, (user_id,), fetch_all=True)
            return [self._dict_to_fd_account(r) for r in results or []]
        except Exception as e:
            raise ValidationException(f"Error fetching FDs for user: {str(e)}")

    def get_all_fds(self) -> List[FDAccount]:
        """Get ALL FD accounts in the system (admin use only)"""
        try:
            query = f"SELECT * FROM {self.table_name} ORDER BY start_date DESC"
            results = self.db.execute_query(query, fetch_all=True)
            return [self._dict_to_fd_account(r) for r in results or []]
        except Exception as e:
            raise ValidationException(f"Error fetching all FDs: {str(e)}")

    def get_active_fds(self, account_id: int = None) -> List[FDAccount]:
        """Get active FD accounts, optionally filtered by account"""
        try:
            if account_id:
                query = f"SELECT * FROM {self.table_name} WHERE account_id = %s AND status = 'active' ORDER BY start_date DESC"
                results = self.db.execute_query(query, (account_id,), fetch_all=True)
            else:
                query = f"SELECT * FROM {self.table_name} WHERE status = 'active' ORDER BY start_date DESC"
                results = self.db.execute_query(query, fetch_all=True)

            return [self._dict_to_fd_account(fd_data) for fd_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting active FDs: {str(e)}")

    
    def get_maturing_fds(self, days_ahead: int = 30) -> List[FDAccount]:
        """Get FDs maturing within specified days"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE status = 'active' 
                AND maturity_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
                ORDER BY maturity_date ASC
            """
            results = self.db.execute_query(query, (days_ahead,), fetch_all=True)
            return [self._dict_to_fd_account(fd_data) for fd_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting maturing FDs: {str(e)}")
    
    def get_matured_fds(self) -> List[FDAccount]:
        """Get FDs that have already matured but not closed"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE status = 'active' 
                AND maturity_date <= CURDATE()
                ORDER BY maturity_date ASC
            """
            results = self.db.execute_query(query, fetch_all=True)
            return [self._dict_to_fd_account(fd_data) for fd_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting matured FDs: {str(e)}")
    
    def calculate_maturity_amount(self, fd_id: int) -> Decimal:
        """Calculate maturity amount for an FD"""
        fd = self.find_fd_by_id(fd_id)
        if not fd:
            raise ValidationException(f"FD {fd_id} not found")
        
        # Calculate compound interest
        # A = P(1 + r/n)^(nt) where n=1 for annual compounding
        principal = fd.principal_amount
        rate = fd.interest_rate / 100  # Convert percentage to decimal
        
        # Calculate tenure in years
        tenure_days = (fd.maturity_date - fd.start_date).days
        tenure_years = tenure_days / 365.25
        
        maturity_amount = principal * ((1 + rate) ** tenure_years)
        return maturity_amount.quantize(Decimal('0.01'))
    
    def update_maturity_amount(self, fd_id: int, maturity_amount: Decimal) -> bool:
        """Update maturity amount for an FD"""
        return self.update(fd_id, {'maturity_amount': maturity_amount})
    
    def close_fd(self, fd_id: int, closure_type: str = 'matured') -> bool:
        """Close an FD account"""
        valid_statuses = ['closed', 'premature_closed']
        status = 'premature_closed' if closure_type == 'premature' else 'closed'
        
        if status not in valid_statuses:
            raise ValidationException(f"Invalid closure status: {status}")
        
        return self.update(fd_id, {'status': status})
    
    def premature_close_fd(self, fd_id: int) -> Dict[str, Any]:
        """Handle premature closure of FD with penalty calculation"""
        fd = self.find_fd_by_id(fd_id)
        if not fd:
            raise ValidationException(f"FD {fd_id} not found")
        
        if fd.status != 'active':
            raise ValidationException(f"FD {fd_id} is not active")
        
        # Calculate premature closure amount (with penalty)
        days_completed = (date.today() - fd.start_date).days
        total_days = (fd.maturity_date - fd.start_date).days
        
        if days_completed < 90:  # Minimum 90 days for any interest
            closure_amount = fd.principal_amount
            penalty_amount = Decimal('0.00')
        else:
            # Calculate proportional interest with penalty
            proportional_rate = fd.interest_rate * 0.75  # 25% penalty
            tenure_years = days_completed / 365.25
            
            closure_amount = fd.principal_amount * ((1 + (proportional_rate / 100)) ** tenure_years)
            penalty_amount = (fd.maturity_amount or self.calculate_maturity_amount(fd_id)) - closure_amount
        
        # Update status
        self.close_fd(fd_id, 'premature')
        
        return {
            'fd_id': fd_id,
            'principal_amount': fd.principal_amount,
            'closure_amount': closure_amount.quantize(Decimal('0.01')),
            'penalty_amount': penalty_amount.quantize(Decimal('0.01')),
            'days_completed': days_completed,
            'total_days': total_days
        }
    
    def get_fd_summary(self, account_id: int) -> Dict[str, Any]:
        """Get FD summary for an account"""
        try:
            query = f"""
                SELECT 
                    COUNT(*) as total_fds,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_fds,
                    SUM(CASE WHEN status = 'active' THEN principal_amount ELSE 0 END) as total_invested,
                    SUM(CASE WHEN status = 'active' THEN maturity_amount ELSE 0 END) as total_maturity_value,
                    AVG(CASE WHEN status = 'active' THEN interest_rate ELSE NULL END) as avg_interest_rate
                FROM {self.table_name} 
                WHERE account_id = %s
            """
            result = self.db.execute_query(query, (account_id,), fetch_one=True)
            
            return {
                'total_fds': result['total_fds'] or 0,
                'active_fds': result['active_fds'] or 0,
                'total_invested': result['total_invested'] or Decimal('0.00'),
                'total_maturity_value': result['total_maturity_value'] or Decimal('0.00'),
                'avg_interest_rate': result['avg_interest_rate'] or Decimal('0.00'),
                'expected_returns': (result['total_maturity_value'] or Decimal('0.00')) - (result['total_invested'] or Decimal('0.00'))
            }
        except Exception as e:
            raise ValidationException(f"Error getting FD summary: {str(e)}")
    
    def _dict_to_fd_account(self, fd_data: dict) -> FDAccount:
        """Convert dictionary to FDAccount object"""
        return FDAccount(
            fd_id=fd_data['fd_id'],
            account_id=fd_data['account_id'],
            plan_id=fd_data['plan_id'],
            principal_amount=fd_data['principal_amount'],
            interest_rate=fd_data['interest_rate'],
            start_date=fd_data.get('start_date'),
            maturity_date=fd_data.get('maturity_date'),
            maturity_amount=fd_data.get('maturity_amount'),
            payout_mode=fd_data.get('payout_mode', 'on_maturity'),
            status=fd_data.get('status', 'active'),
            created_at=fd_data.get('created_at')
        )