"""
Authentication Service
Business logic for user authentication and security operations
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets

from core.repositories.user_repository import UserRepository
from core.repositories.otp_repository import OTPRepository
from core.repositories.customer_repository import CustomerRepository
from core.models.entities import User, UserRole, Customer, RegistrationStatus
from utils.exceptions import (
    AuthenticationException, ValidationException, 
    InvalidOTPException, AuthorizationException
)
from utils.validators import BankingValidator
from utils.helpers import SecurityUtils, LoggingUtils

class AuthenticationService:
    """Service class for authentication and security operations"""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.otp_repo = OTPRepository()
        self.customer_repo = CustomerRepository()
        from core.services.account_service import AccountService
        self.account_svc = AccountService()
        self.active_sessions = {}  # In production, use Redis or database
    
    def login(self, username: str, password: str, ip_address: str = None) -> Dict[str, Any]:
        """Authenticate user login"""
        try:
            # Validate inputs
            if not username or not password:
                raise ValidationException("Username and password are required")
            
            # Authenticate user
            user = self.user_repo.authenticate(username, password)
            
            # Block users with pending registration or blocked status
            if user.registration_status and user.registration_status != 'active':
                status_messages = {
                    'pending_verification': 'Your phone number has not been verified. Please complete OTP verification.',
                    'pending_kyc': 'Your account is pending admin approval. Please wait for verification.',
                    'rejected': 'Your registration was rejected. Please contact the bank.',
                    'blocked': 'Your account has been blocked. Please contact the bank for assistance.'
                }
                msg = status_messages.get(user.registration_status, 'Account not yet activated.')
                raise AuthenticationException(msg)
            
            # Generate session token
            session_token = SecurityUtils.generate_session_token()
            session_data = {
                'user_id': user.user_id,
                'username': user.username,
                'role': user.role.value,
                'registration_status': user.registration_status,
                'login_time': datetime.now(),
                'ip_address': ip_address,
                'last_activity': datetime.now()
            }
            
            # Store session (in production, use secure session storage)
            self.active_sessions[session_token] = session_data
            
            # Log successful login
            LoggingUtils.log_security_event(
                "login_success",
                user_id=user.user_id,
                ip_address=ip_address,
                details={'username': username, 'role': user.role.value}
            )
            
            return {
                'success': True,
                'session_token': session_token,
                'user_id': user.user_id,
                'username': user.username,
                'role': user.role.value,
                'registration_status': user.registration_status,
                'login_time': session_data['login_time']
            }
            
        except AuthenticationException as e:
            # Log failed login attempt
            LoggingUtils.log_security_event(
                "login_failed",
                ip_address=ip_address,
                details={'username': username, 'error': str(e)}
            )
            raise
        except Exception as e:
            LoggingUtils.log_security_event(
                "login_error",
                ip_address=ip_address,
                details={'username': username, 'error': str(e)}
            )
            raise AuthenticationException("Login failed due to system error")
    
    def logout(self, session_token: str) -> bool:
        """Logout user and invalidate session"""
        if session_token in self.active_sessions:
            session_data = self.active_sessions[session_token]
            
            # Log logout
            LoggingUtils.log_security_event(
                "logout",
                user_id=session_data.get('user_id'),
                details={'username': session_data.get('username')}
            )
            
            # Remove session
            del self.active_sessions[session_token]
            return True
        
        return False
    
    def validate_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Validate session token and return user info"""
        if session_token not in self.active_sessions:
            return None
        
        session_data = self.active_sessions[session_token]
        
        # Check session timeout (30 minutes of inactivity)
        timeout_minutes = 30
        if datetime.now() - session_data['last_activity'] > timedelta(minutes=timeout_minutes):
            # Session expired
            del self.active_sessions[session_token]
            return None
        
        # Update last activity
        session_data['last_activity'] = datetime.now()
        
        return session_data
    
    def create_user(self, username: str, password: str, role: UserRole, 
                   created_by: int) -> Dict[str, Any]:
        """Create a new user account"""
        try:
            # Validate inputs
            if not username:
                raise ValidationException("Username is required")
            
            BankingValidator.validate_password(password)
            
            # Check if username already exists
            existing_user = self.user_repo.find_by_username(username)
            if existing_user:
                raise ValidationException("Username already exists")
            
            # Create user
            user = User(
                username=username,
                password_hash=password,  # Will be hashed by repository
                role=role,
                is_active=True
            )
            
            user_id = self.user_repo.create_user(user)
            
            # Log user creation
            LoggingUtils.log_security_event(
                "user_created",
                user_id=created_by,
                details={'new_user_id': user_id, 'username': username, 'role': role.value}
            )
            
            return {
                'user_id': user_id,
                'username': username,
                'role': role.value,
                'created': True
            }
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "user_creation_failed",
                user_id=created_by,
                details={'username': username, 'error': str(e)}
            )
            raise
    
    def register_user(self, full_name: str, phone: str, email: str,
                      dob, username: str, password: str) -> Dict[str, Any]:
        """Self-registration for new users (creates User + Customer, generates OTP)"""
        try:
            # Validate all inputs
            if not full_name or len(full_name.strip()) < 2:
                raise ValidationException("Full name must be at least 2 characters")
            if len(full_name) > 100:
                raise ValidationException("Full name cannot exceed 100 characters")
            
            BankingValidator.validate_phone(phone)
            if email:
                BankingValidator.validate_email(email)
            BankingValidator.validate_password(password)
            
            if not username or len(username) < 4 or len(username) > 30:
                raise ValidationException("Username must be 4-30 characters")
            
            import re
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                raise ValidationException("Username can only contain letters, digits, and underscores")
            
            if password.lower() == username.lower():
                raise ValidationException("Password cannot be the same as username")
            
            # Age check (must be 18+)
            from datetime import date
            if dob:
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                if age < 18:
                    raise ValidationException("You must be at least 18 years old to register")
            else:
                raise ValidationException("Date of birth is required")
            
            # Check duplicates
            existing_user = self.user_repo.find_by_username(username)
            if existing_user:
                raise ValidationException("Username already exists")
            
            existing_phone = self.user_repo.find_by_phone(phone)
            if existing_phone:
                raise ValidationException("This phone number is already registered")
            
            # Create User record (inactive, pending verification)
            user = User(
                username=username,
                password_hash=password,
                role=UserRole.CUSTOMER,
                is_active=False,
                phone=phone,
                email=email if email else None,
                registration_status=RegistrationStatus.PENDING_VERIFICATION.value
            )
            user_id = self.user_repo.create_user(user)
            
            # Create linked Customer record
            customer = Customer(
                full_name=full_name.strip(),
                dob=dob,
                phone=phone,
                email=email if email else None,
                user_id=user_id,
                kyc_status='not_started'
            )
            self.customer_repo.create_customer(customer)
            
            # Generate OTP for phone verification
            otp_code = self.otp_repo.generate_otp(user_id, expiry_minutes=5)
            
            LoggingUtils.log_security_event(
                "user_registered",
                user_id=user_id,
                details={'username': username, 'phone': phone}
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'otp_code': otp_code,  # In production: send via SMS, don't return
                'phone': phone,
                'message': 'Registration initiated. Please verify your phone number.'
            }
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "registration_failed",
                details={'username': username, 'error': str(e)}
            )
            raise
    
    def verify_registration_otp(self, user_id: int, otp_code: str) -> Dict[str, Any]:
        """Verify OTP during registration and upgrade status to pending_kyc"""
        try:
            BankingValidator.validate_otp(otp_code)
            
            is_valid = self.otp_repo.validate_otp(user_id, otp_code)
            
            if is_valid:
                # Upgrade registration status
                self.user_repo.update_registration_status(
                    user_id, RegistrationStatus.PENDING_KYC.value
                )
                
                LoggingUtils.log_security_event(
                    "registration_otp_verified",
                    user_id=user_id,
                    details={'status': 'pending_kyc'}
                )
                
                return {
                    'success': True,
                    'message': 'Phone verified successfully. Your account is pending KYC approval by a bank officer.'
                }
            else:
                raise InvalidOTPException("Invalid or expired OTP")
            
        except InvalidOTPException:
            raise
        except Exception as e:
            LoggingUtils.log_security_event(
                "registration_otp_failed",
                user_id=user_id,
                details={'error': str(e)}
            )
            raise
    
    def approve_kyc(self, user_id: int, approved_by: int) -> Dict[str, Any]:
        """Admin/Teller approves KYC — activates user account"""
        try:
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            if user.registration_status != RegistrationStatus.PENDING_KYC.value:
                raise ValidationException("User is not in pending KYC state")
            
            # Activate user
            self.user_repo.update_registration_status(
                user_id, RegistrationStatus.ACTIVE.value
            )
            self.user_repo.update(user_id, {'is_active': True})
            
            # Update customer KYC status
            customer = self.customer_repo.find_by_user_id(user_id)
            if customer:
                self.customer_repo.update_kyc_status(
                    user_id, 'verified', verified_by=approved_by
                )
            
            LoggingUtils.log_security_event(
                "kyc_approved",
                user_id=approved_by,
                details={'target_user_id': user_id, 'username': user.username}
            )

            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=approved_by,
                role='admin',
                action='KYC_APPROVE',
                details={'target_user_id': user_id, 'username': user.username}
            )
            
            # Day 2: Automatic Account Creation on Approval
            self.account_svc.initiate_savings_account(user_id)
            
            return {'success': True, 'message': f'KYC approved for {user.username}'}
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "kyc_approval_failed",
                user_id=approved_by,
                details={'target_user_id': user_id, 'error': str(e)}
            )
            raise
    
    def reject_kyc(self, user_id: int, rejected_by: int, reason: str = "") -> Dict[str, Any]:
        """Admin/Teller rejects KYC"""
        try:
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            
            self.user_repo.update_registration_status(
                user_id, RegistrationStatus.REJECTED.value
            )
            
            customer = self.customer_repo.find_by_user_id(user_id)
            if customer:
                self.customer_repo.update_kyc_status(
                    user_id, 'rejected', verified_by=rejected_by
                )
            
            LoggingUtils.log_security_event(
                "kyc_rejected",
                user_id=rejected_by,
                details={'target_user_id': user_id, 'reason': reason}
            )

            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=rejected_by,
                role='admin',
                action='KYC_REJECT',
                details={'target_user_id': user_id, 'username': user.username, 'reason': reason}
            )
            
            return {'success': True, 'message': f'KYC rejected for {user.username}'}
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "kyc_rejection_failed",
                user_id=rejected_by,
                details={'target_user_id': user_id, 'error': str(e)}
            )
            raise
    
    def approve_user(self, user_id: int, approved_by: int) -> Dict[str, Any]:
        """Admin approves a pending user — activates account"""
        try:
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            if user.registration_status not in ['pending_kyc', 'pending_verification']:
                raise ValidationException("User is not in pending state")
            
            # Activate user
            self.user_repo.update_registration_status(
                user_id, RegistrationStatus.ACTIVE.value
            )
            self.user_repo.update(user_id, {'is_active': True})
            
            # Update customer KYC status if exists
            customer = self.customer_repo.find_by_user_id(user_id)
            if customer:
                self.customer_repo.update_kyc_status(
                    user_id, 'verified', verified_by=approved_by
                )
            
            LoggingUtils.log_security_event(
                "user_approved",
                user_id=approved_by,
                details={'target_user_id': user_id, 'username': user.username}
            )

            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=approved_by,
                role='admin',
                action='USER_APPROVE',
                details={'target_user_id': user_id, 'username': user.username}
            )
            
            # Day 2: Automatic Account Creation on Approval
            self.account_svc.initiate_savings_account(user_id)
            
            return {'success': True, 'message': f'User {user.username} approved and activated'}
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "user_approval_failed",
                user_id=approved_by,
                details={'target_user_id': user_id, 'error': str(e)}
            )
            raise
    
    def block_user(self, user_id: int, blocked_by: int, reason: str = "") -> Dict[str, Any]:
        """Admin blocks a user account"""
        try:
            # Prevent admin from blocking themselves
            if user_id == blocked_by:
                raise ValidationException("You cannot block your own account")
            
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            
            # Prevent blocking the last admin
            if user.role == UserRole.ADMIN:
                admin_count = len(self.user_repo.get_users_by_role(UserRole.ADMIN))
                if admin_count <= 1:
                    raise ValidationException("Cannot block the last admin user")
            
            self.user_repo.update_registration_status(
                user_id, RegistrationStatus.BLOCKED.value
            )
            self.user_repo.update(user_id, {'is_active': False})
            
            # Invalidate all active sessions
            self._invalidate_user_sessions(user_id)
            
            LoggingUtils.log_security_event(
                "user_blocked",
                user_id=blocked_by,
                details={'target_user_id': user_id, 'username': user.username, 'reason': reason}
            )

            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=blocked_by,
                role='admin',
                action='USER_BLOCK',
                details={'target_user_id': user_id, 'username': user.username, 'reason': reason}
            )
            
            return {'success': True, 'message': f'User {user.username} has been blocked'}
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "user_blocking_failed",
                user_id=blocked_by,
                details={'target_user_id': user_id, 'error': str(e)}
            )
            raise
    
    def unblock_user(self, user_id: int, unblocked_by: int) -> Dict[str, Any]:
        """Admin unblocks a blocked user account"""
        try:
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            if user.registration_status != RegistrationStatus.BLOCKED.value:
                raise ValidationException("User is not blocked")
            
            self.user_repo.update_registration_status(
                user_id, RegistrationStatus.ACTIVE.value
            )
            self.user_repo.update(user_id, {'is_active': True})
            
            LoggingUtils.log_security_event(
                "user_unblocked",
                user_id=unblocked_by,
                details={'target_user_id': user_id, 'username': user.username}
            )

            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=unblocked_by,
                role='admin',
                action='USER_UNBLOCK',
                details={'target_user_id': user_id, 'username': user.username}
            )
            
            return {'success': True, 'message': f'User {user.username} has been unblocked'}
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "user_unblocking_failed",
                user_id=unblocked_by,
                details={'target_user_id': user_id, 'error': str(e)}
            )
            raise
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            # Get user
            user_data = self.user_repo.find_by_id(user_id)
            if not user_data:
                raise ValidationException("User not found")
            
            user = self.user_repo._dict_to_user(user_data)
            
            # Verify old password
            if not self.user_repo._verify_password(old_password, user.password_hash):
                raise AuthenticationException("Current password is incorrect")
            
            # Validate new password
            BankingValidator.validate_password(new_password)
            
            # Change password
            success = self.user_repo.change_password(user_id, new_password)
            
            if success:
                # Log password change
                LoggingUtils.log_security_event(
                    "password_changed",
                    user_id=user_id,
                    details={'username': user.username}
                )
                
                # Log to Audit
                from core.services.audit_service import AuditService
                AuditService().log(
                    actor_id=user_id,
                    role='user',
                    action='PASSWORD_CHANGE',
                    details={'username': user.username}
                )
                
                # Invalidate all sessions for this user
                self._invalidate_user_sessions(user_id)
            
            return success
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "password_change_failed",
                user_id=user_id,
                details={'error': str(e)}
            )
            raise
    
    def generate_otp(self, user_id: int, operation_type: str = "general") -> str:
        """Generate OTP for user"""
        try:
            # Check rate limit
            if not self.otp_repo.check_rate_limit(user_id):
                raise ValidationException("Too many OTP requests. Please try again later.")
            
            # Generate OTP
            otp_code = self.otp_repo.generate_otp(user_id, expiry_minutes=5)
            
            # Log OTP generation
            LoggingUtils.log_security_event(
                "otp_generated",
                user_id=user_id,
                details={'operation_type': operation_type}
            )
            
            return otp_code
            
        except Exception as e:
            LoggingUtils.log_security_event(
                "otp_generation_failed",
                user_id=user_id,
                details={'error': str(e), 'operation_type': operation_type}
            )
            raise
    
    def validate_otp(self, user_id: int, otp_code: str, operation_type: str = "general") -> bool:
        """Validate OTP for user"""
        try:
            # Validate OTP format
            BankingValidator.validate_otp(otp_code)
            
            # Validate OTP
            is_valid = self.otp_repo.validate_otp(user_id, otp_code)
            
            # Log OTP validation
            LoggingUtils.log_security_event(
                "otp_validated" if is_valid else "otp_validation_failed",
                user_id=user_id,
                details={'operation_type': operation_type, 'valid': is_valid}
            )
            
            return is_valid
            
        except InvalidOTPException as e:
            LoggingUtils.log_security_event(
                "otp_validation_failed",
                user_id=user_id,
                details={'error': str(e), 'operation_type': operation_type}
            )
            raise
        except Exception as e:
            LoggingUtils.log_security_event(
                "otp_validation_error",
                user_id=user_id,
                details={'error': str(e), 'operation_type': operation_type}
            )
            raise
    
    def check_permission(self, session_token: str, required_role: UserRole) -> bool:
        """Check if user has required permission"""
        session_data = self.validate_session(session_token)
        if not session_data:
            raise AuthenticationException("Invalid or expired session")
        
        user_role = UserRole(session_data['role'])
        
        # Role hierarchy: ADMIN > CUSTOMER
        role_hierarchy = {
            UserRole.CUSTOMER: 1,
            UserRole.ADMIN: 2
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        has_permission = user_level >= required_level
        
        if not has_permission:
            LoggingUtils.log_security_event(
                "permission_denied",
                user_id=session_data['user_id'],
                details={
                    'required_role': required_role.value,
                    'user_role': user_role.value
                }
            )
        
        return has_permission
    
    def get_user_info(self, session_token: str) -> Dict[str, Any]:
        """Get user information from session"""
        session_data = self.validate_session(session_token)
        if not session_data:
            raise AuthenticationException("Invalid or expired session")
        
        return {
            'user_id': session_data['user_id'],
            'username': session_data['username'],
            'role': session_data['role'],
            'login_time': session_data['login_time'],
            'last_activity': session_data['last_activity']
        }
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of active sessions (admin only)"""
        sessions = []
        for token, data in self.active_sessions.items():
            sessions.append({
                'session_token': token[:8] + "...",  # Masked token
                'user_id': data['user_id'],
                'username': data['username'],
                'role': data['role'],
                'login_time': data['login_time'],
                'last_activity': data['last_activity'],
                'ip_address': data.get('ip_address')
            })
        
        return sessions
    
    def force_logout(self, user_id: int, performed_by: int) -> int:
        """Force logout all sessions for a user (admin only)"""
        count = self._invalidate_user_sessions(user_id)
        
        LoggingUtils.log_security_event(
            "force_logout",
            user_id=performed_by,
            details={'target_user_id': user_id, 'sessions_terminated': count}
        )

        # Log to Audit
        from core.services.audit_service import AuditService
        AuditService().log(
            actor_id=performed_by,
            role='admin',
            action='FORCE_LOGOUT',
            details={'target_user_id': user_id, 'sessions_terminated': count}
        )
        
        return count
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        expired_tokens = []
        timeout_minutes = 30
        
        for token, data in self.active_sessions.items():
            if datetime.now() - data['last_activity'] > timedelta(minutes=timeout_minutes):
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.active_sessions[token]
        
        if len(expired_tokens) > 0:
            # Log to Audit
            from core.services.audit_service import AuditService
            AuditService().log(
                actor_id=0, # System action
                role='system',
                action='SESSION_CLEANUP',
                details={'tokens_removed': len(expired_tokens)}
            )
        
        return len(expired_tokens)
    
    def _invalidate_user_sessions(self, user_id: int) -> int:
        """Invalidate all sessions for a specific user"""
        tokens_to_remove = []
        
        for token, data in self.active_sessions.items():
            if data['user_id'] == user_id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self.active_sessions[token]
        
        return len(tokens_to_remove)