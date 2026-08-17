"""
Documents - Document type implementations.
Contains concrete implementations for different document types.
Documents use injected models through dependency injection.
"""

from typing import Dict, Any, List
from models.base import BaseDocument


class Agreement(BaseDocument):
    """Agreement document type implementation."""
    
    def get_document_type(self) -> str:
        """Return document type identifier."""
        return "agreement"
    
    def get_required_fields(self) -> List[str]:
        """Return required fields for agreement documents."""
        return [
            "agreement_date",
            "parties",
            "agreement_type"
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Return optional fields for agreement documents."""
        return [
            "effective_date",
            "expiry_date",
            "termination_clause",
            "governing_law",
            "jurisdiction",
            "consideration",
            "obligations",
            "signatures"
        ]
    
    def extract_fields(self, document_path: str) -> Dict[str, Any]:
        """Extract fields specific to agreement documents."""
        extracted = {}
        
        # Try using ADI if available
        if self.adi_model:
            try:
                adi_result = self.adi_model.analyze_document(document_path)
                extracted.update(self._extract_from_adi(adi_result))
            except Exception as e:
                print(f"ADI extraction failed: {e}")
        
        # Try using OCR + LLM if ADI not available or incomplete
        if self.ocr_model and self.llm_model:
            try:
                ocr_result = self.ocr_model.process_pdf(document_path)
                text = ocr_result.get('text', '')
                
                if text:
                    llm_extracted = self._extract_with_llm(text)
                    extracted.update(llm_extracted)
            except Exception as e:
                print(f"OCR+LLM extraction failed: {e}")
        
        # Add metadata
        extracted['document_type'] = self.get_document_type()
        extracted['source_file'] = document_path
        
        return extracted
    
    def _extract_from_adi(self, adi_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract agreement fields from ADI result."""
        extracted = {}
        
        # Extract from key-value pairs
        kv_pairs = adi_result.get('key_value_pairs', {})
        
        # Map common agreement field names
        field_mappings = {
            'date': 'agreement_date',
            'agreement date': 'agreement_date',
            'effective date': 'effective_date',
            'expiry date': 'expiry_date',
            'parties': 'parties',
            'party': 'parties',
            'type': 'agreement_type',
            'agreement type': 'agreement_type',
            'consideration': 'consideration',
            'governing law': 'governing_law',
            'jurisdiction': 'jurisdiction'
        }
        
        for key, value in kv_pairs.items():
            key_lower = key.lower()
            for pattern, field_name in field_mappings.items():
                if pattern in key_lower:
                    extracted[field_name] = value
                    break
        
        return extracted
    
    def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Extract agreement fields using LLM."""
        schema = {
            'agreement_date': {
                'type': 'string',
                'description': 'Date when the agreement was signed',
                'required': True
            },
            'parties': {
                'type': 'string',
                'description': 'Names of parties involved in the agreement',
                'required': True
            },
            'agreement_type': {
                'type': 'string',
                'description': 'Type of agreement (e.g., NDA, Service Agreement, Lease)',
                'required': True
            },
            'effective_date': {
                'type': 'string',
                'description': 'Date when the agreement becomes effective',
                'required': False
            },
            'expiry_date': {
                'type': 'string',
                'description': 'Date when the agreement expires',
                'required': False
            },
            'consideration': {
                'type': 'string',
                'description': 'Payment or value exchanged in the agreement',
                'required': False
            },
            'governing_law': {
                'type': 'string',
                'description': 'Governing law of the agreement',
                'required': False
            }
        }
        
        return self.llm_model.extract_structured_data(text, schema)
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted agreement data."""
        required_fields = self.get_required_fields()
        
        for field in required_fields:
            if field not in data or not data[field]:
                return False
        
        return True


class Invoice(BaseDocument):
    """Invoice document type implementation."""
    
    def get_document_type(self) -> str:
        """Return document type identifier."""
        return "invoice"
    
    def get_required_fields(self) -> List[str]:
        """Return required fields for invoice documents."""
        return [
            "invoice_number",
            "invoice_date",
            "total_amount"
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Return optional fields for invoice documents."""
        return [
            "due_date",
            "vendor_name",
            "customer_name",
            "line_items",
            "tax_amount",
            "discount_amount",
            "payment_terms",
            "currency"
        ]
    
    def extract_fields(self, document_path: str) -> Dict[str, Any]:
        """Extract fields specific to invoice documents."""
        extracted = {}
        
        # Try using ADI if available
        if self.adi_model:
            try:
                adi_result = self.adi_model.analyze_document(document_path)
                extracted.update(self._extract_from_adi(adi_result))
            except Exception as e:
                print(f"ADI extraction failed: {e}")
        
        # Try using OCR + LLM if ADI not available or incomplete
        if self.ocr_model and self.llm_model:
            try:
                ocr_result = self.ocr_model.process_pdf(document_path)
                text = ocr_result.get('text', '')
                
                if text:
                    llm_extracted = self._extract_with_llm(text)
                    extracted.update(llm_extracted)
            except Exception as e:
                print(f"OCR+LLM extraction failed: {e}")
        
        # Add metadata
        extracted['document_type'] = self.get_document_type()
        extracted['source_file'] = document_path
        
        return extracted
    
    def _extract_from_adi(self, adi_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract invoice fields from ADI result."""
        extracted = {}
        
        # Extract from key-value pairs
        kv_pairs = adi_result.get('key_value_pairs', {})
        
        # Map common invoice field names
        field_mappings = {
            'invoice number': 'invoice_number',
            'invoice #': 'invoice_number',
            'invoice no': 'invoice_number',
            'invoice date': 'invoice_date',
            'date': 'invoice_date',
            'total': 'total_amount',
            'total amount': 'total_amount',
            'amount': 'total_amount',
            'due date': 'due_date',
            'vendor': 'vendor_name',
            'supplier': 'vendor_name',
            'customer': 'customer_name',
            'bill to': 'customer_name',
            'tax': 'tax_amount',
            'vat': 'tax_amount',
            'currency': 'currency'
        }
        
        for key, value in kv_pairs.items():
            key_lower = key.lower()
            for pattern, field_name in field_mappings.items():
                if pattern in key_lower:
                    extracted[field_name] = value
                    break
        
        # Extract line items from tables
        tables = adi_result.get('tables', [])
        if tables:
            line_items = self._extract_line_items_from_tables(tables)
            if line_items:
                extracted['line_items'] = line_items
        
        return extracted
    
    def _extract_line_items_from_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract line items from tables."""
        line_items = []
        
        for table in tables:
            cells = table.get('cells', [])
            rows = {}
            
            # Organize cells by row
            for cell in cells:
                row_idx = cell.get('row_index', 0)
                col_idx = cell.get('column_index', 0)
                content = cell.get('content', '')
                
                if row_idx not in rows:
                    rows[row_idx] = {}
                rows[row_idx][col_idx] = content
            
            # Skip header row (assume first row is header)
            if len(rows) > 1:
                for row_idx in range(1, len(rows)):
                    row_data = rows[row_idx]
                    if len(row_data) >= 2:  # At least description and amount
                        line_items.append({
                            'description': row_data.get(0, ''),
                            'quantity': row_data.get(1, '1'),
                            'unit_price': row_data.get(2, '0'),
                            'amount': row_data.get(3, '0')
                        })
        
        return line_items
    
    def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Extract invoice fields using LLM."""
        schema = {
            'invoice_number': {
                'type': 'string',
                'description': 'Invoice number',
                'required': True
            },
            'invoice_date': {
                'type': 'string',
                'description': 'Date of the invoice',
                'required': True
            },
            'total_amount': {
                'type': 'string',
                'description': 'Total amount of the invoice',
                'required': True
            },
            'due_date': {
                'type': 'string',
                'description': 'Payment due date',
                'required': False
            },
            'vendor_name': {
                'type': 'string',
                'description': 'Name of the vendor or supplier',
                'required': False
            },
            'customer_name': {
                'type': 'string',
                'description': 'Name of the customer or client',
                'required': False
            },
            'currency': {
                'type': 'string',
                'description': 'Currency code (e.g., USD, EUR, INR)',
                'required': False
            }
        }
        
        return self.llm_model.extract_structured_data(text, schema)
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted invoice data."""
        required_fields = self.get_required_fields()
        
        for field in required_fields:
            if field not in data or not data[field]:
                return False
        
        return True


class PAN(BaseDocument):
    """PAN card document type implementation."""
    
    def get_document_type(self) -> str:
        """Return document type identifier."""
        return "pan"
    
    def get_required_fields(self) -> List[str]:
        """Return required fields for PAN documents."""
        return [
            "pan_number",
            "name"
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Return optional fields for PAN documents."""
        return [
            "father_name",
            "date_of_birth",
            "gender"
        ]
    
    def extract_fields(self, document_path: str) -> Dict[str, Any]:
        """Extract fields specific to PAN documents."""
        extracted = {}
        
        # Try using ADI if available
        if self.adi_model:
            try:
                adi_result = self.adi_model.analyze_document(document_path)
                extracted.update(self._extract_from_adi(adi_result))
            except Exception as e:
                print(f"ADI extraction failed: {e}")
        
        # Try using OCR + LLM if ADI not available or incomplete
        if self.ocr_model and self.llm_model:
            try:
                ocr_result = self.ocr_model.process_image(document_path)
                text = ocr_result.get('text', '')
                
                if text:
                    llm_extracted = self._extract_with_llm(text)
                    extracted.update(llm_extracted)
            except Exception as e:
                print(f"OCR+LLM extraction failed: {e}")
        
        # Add metadata
        extracted['document_type'] = self.get_document_type()
        extracted['source_file'] = document_path
        
        return extracted
    
    def _extract_from_adi(self, adi_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract PAN fields from ADI result."""
        extracted = {}
        
        # Extract from key-value pairs
        kv_pairs = adi_result.get('key_value_pairs', {})
        
        # Map common PAN field names
        field_mappings = {
            'pan number': 'pan_number',
            'pan': 'pan_number',
            'permanent account number': 'pan_number',
            'name': 'name',
            'father name': 'father_name',
            "father's name": 'father_name',
            'date of birth': 'date_of_birth',
            'dob': 'date_of_birth',
            'gender': 'gender'
        }
        
        for key, value in kv_pairs.items():
            key_lower = key.lower()
            for pattern, field_name in field_mappings.items():
                if pattern in key_lower:
                    extracted[field_name] = value
                    break
        
        return extracted
    
    def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Extract PAN fields using LLM."""
        schema = {
            'pan_number': {
                'type': 'string',
                'description': '10-character PAN number (e.g., ABCDE1234F)',
                'required': True
            },
            'name': {
                'type': 'string',
                'description': 'Name of the PAN card holder',
                'required': True
            },
            'father_name': {
                'type': 'string',
                'description': "Father's name",
                'required': False
            },
            'date_of_birth': {
                'type': 'string',
                'description': 'Date of birth',
                'required': False
            }
        }
        
        return self.llm_model.extract_structured_data(text, schema)
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted PAN data."""
        required_fields = self.get_required_fields()
        
        for field in required_fields:
            if field not in data or not data[field]:
                return False
        
        # Validate PAN number format (10 characters, first 5 letters, next 4 numbers, last 1 letter)
        pan_number = data.get('pan_number', '')
        if len(pan_number) != 10:
            return False
        
        return True


class Aadhaar(BaseDocument):
    """Aadhaar card document type implementation."""
    
    def get_document_type(self) -> str:
        """Return document type identifier."""
        return "aadhaar"
    
    def get_required_fields(self) -> List[str]:
        """Return required fields for Aadhaar documents."""
        return [
            "aadhaar_number",
            "name"
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Return optional fields for Aadhaar documents."""
        return [
            "date_of_birth",
            "gender",
            "address"
        ]
    
    def extract_fields(self, document_path: str) -> Dict[str, Any]:
        """Extract fields specific to Aadhaar documents."""
        extracted = {}
        
        # Try using ADI if available
        if self.adi_model:
            try:
                adi_result = self.adi_model.analyze_document(document_path)
                extracted.update(self._extract_from_adi(adi_result))
            except Exception as e:
                print(f"ADI extraction failed: {e}")
        
        # Try using OCR + LLM if ADI not available or incomplete
        if self.ocr_model and self.llm_model:
            try:
                ocr_result = self.ocr_model.process_image(document_path)
                text = ocr_result.get('text', '')
                
                if text:
                    llm_extracted = self._extract_with_llm(text)
                    extracted.update(llm_extracted)
            except Exception as e:
                print(f"OCR+LLM extraction failed: {e}")
        
        # Add metadata
        extracted['document_type'] = self.get_document_type()
        extracted['source_file'] = document_path
        
        return extracted
    
    def _extract_from_adi(self, adi_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Aadhaar fields from ADI result."""
        extracted = {}
        
        # Extract from key-value pairs
        kv_pairs = adi_result.get('key_value_pairs', {})
        
        # Map common Aadhaar field names
        field_mappings = {
            'aadhaar number': 'aadhaar_number',
            'aadhaar no': 'aadhaar_number',
            'uid': 'aadhaar_number',
            'name': 'name',
            'date of birth': 'date_of_birth',
            'dob': 'date_of_birth',
            'gender': 'gender',
            'address': 'address'
        }
        
        for key, value in kv_pairs.items():
            key_lower = key.lower()
            for pattern, field_name in field_mappings.items():
                if pattern in key_lower:
                    extracted[field_name] = value
                    break
        
        return extracted
    
    def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Extract Aadhaar fields using LLM."""
        schema = {
            'aadhaar_number': {
                'type': 'string',
                'description': '12-digit Aadhaar number',
                'required': True
            },
            'name': {
                'type': 'string',
                'description': 'Name of the Aadhaar card holder',
                'required': True
            },
            'date_of_birth': {
                'type': 'string',
                'description': 'Date of birth',
                'required': False
            },
            'gender': {
                'type': 'string',
                'description': 'Gender (Male/Female)',
                'required': False
            }
        }
        
        return self.llm_model.extract_structured_data(text, schema)
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted Aadhaar data."""
        required_fields = self.get_required_fields()
        
        for field in required_fields:
            if field not in data or not data[field]:
                return False
        
        # Validate Aadhaar number format (12 digits)
        aadhaar_number = data.get('aadhaar_number', '').replace(' ', '').replace('-', '')
        if len(aadhaar_number) != 12 or not aadhaar_number.isdigit():
            return False
        
        return True
