"""
Audit Repository
Handles database operations for audit_logs table
"""
from typing import List, Dict, Any
from core.repositories.base_repository import BaseRepository

class AuditRepository(BaseRepository):
    """Repository for audit_logs table operations"""
    
    def __init__(self):
        super().__init__('audit_logs', 'audit_id')
    
    def log_action(self, actor_id: int, role: str, action: str, details: str = None) -> int:
        """Create a new audit log entry"""
        log_data = {
            'actor_id': actor_id,
            'role': role,
            'action': action,
            'details': details
        }
        return self.create(log_data)
    
    def get_recent_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent audit logs for admin display"""
        query = f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT %s"
        return self.db.execute_query(query, (limit,), fetch_all=True)
