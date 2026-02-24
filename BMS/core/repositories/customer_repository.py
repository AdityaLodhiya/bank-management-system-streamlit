"""
Customer Repository
Handles database operations for customers table
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal

from core.repositories.base_repository import BaseRepository
from core.models.entities import Customer, EmploymentType, RiskProfile
from utils.exceptions import CustomerNotFoundException, ValidationException

class CustomerRepository(BaseRepository):
    """Repository for customers table operations"""
    
    def __init__(self):
        super().__init__('customers', 'user_id', auto_increment=False)
    
    def create_customer(self, customer: Customer) -> int:
        """Create a new customer"""
        if not customer.full_name:
            raise ValidationException("Customer name is required")
        
        customer_data = {
            'full_name': customer.full_name,
            'dob': customer.dob,
            'phone': customer.phone,
            'email': customer.email,
            'govt_id': customer.govt_id,
            'address': customer.address,
            'employment_type': customer.employment_type.value if customer.employment_type else None,
            'monthly_income': customer.monthly_income,
            'risk_profile': customer.risk_profile.value if customer.risk_profile else None
        }
        
        if customer.kyc_status:
            customer_data['kyc_status'] = customer.kyc_status
        
        # In the refactored system, customer.user_id IS the primary identifier.
        # If it's not set, it will be auto-inserted if DB handles it, 
        # but usually it's set from the User registration.
        if customer.user_id:
            customer_data['user_id'] = customer.user_id
        
        return self.create(customer_data)
    
    def find_customer_by_id(self, user_id: int) -> Optional[Customer]:
        """Find customer by user ID"""
        customer_data = self.find_by_id(user_id)
        if not customer_data:
            return None
        
        return self._dict_to_customer(customer_data)
    
    def find_by_phone(self, phone: str) -> Optional[Customer]:
        """Find customer by phone number"""
        if not phone:
            return None
        
        customers = self.find_by_field('phone', phone)
        if not customers:
            return None
        
        return self._dict_to_customer(customers[0])
    
    def find_by_email(self, email: str) -> Optional[Customer]:
        """Find customer by email"""
        if not email:
            return None
        
        customers = self.find_by_field('email', email)
        if not customers:
            return None
        
        return self._dict_to_customer(customers[0])
    
    def find_by_govt_id(self, govt_id: str) -> Optional[Customer]:
        """Find customer by government ID"""
        if not govt_id:
            return None
        
        customers = self.find_by_field('govt_id', govt_id)
        if not customers:
            return None
        
        return self._dict_to_customer(customers[0])
    
    def update_customer(self, customer: Customer) -> bool:
        """Update customer information"""
        if not customer.user_id:
            raise ValidationException("User ID is required for update")
        
        customer_data = {
            'full_name': customer.full_name,
            'dob': customer.dob,
            'phone': customer.phone,
            'email': customer.email,
            'govt_id': customer.govt_id,
            'address': customer.address,
            'employment_type': customer.employment_type.value if customer.employment_type else None,
            'monthly_income': customer.monthly_income,
            'risk_profile': customer.risk_profile.value if customer.risk_profile else None
        }
        
        return self.update(customer.user_id, customer_data)
    
    def search_customers(self, criteria: Dict[str, Any]) -> List[Customer]:
        """Search customers by multiple criteria"""
        try:
            where_conditions = []
            params = []
            
            if criteria.get('name'):
                where_conditions.append("full_name LIKE %s")
                params.append(f"%{criteria['name']}%")
            
            if criteria.get('phone'):
                where_conditions.append("phone LIKE %s")
                params.append(f"%{criteria['phone']}%")
            
            if criteria.get('email'):
                where_conditions.append("email LIKE %s")
                params.append(f"%{criteria['email']}%")
            
            if criteria.get('employment_type'):
                where_conditions.append("employment_type = %s")
                params.append(criteria['employment_type'])
            
            if criteria.get('risk_profile'):
                where_conditions.append("risk_profile = %s")
                params.append(criteria['risk_profile'])
            
            if not where_conditions:
                return self.get_all_customers()
            
            where_clause = " AND ".join(where_conditions)
            query = f"SELECT * FROM {self.table_name} WHERE {where_clause}"
            
            results = self.db.execute_query(query, tuple(params), fetch_all=True)
            return [self._dict_to_customer(customer_data) for customer_data in results or []]
            
        except Exception as e:
            raise ValidationException(f"Error searching customers: {str(e)}")
    
    def get_all_customers(self, limit: int = None, offset: int = 0) -> List[Customer]:
        """Get all customers with optional pagination"""
        customers_data = self.find_all(limit, offset)
        return [self._dict_to_customer(customer_data) for customer_data in customers_data]
    
    def get_customers_by_risk_profile(self, risk_profile: RiskProfile) -> List[Customer]:
        """Get customers by risk profile"""
        customers_data = self.find_by_field('risk_profile', risk_profile.value)
        return [self._dict_to_customer(customer_data) for customer_data in customers_data]
    
    def get_customers_by_employment_type(self, employment_type: EmploymentType) -> List[Customer]:
        """Get customers by employment type"""
        customers_data = self.find_by_field('employment_type', employment_type.value)
        return [self._dict_to_customer(customer_data) for customer_data in customers_data]
    
    def update_risk_profile(self, user_id: int, risk_profile: RiskProfile) -> bool:
        """Update customer risk profile"""
        return self.update(user_id, {'risk_profile': risk_profile.value})
    
    def update_monthly_income(self, user_id: int, monthly_income: Decimal) -> bool:
        """Update customer monthly income"""
        return self.update(user_id, {'monthly_income': monthly_income})
    
    def customer_exists(self, user_id: int) -> bool:
        """Check if customer exists"""
        return self.exists(user_id)
    
    def get_customer_count(self) -> int:
        """Get total number of customers"""
        return self.count()
    
    def find_by_user_id(self, user_id: int) -> Optional[Customer]:
        """Find customer linked to a user account"""
        if not user_id:
            return None
        customers = self.find_by_field('user_id', user_id)
        if not customers:
            return None
        return self._dict_to_customer(customers[0])
    
    def update_kyc_status(self, user_id: int, status: str, verified_by: int = None) -> bool:
        """Update customer KYC status"""
        from datetime import datetime
        update_data = {'kyc_status': status}
        if verified_by:
            update_data['kyc_verified_by'] = verified_by
            update_data['kyc_verified_at'] = datetime.now()
        return self.update(user_id, update_data)
    
    def _dict_to_customer(self, customer_data: dict) -> Customer:
        """Convert dictionary to Customer object"""
        return Customer(
            user_id=customer_data['user_id'],
            full_name=customer_data['full_name'],
            dob=customer_data.get('dob'),
            phone=customer_data.get('phone'),
            email=customer_data.get('email'),
            govt_id=customer_data.get('govt_id'),
            address=customer_data.get('address'),
            employment_type=EmploymentType(customer_data['employment_type']) if customer_data.get('employment_type') else None,
            monthly_income=customer_data.get('monthly_income'),
            risk_profile=RiskProfile(customer_data['risk_profile']) if customer_data.get('risk_profile') else None,
            kyc_status=customer_data.get('kyc_status', 'not_started'),
            kyc_verified_by=customer_data.get('kyc_verified_by'),
            kyc_verified_at=customer_data.get('kyc_verified_at'),
            created_at=customer_data.get('created_at')
        )