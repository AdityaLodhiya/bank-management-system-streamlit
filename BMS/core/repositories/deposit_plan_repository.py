"""
Deposit Plan Repository
Handles database operations for deposit_plans table (FD/RD products)
"""

from typing import Optional, List
from decimal import Decimal

from core.repositories.base_repository import BaseRepository
from core.models.entities import DepositPlan, PlanType
from utils.exceptions import ValidationException, PlanNotFoundException

class DepositPlanRepository(BaseRepository):
    """Repository for deposit_plans table operations"""
    
    def __init__(self):
        super().__init__('deposit_plans', 'plan_id')
    
    def create_deposit_plan(self, plan: DepositPlan) -> int:
        """Create a new deposit plan"""
        if not plan.plan_name or plan.tenure_months <= 0:
            raise ValidationException("Plan name and positive tenure are required")
        
        plan_data = {
            'plan_type': plan.plan_type.value if isinstance(plan.plan_type, PlanType) else plan.plan_type,
            'plan_name': plan.plan_name,
            'tenure_months': plan.tenure_months,
            'interest_rate': plan.interest_rate,
            'min_amount': plan.min_amount,
            'max_amount': plan.max_amount,
            'penalty_rate': plan.penalty_rate,
            'is_active': plan.is_active
        }
        
        return self.create(plan_data)
    
    def find_plan_by_id(self, plan_id: int) -> Optional[DepositPlan]:
        """Find deposit plan by ID"""
        plan_data = self.find_by_id(plan_id)
        if not plan_data:
            return None
        
        return self._dict_to_deposit_plan(plan_data)
    
    def get_active_plans(self, plan_type: PlanType = None) -> List[DepositPlan]:
        """Get all active deposit plans, optionally filtered by type"""
        try:
            if plan_type:
                query = f"SELECT * FROM {self.table_name} WHERE is_active = 1 AND plan_type = %s ORDER BY tenure_months"
                results = self.db.execute_query(query, (plan_type.value,), fetch_all=True)
            else:
                query = f"SELECT * FROM {self.table_name} WHERE is_active = 1 ORDER BY plan_type, tenure_months"
                results = self.db.execute_query(query, fetch_all=True)
            
            return [self._dict_to_deposit_plan(plan_data) for plan_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting active plans: {str(e)}")
    
    def get_fd_plans(self) -> List[DepositPlan]:
        """Get all active FD plans"""
        return self.get_active_plans(PlanType.FD)
    
    def get_rd_plans(self) -> List[DepositPlan]:
        """Get all active RD plans"""
        return self.get_active_plans(PlanType.RD)
    
    def find_by_tenure(self, plan_type: PlanType, tenure_months: int) -> List[DepositPlan]:
        """Find plans by type and tenure"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE plan_type = %s AND tenure_months = %s AND is_active = 1
                ORDER BY interest_rate DESC
            """
            results = self.db.execute_query(query, (plan_type.value, tenure_months), fetch_all=True)
            return [self._dict_to_deposit_plan(plan_data) for plan_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error finding plans by tenure: {str(e)}")
    
    def find_by_amount_range(self, plan_type: PlanType, amount: Decimal) -> List[DepositPlan]:
        """Find plans suitable for a given amount"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE plan_type = %s 
                AND min_amount <= %s 
                AND (max_amount IS NULL OR max_amount >= %s)
                AND is_active = 1
                ORDER BY interest_rate DESC
            """
            results = self.db.execute_query(query, (plan_type.value, amount, amount), fetch_all=True)
            return [self._dict_to_deposit_plan(plan_data) for plan_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error finding plans by amount: {str(e)}")
    
    def get_best_rate_plan(self, plan_type: PlanType, tenure_months: int, amount: Decimal) -> Optional[DepositPlan]:
        """Get the plan with best interest rate for given criteria"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE plan_type = %s 
                AND tenure_months = %s
                AND min_amount <= %s 
                AND (max_amount IS NULL OR max_amount >= %s)
                AND is_active = 1
                ORDER BY interest_rate DESC
                LIMIT 1
            """
            result = self.db.execute_query(query, (plan_type.value, tenure_months, amount, amount), fetch_one=True)
            return self._dict_to_deposit_plan(result) if result else None
        except Exception as e:
            raise ValidationException(f"Error finding best rate plan: {str(e)}")
    
    def update_plan(self, plan: DepositPlan) -> bool:
        """Update deposit plan"""
        if not plan.plan_id:
            raise ValidationException("Plan ID is required for update")
        
        plan_data = {
            'plan_name': plan.plan_name,
            'tenure_months': plan.tenure_months,
            'interest_rate': plan.interest_rate,
            'min_amount': plan.min_amount,
            'max_amount': plan.max_amount,
            'penalty_rate': plan.penalty_rate,
            'is_active': plan.is_active
        }
        
        return self.update(plan.plan_id, plan_data)
    
    def deactivate_plan(self, plan_id: int) -> bool:
        """Deactivate a deposit plan"""
        return self.update(plan_id, {'is_active': False})
    
    def activate_plan(self, plan_id: int) -> bool:
        """Activate a deposit plan"""
        return self.update(plan_id, {'is_active': True})
    
    def update_interest_rate(self, plan_id: int, new_rate: Decimal) -> bool:
        """Update interest rate for a plan"""
        return self.update(plan_id, {'interest_rate': new_rate})
    
    def get_plan_statistics(self) -> dict:
        """Get statistics about deposit plans"""
        try:
            query = f"""
                SELECT 
                    plan_type,
                    COUNT(*) as total_plans,
                    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_plans,
                    AVG(interest_rate) as avg_interest_rate,
                    MIN(interest_rate) as min_interest_rate,
                    MAX(interest_rate) as max_interest_rate
                FROM {self.table_name}
                GROUP BY plan_type
            """
            results = self.db.execute_query(query, fetch_all=True)
            
            stats = {}
            for result in results or []:
                stats[result['plan_type']] = {
                    'total_plans': result['total_plans'],
                    'active_plans': result['active_plans'],
                    'avg_interest_rate': result['avg_interest_rate'],
                    'min_interest_rate': result['min_interest_rate'],
                    'max_interest_rate': result['max_interest_rate']
                }
            
            return stats
        except Exception as e:
            raise ValidationException(f"Error getting plan statistics: {str(e)}")
    
    def _dict_to_deposit_plan(self, plan_data: dict) -> DepositPlan:
        """Convert dictionary to DepositPlan object"""
        return DepositPlan(
            plan_id=plan_data['plan_id'],
            plan_type=PlanType(plan_data['plan_type']),
            plan_name=plan_data['plan_name'],
            tenure_months=plan_data['tenure_months'],
            interest_rate=plan_data['interest_rate'],
            min_amount=plan_data['min_amount'],
            max_amount=plan_data.get('max_amount'),
            penalty_rate=plan_data.get('penalty_rate'),
            is_active=bool(plan_data['is_active']),
            created_at=plan_data.get('created_at')
        )