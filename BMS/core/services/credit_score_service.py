"""
Credit Score Service — Tracks and updates customer creditworthiness.
"""
from decimal import Decimal
from core.repositories.credit_score_repository import CreditScoreRepository
from core.repositories.customer_repository import CustomerRepository

class CreditScoreService:
    def __init__(self):
        self.credit_repo = CreditScoreRepository()
        self.customer_repo = CustomerRepository()

    def update_customer_score(self, user_id: int, points: int, reason: str):
        """Update credit score and log history"""
        return self.credit_repo.calculate_and_save_score(user_id)

    def get_eligibility(self, user_id: int, loan_amount: Decimal) -> bool:
        """Check if customer is eligible for a specific loan amount"""
        score_data = self.credit_repo.get_latest_score(user_id)
        score = score_data.current_score if score_data else 0
        
        if score < 600: return False
        if score < 700 and loan_amount > 500000: return False
        
        return True
