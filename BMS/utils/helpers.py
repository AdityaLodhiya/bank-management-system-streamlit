"""
Helper Utilities
Common utility functions for banking operations
"""

import uuid
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class NumberUtils:
    """Utility functions for number operations"""
    
    @staticmethod
    def round_currency(amount: Decimal) -> Decimal:
        """Round amount to 2 decimal places for currency"""
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_percentage(amount: Decimal, percentage: Decimal) -> Decimal:
        """Calculate percentage of an amount"""
        result = amount * (percentage / 100)
        return NumberUtils.round_currency(result)
    
    @staticmethod
    def calculate_compound_interest(principal: Decimal, rate: Decimal, 
                                  time_years: Decimal, compound_frequency: int = 1) -> Decimal:
        """Calculate compound interest"""
        # A = P(1 + r/n)^(nt)
        rate_decimal = rate / 100
        compound_rate = Decimal(1) + (rate_decimal / compound_frequency)
        exponent = compound_frequency * time_years
        
        # Convert to float for power operation, then back to Decimal
        amount = Decimal(str(float(principal) * (float(compound_rate) ** float(exponent))))
        return NumberUtils.round_currency(amount)
    
    @staticmethod
    def calculate_simple_interest(principal: Decimal, rate: Decimal, time_years: Decimal) -> Decimal:
        """Calculate simple interest"""
        # SI = P * R * T / 100
        interest = principal * rate * time_years / 100
        return NumberUtils.round_currency(interest)
    
    @staticmethod
    def calculate_emi(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> Decimal:
        """Calculate EMI using standard formula"""
        if annual_rate == 0:
            return NumberUtils.round_currency(principal / tenure_months)
        
        monthly_rate = annual_rate / (12 * 100)  # Convert to monthly decimal rate
        
        # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        power_term = (1 + monthly_rate) ** tenure_months
        emi = principal * monthly_rate * power_term / (power_term - 1)
        
        return NumberUtils.round_currency(emi)

class DateUtils:
    """Utility functions for date operations"""
    
    @staticmethod
    def add_months(start_date: date, months: int) -> date:
        """Add months to a date"""
        from dateutil.relativedelta import relativedelta
        return start_date + relativedelta(months=months)
    
    @staticmethod
    def add_years(start_date: date, years: int) -> date:
        """Add years to a date"""
        from dateutil.relativedelta import relativedelta
        return start_date + relativedelta(years=years)
    
    @staticmethod
    def get_age(birth_date: date, reference_date: date = None) -> int:
        """Calculate age from birth date"""
        if reference_date is None:
            reference_date = date.today()
        
        age = reference_date.year - birth_date.year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    @staticmethod
    def get_business_days_between(start_date: date, end_date: date) -> int:
        """Calculate business days between two dates (excluding weekends)"""
        current_date = start_date
        business_days = 0
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                business_days += 1
            current_date += timedelta(days=1)
        
        return business_days
    
    @staticmethod
    def is_business_day(check_date: date) -> bool:
        """Check if date is a business day (Monday-Friday)"""
        return check_date.weekday() < 5
    
    @staticmethod
    def get_next_business_day(start_date: date) -> date:
        """Get next business day"""
        next_date = start_date + timedelta(days=1)
        while not DateUtils.is_business_day(next_date):
            next_date += timedelta(days=1)
        return next_date
    
    @staticmethod
    def get_month_end(check_date: date) -> date:
        """Get last day of the month"""
        from dateutil.relativedelta import relativedelta
        next_month = check_date.replace(day=1) + relativedelta(months=1)
        return next_month - timedelta(days=1)

class StringUtils:
    """Utility functions for string operations"""
    
    @staticmethod
    def generate_reference_number(prefix: str = "TXN") -> str:
        """Generate unique reference number"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{prefix}{timestamp}{unique_id}"
    
    @staticmethod
    def generate_account_number(prefix: str = "ACC") -> str:
        """Generate unique account number"""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:6].upper()
        return f"{prefix}{timestamp}{unique_id}"
    
    @staticmethod
    def mask_account_number(account_number: str) -> str:
        """Mask account number for display (show only last 4 digits)"""
        if len(account_number) <= 4:
            return account_number
        
        masked_part = "*" * (len(account_number) - 4)
        return masked_part + account_number[-4:]
    
    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """Mask phone number for display"""
        if len(phone) <= 4:
            return phone
        
        return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]
    
    @staticmethod
    def format_currency(amount: Decimal, currency_symbol: str = "₹") -> str:
        """Format amount as currency string"""
        # Indian number format with commas
        amount_str = f"{amount:,.2f}"
        return f"{currency_symbol}{amount_str}"
    
    @staticmethod
    def clean_string(text: str) -> str:
        """Clean and normalize string input"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        return " ".join(text.strip().split())

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_hash(data: str, salt: str = "") -> str:
        """Generate SHA-256 hash of data"""
        combined = f"{data}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return str(uuid.uuid4())
    
    @staticmethod
    def is_strong_password(password: str) -> Dict[str, Any]:
        """Check password strength and return detailed analysis"""
        checks = {
            'length': len(password) >= 8,
            'uppercase': any(c.isupper() for c in password),
            'lowercase': any(c.islower() for c in password),
            'digit': any(c.isdigit() for c in password),
            'special': any(c in "!@#$%^&*(),.?\":{}|<>" for c in password),
            'no_common': password.lower() not in ['password', '12345678', 'qwerty123']
        }
        
        strength_score = sum(checks.values())
        
        if strength_score >= 6:
            strength = "Strong"
        elif strength_score >= 4:
            strength = "Medium"
        else:
            strength = "Weak"
        
        return {
            'strength': strength,
            'score': strength_score,
            'checks': checks,
            'suggestions': SecurityUtils._get_password_suggestions(checks)
        }
    
    @staticmethod
    def _get_password_suggestions(checks: Dict[str, bool]) -> list:
        """Get password improvement suggestions"""
        suggestions = []
        
        if not checks['length']:
            suggestions.append("Use at least 8 characters")
        if not checks['uppercase']:
            suggestions.append("Add uppercase letters")
        if not checks['lowercase']:
            suggestions.append("Add lowercase letters")
        if not checks['digit']:
            suggestions.append("Add numbers")
        if not checks['special']:
            suggestions.append("Add special characters")
        if not checks['no_common']:
            suggestions.append("Avoid common passwords")
        
        return suggestions

class LoggingUtils:
    """Logging utility functions"""
    
    @staticmethod
    def log_transaction(transaction_type: str, account_id: int, amount: Decimal, 
                       user_id: int = None, details: Dict[str, Any] = None):
        """Log transaction for audit trail"""
        log_data = {
            'transaction_type': transaction_type,
            'account_id': account_id,
            'amount': str(amount),
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"Transaction: {transaction_type}", extra=log_data)
    
    @staticmethod
    def log_security_event(event_type: str, user_id: int = None, 
                          ip_address: str = None, details: Dict[str, Any] = None):
        """Log security events"""
        log_data = {
            'event_type': event_type,
            'user_id': user_id,
            'ip_address': ip_address,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        
        logger.warning(f"Security Event: {event_type}", extra=log_data)
    
    @staticmethod
    def log_business_event(event_type: str, entity_type: str, entity_id: int,
                          user_id: int = None, details: Dict[str, Any] = None):
        """Log business events"""
        log_data = {
            'event_type': event_type,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"Business Event: {event_type}", extra=log_data)