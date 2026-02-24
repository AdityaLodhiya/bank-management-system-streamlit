"""
Audit Service
Business logic for system-wide auditing and logging
"""
import json
from typing import Any, Dict
from core.repositories.audit_repository import AuditRepository

class AuditService:
    """Service class for auditing critical system actions"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditService, cls).__new__(cls)
            cls._instance.repo = AuditRepository()
        return cls._instance
    
    def log(self, actor_id: int, role: str, action: str, details: Any = None):
        """Log a system action with optional structured details"""
        details_str = json.dumps(details) if details else None
        return self.repo.log_action(actor_id, role, action, details_str)

    def get_latest_activity(self, count: int = 15):
        """Fetch latest activity for admin dashboard"""
        return self.repo.get_recent_logs(count)
