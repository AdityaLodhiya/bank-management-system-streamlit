"""
Input Validation Utilities
Provides validation functions for banking system inputs
"""

import re
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from utils.exceptions import ValidationException

class BankingValidator:
    """Validation utilities for banking operations"""
    
    @staticmethod
    def validate_amount(amount: Decimal, min_amount: Decimal = None, max_amount: Decimal = None) -> bool:
        """Validate monetary amount"""
        if not isinstance(amount, Decimal):
            raise ValidationException("Amount must be a Decimal")
        
        if amount <= 0:
            raise ValidationException("Amount must be positive")
        
        if min_amount and amount < min_amount:
            raise ValidationException(f"Amount must be at least {min_amount}")
        
        if max_amount and amount > max_amount:
            raise ValidationException(f"Amount cannot exceed {max_amount}")
        
        # Check decimal places (max 2 for currency)
        if amount.as_tuple().exponent < -2:
            raise ValidationException("Amount cannot have more than 2 decimal places")
        
        return True
    
    @staticmethod
    def validate_account_number(account_number: str) -> bool:
        """Validate account number format"""
        if not account_number:
            raise ValidationException("Account number is required")
        
        if not isinstance(account_number, str):
            raise ValidationException("Account number must be a string")
        
        # Account number should be alphanumeric, 6-20 characters
        if not re.match(r'^[A-Za-z0-9]{6,20}$', account_number):
            raise ValidationException("Account number must be 6-20 alphanumeric characters")
        
        return True
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number"""
        if not phone:
            raise ValidationException("Phone number is required")
        
        # Indian phone number format: 10 digits
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise ValidationException("Phone number must be 10 digits starting with 6-9")
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address"""
        if not email:
            return True  # Email is optional
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationException("Invalid email format")
        
        return True
    
    @staticmethod
    def validate_name(name: str, field_name: str = "Name") -> bool:
        """Validate person name"""
        if not name:
            raise ValidationException(f"{field_name} is required")
        
        if not isinstance(name, str):
            raise ValidationException(f"{field_name} must be a string")
        
        if len(name.strip()) < 2:
            raise ValidationException(f"{field_name} must be at least 2 characters")
        
        if len(name.strip()) > 100:
            raise ValidationException(f"{field_name} cannot exceed 100 characters")
        
        # Allow letters, spaces, dots, apostrophes
        if not re.match(r"^[a-zA-Z\s.']+$", name.strip()):
            raise ValidationException(f"{field_name} can only contain letters, spaces, dots, and apostrophes")
        
        return True
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """Validate password strength"""
        if not password:
            raise ValidationException("Password is required")
        
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters")
        
        if len(password) > 128:
            raise ValidationException("Password cannot exceed 128 characters")
        
        # Check for at least one uppercase, lowercase, digit, and special character
        if not re.search(r'[A-Z]', password):
            raise ValidationException("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            raise ValidationException("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            raise ValidationException("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationException("Password must contain at least one special character")
        
        return True
    
    @staticmethod
    def validate_date_of_birth(dob: date) -> bool:
        """Validate date of birth"""
        if not dob:
            raise ValidationException("Date of birth is required")
        
        if not isinstance(dob, date):
            raise ValidationException("Date of birth must be a date object")
        
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        if age < 18:
            raise ValidationException("Customer must be at least 18 years old")
        
        if age > 120:
            raise ValidationException("Invalid date of birth")
        
        return True
    
    @staticmethod
    def validate_tenure(tenure_months: int, min_tenure: int = 1, max_tenure: int = 360) -> bool:
        """Validate loan/deposit tenure"""
        if not isinstance(tenure_months, int):
            raise ValidationException("Tenure must be an integer")
        
        if tenure_months < min_tenure:
            raise ValidationException(f"Tenure must be at least {min_tenure} months")
        
        if tenure_months > max_tenure:
            raise ValidationException(f"Tenure cannot exceed {max_tenure} months")
        
        return True
    
    @staticmethod
    def validate_interest_rate(rate: Decimal, min_rate: Decimal = Decimal('0.1'), max_rate: Decimal = Decimal('50.0')) -> bool:
        """Validate interest rate"""
        if not isinstance(rate, Decimal):
            raise ValidationException("Interest rate must be a Decimal")
        
        if rate < min_rate:
            raise ValidationException(f"Interest rate must be at least {min_rate}%")
        
        if rate > max_rate:
            raise ValidationException(f"Interest rate cannot exceed {max_rate}%")
        
        return True
    
    @staticmethod
    def validate_credit_score(score: int) -> bool:
        """Validate credit score"""
        if not isinstance(score, int):
            raise ValidationException("Credit score must be an integer")
        
        if score < 300 or score > 850:
            raise ValidationException("Credit score must be between 300 and 850")
        
        return True
    
    @staticmethod
    def validate_otp(otp: str) -> bool:
        """Validate OTP format"""
        if not otp:
            raise ValidationException("OTP is required")
        
        if not isinstance(otp, str):
            raise ValidationException("OTP must be a string")
        
        if not re.match(r'^\d{6}$', otp):
            raise ValidationException("OTP must be exactly 6 digits")
        
        return True
    
    @staticmethod
    def validate_transaction_reference(reference: str) -> bool:
        """Validate transaction reference number"""
        if not reference:
            raise ValidationException("Transaction reference is required")
        
        if not isinstance(reference, str):
            raise ValidationException("Transaction reference must be a string")
        
        if len(reference) < 6 or len(reference) > 50:
            raise ValidationException("Transaction reference must be 6-50 characters")
        
        # Alphanumeric with some special characters allowed
        if not re.match(r'^[A-Za-z0-9\-_]+$', reference):
            raise ValidationException("Transaction reference can only contain letters, numbers, hyphens, and underscores")
        
        return True

class BusinessRuleValidator:
    """Business rule validation for banking operations"""
    
    @staticmethod
    def validate_minimum_balance(account_type: str, balance: Decimal) -> Decimal:
        """Get minimum balance requirement for account type"""
        min_balances = {
            'savings': Decimal('500.00'),
            'current': Decimal('1000.00'),
            'salary': Decimal('0.00')
        }
        
        return min_balances.get(account_type.lower(), Decimal('500.00'))
    
    @staticmethod
    def validate_overdraft_limit(account_type: str, monthly_income: Decimal = None) -> Decimal:
        """Calculate overdraft limit based on account type and income"""
        if account_type.lower() != 'current':
            return Decimal('0.00')
        
        if monthly_income:
            # Overdraft limit = 3x monthly income, max 100,000
            limit = min(monthly_income * 3, Decimal('100000.00'))
            return limit
        
        # Default overdraft for current accounts
        return Decimal('10000.00')
    
    @staticmethod
    def validate_loan_eligibility(monthly_income: Decimal, existing_emi: Decimal, 
                                requested_emi: Decimal, credit_score: int) -> Dict[str, Any]:
        """Validate loan eligibility based on income and credit score"""
        total_emi = existing_emi + requested_emi
        emi_ratio = (total_emi / monthly_income) * 100
        
        # Maximum EMI ratio: 50% of income
        max_emi_ratio = Decimal('50.0')
        
        # Minimum credit score: 650
        min_credit_score = 650
        
        eligible = True
        reasons = []
        
        if emi_ratio > max_emi_ratio:
            eligible = False
            reasons.append(f"EMI ratio ({emi_ratio:.1f}%) exceeds maximum allowed ({max_emi_ratio}%)")
        
        if credit_score < min_credit_score:
            eligible = False
            reasons.append(f"Credit score ({credit_score}) below minimum required ({min_credit_score})")
        
        return {
            'eligible': eligible,
            'emi_ratio': emi_ratio,
            'reasons': reasons,
            'max_loan_amount': monthly_income * max_emi_ratio / 100 * 12 * 5  # Rough estimate
        }