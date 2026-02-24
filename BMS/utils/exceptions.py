"""
Custom Exceptions for SecureCore Banking System
"""

class BankingSystemException(Exception):
    """Base exception for all banking system errors"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class ValidationException(BankingSystemException):
    """Raised when input validation fails"""
    pass

class InsufficientFundsException(BankingSystemException):
    """Raised when account has insufficient funds for operation"""
    pass

class AccountNotFoundException(BankingSystemException):
    """Raised when referenced account does not exist"""
    pass

class CustomerNotFoundException(BankingSystemException):
    """Raised when referenced customer does not exist"""
    pass

class DatabaseException(BankingSystemException):
    """Raised when database operations fail"""
    pass

class AuthenticationException(BankingSystemException):
    """Raised when authentication fails"""
    pass

class AuthorizationException(BankingSystemException):
    """Raised when user lacks permission for operation"""
    pass

class AccountFrozenException(BankingSystemException):
    """Raised when trying to operate on frozen account"""
    pass

class InvalidTransactionException(BankingSystemException):
    """Raised when transaction is invalid"""
    pass

class LoanNotFoundException(BankingSystemException):
    """Raised when referenced loan does not exist"""
    pass

class InvalidOTPException(BankingSystemException):
    """Raised when OTP is invalid or expired"""
    pass

class PlanNotFoundException(BankingSystemException):
    """Raised when deposit/loan plan not found"""
    pass