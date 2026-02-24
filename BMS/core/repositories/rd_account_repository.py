"""
Recurring Deposit Account Repository
Handles database operations for rd_accounts and rd_installments tables
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from core.repositories.base_repository import BaseRepository
from core.models.entities import RDAccount
from utils.exceptions import ValidationException

class RDAccountRepository(BaseRepository):
    """Repository for rd_accounts table operations"""
    
    def __init__(self):
        super().__init__('rd_accounts', 'rd_id')
    
    def create_rd_account(self, rd_account: RDAccount) -> int:
        """Create a new RD account"""
        if not rd_account.account_id or not rd_account.plan_id or rd_account.installment_amount <= 0:
            raise ValidationException("Account ID, Plan ID, and positive installment amount are required")
        
        rd_data = {
            'account_id': rd_account.account_id,
            'plan_id': rd_account.plan_id,
            'installment_amount': rd_account.installment_amount,
            'total_installments': rd_account.total_installments,
            'paid_installments': rd_account.paid_installments,
            'interest_rate': rd_account.interest_rate,
            'start_date': rd_account.start_date or date.today(),
            'maturity_date': rd_account.maturity_date,
            'status': rd_account.status,
            'next_due_date': rd_account.next_due_date
        }
        
        rd_id = self.create(rd_data)
        
        # Create installment schedule
        if rd_id:
            self._create_installment_schedule(rd_id, rd_account)
        
        return rd_id
    
    def find_rd_by_id(self, rd_id: int) -> Optional[RDAccount]:
        """Find RD account by ID"""
        rd_data = self.find_by_id(rd_id)
        if not rd_data:
            return None
        
        return self._dict_to_rd_account(rd_data)
    
    def find_by_account(self, account_id: int) -> List[RDAccount]:
        """Find all RD accounts for a customer account"""
        rd_accounts_data = self.find_by_field('account_id', account_id)
        return [self._dict_to_rd_account(rd_data) for rd_data in rd_accounts_data]

    def find_by_user(self, user_id: int) -> List[RDAccount]:
        """Find all RD accounts belonging to a user (via accounts JOIN)"""
        try:
            query = f"""
                SELECT r.* FROM {self.table_name} r
                JOIN accounts a ON r.account_id = a.account_id
                WHERE a.user_id = %s
                ORDER BY r.start_date DESC
            """
            results = self.db.execute_query(query, (user_id,), fetch_all=True)
            return [self._dict_to_rd_account(r) for r in results or []]
        except Exception as e:
            raise ValidationException(f"Error fetching RDs for user: {str(e)}")

    def get_all_rds(self) -> List[RDAccount]:
        """Get ALL RD accounts in the system (admin use only)"""
        try:
            query = f"SELECT * FROM {self.table_name} ORDER BY start_date DESC"
            results = self.db.execute_query(query, fetch_all=True)
            return [self._dict_to_rd_account(r) for r in results or []]
        except Exception as e:
            raise ValidationException(f"Error fetching all RDs: {str(e)}")

    def get_active_rds(self, account_id: int = None) -> List[RDAccount]:
        """Get active RD accounts, optionally filtered by account"""
        try:
            if account_id:
                query = f"SELECT * FROM {self.table_name} WHERE account_id = %s AND status = 'active' ORDER BY start_date DESC"
                results = self.db.execute_query(query, (account_id,), fetch_all=True)
            else:
                query = f"SELECT * FROM {self.table_name} WHERE status = 'active' ORDER BY start_date DESC"
                results = self.db.execute_query(query, fetch_all=True)

            return [self._dict_to_rd_account(rd_data) for rd_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting active RDs: {str(e)}")

    
    def get_due_installments(self, rd_id: int = None) -> List[Dict[str, Any]]:
        """Get due installments for RD(s)"""
        try:
            if rd_id:
                query = """
                    SELECT ri.*, ra.account_id, ra.installment_amount
                    FROM rd_installments ri
                    JOIN rd_accounts ra ON ri.rd_id = ra.rd_id
                    WHERE ri.rd_id = %s AND ri.status = 'due' AND ri.due_date <= CURDATE()
                    ORDER BY ri.due_date ASC
                """
                results = self.db.execute_query(query, (rd_id,), fetch_all=True)
            else:
                query = """
                    SELECT ri.*, ra.account_id, ra.installment_amount
                    FROM rd_installments ri
                    JOIN rd_accounts ra ON ri.rd_id = ra.rd_id
                    WHERE ri.status = 'due' AND ri.due_date <= CURDATE()
                    ORDER BY ri.due_date ASC
                """
                results = self.db.execute_query(query, fetch_all=True)
            
            return results or []
        except Exception as e:
            raise ValidationException(f"Error getting due installments: {str(e)}")
    
    def pay_installment(self, rd_id: int, installment_number: int, payment_date: date = None) -> bool:
        """Mark an installment as paid"""
        try:
            payment_date = payment_date or date.today()
            
            # Update installment status
            query = """
                UPDATE rd_installments 
                SET status = 'paid', paid_date = %s 
                WHERE rd_id = %s AND installment_number = %s
            """
            self.db.execute_query(query, (payment_date, rd_id, installment_number))
            
            # Update RD account paid installments count
            query = """
                UPDATE rd_accounts 
                SET paid_installments = paid_installments + 1,
                    next_due_date = (
                        SELECT MIN(due_date) FROM rd_installments 
                        WHERE rd_id = %s AND status = 'due'
                    )
                WHERE rd_id = %s
            """
            self.db.execute_query(query, (rd_id, rd_id))
            
            return True
        except Exception as e:
            raise ValidationException(f"Error paying installment: {str(e)}")
    
    def mark_installment_missed(self, rd_id: int, installment_number: int, penalty_amount: Decimal = None) -> bool:
        """Mark an installment as missed and apply penalty"""
        try:
            penalty_amount = penalty_amount or Decimal('0.00')
            
            # Update installment status
            query = """
                UPDATE rd_installments 
                SET status = 'missed', penalty_amount = %s 
                WHERE rd_id = %s AND installment_number = %s
            """
            self.db.execute_query(query, (penalty_amount, rd_id, installment_number))
            
            # Update next due date
            query = """
                UPDATE rd_accounts 
                SET next_due_date = (
                    SELECT MIN(due_date) FROM rd_installments 
                    WHERE rd_id = %s AND status = 'due'
                )
                WHERE rd_id = %s
            """
            self.db.execute_query(query, (rd_id, rd_id))
            
            return True
        except Exception as e:
            raise ValidationException(f"Error marking installment missed: {str(e)}")
    
    def get_installment_history(self, rd_id: int) -> List[Dict[str, Any]]:
        """Get installment history for an RD"""
        try:
            query = """
                SELECT * FROM rd_installments 
                WHERE rd_id = %s 
                ORDER BY installment_number ASC
            """
            results = self.db.execute_query(query, (rd_id,), fetch_all=True)
            return results or []
        except Exception as e:
            raise ValidationException(f"Error getting installment history: {str(e)}")
    
    def calculate_maturity_amount(self, rd_id: int) -> Decimal:
        """Calculate maturity amount for RD using compound interest"""
        rd = self.find_rd_by_id(rd_id)
        if not rd:
            raise ValidationException(f"RD {rd_id} not found")
        
        # RD maturity calculation: Sum of compound interest for each installment
        monthly_amount = rd.installment_amount
        annual_rate = rd.interest_rate / 100
        monthly_rate = annual_rate / 12
        total_months = rd.total_installments
        
        maturity_amount = Decimal('0.00')
        
        # Each installment earns interest for different periods
        for month in range(1, total_months + 1):
            months_earning_interest = total_months - month + 1
            installment_maturity = monthly_amount * ((1 + monthly_rate) ** months_earning_interest)
            maturity_amount += installment_maturity
        
        return maturity_amount.quantize(Decimal('0.01'))
    
    def close_rd(self, rd_id: int, closure_type: str = 'matured') -> Dict[str, Any]:
        """Close an RD account"""
        rd = self.find_rd_by_id(rd_id)
        if not rd:
            raise ValidationException(f"RD {rd_id} not found")
        
        # Calculate closure amount
        paid_installments = rd.paid_installments
        total_deposited = rd.installment_amount * paid_installments
        
        if closure_type == 'premature':
            # Premature closure with penalty
            if paid_installments < 6:  # Minimum 6 months
                closure_amount = total_deposited  # No interest
            else:
                # Reduced interest rate for premature closure
                reduced_rate = rd.interest_rate * 0.75  # 25% penalty
                maturity_amount = self._calculate_partial_maturity(rd, paid_installments, reduced_rate)
                closure_amount = maturity_amount
            
            status = 'closed'
        else:
            # Normal maturity
            closure_amount = self.calculate_maturity_amount(rd_id)
            status = 'closed'
        
        # Update RD status
        self.update(rd_id, {'status': status})
        
        return {
            'rd_id': rd_id,
            'total_deposited': total_deposited,
            'closure_amount': closure_amount,
            'interest_earned': closure_amount - total_deposited,
            'paid_installments': paid_installments,
            'total_installments': rd.total_installments,
            'closure_type': closure_type
        }
    
    def get_rd_summary(self, account_id: int) -> Dict[str, Any]:
        """Get RD summary for an account"""
        try:
            query = f"""
                SELECT 
                    COUNT(*) as total_rds,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_rds,
                    SUM(CASE WHEN status = 'active' THEN installment_amount * paid_installments ELSE 0 END) as total_deposited,
                    AVG(CASE WHEN status = 'active' THEN interest_rate ELSE NULL END) as avg_interest_rate
                FROM {self.table_name} 
                WHERE account_id = %s
            """
            result = self.db.execute_query(query, (account_id,), fetch_one=True)
            
            return {
                'total_rds': result['total_rds'] or 0,
                'active_rds': result['active_rds'] or 0,
                'total_deposited': result['total_deposited'] or Decimal('0.00'),
                'avg_interest_rate': result['avg_interest_rate'] or Decimal('0.00')
            }
        except Exception as e:
            raise ValidationException(f"Error getting RD summary: {str(e)}")
    
    def _create_installment_schedule(self, rd_id: int, rd_account: RDAccount):
        """Create installment schedule for RD"""
        try:
            installments = []
            current_date = rd_account.start_date or date.today()
            
            for i in range(1, rd_account.total_installments + 1):
                due_date = current_date + relativedelta(months=i-1)
                installments.append((
                    rd_id,
                    i,
                    due_date,
                    rd_account.installment_amount
                ))
            
            query = """
                INSERT INTO rd_installments (rd_id, installment_number, due_date, amount)
                VALUES (%s, %s, %s, %s)
            """
            self.db.execute_many(query, installments)
            
        except Exception as e:
            raise ValidationException(f"Error creating installment schedule: {str(e)}")
    
    def _calculate_partial_maturity(self, rd: RDAccount, paid_installments: int, interest_rate: Decimal) -> Decimal:
        """Calculate maturity amount for partial RD closure"""
        monthly_amount = rd.installment_amount
        annual_rate = interest_rate / 100
        monthly_rate = annual_rate / 12
        
        maturity_amount = Decimal('0.00')
        
        for month in range(1, paid_installments + 1):
            months_earning_interest = paid_installments - month + 1
            installment_maturity = monthly_amount * ((1 + monthly_rate) ** months_earning_interest)
            maturity_amount += installment_maturity
        
        return maturity_amount.quantize(Decimal('0.01'))
    
    def _dict_to_rd_account(self, rd_data: dict) -> RDAccount:
        """Convert dictionary to RDAccount object"""
        return RDAccount(
            rd_id=rd_data['rd_id'],
            account_id=rd_data['account_id'],
            plan_id=rd_data['plan_id'],
            installment_amount=rd_data['installment_amount'],
            total_installments=rd_data['total_installments'],
            paid_installments=rd_data['paid_installments'],
            interest_rate=rd_data['interest_rate'],
            start_date=rd_data.get('start_date'),
            maturity_date=rd_data.get('maturity_date'),
            status=rd_data.get('status', 'active'),
            next_due_date=rd_data.get('next_due_date'),
            created_at=rd_data.get('created_at')
        )