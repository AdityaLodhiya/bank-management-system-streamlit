"""
Transaction Service
Business logic for transaction processing operations
"""

from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional, Dict, Any

from core.repositories.transaction_repository import TransactionRepository
from core.repositories.account_repository import AccountRepository
from core.repositories.notification_repository import NotificationRepository
from core.models.entities import Transaction, Account
from utils.exceptions import (
    ValidationException, AccountNotFoundException, 
    InsufficientFundsException, InvalidTransactionException
)
from utils.validators import BankingValidator
from utils.helpers import StringUtils, NumberUtils, LoggingUtils
from db.database import db_manager

class TransactionService:
    """Service class for transaction processing operations"""
    
    def __init__(self):
        self.transaction_repo = TransactionRepository()
        self.account_repo = AccountRepository()
        self.notification_repo = NotificationRepository()
    
    def deposit(self, account_id: int, amount: Decimal, description: str = None, 
               performed_by: int = None, txn_type: str = "DEPOSIT",
               reference: str = None) -> Dict[str, Any]:
        """Process a deposit transaction"""
        try:
            # Validate inputs
            BankingValidator.validate_amount(amount, Decimal('1.00'))
            
            # 1. Role-based permission (Only ADMIN can perform cash deposits)
            from core.repositories.user_repository import UserRepository
            user_data = UserRepository().find_by_id(performed_by)
            role = user_data.get('role', '').upper() if user_data else ''
            if role != 'ADMIN':
                raise InvalidTransactionException("Unauthorized: Only Admin can perform cash deposits")

            # 2. Get account details
            account = self.account_repo.find_account_by_id(account_id)
            if not account:
                raise AccountNotFoundException(f"Account ID {account_id} not found")
            
            # 3. Strict Account Status Check
            def is_active(acc):
                s = acc.status.value if hasattr(acc.status, 'value') else str(acc.status)
                return str(s).lower() == 'active'

            if not is_active(account):
                raise InvalidTransactionException(f"Transaction blocked: Account status is '{account.status}'")
            
            # Calculate new balance
            new_balance = account.balance + amount
            
            # Generate transaction reference (if not provided)
            if not reference:
                ref_prefix = "DEP" if txn_type == "DEPOSIT" else "CSH"
                reference = StringUtils.generate_reference_number(ref_prefix)
            
            # Use database transaction for atomicity
            with db_manager.get_transaction() as conn:
                # Update account balance
                self.account_repo.update_balance(account_id, new_balance)
                
                # Create transaction record
                transaction = Transaction(
                    account_id=account_id,
                    txn_type=txn_type,
                    amount=amount,
                    balance_after_txn=new_balance,
                    txn_time=datetime.now(),
                    reference=reference,
                    narration=description or f"{txn_type.replace('_', ' ').title()} of {StringUtils.format_currency(amount)}",
                    created_by=performed_by
                )
                
                txn_id = self.transaction_repo.create_transaction(transaction)
                
                # 4. Log to Audit (Admin action)
                from core.services.audit_service import AuditService
                AuditService().log(
                    actor_id=performed_by,
                    role='admin',
                    action='CASH_DEPOSIT',
                    details={'txn_id': txn_id, 'ref': reference, 'amount': str(amount)}
                )
            
            # Log transaction (Legacy log)
            LoggingUtils.log_transaction(
                "deposit",
                account_id,
                amount,
                user_id=performed_by,
                details={'reference': reference, 'new_balance': str(new_balance)}
            )
            
            # Send notification (async)
            self._send_transaction_notification(account, "Deposit", amount, reference)
            
            return {
                'txn_id': txn_id,
                'reference': reference,
                'account_id': account_id,
                'txn_type': 'DEPOSIT',
                'amount': amount,
                'old_balance': account.balance,
                'new_balance': new_balance,
                'timestamp': datetime.now(),
                'status': 'SUCCESS'
            }
            
        except Exception as e:
            LoggingUtils.log_business_event(
                "deposit_failed",
                "transaction",
                0,
                user_id=performed_by,
                details={'error': str(e), 'account_id': account_id, 'amount': str(amount)}
            )
            raise
    
    def withdraw(self, account_id: int, amount: Decimal, description: str = None,
                 performed_by: int = None, reference: str = None) -> Dict[str, Any]:
        """Process a withdrawal transaction"""
        try:
            # Validate inputs
            BankingValidator.validate_amount(amount, Decimal('1.00'))
            
            # 1. Role-based permission (Only ADMIN can perform cash withdrawals)
            from core.repositories.user_repository import UserRepository
            user_data = UserRepository().find_by_id(performed_by)
            role = user_data.get('role', '').upper() if user_data else ''
            if role != 'ADMIN':
                raise InvalidTransactionException("Unauthorized: Only Admin can perform cash withdrawals")

            # 2. Get account details
            account = self.account_repo.find_account_by_id(account_id)
            if not account:
                raise AccountNotFoundException(f"Account {account_id} not found")
            
            # 2. Strict Account Status Check
            def is_active(acc):
                s = acc.status.value if hasattr(acc.status, 'value') else str(acc.status)
                return str(s).lower() == 'active'

            if not is_active(account):
                raise InvalidTransactionException(f"Transaction blocked: Account status is '{account.status}'")
            
            # 3. Check sufficient funds
            if not self.account_repo.validate_sufficient_funds(account_id, amount):
                available = account.balance + account.od_limit
                raise InsufficientFundsException(
                    f"Insufficient funds. Available: {StringUtils.format_currency(available)}, "
                    f"Requested: {StringUtils.format_currency(amount)}"
                )
            
            # Calculate new balance
            new_balance = account.balance - amount
            
            # Generate transaction reference (if not provided)
            if not reference:
                reference = StringUtils.generate_reference_number("WDR")
            
            # Use database transaction for atomicity
            with db_manager.get_transaction() as conn:
                # Update account balance
                self.account_repo.update_balance(account_id, new_balance)
                
                # Create transaction record
                transaction = Transaction(
                    account_id=account_id,
                    txn_type="WITHDRAWAL",
                    amount=amount,
                    balance_after_txn=new_balance,
                    txn_time=datetime.now(),
                    reference=reference,
                    narration=description or f"Cash withdrawal of {StringUtils.format_currency(amount)}",
                    created_by=performed_by
                )
                
                txn_id = self.transaction_repo.create_transaction(transaction)
                
                # 4. Log to Audit (Admin action — only admins can withdraw)
                from core.services.audit_service import AuditService
                AuditService().log(
                    actor_id=performed_by,
                    role='admin',
                    action='CASH_WITHDRAWAL',
                    details={'txn_id': txn_id, 'ref': reference, 'amount': str(amount)}
                )
            
            # Log transaction
            LoggingUtils.log_transaction(
                "withdrawal",
                account_id,
                amount,
                user_id=performed_by,
                details={'reference': reference, 'new_balance': str(new_balance)}
            )
            
            # Send notification
            self._send_transaction_notification(account, "Withdrawal", amount, reference)
            
            # Check for low balance alert
            if new_balance < account.min_balance:
                self._send_low_balance_alert(account, new_balance)
            
            return {
                'txn_id': txn_id,
                'reference': reference,
                'account_id': account_id,
                'txn_type': 'WITHDRAWAL',
                'amount': amount,
                'old_balance': account.balance,
                'new_balance': new_balance,
                'timestamp': datetime.now(),
                'status': 'SUCCESS',
                'overdraft_used': new_balance < Decimal('0.00')
            }
            
        except Exception as e:
            LoggingUtils.log_business_event(
                "withdrawal_failed",
                "transaction",
                0,
                user_id=performed_by,
                details={'error': str(e), 'account_id': account_id, 'amount': str(amount)}
            )
            raise
    
    def transfer(self, from_account_id: int, to_account_id: int, amount: Decimal,
                description: str = None, performed_by: int = None,
                reference: str = None) -> Dict[str, Any]:
        """Process a transfer between accounts"""
        try:
            # Validate inputs
            BankingValidator.validate_amount(amount, Decimal('1.00'))
            
            if from_account_id == to_account_id:
                raise ValidationException("Cannot transfer to the same account")
            
            # Get account details
            from_account = self.account_repo.find_account_by_id(from_account_id)
            to_account = self.account_repo.find_account_by_id(to_account_id)
            if not from_account:
                raise AccountNotFoundException(f"Source account ID {from_account_id} not found")
            if not to_account:
                raise AccountNotFoundException(f"Destination account ID {to_account_id} not found")
            
            # 1. Ownership check for customers
            from core.repositories.user_repository import UserRepository
            user_data = UserRepository().find_by_id(performed_by)
            role = user_data.get('role', '').upper() if user_data else ''
            
            if role != 'ADMIN':
                if from_account.user_id != performed_by:
                    raise InvalidTransactionException("Unauthorized: You can only transfer funds from your own account")

            # 2. Strict Status Checks
            def is_active(acc):
                s = acc.status.value if hasattr(acc.status, 'value') else str(acc.status)
                return str(s).lower() == 'active'
            
            if not is_active(from_account):
                raise InvalidTransactionException(f"Transfer blocked: Source account is {from_account.status}")
            if not is_active(to_account):
                raise InvalidTransactionException(f"Transfer blocked: Destination account is {to_account.status}")
            
            # Check sufficient funds in source account
            if not self.account_repo.validate_sufficient_funds(from_account_id, amount):
                available = from_account.balance + from_account.od_limit
                raise InsufficientFundsException(
                    f"Insufficient funds in source account. Available: {StringUtils.format_currency(available)}"
                )
            
            # Calculate new balances
            from_new_balance = from_account.balance - amount
            to_new_balance = to_account.balance + amount
            
            # Generate transaction reference (if not provided)
            if not reference:
                reference = StringUtils.generate_reference_number("TRF")
            
            # Use database transaction for atomicity
            with db_manager.get_transaction() as conn:
                # Update both account balances
                self.account_repo.update_balance(from_account_id, from_new_balance)
                self.account_repo.update_balance(to_account_id, to_new_balance)
                
                # Create debit transaction for source account
                debit_transaction = Transaction(
                    account_id=from_account_id,
                    related_account_id=to_account_id,
                    txn_type="TRANSFER_DEBIT",
                    amount=amount,
                    balance_after_txn=from_new_balance,
                    txn_time=datetime.now(),
                    reference=f"{reference}-D",
                    narration=description or f"Transfer to {to_account.account_number}",
                    created_by=performed_by
                )
                
                # Create credit transaction for destination account
                credit_transaction = Transaction(
                    account_id=to_account_id,
                    related_account_id=from_account_id,
                    txn_type="TRANSFER_CREDIT",
                    amount=amount,
                    balance_after_txn=to_new_balance,
                    txn_time=datetime.now(),
                    reference=f"{reference}-C",
                    narration=description or f"Transfer from {from_account.account_number}",
                    created_by=performed_by
                )
                
                debit_txn_id = self.transaction_repo.create_transaction(debit_transaction)
                credit_txn_id = self.transaction_repo.create_transaction(credit_transaction)

                # Log to Audit
                from core.services.audit_service import AuditService
                AuditService().log(
                    actor_id=performed_by,
                    role='customer',
                    action='TRANSFER',
                    details={'ref': reference, 'from': from_account_id, 'to': to_account_id, 'amount': str(amount)}
                )
            
            # Log transaction (Legacy)
            LoggingUtils.log_transaction(
                "transfer",
                from_account_id,
                amount,
                user_id=performed_by,
                details={
                    'reference': reference,
                    'to_account': to_account_id,
                    'from_new_balance': str(from_new_balance),
                    'to_new_balance': str(to_new_balance)
                }
            )
            
            # Send notifications to both accounts
            self._send_transaction_notification(from_account, "Transfer Debit", amount, reference)
            self._send_transaction_notification(to_account, "Transfer Credit", amount, reference)
            
            return {
                'debit_txn_id': debit_txn_id,
                'credit_txn_id': credit_txn_id,
                'reference': reference,
                'from_account_id': from_account_id,
                'to_account_id': to_account_id,
                'amount': amount,
                'from_old_balance': from_account.balance,
                'from_new_balance': from_new_balance,
                'to_old_balance': to_account.balance,
                'to_new_balance': to_new_balance,
                'timestamp': datetime.now(),
                'status': 'SUCCESS'
            }
            
        except Exception as e:
            LoggingUtils.log_business_event(
                "transfer_failed",
                "transaction",
                0,
                user_id=performed_by,
                details={
                    'error': str(e),
                    'from_account': from_account_id,
                    'to_account': to_account_id,
                    'amount': str(amount)
                }
            )
            raise
    
    def get_transaction_history(self, account_id: int, performed_by: int = None,
                               limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get transaction history for an account with RBAC"""
        # 1. Get account details for ownership check
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")

        # 2. Role-based check
        from core.repositories.user_repository import UserRepository
        user_data = UserRepository().find_by_id(performed_by)
        role = user_data.get('role', '').upper() if user_data else ''
        
        if role != 'ADMIN' and account.user_id != performed_by:
            raise InvalidTransactionException("Unauthorized: You can only view statements for your own account")

        transactions = self.transaction_repo.find_by_account(account_id, limit, offset)
        
        history = []
        for txn in transactions:
            history.append({
                'txn_id': txn.txn_id,
                'reference': txn.reference,
                'txn_type': txn.txn_type,
                'amount': txn.amount,
                'balance_after_txn': txn.balance_after_txn,  # matches UI display column
                'narration': txn.narration,
                'txn_time': txn.txn_time,
                'related_account': txn.related_account_id
            })
        
        return history
    
    def get_transaction_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        """Get transaction details by reference number"""
        transaction = self.transaction_repo.find_by_reference(reference)
        if not transaction:
            return None
        
        return {
            'txn_id': transaction.txn_id,
            'reference': transaction.reference,
            'account_id': transaction.account_id,
            'txn_type': transaction.txn_type,
            'amount': transaction.amount,
            'balance_after': transaction.balance_after_txn,
            'description': transaction.narration,
            'timestamp': transaction.txn_time,
            'related_account': transaction.related_account_id,
            'created_by': transaction.created_by
        }
    
    def get_transaction_summary(self, account_id: int, days: int = 30, performed_by: int = None) -> Dict[str, Any]:
        """Get transaction summary for an account with RBAC"""
        # 1. Get account details for ownership check
        account = self.account_repo.find_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")

        # 2. Role-based check
        from core.repositories.user_repository import UserRepository
        user_data = UserRepository().find_by_id(performed_by)
        role = user_data.get('role', '').upper() if user_data else ''
        
        if role != 'ADMIN' and account.user_id != performed_by:
            raise InvalidTransactionException("Unauthorized: You can only view summaries for your own account")

        summary = self.transaction_repo.get_transaction_summary(account_id, days)
        
        return {
            'account_id': account_id,
            'period_days': days,
            'total_transactions': summary['total_transactions'],
            'total_credits': summary['total_credits'],
            'total_debits': summary['total_debits'],
            'net_amount': summary['net_amount'],
            'average_transaction': summary['avg_amount']
        }
    
    def search_transactions(self, criteria: Dict[str, Any], performed_by: int = None) -> List[Dict[str, Any]]:
        """Search transactions by criteria with RBAC"""
        # RBAC Check if account_id is provided in search criteria
        target_account_id = criteria.get('account_id')
        if target_account_id:
            account = self.account_repo.find_account_by_id(target_account_id)
            if account:
                from core.repositories.user_repository import UserRepository
                user_data = UserRepository().find_by_id(performed_by)
                role = user_data.get('role', '').upper() if user_data else ''
                
                if role != 'ADMIN' and account.user_id != performed_by:
                    raise InvalidTransactionException("Unauthorized search criteria for specified account")

        transactions = self.transaction_repo.search_transactions(criteria)
        
        results = []
        for txn in transactions:
            results.append({
                'txn_id': txn.txn_id,
                'reference': txn.reference,
                'account_id': txn.account_id,
                'txn_type': txn.txn_type,
                'amount': txn.amount,
                'balance_after': txn.balance_after_txn,
                'description': txn.narration,
                'timestamp': txn.txn_time,
                'related_account': txn.related_account_id
            })
        
        return results
    
    def _send_transaction_notification(self, account: Account, txn_type: str, 
                                     amount: Decimal, reference: str):
        """Send transaction notification to customer"""
        try:
            self.notification_repo.create_transaction_notification(
                user_id=account.user_id,
                transaction_type=txn_type,
                amount=StringUtils.format_currency(amount),
                account_number=StringUtils.mask_account_number(account.account_number)
            )
        except Exception as e:
            # Log error but don't fail transaction
            LoggingUtils.log_business_event(
                "notification_failed",
                "notification",
                0,
                details={'error': str(e), 'account_id': account.account_id}
            )
    
    def _send_low_balance_alert(self, account: Account, current_balance: Decimal):
        """Send low balance alert notification"""
        try:
            self.notification_repo.create_balance_alert(
                user_id=account.user_id,
                current_balance=StringUtils.format_currency(current_balance),
                account_number=StringUtils.mask_account_number(account.account_number)
            )
        except Exception as e:
            # Log error but don't fail transaction
            LoggingUtils.log_business_event(
                "low_balance_alert_failed",
                "notification",
                0,
                details={'error': str(e), 'account_id': account.account_id}
            )