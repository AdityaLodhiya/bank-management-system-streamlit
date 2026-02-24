"""
Base Repository Class
Provides common database operations for all repositories
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging
from mysql.connector import Error

from db.database import db_manager
from utils.exceptions import DatabaseException, ValidationException

logger = logging.getLogger(__name__)

class BaseRepository(ABC):
    """Base repository with common CRUD operations"""
    
    def __init__(self, table_name: str, primary_key: str = 'id', auto_increment: bool = True):
        self.table_name = table_name
        self.primary_key = primary_key
        self.auto_increment = auto_increment
        self.db = db_manager
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new record"""
        try:
            # Remove None values and skip primary key ONLY if it's auto-incremented
            clean_data = {
                k: v for k, v in data.items() 
                if v is not None and (not self.auto_increment or k != self.primary_key)
            }
            
            if not clean_data:
                raise ValidationException("No data provided for creation")
            
            columns = ', '.join(clean_data.keys())
            placeholders = ', '.join(['%s'] * len(clean_data))
            values = tuple(clean_data.values())
            
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            result = self.db.execute_query(query, values)
            logger.info(f"Created record in {self.table_name} with ID: {result}")
            return result
            
        except Error as e:
            logger.error(f"Error creating record in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to create record: {str(e)}")
    
    def find_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Find record by primary key"""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = %s"
            result = self.db.execute_query(query, (record_id,), fetch_one=True)
            return result
            
        except Error as e:
            logger.error(f"Error finding record by ID in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to find record: {str(e)}")
    
    def find_all(self, limit: int = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Find all records with optional pagination"""
        try:
            query = f"SELECT * FROM {self.table_name}"
            params = []
            
            if limit:
                query += " LIMIT %s OFFSET %s"
                params = [limit, offset]
            
            result = self.db.execute_query(query, tuple(params), fetch_all=True)
            return result or []
            
        except Error as e:
            logger.error(f"Error finding all records in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to find records: {str(e)}")
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """Update record by primary key"""
        try:
            # Remove None values and primary key
            clean_data = {k: v for k, v in data.items() if v is not None and k != self.primary_key}
            
            if not clean_data:
                return False
            
            set_clause = ', '.join([f"{k} = %s" for k in clean_data.keys()])
            values = tuple(clean_data.values()) + (record_id,)
            
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = %s"
            
            self.db.execute_query(query, values)
            logger.info(f"Updated record in {self.table_name} with ID: {record_id}")
            return True
            
        except Error as e:
            logger.error(f"Error updating record in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to update record: {str(e)}")
    
    def delete(self, record_id: int) -> bool:
        """Delete record by primary key"""
        try:
            query = f"DELETE FROM {self.table_name} WHERE {self.primary_key} = %s"
            self.db.execute_query(query, (record_id,))
            logger.info(f"Deleted record from {self.table_name} with ID: {record_id}")
            return True
            
        except Error as e:
            logger.error(f"Error deleting record from {self.table_name}: {e}")
            raise DatabaseException(f"Failed to delete record: {str(e)}")
    
    def find_by_field(self, field_name: str, field_value: Any) -> List[Dict[str, Any]]:
        """Find records by specific field"""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {field_name} = %s"
            result = self.db.execute_query(query, (field_value,), fetch_all=True)
            return result or []
            
        except Error as e:
            logger.error(f"Error finding records by {field_name} in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to find records: {str(e)}")
    
    def count(self, where_clause: str = None, params: tuple = None) -> int:
        """Count records with optional where clause"""
        try:
            query = f"SELECT COUNT(*) as count FROM {self.table_name}"
            if where_clause:
                query += f" WHERE {where_clause}"
            
            result = self.db.execute_query(query, params, fetch_one=True)
            return result['count'] if result else 0
            
        except Error as e:
            logger.error(f"Error counting records in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to count records: {str(e)}")
    
    def exists(self, record_id: int) -> bool:
        """Check if record exists"""
        try:
            query = f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = %s LIMIT 1"
            result = self.db.execute_query(query, (record_id,), fetch_one=True)
            return result is not None
            
        except Error as e:
            logger.error(f"Error checking existence in {self.table_name}: {e}")
            raise DatabaseException(f"Failed to check existence: {str(e)}")