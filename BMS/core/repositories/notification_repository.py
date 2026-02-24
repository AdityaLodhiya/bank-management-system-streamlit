"""
Notification Repository
Handles database operations for notifications table
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from core.repositories.base_repository import BaseRepository
from core.models.entities import Notification
from utils.exceptions import ValidationException

class NotificationRepository(BaseRepository):
    """Repository for notifications table operations"""
    
    def __init__(self):
        super().__init__('notifications', 'notification_id')
    
    def create_notification(self, notification: Notification) -> int:
        """Create a new notification"""
        if not notification.type or not notification.content:
            raise ValidationException("Notification type and content are required")
        
        notification_data = {
            'user_id': notification.user_id,
            'channel': notification.channel,
            'type': notification.type,
            'content': notification.content,
            'status': notification.status,
            'created_at': notification.created_at or datetime.now()
        }
        
        return self.create(notification_data)
    
    def find_notification_by_id(self, notification_id: int) -> Optional[Notification]:
        """Find notification by ID"""
        notification_data = self.find_by_id(notification_id)
        if not notification_data:
            return None
        
        return self._dict_to_notification(notification_data)
    
    def get_customer_notifications(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Notification]:
        """Get notifications for a customer with pagination"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """
            results = self.db.execute_query(query, (user_id, limit, offset), fetch_all=True)
            return [self._dict_to_notification(notif_data) for notif_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting customer notifications: {str(e)}")
    
    def get_notifications_by_type(self, notification_type: str, limit: int = 100) -> List[Notification]:
        """Get notifications by type"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE type = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (notification_type, limit), fetch_all=True)
            return [self._dict_to_notification(notif_data) for notif_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting notifications by type: {str(e)}")
    
    def get_notifications_by_status(self, status: str, limit: int = 100) -> List[Notification]:
        """Get notifications by status"""
        try:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE status = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (status, limit), fetch_all=True)
            return [self._dict_to_notification(notif_data) for notif_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting notifications by status: {str(e)}")
    
    def get_pending_notifications(self) -> List[Notification]:
        """Get all queued notifications waiting to be sent"""
        return self.get_notifications_by_status('queued')
    
    def get_failed_notifications(self, retry_eligible_only: bool = True) -> List[Notification]:
        """Get failed notifications, optionally only those eligible for retry"""
        try:
            if retry_eligible_only:
                # Get failed notifications from last 24 hours (eligible for retry)
                cutoff_time = datetime.now() - timedelta(hours=24)
                query = f"""
                    SELECT * FROM {self.table_name} 
                    WHERE status = 'failed' AND created_at >= %s
                    ORDER BY created_at DESC
                """
                results = self.db.execute_query(query, (cutoff_time,), fetch_all=True)
            else:
                results = self.get_notifications_by_status('failed')
            
            return [self._dict_to_notification(notif_data) for notif_data in results or []]
        except Exception as e:
            raise ValidationException(f"Error getting failed notifications: {str(e)}")
    
    def update_notification_status(self, notification_id: int, status: str) -> bool:
        """Update notification status"""
        valid_statuses = ['queued', 'sent', 'failed']
        if status not in valid_statuses:
            raise ValidationException(f"Invalid status: {status}")
        
        return self.update(notification_id, {'status': status})
    
    def mark_as_sent(self, notification_id: int) -> bool:
        """Mark notification as sent"""
        return self.update_notification_status(notification_id, 'sent')
    
    def mark_as_failed(self, notification_id: int) -> bool:
        """Mark notification as failed"""
        return self.update_notification_status(notification_id, 'failed')
    
    def create_transaction_notification(self, user_id: int, transaction_type: str, 
                                     amount: str, account_number: str, channel: str = 'sms') -> int:
        """Create a transaction notification"""
        content = f"Transaction Alert: {transaction_type} of {amount} in account {account_number}. Thank you for banking with us."
        
        notification = Notification(
            user_id=user_id,
            channel=channel,
            type='transaction_alert',
            content=content,
            status='queued'
        )
        
        return self.create_notification(notification)
    
    def create_balance_alert(self, user_id: int, current_balance: str, 
                           account_number: str, channel: str = 'sms') -> int:
        """Create a low balance alert notification"""
        content = f"Balance Alert: Your account {account_number} balance is {current_balance}. Please maintain minimum balance."
        
        notification = Notification(
            user_id=user_id,
            channel=channel,
            type='balance_alert',
            content=content,
            status='queued'
        )
        
        return self.create_notification(notification)
    
    def create_emi_reminder(self, user_id: int, emi_amount: str, 
                          due_date: str, loan_id: int, channel: str = 'sms') -> int:
        """Create an EMI reminder notification"""
        content = f"EMI Reminder: Your loan EMI of {emi_amount} is due on {due_date}. Loan ID: {loan_id}. Please pay on time to avoid penalties."
        
        notification = Notification(
            user_id=user_id,
            channel=channel,
            type='emi_reminder',
            content=content,
            status='queued'
        )
        
        return self.create_notification(notification)
    
    def create_maturity_notification(self, user_id: int, investment_type: str, 
                                   maturity_amount: str, maturity_date: str, 
                                   channel: str = 'sms') -> int:
        """Create an investment maturity notification"""
        content = f"Maturity Alert: Your {investment_type} matures on {maturity_date} with amount {maturity_amount}. Please visit branch for processing."
        
        notification = Notification(
            user_id=user_id,
            channel=channel,
            type='maturity_alert',
            content=content,
            status='queued'
        )
        
        return self.create_notification(notification)
    
    def create_loan_approval_notification(self, user_id: int, loan_amount: str, 
                                        loan_type: str, channel: str = 'sms') -> int:
        """Create a loan approval notification"""
        content = f"Loan Approved: Your {loan_type} loan of {loan_amount} has been approved. Please visit branch for disbursement."
        
        notification = Notification(
            user_id=user_id,
            channel=channel,
            type='loan_approval',
            content=content,
            status='queued'
        )
        
        return self.create_notification(notification)
    
    def get_notification_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get notification statistics for the last N days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_notifications,
                    COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                    COUNT(CASE WHEN status = 'queued' THEN 1 END) as queued_count,
                    COUNT(CASE WHEN channel = 'sms' THEN 1 END) as sms_count,
                    COUNT(CASE WHEN channel = 'email' THEN 1 END) as email_count
                FROM {self.table_name}
                WHERE created_at >= %s
            """
            result = self.db.execute_query(query, (cutoff_date,), fetch_one=True)
            
            if result:
                total = result['total_notifications'] or 0
                sent = result['sent_count'] or 0
                
                return {
                    'total_notifications': total,
                    'sent_count': sent,
                    'failed_count': result['failed_count'] or 0,
                    'queued_count': result['queued_count'] or 0,
                    'sms_count': result['sms_count'] or 0,
                    'email_count': result['email_count'] or 0,
                    'success_rate': (sent / total * 100) if total > 0 else 0
                }
            else:
                return {
                    'total_notifications': 0,
                    'sent_count': 0,
                    'failed_count': 0,
                    'queued_count': 0,
                    'sms_count': 0,
                    'email_count': 0,
                    'success_rate': 0
                }
        except Exception as e:
            raise ValidationException(f"Error getting notification statistics: {str(e)}")
    
    def cleanup_old_notifications(self, days_to_keep: int = 90) -> int:
        """Clean up old notifications (keep only last N days)"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Get count before deletion
            count_query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE created_at < %s"
            count_result = self.db.execute_query(count_query, (cutoff_date,), fetch_one=True)
            deleted_count = count_result['count'] if count_result else 0
            
            # Delete old notifications
            query = f"DELETE FROM {self.table_name} WHERE created_at < %s"
            self.db.execute_query(query, (cutoff_date,))
            
            return deleted_count
        except Exception as e:
            raise ValidationException(f"Error cleaning up old notifications: {str(e)}")
    
    def _dict_to_notification(self, notification_data: dict) -> Notification:
        """Convert dictionary to Notification object"""
        return Notification(
            notification_id=notification_data['notification_id'],
            user_id=notification_data.get('user_id'),
            channel=notification_data.get('channel', 'sms'),
            type=notification_data['type'],
            content=notification_data['content'],
            status=notification_data.get('status', 'queued'),
            created_at=notification_data.get('created_at')
        )