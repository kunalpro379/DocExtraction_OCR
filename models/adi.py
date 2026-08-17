"""
ADI - Document Intelligence model implementations.
Contains concrete implementations for document intelligence services.
"""

from typing import Dict, Any, List
from models.base import BaseADI


class AzureDocumentIntelligence(BaseADI):
    """Azure Document Intelligence (formerly Form Recognizer) implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.model_id = None
    
    def initialize(self):
        """Initialize Azure Document Intelligence client."""
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential
            
            endpoint = self.config.get('endpoint')
            key = self.config.get('api_key')
            self.model_id = self.config.get('model_id', 'prebuilt-document')
            
            if not endpoint or not key:
                raise ValueError("Azure endpoint and api_key are required")
            
            self.client = DocumentAnalysisClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(key)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure Document Intelligence: {e}")
    
    def cleanup(self):
        """Clean up Azure Document Intelligence resources."""
        self.client = None
    
    def analyze_document(self, document_path: str) -> Dict[str, Any]:
        """Analyze document using Azure Document Intelligence."""
        if not self.client:
            self.initialize()
        
        try:
            with open(document_path, "rb") as document_file:
                document_data = document_file.read()
            
            poller = self.client.begin_analyze_document(
                model_id=self.model_id,
                document=document_data
            )
            result = poller.result()
            
            # Convert Azure result to standardized format
            return self._convert_azure_result(result, document_path)
            
        except Exception as e:
            raise RuntimeError(f"Azure Document Intelligence analysis failed: {e}")
    
    def extract_tables(self, document_path: str) -> List[Dict[str, Any]]:
        """Extract tables from document."""
        analysis_result = self.analyze_document(document_path)
        return analysis_result.get('tables', [])
    
    def extract_key_value_pairs(self, document_path: str) -> Dict[str, str]:
        """Extract key-value pairs from document."""
        analysis_result = self.analyze_document(document_path)
        return analysis_result.get('key_value_pairs', {})
    
    def _convert_azure_result(self, azure_result, document_path: str) -> Dict[str, Any]:
        """Convert Azure Document Intelligence result to standardized format."""
        result = {
            'document_path': document_path,
            'source': 'azure_document_intelligence',
            'content': azure_result.content,
            'tables': [],
            'key_value_pairs': {},
            'pages': [],
            'paragraphs': []
        }
        
        # Extract tables
        for table in azure_result.tables:
            table_data = {
                'row_count': table.row_count,
                'column_count': table.column_count,
                'cells': []
            }
            for cell in table.cells:
                table_data['cells'].append({
                    'row_index': cell.row_index,
                    'column_index': cell.column_index,
                    'content': cell.content,
                    'row_span': cell.row_span,
                    'column_span': cell.column_span
                })
            result['tables'].append(table_data)
        
        # Extract key-value pairs
        for kv_pair in azure_result.key_value_pairs:
            if kv_pair.key and kv_pair.value:
                key = kv_pair.key.content
                value = kv_pair.value.content if kv_pair.value else ""
                result['key_value_pairs'][key] = value
        
        # Extract pages
        for page in azure_result.pages:
            page_data = {
                'page_number': page.page_number,
                'width': page.width,
                'height': page.height,
                'spans': []
            }
            for span in page.spans:
                page_data['spans'].append({
                    'offset': span.offset,
                    'length': span.length
                })
            result['pages'].append(page_data)
        
        # Extract paragraphs
        for paragraph in azure_result.paragraphs:
            paragraph_data = {
                'content': paragraph.content,
                'role': paragraph.role if hasattr(paragraph, 'role') else None
            }
            result['paragraphs'].append(paragraph_data)
        
        return result


class LegacyADI(BaseADI):
    """Legacy ADI implementation (wrapper around existing ADI module)."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialized = False
    
    def initialize(self):
        """Initialize legacy ADI module."""
        try:
            # Import the existing ADI module
            import sys
            import os
            # Add parent directory to path if needed
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            
            # This will import the existing ADI module
            global ADI
            import ADI
            
            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to initialize legacy ADI: {e}")
    
    def cleanup(self):
        """Clean up legacy ADI resources."""
        self._initialized = False
    
    def analyze_document(self, document_path: str) -> Dict[str, Any]:
        """Analyze document using legacy ADI module."""
        if not self._initialized:
            self.initialize()
        
        try:
            # Call the existing analyze_pdf function
            result = ADI.analyze_pdf(document_path)
            
            # Convert to standardized format if needed
            return self._convert_legacy_result(result, document_path)
            
        except Exception as e:
            raise RuntimeError(f"Legacy ADI analysis failed: {e}")
    
    def extract_tables(self, document_path: str) -> List[Dict[str, Any]]:
        """Extract tables using legacy ADI."""
        analysis_result = self.analyze_document(document_path)
        return analysis_result.get('tables', [])
    
    def extract_key_value_pairs(self, document_path: str) -> Dict[str, str]:
        """Extract key-value pairs using legacy ADI."""
        analysis_result = self.analyze_document(document_path)
        return analysis_result.get('key_value_pairs', {})
    
    def _convert_legacy_result(self, legacy_result, document_path: str) -> Dict[str, Any]:
        """Convert legacy ADI result to standardized format."""
        # Assuming the legacy result has a similar structure to Azure
        result = {
            'document_path': document_path,
            'source': 'legacy_adi',
            'content': legacy_result.get('analyzeResult', {}).get('content', ''),
            'tables': legacy_result.get('analyzeResult', {}).get('tables', []),
            'key_value_pairs': self._extract_kv_pairs_from_legacy(legacy_result),
            'pages': legacy_result.get('analyzeResult', {}).get('pages', []),
            'paragraphs': legacy_result.get('analyzeResult', {}).get('paragraphs', [])
        }
        return result
    
    def _extract_kv_pairs_from_legacy(self, legacy_result) -> Dict[str, str]:
        """Extract key-value pairs from legacy result format."""
        kv_pairs = {}
        # This depends on the actual structure of the legacy result
        # Adjust based on the actual ADI module output
        analyze_result = legacy_result.get('analyzeResult', {})
        # Try to extract key-value pairs from documents or fields
        if 'documents' in analyze_result:
            for doc in analyze_result['documents']:
                if 'fields' in doc:
                    for field_name, field_data in doc['fields'].items():
                        if 'value' in field_data:
                            kv_pairs[field_name] = field_data['value']
        return kv_pairs
