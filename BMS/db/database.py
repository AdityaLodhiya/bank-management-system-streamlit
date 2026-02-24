"""
Database Configuration and Connection Management
Handles MySQL connection pooling and configuration for SecureCore Banking System
"""

import mysql.connector
from mysql.connector import pooling, Error
import os
from typing import Optional
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        # Database configuration - UPDATE THESE WITH YOUR XAMPP SETTINGS
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'database': os.getenv('DB_NAME', 'securecore_db'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),  # Default XAMPP password is empty
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': False,
            'pool_name': 'securecore_pool',
            'pool_size': 10,
            'pool_reset_session': True
        }
        
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.connection_pool = pooling.MySQLConnectionPool(**self.config)
            logger.info("Database connection pool initialized successfully")
        except Error as e:
            logger.error(f"Error creating connection pool: {e}")
            raise
    
    def get_connection(self):
        """Get connection from pool"""
        try:
            return self.connection_pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result[0] == 1
        except Error as e:
            logger.error(f"Database connection test failed: {e}")
            return False

class DatabaseManager:
    """Database operations manager"""
    
    def __init__(self):
        self.db_config = DatabaseConfig()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            connection = self.db_config.get_connection()
            yield connection
        except Error as e:
            if connection:
                connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    @contextmanager
    def get_transaction(self):
        """Context manager for database transactions"""
        connection = None
        try:
            connection = self.db_config.get_connection()
            connection.start_transaction()
            yield connection
            connection.commit()
        except Error as e:
            if connection:
                connection.rollback()
            logger.error(f"Transaction error: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
        """Execute a query and return results"""
        with self.get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                
                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    connection.commit()
                    return cursor.lastrowid
            finally:
                cursor.close()
    
    def execute_many(self, query: str, params_list: list):
        """Execute query with multiple parameter sets"""
        with self.get_transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.executemany(query, params_list)
                return cursor.rowcount
            finally:
                cursor.close()

# Global database manager instance
db_manager = DatabaseManager()