"""
Credit Score Repository
Handles database operations for credit_score table
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from core.repositories.base_repository import BaseRepository
from core.models.entities import CreditScore
from utils.exceptions import ValidationException

class CreditScoreRepository(BaseRepository):
    """Repository for credit_score table operations"""
    
    def __init__(self):
        super().__init__('credit_score', 'score_id')
    
    def create_credit_score(self, credit_score: CreditScore) -> int:
        """Create a new credit score record"""
        if not credit_score.user_id or not (300 <= credit_score.score <= 850):
            raise ValidationException("User ID and valid score (300-850) are required")
        
        score_data = {
            'user_id': credit_score.user_id,
            'score': credit_score.score,
            'reason_summary': credit_score.reason_summary,
            'calculated_at': credit_score.calculated_at or datetime.now()
        }
        
        return self.create(score_data)
    
    def find_score_by_id(self, score_id: int) -> Optional[CreditScore]:
        """Find credit score by ID"""
        score_data = self.find_by_id(score_id)
        if not score_data:
            return None
        
        return self._dict_to_credit_score(score_data)
    
    def get_latest_score(self, user_id: int) -> Optional[CreditScore]:
        """Get the latest credit score for a customer"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s 
                ORDER BY calculated_at DESC 
                LIMIT 1
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            return self._dict_to_credit_score(result) if result else None
        except Exception as e:
            raise ValidationException(f"Error getting latest credit score: {str(e)}")
    
    def get_score_history(self, user_id: int, limit: int = 12) -> List[CreditScore]:
        """Get credit score history for a customer"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s 
                ORDER BY calculated_at DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit), fetch_all=True)
            return [self._dict_to_credit_score(score_data) for score_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting credit score history: {str(e)}")
    
    def calculate_credit_score(self, user_id: int) -> int:
        """Calculate credit score based on customer's financial behavior"""
        try:
            # Get customer's financial data
            payment_history_score = self._calculate_payment_history_score(user_id)
            credit_utilization_score = self._calculate_credit_utilization_score(user_id)
            account_age_score = self._calculate_account_age_score(user_id)
            loan_diversity_score = self._calculate_loan_diversity_score(user_id)
            recent_inquiries_score = self._calculate_recent_inquiries_score(user_id)
            
            # Weighted calculation (similar to FICO model)
            weights = {
                'payment_history': 0.35,      # 35%
                'credit_utilization': 0.30,   # 30%
                'account_age': 0.15,          # 15%
                'loan_diversity': 0.10,       # 10%
                'recent_inquiries': 0.10      # 10%
            }
            
            weighted_score = (
                payment_history_score * weights['payment_history'] +
                credit_utilization_score * weights['credit_utilization'] +
                account_age_score * weights['account_age'] +
                loan_diversity_score * weights['loan_diversity'] +
                recent_inquiries_score * weights['recent_inquiries']
            )
            
            # Scale to 300-850 range
            final_score = int(300 + (weighted_score / 100) * 550)
            
            # Ensure score is within valid range
            final_score = max(300, min(850, final_score))
            
            return final_score
            
        except Exception as e:
            raise ValidationException(f"Error calculating credit score: {str(e)}")
    
    def update_credit_score(self, user_id: int, reason: str = None) -> int:
        """Calculate and update credit score for a customer"""
        new_score = self.calculate_credit_score(user_id)
        
        credit_score = CreditScore(
            user_id=user_id,
            score=new_score,
            reason_summary=reason or "Automated score update",
            calculated_at=datetime.now()
        )
        
        score_id = self.create_credit_score(credit_score)
        return new_score
    
    def get_score_distribution(self) -> Dict[str, int]:
        """Get distribution of credit scores across ranges"""
        try:
            query = f"""
                SELECT 
                    CASE 
                        WHEN score >= 800 THEN 'Excellent (800-850)'
                        WHEN score >= 740 THEN 'Very Good (740-799)'
                        WHEN score >= 670 THEN 'Good (670-739)'
                        WHEN score >= 580 THEN 'Fair (580-669)'
                        ELSE 'Poor (300-579)'
                    END as score_range,
                    COUNT(*) as count
                FROM (
                    SELECT DISTINCT user_id, 
                           FIRST_VALUE(score) OVER (PARTITION BY user_id ORDER BY calculated_at DESC) as score
                    FROM {self.table_name}
                ) latest_scores
                GROUP BY score_range
                ORDER BY MIN(score) DESC
            """
            results = self.db.execute_query(query, fetch_all=True)
            
            distribution = {}
            for result in results or []:
                distribution[result['score_range']] = result['count']
            
            return distribution
        except Exception as e:
            raise ValidationException(f"Error getting score distribution: {str(e)}")
    
    def get_customers_by_score_range(self, min_score: int, max_score: int) -> List[int]:
        """Get user IDs within a score range"""
        try:
            query = f"""
                SELECT DISTINCT user_id
                FROM (
                    SELECT user_id, 
                           FIRST_VALUE(score) OVER (PARTITION BY user_id ORDER BY calculated_at DESC) as latest_score
                    FROM {self.table_name}
                ) latest_scores
                WHERE latest_score BETWEEN %s AND %s
            """
            results = self.db.execute_query(query, (min_score, max_score), fetch_all=True)
            return [result['user_id'] for result in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting customers by score range: {str(e)}")
    
    def _calculate_payment_history_score(self, user_id: int) -> float:
        """Calculate payment history score (0-100)"""
        try:
            # Check loan payment history
            query = """
                SELECT 
                    COUNT(*) as total_emis,
                    COUNT(CASE WHEN status = 'paid' AND paid_date <= due_date THEN 1 END) as on_time_payments,
                    COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue_payments
                FROM loan_emi le
                JOIN loans l ON le.loan_id = l.loan_id
                WHERE l.user_id = %s AND le.due_date < CURDATE()
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            
            if not result or result['total_emis'] == 0:
                return 70.0  # Default score for new customers
            
            on_time_ratio = result['on_time_payments'] / result['total_emis']
            overdue_ratio = result['overdue_payments'] / result['total_emis']
            
            # Score based on payment behavior
            score = 100 * on_time_ratio - 50 * overdue_ratio
            return max(0, min(100, score))
            
        except Exception:
            return 70.0  # Default score on error
    
    def _calculate_credit_utilization_score(self, user_id: int) -> float:
        """Calculate credit utilization score (0-100)"""
        try:
            # Check account balances vs overdraft limits
            query = """
                SELECT 
                    SUM(od_limit) as total_credit_limit,
                    SUM(CASE WHEN balance < 0 THEN ABS(balance) ELSE 0 END) as total_used_credit
                FROM accounts
                WHERE user_id = %s AND od_limit > 0 AND status = 'active'
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            
            if not result or not result['total_credit_limit'] or result['total_credit_limit'] == 0:
                return 85.0  # Good score if no credit utilization
            
            utilization_ratio = result['total_used_credit'] / result['total_credit_limit']
            
            # Lower utilization = higher score
            if utilization_ratio <= 0.1:  # Under 10%
                return 100.0
            elif utilization_ratio <= 0.3:  # Under 30%
                return 80.0
            elif utilization_ratio <= 0.5:  # Under 50%
                return 60.0
            elif utilization_ratio <= 0.7:  # Under 70%
                return 40.0
            else:
                return 20.0
                
        except Exception:
            return 85.0  # Default score on error
    
    def _calculate_account_age_score(self, user_id: int) -> float:
        """Calculate account age score (0-100)"""
        try:
            query = """
                SELECT MIN(opening_date) as oldest_account_date
                FROM accounts
                WHERE user_id = %s AND status IN ('active', 'closed')
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            
            if not result or not result['oldest_account_date']:
                return 50.0  # Default for new customers
            
            account_age_days = (datetime.now().date() - result['oldest_account_date']).days
            account_age_years = account_age_days / 365.25
            
            # Longer history = higher score
            if account_age_years >= 10:
                return 100.0
            elif account_age_years >= 5:
                return 80.0
            elif account_age_years >= 2:
                return 60.0
            elif account_age_years >= 1:
                return 40.0
            else:
                return 20.0
                
        except Exception:
            return 50.0  # Default score on error
    
    def _calculate_loan_diversity_score(self, user_id: int) -> float:
        """Calculate loan diversity score (0-100)"""
        try:
            query = """
                SELECT COUNT(DISTINCT loan_plan_id) as loan_types
                FROM loans
                WHERE user_id = %s AND status IN ('active', 'closed')
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            
            loan_types = result['loan_types'] if result else 0
            
            # More diverse credit mix = higher score
            if loan_types >= 3:
                return 100.0
            elif loan_types == 2:
                return 80.0
            elif loan_types == 1:
                return 60.0
            else:
                return 40.0  # No loans, but not necessarily bad
                
        except Exception:
            return 60.0  # Default score on error
    
    def _calculate_recent_inquiries_score(self, user_id: int) -> float:
        """Calculate recent inquiries score (0-100)"""
        try:
            # Count recent loan applications (last 6 months)
            six_months_ago = datetime.now() - timedelta(days=180)
            
            query = """
                SELECT COUNT(*) as recent_applications
                FROM loans
                WHERE user_id = %s AND created_at >= %s
            """
            result = self.db.execute_query(query, (user_id, six_months_ago), fetch_one=True)
            
            recent_applications = result['recent_applications'] if result else 0
            
            # Fewer recent inquiries = higher score
            if recent_applications == 0:
                return 100.0
            elif recent_applications <= 2:
                return 80.0
            elif recent_applications <= 4:
                return 60.0
            else:
                return 30.0
                
        except Exception:
            return 80.0  # Default score on error
    
    def _dict_to_credit_score(self, score_data: dict) -> CreditScore:
        """Convert dictionary to CreditScore object"""
        return CreditScore(
            score_id=score_data['score_id'],
            user_id=score_data['user_id'],
            score=score_data['score'],
            reason_summary=score_data.get('reason_summary'),
            calculated_at=score_data.get('calculated_at')
        )