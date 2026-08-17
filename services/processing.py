"""
Processing - Document processing pipeline service.
Orchestrates the entire document processing workflow.
"""

import os
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from config import settings
from services.extraction import extraction_service
from services.validation import validation_service
from utils.logger import get_logger


class ProcessingService:
    """Service for processing documents through the complete pipeline."""
    
    def __init__(self):
        """Initialize processing service."""
        self.logger = get_logger(__name__)
        self.extraction_service = extraction_service
        self.validation_service = validation_service
    
    def process_input_folder(self, input_base_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Process all documents in the Input folder structure.
        Expected structure: Input/DocumentType/files (e.g., Input/agreement/files)
        
        Args:
            input_base_path: Base input path (defaults to settings)
            
        Returns:
            Summary of processing results
        """
        input_path = input_base_path or settings.get_input_dir()
        
        if not os.path.exists(input_path):
            self.logger.error(f"Input directory not found: {input_path}")
            return {
                'success': False,
                'error': f"Input directory not found: {input_path}",
                'processed': 0,
                'failed': 0
            }
        
        results = {
            'success': True,
            'processed': 0,
            'failed': 0,
            'document_types': {},
            'errors': []
        }
        
        # Process each document type folder
        for item in os.listdir(input_path):
            item_path = os.path.join(input_path, item)
            
            if os.path.isdir(item_path):
                document_type = item.lower()
                
                # Check if this is a document type folder (contains 'files' subfolder or PDFs directly)
                files_folder = os.path.join(item_path, 'files')
                
                if os.path.exists(files_folder):
                    # Process from Input/DocumentType/files
                    type_result = self._process_document_folder(files_folder, document_type)
                else:
                    # Process from Input/DocumentType directly
                    type_result = self._process_document_folder(item_path, document_type)
                
                results['document_types'][document_type] = type_result
                results['processed'] += type_result['processed']
                results['failed'] += type_result['failed']
                results['errors'].extend(type_result['errors'])
        
        self.logger.info(f"Processing complete. Processed: {results['processed']}, Failed: {results['failed']}")
        return results
    
    def _process_document_folder(self, folder_path: str, document_type: str) -> Dict[str, Any]:
        """
        Process all documents in a specific folder for a document type.
        
        Args:
            folder_path: Path to the folder containing documents
            document_type: Type of document to process
            
        Returns:
            Processing results for this folder
        """
        result = {
            'document_type': document_type,
            'folder': folder_path,
            'processed': 0,
            'failed': 0,
            'files': [],
            'errors': []
        }
        
        # Get all PDF files
        pdf_files = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith('.pdf')
        ]
        
        if not pdf_files:
            self.logger.warning(f"No PDF files found in {folder_path}")
            return result
        
        self.logger.info(f"Processing {len(pdf_files)} files for document type: {document_type}")
        
        for pdf_file in pdf_files:
            file_path = os.path.join(folder_path, pdf_file)
            file_result = self._process_single_document(file_path, document_type)
            
            result['files'].append(file_result)
            
            if file_result['success']:
                result['processed'] += 1
            else:
                result['failed'] += 1
                result['errors'].append(file_result['error'])
        
        return result
    
    def _process_single_document(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        Process a single document through the complete pipeline.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document
            
        Returns:
            Processing result for this document
        """
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            self.logger.info(f"Processing document: {file_path}")
            
            # Step 1: Extract data
            extracted_data = self.extraction_service.extract_from_document(file_path, document_type)
            
            if 'error' in extracted_data:
                raise Exception(extracted_data['error'])
            
            # Step 2: Sanitize data
            sanitized_data = self.validation_service.sanitize_data(extracted_data)
            
            # Step 3: Validate data
            is_valid, validation_errors = self.validation_service.validate_extracted_data(
                sanitized_data, document_type
            )
            
            # Step 4: Save results
            self._save_document_results(file_name, sanitized_data, document_type, is_valid, validation_errors)
            
            self.logger.info(f"Successfully processed: {file_path}")
            
            return {
                'success': True,
                'file_path': file_path,
                'document_type': document_type,
                'is_valid': is_valid,
                'validation_errors': validation_errors
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process {file_path}: {e}")
            return {
                'success': False,
                'file_path': file_path,
                'document_type': document_type,
                'error': str(e)
            }
    
    def _save_document_results(self, file_name: str, data: Dict[str, Any], 
                               document_type: str, is_valid: bool, 
                               validation_errors: List[str]) -> None:
        """
        Save extraction results in multiple formats.
        
        Args:
            file_name: Name of the file (without extension)
            data: Extracted and sanitized data
            document_type: Type of document
            is_valid: Whether the data passed validation
            validation_errors: List of validation errors
        """
        # Create output directory structure
        output_dir = settings.get_extracted_dir()
        document_output_dir = os.path.join(output_dir, document_type)
        os.makedirs(document_output_dir, exist_ok=True)
        
        # Add validation info to data
        data['validation'] = {
            'is_valid': is_valid,
            'errors': validation_errors
        }
        
        # Save as JSON
        json_path = os.path.join(document_output_dir, f"{file_name}_extracted.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save to OutputRaw directory as well
        output_raw_dir = settings.get_output_raw_dir()
        os.makedirs(output_raw_dir, exist_ok=True)
        raw_json_path = os.path.join(output_raw_dir, f"{file_name}_extracted.json")
        with open(raw_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.logger.debug(f"Saved results to {json_path} and {raw_json_path}")
    
    def process_single_file(self, file_path: str, document_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a single file with optional document type override.
        
        Args:
            file_path: Path to the document file
            document_type: Document type (auto-detected if not provided)
            
        Returns:
            Processing result
        """
        # Auto-detect document type if not provided
        if not document_type:
            document_type = self.extraction_service.detect_document_type(file_path)
        
        return self._process_single_document(file_path, document_type)
    
    def reprocess_extracted_data(self, document_name: str, document_type: str) -> Dict[str, Any]:
        """
        Re-process already extracted data (useful for updating extraction logic).
        
        Args:
            document_name: Name of the document (without extension)
            document_type: Type of document
            
        Returns:
            Processing result
        """
        # Try to find the extracted JSON file
        output_raw_dir = settings.get_output_raw_dir()
        json_path = os.path.join(output_raw_dir, f"{document_name}_extracted.json")
        
        if not os.path.exists(json_path):
            # Try alternative location
            extracted_dir = settings.get_extracted_dir()
            json_path = os.path.join(extracted_dir, document_type, f"{document_name}_extracted.json")
        
        if not os.path.exists(json_path):
            return {
                'success': False,
                'error': f"Extracted data not found for {document_name}"
            }
        
        try:
            # Load existing data
            with open(json_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            
            # Get original file path if available
            original_file = original_data.get('source_file')
            
            if original_file and os.path.exists(original_file):
                # Re-extract from original file
                return self._process_single_document(original_file, document_type)
            else:
                # Re-validate existing data
                sanitized_data = self.validation_service.sanitize_data(original_data)
                is_valid, validation_errors = self.validation_service.validate_extracted_data(
                    sanitized_data, document_type
                )
                
                # Update validation info
                sanitized_data['validation'] = {
                    'is_valid': is_valid,
                    'errors': validation_errors
                }
                
                # Save updated results
                self._save_document_results(document_name, sanitized_data, document_type, is_valid, validation_errors)
                
                return {
                    'success': True,
                    'document_name': document_name,
                    'document_type': document_type,
                    'is_valid': is_valid,
                    'validation_errors': validation_errors,
                    'reprocessed': True
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all processed documents.
        
        Returns:
            Summary statistics
        """
        output_raw_dir = settings.get_output_raw_dir()
        
        if not os.path.exists(output_raw_dir):
            return {
                'total_processed': 0,
                'by_type': {},
                'valid_count': 0,
                'invalid_count': 0
            }
        
        summary = {
            'total_processed': 0,
            'by_type': {},
            'valid_count': 0,
            'invalid_count': 0
        }
        
        for file_name in os.listdir(output_raw_dir):
            if file_name.endswith('_extracted.json'):
                file_path = os.path.join(output_raw_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    doc_type = data.get('document_type', 'unknown')
                    is_valid = data.get('validation', {}).get('is_valid', False)
                    
                    summary['total_processed'] += 1
                    summary['by_type'][doc_type] = summary['by_type'].get(doc_type, 0) + 1
                    
                    if is_valid:
                        summary['valid_count'] += 1
                    else:
                        summary['invalid_count'] += 1
                        
                except Exception as e:
                    self.logger.warning(f"Failed to read {file_path}: {e}")
        
        return summary


# Global processing service instance
processing_service = ProcessingService()
