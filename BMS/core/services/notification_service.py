"""
Notification Service — Handles system alerts and notifications.
"""
from core.repositories.notification_repository import NotificationRepository
from core.models.entities import Notification

class NotificationService:
    def __init__(self):
        self.repo = NotificationRepository()

    def notify(self, user_id: int, title: str, message: str, n_type: str = "info"):
        """Create a notification record"""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=n_type,
            is_read=False
        )
        return self.repo.create_notification(notification)

    def get_unread(self, user_id: int):
        """Fetch unread notifications for a user"""
        return self.repo.get_customer_notifications(user_id)

    def mark_as_read(self, notification_id: int):
        """Mark notification as read"""
        return self.repo.mark_read(notification_id)
