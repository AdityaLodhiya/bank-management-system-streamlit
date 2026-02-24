"""
User Repository
Handles database operations for users table
"""

from typing import Optional, List
import bcrypt
from datetime import datetime, timedelta

from core.repositories.base_repository import BaseRepository
from core.models.entities import User, UserRole
from utils.exceptions import AuthenticationException, ValidationException

class UserRepository(BaseRepository):
    """Repository for users table operations"""
    
    def __init__(self):
        super().__init__('users', 'user_id')
    
    def create_user(self, user: User) -> int:
        """Create a new user with hashed password"""
        if not user.username or not user.password_hash:
            raise ValidationException("Username and password are required")
        
        # Hash password if not already hashed
        if not user.password_hash.startswith('$2b$'):
            user.password_hash = self._hash_password(user.password_hash)
        
        user_data = {
            'username': user.username,
            'password_hash': user.password_hash,
            'role': user.role.value if isinstance(user.role, UserRole) else user.role,
            'is_active': user.is_active,
            'failed_attempts': user.failed_attempts
        }
        
        # Include registration fields if present
        if user.phone:
            user_data['phone'] = user.phone
        if user.email:
            user_data['email'] = user.email
        if user.registration_status:
            user_data['registration_status'] = user.registration_status
        
        return self.create(user_data)
    
    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        if not username:
            return None
        
        users = self.find_by_field('username', username)
        if not users:
            return None
        
        user_data = users[0]
        return self._dict_to_user(user_data)
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = self.find_by_username(username)
        if not user:
            raise AuthenticationException("Invalid username or password")
        
        if not user.is_active:
            raise AuthenticationException("Account is deactivated")
        
        if user.locked_until and user.locked_until > datetime.now():
            raise AuthenticationException(f"Account is locked until {user.locked_until}")
        
        if not self._verify_password(password, user.password_hash):
            self._increment_failed_attempts(user.user_id)
            raise AuthenticationException("Invalid username or password")
        
        # Reset failed attempts on successful login
        if user.failed_attempts > 0:
            self._reset_failed_attempts(user.user_id)
        
        return user
    
    def update_failed_attempts(self, user_id: int, attempts: int) -> bool:
        """Update failed login attempts"""
        return self.update(user_id, {'failed_attempts': attempts})
    
    def lock_user(self, user_id: int, lock_duration_minutes: int = 30) -> bool:
        """Lock user account for specified duration"""
        lock_until = datetime.now() + timedelta(minutes=lock_duration_minutes)
        return self.update(user_id, {
            'locked_until': lock_until,
            'failed_attempts': 0
        })
    
    def unlock_user(self, user_id: int) -> bool:
        """Unlock user account"""
        return self.update(user_id, {
            'locked_until': None,
            'failed_attempts': 0
        })
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change user password"""
        hashed_password = self._hash_password(new_password)
        return self.update(user_id, {'password_hash': hashed_password})
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user account"""
        return self.update(user_id, {'is_active': False})
    
    def activate_user(self, user_id: int) -> bool:
        """Activate user account"""
        return self.update(user_id, {'is_active': True})
    
    def get_active_users(self) -> List[User]:
        """Get all active users"""
        users_data = self.find_by_field('is_active', True)
        return [self._dict_to_user(user_data) for user_data in users_data]
    
    def get_users_by_role(self, role: UserRole) -> List[User]:
        """Get users by role"""
        role_value = role.value if isinstance(role, UserRole) else role
        users_data = self.find_by_field('role', role_value)
        return [self._dict_to_user(user_data) for user_data in users_data]
    
    def find_by_phone(self, phone: str) -> Optional[User]:
        """Find user by phone number"""
        if not phone:
            return None
        users = self.find_by_field('phone', phone)
        if not users:
            return None
        return self._dict_to_user(users[0])
    
    def get_pending_registrations(self) -> List[User]:
        """Get all users in pending_kyc status"""
        users_data = self.find_by_field('registration_status', 'pending_kyc')
        return [self._dict_to_user(user_data) for user_data in users_data]
    
    def update_registration_status(self, user_id: int, status: str) -> bool:
        """Update user registration status"""
        return self.update(user_id, {'registration_status': status})
    
    def get_all(self) -> List[User]:
        """Get all users (for admin user management)"""
        users_data = self.find_all()
        return [self._dict_to_user(user_data) for user_data in users_data]
    
    def get_users_by_status(self, status: str) -> List[User]:
        """Get users by registration status"""
        users_data = self.find_by_field('registration_status', status)
        return [self._dict_to_user(user_data) for user_data in users_data]
    
    def _increment_failed_attempts(self, user_id: int):
        """Increment failed login attempts"""
        user_data = self.find_by_id(user_id)
        if user_data:
            new_attempts = user_data['failed_attempts'] + 1
            self.update_failed_attempts(user_id, new_attempts)
            
            # Lock account after 5 failed attempts
            if new_attempts >= 5:
                self.lock_user(user_id, 30)  # Lock for 30 minutes
    
    def _reset_failed_attempts(self, user_id: int):
        """Reset failed login attempts"""
        self.update_failed_attempts(user_id, 0)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def _dict_to_user(self, user_data: dict) -> User:
        """Convert dictionary to User object"""
        return User(
            user_id=user_data['user_id'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            role=UserRole(user_data['role']),
            is_active=bool(user_data['is_active']),
            failed_attempts=user_data['failed_attempts'],
            locked_until=user_data.get('locked_until'),
            phone=user_data.get('phone'),
            email=user_data.get('email'),
            registration_status=user_data.get('registration_status', 'active'),
            registered_at=user_data.get('registered_at'),
            created_at=user_data.get('created_at')
        )