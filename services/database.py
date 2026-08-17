"""
Database - Data persistence service.
Handles storage and retrieval of extracted document data.
"""

import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from config import settings
from utils.logger import get_logger


class DatabaseService:
    """Service for database operations and data persistence."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database service.
        
        Args:
            db_path: Path to SQLite database file (defaults to document_extraction.db)
        """
        self.logger = get_logger(__name__)
        self.db_path = db_path or os.path.join(os.getcwd(), 'document_extraction.db')
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create documents table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_name TEXT NOT NULL,
                        document_type TEXT NOT NULL,
                        file_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        extraction_status TEXT DEFAULT 'pending',
                        validation_status TEXT DEFAULT 'pending',
                        raw_data TEXT,
                        extracted_data TEXT
                    )
                """)
                
                # Create extractions table for structured field data
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS extractions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER NOT NULL,
                        field_name TEXT NOT NULL,
                        field_value TEXT,
                        field_type TEXT,
                        is_required INTEGER DEFAULT 0,
                        is_valid INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents (id)
                    )
                """)
                
                # Create validation_errors table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS validation_errors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER NOT NULL,
                        error_message TEXT,
                        field_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents (id)
                    )
                """)
                
                # Create indexes for better query performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_type 
                    ON documents(document_type)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_status 
                    ON documents(extraction_status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_extractions_document 
                    ON extractions(document_id)
                """)
                
                conn.commit()
                self.logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def save_document(self, document_name: str, document_type: str, 
                     file_path: str, extracted_data: Dict[str, Any],
                     is_valid: bool, validation_errors: List[str]) -> int:
        """
        Save document and extracted data to database.
        
        Args:
            document_name: Name of the document
            document_type: Type of document
            file_path: Path to the source file
            extracted_data: Dictionary of extracted field data
            is_valid: Whether the data passed validation
            validation_errors: List of validation errors
            
        Returns:
            Document ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert document record
                cursor.execute("""
                    INSERT INTO documents 
                    (document_name, document_type, file_path, extraction_status, validation_status, extracted_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    document_name,
                    document_type,
                    file_path,
                    'completed',
                    'valid' if is_valid else 'invalid',
                    json.dumps(extracted_data)
                ))
                
                document_id = cursor.lastrowid
                
                # Insert extracted fields
                for field_name, field_value in extracted_data.items():
                    if field_name in ['document_type', 'source_file', 'validation']:
                        continue  # Skip metadata fields
                    
                    cursor.execute("""
                        INSERT INTO extractions 
                        (document_id, field_name, field_value, field_type, is_valid)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        document_id,
                        field_name,
                        str(field_value) if field_value else None,
                        type(field_value).__name__,
                        1
                    ))
                
                # Insert validation errors if any
                for error in validation_errors:
                    cursor.execute("""
                        INSERT INTO validation_errors 
                        (document_id, error_message)
                        VALUES (?, ?)
                    """, (document_id, error))
                
                conn.commit()
                self.logger.info(f"Saved document {document_name} with ID {document_id}")
                return document_id
                
        except Exception as e:
            self.logger.error(f"Failed to save document {document_name}: {e}")
            raise
    
    def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document data dictionary or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM documents WHERE id = ?
                """, (document_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve document {document_id}: {e}")
            return None
    
    def get_document_by_name(self, document_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve document by name.
        
        Args:
            document_name: Document name
            
        Returns:
            Document data dictionary or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM documents WHERE document_name = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (document_name,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve document {document_name}: {e}")
            return None
    
    def get_documents_by_type(self, document_type: str) -> List[Dict[str, Any]]:
        """
        Retrieve all documents of a specific type.
        
        Args:
            document_type: Type of document
            
        Returns:
            List of document data dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM documents WHERE document_type = ?
                    ORDER BY created_at DESC
                """, (document_type,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve documents of type {document_type}: {e}")
            return []
    
    def get_document_fields(self, document_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve extracted fields for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of field data dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM extractions WHERE document_id = ?
                """, (document_id,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve fields for document {document_id}: {e}")
            return []
    
    def get_validation_errors(self, document_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve validation errors for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of error data dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM validation_errors WHERE document_id = ?
                """, (document_id,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve validation errors for document {document_id}: {e}")
            return []
    
    def update_document(self, document_id: int, extracted_data: Dict[str, Any],
                       is_valid: bool, validation_errors: List[str]) -> bool:
        """
        Update document with new extraction data.
        
        Args:
            document_id: Document ID
            extracted_data: Updated extracted data
            is_valid: Whether the data is valid
            validation_errors: List of validation errors
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update document record
                cursor.execute("""
                    UPDATE documents 
                    SET extracted_data = ?, validation_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    json.dumps(extracted_data),
                    'valid' if is_valid else 'invalid',
                    document_id
                ))
                
                # Delete old extractions and validation errors
                cursor.execute("DELETE FROM extractions WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM validation_errors WHERE document_id = ?", (document_id,))
                
                # Insert new extractions
                for field_name, field_value in extracted_data.items():
                    if field_name in ['document_type', 'source_file', 'validation']:
                        continue
                    
                    cursor.execute("""
                        INSERT INTO extractions 
                        (document_id, field_name, field_value, field_type, is_valid)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        document_id,
                        field_name,
                        str(field_value) if field_value else None,
                        type(field_value).__name__,
                        1
                    ))
                
                # Insert new validation errors
                for error in validation_errors:
                    cursor.execute("""
                        INSERT INTO validation_errors 
                        (document_id, error_message)
                        VALUES (?, ?)
                    """, (document_id, error))
                
                conn.commit()
                self.logger.info(f"Updated document {document_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update document {document_id}: {e}")
            return False
    
    def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all related data.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete related records first (foreign key constraints)
                cursor.execute("DELETE FROM validation_errors WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM extractions WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                
                conn.commit()
                self.logger.info(f"Deleted document {document_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete document {document_id}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total documents
                cursor.execute("SELECT COUNT(*) FROM documents")
                total_docs = cursor.fetchone()[0]
                
                # Documents by type
                cursor.execute("""
                    SELECT document_type, COUNT(*) as count 
                    FROM documents 
                    GROUP BY document_type
                """)
                by_type = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Valid vs invalid
                cursor.execute("""
                    SELECT validation_status, COUNT(*) as count 
                    FROM documents 
                    GROUP BY validation_status
                """)
                validation_status = {row[0]: row[1] for row in cursor.fetchall()}
                
                return {
                    'total_documents': total_docs,
                    'by_type': by_type,
                    'validation_status': validation_status
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {
                'total_documents': 0,
                'by_type': {},
                'validation_status': {}
            }
    
    def export_to_json(self, output_path: str) -> bool:
        """
        Export all documents to JSON file.
        
        Args:
            output_path: Path to output JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM documents")
                documents = [dict(row) for row in cursor.fetchall()]
                
                # Add extracted fields to each document
                for doc in documents:
                    doc_id = doc['id']
                    cursor.execute("SELECT * FROM extractions WHERE document_id = ?", (doc_id,))
                    doc['fields'] = [dict(row) for row in cursor.fetchall()]
                    
                    cursor.execute("SELECT * FROM validation_errors WHERE document_id = ?", (doc_id,))
                    doc['validation_errors'] = [dict(row) for row in cursor.fetchall()]
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(documents, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Exported data to {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to export to JSON: {e}")
            return False


# Global database service instance
database_service = DatabaseService()
