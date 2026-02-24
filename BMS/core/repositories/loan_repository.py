"""
Loan Repository
Handles database operations for loans and loan_emi tables
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from core.repositories.base_repository import BaseRepository
from core.models.entities import Loan, LoanStatus, LoanType
from utils.exceptions import ValidationException, LoanNotFoundException

class LoanRepository(BaseRepository):
    """Repository for loans table operations"""
    
    def __init__(self):
        super().__init__('loans', 'loan_id')
    
    def create_loan(self, loan: Loan) -> int:
        """Create a new loan application"""
        if not loan.user_id or not loan.account_id or loan.principal_amount <= 0:
            raise ValidationException("User ID, Account ID, and positive principal amount are required")
        
        loan_data = {
            'user_id': loan.user_id,
            'account_id': loan.account_id,
            'loan_plan_id': loan.loan_plan_id,
            'loan_type': loan.loan_type.value if isinstance(loan.loan_type, LoanType) else (loan.loan_type or 'personal'),
            'principal_amount': loan.principal_amount,
            'interest_rate_annual': loan.interest_rate_annual,
            'tenure_months': loan.tenure_months,
            'emi_amount': loan.emi_amount,
            'sanction_date': loan.sanction_date,
            'disbursement_date': loan.disbursement_date,
            'status': loan.status.value if isinstance(loan.status, LoanStatus) else loan.status,
            'total_interest_payable': loan.total_interest_payable,
            'remaining_principal': loan.remaining_principal or loan.principal_amount,
            'credit_score_at_sanction': loan.credit_score_at_sanction,
            'created_by': loan.created_by,
            'reference': getattr(loan, 'reference', None)
        }
        
        return self.create(loan_data)
    
    def find_loan_by_id(self, loan_id: int) -> Optional[Loan]:
        """Find loan by ID"""
        loan_data = self.find_by_id(loan_id)
        if not loan_data:
            return None
        
        return self._dict_to_loan(loan_data)
    
    def find_by_customer(self, user_id: int) -> List[Loan]:
        """Find all loans for a customer"""
        loans_data = self.find_by_field('user_id', user_id)
        return [self._dict_to_loan(loan_data) for loan_data in loans_data]
    
    def get_active_loans(self, user_id: int = None) -> List[Loan]:
        """Get active loans, optionally filtered by user"""
        try:
            if user_id:
                query = f"SELECT * FROM {self.table_name} WHERE user_id = %s AND status = 'active' ORDER BY disbursement_date DESC"
                results = self.db.execute_query(query, (user_id,), fetch_all=True)
            else:
                query = f"SELECT * FROM {self.table_name} WHERE status = 'active' ORDER BY disbursement_date DESC"
                results = self.db.execute_query(query, fetch_all=True)
            
            return [self._dict_to_loan(loan_data) for loan_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting active loans: {str(e)}")
    
    def get_pending_approvals(self) -> List[Loan]:
        """Get loans pending approval"""
        loans_data = self.find_by_field('status', 'pending_approval')
        return [self._dict_to_loan(loan_data) for loan_data in loans_data]

    def get_all_loans(self) -> List[Loan]:
        """Get ALL loans in the system (admin use only)"""
        try:
            query = f"SELECT * FROM {self.table_name} ORDER BY created_at DESC"
            results = self.db.execute_query(query, fetch_all=True)
            return [self._dict_to_loan(loan_data) for loan_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error fetching all loans: {str(e)}")

    def approve_loan(self, loan_id: int, approved_amount: Decimal, interest_rate: Decimal, 
                    tenure_months: int, approved_by: int) -> bool:
        """Approve a loan application"""
        # Calculate EMI
        emi_amount = self.calculate_emi(approved_amount, interest_rate, tenure_months)
        total_interest = (emi_amount * tenure_months) - approved_amount
        
        loan_data = {
            'principal_amount': approved_amount,
            'interest_rate_annual': interest_rate,
            'tenure_months': tenure_months,
            'emi_amount': emi_amount,
            'total_interest_payable': total_interest,
            'remaining_principal': approved_amount,
            'status': 'approved',
            'sanction_date': date.today()
        }
        
        success = self.update(loan_id, loan_data)
        
        if success:
            # Create EMI schedule
            self._create_emi_schedule(loan_id, emi_amount, tenure_months, interest_rate, approved_amount)
        
        return success
    
    def disburse_loan(self, loan_id: int) -> bool:
        """Mark loan as disbursed"""
        loan_data = {
            'status': 'active',
            'disbursement_date': date.today()
        }
        
        return self.update(loan_id, loan_data)
    
    def reject_loan(self, loan_id: int, reason: str = None) -> bool:
        """Reject a loan application"""
        return self.update(loan_id, {'status': 'rejected'})
    
    def calculate_emi(self, principal: Decimal, annual_rate: Decimal, tenure_months: int) -> Decimal:
        """Calculate EMI using standard formula"""
        if annual_rate == 0:
            return principal / tenure_months
        
        monthly_rate = annual_rate / (12 * 100)  # Convert to monthly decimal rate
        
        # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        power_term = (1 + monthly_rate) ** tenure_months
        emi = principal * monthly_rate * power_term / (power_term - 1)
        
        return emi.quantize(Decimal('0.01'))
    
    def get_due_emis(self, loan_id: int = None) -> List[Dict[str, Any]]:
        """Get due EMIs for loan(s)"""
        try:
            if loan_id:
                query = """
                    SELECT le.*, l.user_id, l.account_id
                    FROM loan_emi le
                    JOIN loans l ON le.loan_id = l.loan_id
                    WHERE le.loan_id = %s AND le.status = 'due' AND le.due_date <= CURDATE()
                    ORDER BY le.due_date ASC
                """
                results = self.db.execute_query(query, (loan_id,), fetch_all=True)
            else:
                query = """
                    SELECT le.*, l.user_id, l.account_id
                    FROM loan_emi le
                    JOIN loans l ON le.loan_id = l.loan_id
                    WHERE le.status = 'due' AND le.due_date <= CURDATE()
                    ORDER BY le.due_date ASC
                """
                results = self.db.execute_query(query, fetch_all=True)
            
            return results or []
        except Exception as e:
            raise ValidationException(f"Error getting due EMIs: {str(e)}")
    
    def pay_emi(self, loan_id: int, installment_number: int, payment_date: date = None) -> bool:
        """Mark an EMI as paid and update loan balance"""
        try:
            payment_date = payment_date or date.today()
            
            # Get EMI details
            query = "SELECT * FROM loan_emi WHERE loan_id = %s AND installment_number = %s"
            emi_data = self.db.execute_query(query, (loan_id, installment_number), fetch_one=True)
            
            if not emi_data:
                raise ValidationException(f"EMI {installment_number} not found for loan {loan_id}")
            
            # Update EMI status
            query = """
                UPDATE loan_emi 
                SET status = 'paid', paid_date = %s 
                WHERE loan_id = %s AND installment_number = %s
            """
            self.db.execute_query(query, (payment_date, loan_id, installment_number))
            
            # Update loan remaining principal
            principal_component = emi_data['principal_component']
            query = """
                UPDATE loans 
                SET remaining_principal = remaining_principal - %s
                WHERE loan_id = %s
            """
            self.db.execute_query(query, (principal_component, loan_id))
            
            # Check if loan is fully paid
            loan = self.find_loan_by_id(loan_id)
            if loan and loan.remaining_principal <= 0:
                self.update(loan_id, {'status': 'closed'})
            
            return True
        except Exception as e:
            raise ValidationException(f"Error paying EMI: {str(e)}")
    
    def mark_emi_overdue(self, loan_id: int, installment_number: int, penalty_amount: Decimal = None) -> bool:
        """Mark an EMI as overdue and apply penalty"""
        try:
            penalty_amount = penalty_amount or Decimal('0.00')
            
            query = """
                UPDATE loan_emi 
                SET status = 'overdue', penalty_amount = %s 
                WHERE loan_id = %s AND installment_number = %s
            """
            self.db.execute_query(query, (penalty_amount, loan_id, installment_number))
            
            return True
        except Exception as e:
            raise ValidationException(f"Error marking EMI overdue: {str(e)}")
    
    def get_emi_history(self, loan_id: int) -> List[Dict[str, Any]]:
        """Get EMI payment history for a loan"""
        try:
            query = """
                SELECT * FROM loan_emi 
                WHERE loan_id = %s 
                ORDER BY installment_number ASC
            """
            results = self.db.execute_query(query, (loan_id,), fetch_all=True)
            return results or []
        except Exception as e:
            raise ValidationException(f"Error getting EMI history: {str(e)}")
    
    def get_loan_summary(self, user_id: int) -> Dict[str, Any]:
        """Get loan summary for a customer"""
        try:
            query = f"""
                SELECT 
                    COUNT(*) as total_loans,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_loans,
                    SUM(CASE WHEN status = 'active' THEN principal_amount ELSE 0 END) as total_borrowed,
                    SUM(CASE WHEN status = 'active' THEN remaining_principal ELSE 0 END) as total_outstanding,
                    SUM(CASE WHEN status = 'active' THEN emi_amount ELSE 0 END) as total_monthly_emi
                FROM {self.table_name} 
                WHERE user_id = %s
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            
            return {
                'total_loans': result['total_loans'] or 0,
                'active_loans': result['active_loans'] or 0,
                'total_borrowed': result['total_borrowed'] or Decimal('0.00'),
                'total_outstanding': result['total_outstanding'] or Decimal('0.00'),
                'total_monthly_emi': result['total_monthly_emi'] or Decimal('0.00')
            }
        except Exception as e:
            raise ValidationException(f"Error getting loan summary: {str(e)}")
    
    def _create_emi_schedule(self, loan_id: int, emi_amount: Decimal, tenure_months: int, 
                           annual_rate: Decimal, principal: Decimal):
        """Create EMI schedule for approved loan"""
        try:
            monthly_rate = annual_rate / (12 * 100)
            remaining_principal = principal
            emis = []
            
            for i in range(1, tenure_months + 1):
                # Calculate interest and principal components
                interest_component = remaining_principal * monthly_rate
                principal_component = emi_amount - interest_component
                
                due_date = date.today() + relativedelta(months=i)
                
                emis.append((
                    loan_id,
                    i,
                    due_date,
                    principal_component,
                    interest_component,
                    emi_amount
                ))
                
                remaining_principal -= principal_component
            
            query = """
                INSERT INTO loan_emi (loan_id, installment_number, due_date, 
                                    principal_component, interest_component, total_emi)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.execute_many(query, emis)
            
        except Exception as e:
            raise ValidationException(f"Error creating EMI schedule: {str(e)}")
    
    def _dict_to_loan(self, loan_data: dict) -> Loan:
        """Convert dictionary to Loan object"""
        raw_type = loan_data.get('loan_type', 'personal')
        try:
            loan_type = LoanType(raw_type) if raw_type else LoanType.PERSONAL
        except ValueError:
            loan_type = LoanType.PERSONAL

        return Loan(
            loan_id=loan_data['loan_id'],
            user_id=loan_data['user_id'],
            account_id=loan_data['account_id'],
            loan_plan_id=loan_data['loan_plan_id'],
            loan_type=loan_type,
            principal_amount=loan_data['principal_amount'],
            interest_rate_annual=loan_data['interest_rate_annual'],
            tenure_months=loan_data['tenure_months'],
            emi_amount=loan_data['emi_amount'],
            sanction_date=loan_data.get('sanction_date'),
            disbursement_date=loan_data.get('disbursement_date'),
            status=LoanStatus(loan_data['status']),
            total_interest_payable=loan_data.get('total_interest_payable'),
            remaining_principal=loan_data.get('remaining_principal'),
            credit_score_at_sanction=loan_data.get('credit_score_at_sanction'),
            created_by=loan_data.get('created_by'),
            reference=loan_data.get('reference'),
            created_at=loan_data.get('created_at')
        )