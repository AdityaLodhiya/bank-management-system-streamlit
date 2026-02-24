"""
OTP Repository
Handles database operations for otp_log table
"""

from typing import Optional, List
from datetime import datetime, timedelta
import random
import string

from core.repositories.base_repository import BaseRepository
from core.models.entities import OTPLog
from utils.exceptions import ValidationException, InvalidOTPException

class OTPRepository(BaseRepository):
    """Repository for otp_log table operations"""
    
    def __init__(self):
        super().__init__('otp_log', 'otp_id')
    
    def generate_otp(self, user_id: int, expiry_minutes: int = 5) -> str:
        """Generate and store a new OTP"""
        if not user_id:
            raise ValidationException("User ID is required")
        
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Set expiry time
        expires_at = datetime.now() + timedelta(minutes=expiry_minutes)
        
        otp_data = {
            'user_id': user_id,
            'otp_code': otp_code,
            'created_at': datetime.now(),
            'expires_at': expires_at,
            'is_used': False
        }
        
        self.create(otp_data)
        return otp_code
    
    def validate_otp(self, user_id: int, otp_code: str) -> bool:
        """Validate OTP and mark as used if valid"""
        if not user_id or not otp_code:
            raise ValidationException("User ID and OTP code are required")
        
        try:
            # Find the most recent unused OTP for the user
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s AND otp_code = %s AND is_used = 0
                ORDER BY created_at DESC 
                LIMIT 1
            """
            result = self.db.execute_query(query, (user_id, otp_code), fetch_one=True)
            
            if not result:
                raise InvalidOTPException("Invalid OTP code")
            
            # Check if OTP has expired
            if datetime.now() > result['expires_at']:
                raise InvalidOTPException("OTP has expired")
            
            # Mark OTP as used
            self.update(result['otp_id'], {
                'is_used': True,
                'used_at': datetime.now()
            })
            
            return True
            
        except InvalidOTPException:
            raise
        except Exception as e:
            raise ValidationException(f"Error validating OTP: {str(e)}")
    
    def find_otp_by_id(self, otp_id: int) -> Optional[OTPLog]:
        """Find OTP by ID"""
        otp_data = self.find_by_id(otp_id)
        if not otp_data:
            return None
        
        return self._dict_to_otp_log(otp_data)
    
    def get_user_otps(self, user_id: int, limit: int = 10) -> List[OTPLog]:
        """Get OTP history for a user"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit), fetch_all=True)
            return [self._dict_to_otp_log(otp_data) for otp_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting user OTPs: {str(e)}")
    
    def get_active_otp(self, user_id: int) -> Optional[OTPLog]:
        """Get the most recent active (unused, non-expired) OTP for a user"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s 
                AND is_used = 0 
                AND expires_at > NOW()
                ORDER BY created_at DESC 
                LIMIT 1
            """
            result = self.db.execute_query(query, (user_id,), fetch_one=True)
            return self._dict_to_otp_log(result) if result else None
        except Exception as e:
            raise ValidationException(f"Error getting active OTP: {str(e)}")
    
    def cleanup_expired_otps(self) -> int:
        """Clean up expired OTPs (older than 24 hours)"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            query = f"DELETE FROM {self.table_name} WHERE expires_at < %s"
            
            # Get count before deletion
            count_query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE expires_at < %s"
            count_result = self.db.execute_query(count_query, (cutoff_time,), fetch_one=True)
            deleted_count = count_result['count'] if count_result else 0
            
            # Delete expired OTPs
            self.db.execute_query(query, (cutoff_time,))
            
            return deleted_count
        except Exception as e:
            raise ValidationException(f"Error cleaning up expired OTPs: {str(e)}")
    
    def invalidate_user_otps(self, user_id: int) -> bool:
        """Invalidate all active OTPs for a user"""
        try:
            query = f"""
                UPDATE {self.table_name} 
                SET is_used = 1, used_at = NOW() 
                WHERE user_id = %s AND is_used = 0
            """
            self.db.execute_query(query, (user_id,))
            return True
        except Exception as e:
            raise ValidationException(f"Error invalidating user OTPs: {str(e)}")
    
    def get_otp_statistics(self, days: int = 30) -> dict:
        """Get OTP usage statistics for the last N days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_generated,
                    COUNT(CASE WHEN is_used = 1 THEN 1 END) as total_used,
                    COUNT(CASE WHEN expires_at < NOW() AND is_used = 0 THEN 1 END) as total_expired,
                    AVG(CASE WHEN is_used = 1 THEN 
                        TIMESTAMPDIFF(SECOND, created_at, used_at) 
                        ELSE NULL END) as avg_usage_time_seconds
                FROM {self.table_name}
                WHERE created_at >= %s
            """
            result = self.db.execute_query(query, (cutoff_date,), fetch_one=True)
            
            if result:
                total_generated = result['total_generated'] or 0
                total_used = result['total_used'] or 0
                
                return {
                    'total_generated': total_generated,
                    'total_used': total_used,
                    'total_expired': result['total_expired'] or 0,
                    'usage_rate': (total_used / total_generated * 100) if total_generated > 0 else 0,
                    'avg_usage_time_seconds': result['avg_usage_time_seconds'] or 0
                }
            else:
                return {
                    'total_generated': 0,
                    'total_used': 0,
                    'total_expired': 0,
                    'usage_rate': 0,
                    'avg_usage_time_seconds': 0
                }
        except Exception as e:
            raise ValidationException(f"Error getting OTP statistics: {str(e)}")
    
    def check_rate_limit(self, user_id: int, max_otps_per_hour: int = 5) -> bool:
        """Check if user has exceeded OTP generation rate limit"""
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            query = f"""
                SELECT COUNT(*) as count 
                FROM {self.table_name} 
                WHERE user_id = %s AND created_at >= %s
            """
            result = self.db.execute_query(query, (user_id, one_hour_ago), fetch_one=True)
            
            count = result['count'] if result else 0
            return count < max_otps_per_hour
        except Exception as e:
            raise ValidationException(f"Error checking rate limit: {str(e)}")
    
    def _dict_to_otp_log(self, otp_data: dict) -> OTPLog:
        """Convert dictionary to OTPLog object"""
        return OTPLog(
            otp_id=otp_data['otp_id'],
            user_id=otp_data['user_id'],
            otp_code=otp_data['otp_code'],
            created_at=otp_data.get('created_at'),
            expires_at=otp_data.get('expires_at'),
            is_used=bool(otp_data['is_used']),
            used_at=otp_data.get('used_at')
        )