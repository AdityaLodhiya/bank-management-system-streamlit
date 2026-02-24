"""
Transaction Repository
Handles database operations for transactions table
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date

from core.repositories.base_repository import BaseRepository
from core.models.entities import Transaction
from utils.exceptions import ValidationException, AccountNotFoundException

class TransactionRepository(BaseRepository):
    """Repository for transactions table operations"""
    
    def __init__(self):
        super().__init__('transactions', 'txn_id')
    
    def create_transaction(self, transaction: Transaction) -> int:
        """Create a new transaction"""
        if not transaction.account_id or transaction.amount <= 0:
            raise ValidationException("Account ID and positive amount are required")
        
        transaction_data = {
            'account_id': transaction.account_id,
            'related_account_id': transaction.related_account_id,
            'txn_type': transaction.txn_type,
            'amount': transaction.amount,
            'balance_after_txn': transaction.balance_after_txn,
            'currency': transaction.currency,
            'txn_time': transaction.txn_time or datetime.now(),
            'reference': transaction.reference,
            'narration': transaction.narration,
            'created_by': transaction.created_by
        }
        
        return self.create(transaction_data)
    
    def find_transaction_by_id(self, txn_id: int) -> Optional[Transaction]:
        """Find transaction by ID"""
        txn_data = self.find_by_id(txn_id)
        if not txn_data:
            return None
        
        return self._dict_to_transaction(txn_data)
    
    def find_by_account(self, account_id: int, limit: int = 50, offset: int = 0) -> List[Transaction]:
        """Find transactions by account with pagination"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE account_id = %s 
                ORDER BY txn_time DESC 
                LIMIT %s OFFSET %s
            """
            results = self.db.execute_query(query, (account_id, limit, offset), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error finding transactions by account: {str(e)}")
    
    def find_by_date_range(self, account_id: int, start_date: date, end_date: date) -> List[Transaction]:
        """Find transactions by account and date range"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE account_id = %s 
                AND DATE(txn_time) BETWEEN %s AND %s 
                ORDER BY txn_time DESC
            """
            results = self.db.execute_query(query, (account_id, start_date, end_date), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error finding transactions by date range: {str(e)}")
    
    def find_by_type(self, account_id: int, txn_type: str) -> List[Transaction]:
        """Find transactions by account and type"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE account_id = %s AND txn_type = %s 
                ORDER BY txn_time DESC
            """
            results = self.db.execute_query(query, (account_id, txn_type), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error finding transactions by type: {str(e)}")
    
    def find_by_reference(self, reference: str) -> Optional[Transaction]:
        """Find transaction by reference number"""
        if not reference:
            return None
        
        transactions = self.find_by_field('reference', reference)
        if not transactions:
            return None
        
        return self._dict_to_transaction(transactions[0])
    
    def get_account_balance_after_transaction(self, account_id: int) -> Decimal:
        """Get the latest balance after transaction for an account"""
        try:
            query = f"""
                SELECT balance_after_txn FROM {self.table_name} 
                WHERE account_id = %s 
                ORDER BY txn_time DESC 
                LIMIT 1
            """
            result = self.db.execute_query(query, (account_id,), fetch_one=True)
            return result['balance_after_txn'] if result else Decimal('0.00')
        except Exception as e:
            raise ValidationException(f"Error getting balance after transaction: {str(e)}")
    
    def get_transaction_summary(self, account_id: int, days: int = 30) -> Dict[str, Any]:
        """Get transaction summary for an account"""
        try:
            query = f"""
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN txn_type LIKE '%deposit%' OR txn_type LIKE '%credit%' THEN amount ELSE 0 END) as total_credits,
                    SUM(CASE WHEN txn_type LIKE '%withdraw%' OR txn_type LIKE '%debit%' THEN amount ELSE 0 END) as total_debits,
                    AVG(amount) as avg_amount
                FROM {self.table_name} 
                WHERE account_id = %s 
                AND txn_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            result = self.db.execute_query(query, (account_id, days), fetch_one=True)
            
            return {
                'total_transactions': result['total_transactions'] or 0,
                'total_credits': result['total_credits'] or Decimal('0.00'),
                'total_debits': result['total_debits'] or Decimal('0.00'),
                'avg_amount': result['avg_amount'] or Decimal('0.00'),
                'net_amount': (result['total_credits'] or Decimal('0.00')) - (result['total_debits'] or Decimal('0.00'))
            }
        except Exception as e:
            raise ValidationException(f"Error getting transaction summary: {str(e)}")
    
    def get_monthly_transactions(self, account_id: int, year: int, month: int) -> List[Transaction]:
        """Get transactions for a specific month"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE account_id = %s 
                AND YEAR(txn_time) = %s 
                AND MONTH(txn_time) = %s 
                ORDER BY txn_time DESC
            """
            results = self.db.execute_query(query, (account_id, year, month), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting monthly transactions: {str(e)}")
    
    def get_transfer_transactions(self, account_id: int) -> List[Transaction]:
        """Get all transfer transactions involving an account"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE (account_id = %s OR related_account_id = %s) 
                AND txn_type LIKE '%transfer%' 
                ORDER BY txn_time DESC
            """
            results = self.db.execute_query(query, (account_id, account_id), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting transfer transactions: {str(e)}")
    
    def search_transactions(self, criteria: Dict[str, Any]) -> List[Transaction]:
        """Search transactions by multiple criteria"""
        try:
            where_conditions = []
            params = []
            
            if criteria.get('account_id'):
                where_conditions.append("account_id = %s")
                params.append(criteria['account_id'])
            
            if criteria.get('txn_type'):
                where_conditions.append("txn_type LIKE %s")
                params.append(f"%{criteria['txn_type']}%")
            
            if criteria.get('min_amount'):
                where_conditions.append("amount >= %s")
                params.append(criteria['min_amount'])
            
            if criteria.get('max_amount'):
                where_conditions.append("amount <= %s")
                params.append(criteria['max_amount'])
            
            if criteria.get('start_date'):
                where_conditions.append("DATE(txn_time) >= %s")
                params.append(criteria['start_date'])
            
            if criteria.get('end_date'):
                where_conditions.append("DATE(txn_time) <= %s")
                params.append(criteria['end_date'])
            
            if criteria.get('reference'):
                where_conditions.append("reference LIKE %s")
                params.append(f"%{criteria['reference']}%")
            
            if not where_conditions:
                return []
            
            where_clause = " AND ".join(where_conditions)
            query = f"SELECT * FROM {self.table_name} WHERE {where_clause} ORDER BY txn_time DESC"
            
            results = self.db.execute_query(query, tuple(params), fetch_all=True)
            return [self._dict_to_transaction(txn_data) for txn_data in results or []]
            
        except Exception as e:
            raise ValidationException(f"Error searching transactions: {str(e)}")
    
    def _dict_to_transaction(self, txn_data: dict) -> Transaction:
        """Convert dictionary to Transaction object"""
        return Transaction(
            txn_id=txn_data['txn_id'],
            account_id=txn_data['account_id'],
            related_account_id=txn_data.get('related_account_id'),
            txn_type=txn_data['txn_type'],
            amount=txn_data['amount'],
            balance_after_txn=txn_data['balance_after_txn'],
            currency=txn_data.get('currency', 'INR'),
            txn_time=txn_data.get('txn_time'),
            reference=txn_data.get('reference'),
            narration=txn_data.get('narration'),
            created_by=txn_data.get('created_by')
        )