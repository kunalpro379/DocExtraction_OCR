"""
Extraction - Document extraction service.
Orchestrates extraction using registered models and document types.
"""

import os
import json
from typing import Dict, Any, Optional, List
from config import settings, registry
from models import BaseDocument, BaseOCR, BaseLLM, BaseADI


class ExtractionService:
    """Service for extracting data from documents using the model registry."""
    
    def __init__(self):
        """Initialize extraction service with models from registry."""
        self.ocr_model: Optional[BaseOCR] = None
        self.llm_model: Optional[BaseLLM] = None
        self.adi_model: Optional[BaseADI] = None
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize models based on settings."""
        try:
            # Initialize OCR model
            ocr_name = settings.get_ocr_model()
            if ocr_name:
                self.ocr_model = registry.get_ocr(ocr_name)
                self.ocr_model.initialize()
            
            # Initialize LLM model
            llm_name = settings.get_llm_model()
            if llm_name:
                self.llm_model = registry.get_llm(llm_name)
                self.llm_model.initialize()
            
            # Initialize ADI model
            adi_name = settings.get_document_intelligence_model()
            if adi_name:
                self.adi_model = registry.get_adi(adi_name)
                self.adi_model.initialize()
                
        except Exception as e:
            print(f"Warning: Failed to initialize models: {e}")
    
    def extract_from_document(self, document_path: str, document_type: str) -> Dict[str, Any]:
        """
        Extract data from a document using the specified document type.
        
        Args:
            document_path: Path to the document file
            document_type: Type of document (e.g., 'agreement', 'invoice', 'pan', 'aadhaar')
            
        Returns:
            Dictionary containing extracted data
        """
        try:
            # Get document instance from registry
            document = registry.get_document(
                document_type,
                ocr_model=self.ocr_model,
                llm_model=self.llm_model,
                adi_model=self.adi_model
            )
            
            # Extract fields
            extracted_data = document.extract_fields(document_path)
            
            return extracted_data
            
        except Exception as e:
            return {
                'error': str(e),
                'document_path': document_path,
                'document_type': document_type
            }
    
    def extract_from_adi_json(self, adi_json_path: str, document_type: str) -> Dict[str, Any]:
        """
        Extract data from a saved ADI JSON file.
        
        Args:
            adi_json_path: Path to the ADI JSON file
            document_type: Type of document
            
        Returns:
            Dictionary containing extracted data
        """
        try:
            # Load ADI JSON
            with open(adi_json_path, 'r', encoding='utf-8') as f:
                adi_dict = json.load(f)
            
            # Get document instance
            document = registry.get_document(
                document_type,
                ocr_model=self.ocr_model,
                llm_model=self.llm_model,
                adi_model=self.adi_model
            )
            
            # If document has ADI-specific extraction method
            if hasattr(document, '_extract_from_adi'):
                extracted = document._extract_from_adi(adi_dict)
            else:
                # Fallback to general extraction
                extracted = document.extract_fields(adi_json_path)
            
            # Add metadata
            extracted['document_type'] = document_type
            extracted['source_file'] = adi_json_path
            extracted['source'] = 'adi_json'
            
            return extracted
            
        except Exception as e:
            return {
                'error': str(e),
                'adi_json_path': adi_json_path,
                'document_type': document_type
            }
    
    def extract_from_text(self, text: str, document_type: str) -> Dict[str, Any]:
        """
        Extract data from raw text using LLM.
        
        Args:
            text: Raw text content
            document_type: Type of document
            
        Returns:
            Dictionary containing extracted data
        """
        try:
            if not self.llm_model:
                raise ValueError("LLM model not initialized")
            
            # Get document instance
            document = registry.get_document(
                document_type,
                ocr_model=self.ocr_model,
                llm_model=self.llm_model,
                adi_model=self.adi_model
            )
            
            # Use LLM extraction if available
            if hasattr(document, '_extract_with_llm'):
                extracted = document._extract_with_llm(text)
            else:
                # Fallback to general LLM call
                extracted = self.llm_model.extract_structured_data(
                    text,
                    self._build_schema_from_document(document)
                )
            
            # Add metadata
            extracted['document_type'] = document_type
            extracted['source'] = 'text'
            
            return extracted
            
        except Exception as e:
            return {
                'error': str(e),
                'document_type': document_type
            }
    
    def _build_schema_from_document(self, document: BaseDocument) -> Dict[str, Any]:
        """Build extraction schema from document field definitions."""
        schema = {}
        
        for field in document.get_required_fields():
            schema[field] = {
                'type': 'string',
                'description': field.replace('_', ' ').title(),
                'required': True
            }
        
        for field in document.get_optional_fields():
            schema[field] = {
                'type': 'string',
                'description': field.replace('_', ' ').title(),
                'required': False
            }
        
        return schema
    
    def extract_batch(self, files: List[str], document_type: str) -> List[Dict[str, Any]]:
        """
        Extract data from multiple documents.
        
        Args:
            files: List of file paths
            document_type: Type of document
            
        Returns:
            List of extraction results
        """
        results = []
        for file_path in files:
            result = self.extract_from_document(file_path, document_type)
            results.append(result)
        return results
    
    def detect_document_type(self, document_path: str) -> str:
        """
        Detect document type from file path or content.
        
        Args:
            document_path: Path to the document
            
        Returns:
            Detected document type (defaults to 'agreement')
        """
        # Simple detection based on folder structure
        # Input/DocumentType/files structure
        parent_dir = os.path.basename(os.path.dirname(document_path))
        parent_lower = parent_dir.lower()
        
        # Map folder names to document types
        type_mapping = {
            'agreement': 'agreement',
            'agreements': 'agreement',
            'invoice': 'invoice',
            'invoices': 'invoice',
            'pan': 'pan',
            'pancard': 'pan',
            'aadhaar': 'aadhaar',
            'aadhar': 'aadhaar'
        }
        
        return type_mapping.get(parent_lower, 'agreement')
    
    def cleanup(self):
        """Clean up model resources."""
        if self.ocr_model:
            self.ocr_model.cleanup()
        if self.llm_model:
            self.llm_model.cleanup()
        if self.adi_model:
            self.adi_model.cleanup()


# Global extraction service instance
extraction_service = ExtractionService()
