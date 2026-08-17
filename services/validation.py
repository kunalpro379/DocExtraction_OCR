"""
Validation - Data validation service.
Provides common validation logic for extracted data.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


class ValidationService:
    """Service for validating extracted document data."""
    
    def __init__(self):
        """Initialize validation service with validation rules."""
        self.validation_rules = {
            'pan_number': self._validate_pan_number,
            'aadhaar_number': self._validate_aadhaar_number,
            'email': self._validate_email,
            'phone': self._validate_phone,
            'date': self._validate_date,
            'amount': self._validate_amount,
            'required_field': self._validate_required_field
        }
    
    def validate_extracted_data(self, data: Dict[str, Any], document_type: str) -> Tuple[bool, List[str]]:
        """
        Validate extracted data for a document type.
        
        Args:
            data: Extracted data dictionary
            document_type: Type of document
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Get required fields for document type
        try:
            from config import registry
            document = registry.get_document(document_type)
            required_fields = document.get_required_fields()
        except:
            # Fallback if registry not available
            required_fields = []
        
        # Check required fields
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"Missing required field: {field}")
            elif not self._validate_field(field, data[field]):
                errors.append(f"Invalid value for field: {field}")
        
        # Validate specific field formats
        for field, value in data.items():
            if value and not self._validate_field(field, value):
                errors.append(f"Invalid format for field: {field}")
        
        return (len(errors) == 0, errors)
    
    def _validate_field(self, field_name: str, value: Any) -> bool:
        """
        Validate a specific field based on its name and value.
        
        Args:
            field_name: Name of the field
            value: Field value
            
        Returns:
            True if valid, False otherwise
        """
        if not value:
            return True  # Empty values are handled by required field validation
        
        field_lower = field_name.lower()
        
        # PAN number validation
        if 'pan' in field_lower and 'number' in field_lower:
            return self._validate_pan_number(value)
        
        # Aadhaar number validation
        if 'aadhaar' in field_lower or 'uid' in field_lower:
            return self._validate_aadhaar_number(value)
        
        # Email validation
        if 'email' in field_lower:
            return self._validate_email(value)
        
        # Phone validation
        if 'phone' in field_lower or 'mobile' in field_lower or 'contact' in field_lower:
            return self._validate_phone(value)
        
        # Date validation
        if 'date' in field_lower and 'birth' not in field_lower:
            return self._validate_date(value)
        
        # Amount validation
        if 'amount' in field_lower or 'price' in field_lower or 'cost' in field_lower:
            return self._validate_amount(value)
        
        return True
    
    def _validate_pan_number(self, value: str) -> bool:
        """
        Validate Indian PAN number format.
        Format: 5 letters + 4 numbers + 1 letter (e.g., ABCDE1234F)
        """
        if not isinstance(value, str):
            return False
        
        # Remove spaces and convert to uppercase
        pan = value.replace(' ', '').upper()
        
        # Check length
        if len(pan) != 10:
            return False
        
        # Check pattern: 5 letters, 4 numbers, 1 letter
        pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        return bool(re.match(pattern, pan))
    
    def _validate_aadhaar_number(self, value: str) -> bool:
        """
        Validate Indian Aadhaar number format.
        Format: 12 digits (can have spaces or dashes)
        """
        if not isinstance(value, str):
            return False
        
        # Remove spaces and dashes
        aadhaar = value.replace(' ', '').replace('-', '')
        
        # Check if all digits and length 12
        return len(aadhaar) == 12 and aadhaar.isdigit()
    
    def _validate_email(self, value: str) -> bool:
        """Validate email format."""
        if not isinstance(value, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, value))
    
    def _validate_phone(self, value: str) -> bool:
        """
        Validate phone number format.
        Accepts Indian and international formats.
        """
        if not isinstance(value, str):
            return False
        
        # Remove common separators
        phone = value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Indian format: 10 digits (can start with +91)
        if phone.startswith('+91'):
            phone = phone[3:]
        
        # Check if all digits and reasonable length (10-15)
        return phone.isdigit() and 10 <= len(phone) <= 15
    
    def _validate_date(self, value: str) -> bool:
        """
        Validate date format.
        Accepts common date formats.
        """
        if not isinstance(value, str):
            return False
        
        # Try parsing common date formats
        date_formats = [
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%d %B %Y',
            '%B %d, %Y'
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def _validate_amount(self, value: Any) -> bool:
        """
        Validate amount/price format.
        Accepts numeric values and currency strings.
        """
        if isinstance(value, (int, float)):
            return value >= 0
        
        if isinstance(value, str):
            # Remove currency symbols and commas
            amount_str = value.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace('₹', '').replace('INR', '').strip()
            
            try:
                amount = float(amount_str)
                return amount >= 0
            except ValueError:
                return False
        
        return False
    
    def _validate_required_field(self, value: Any) -> bool:
        """Validate that a required field is not empty."""
        if value is None:
            return False
        if isinstance(value, str):
            return len(value.strip()) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True
    
    def sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize extracted data by removing extra whitespace and normalizing formats.
        
        Args:
            data: Raw extracted data
            
        Returns:
            Sanitized data dictionary
        """
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Trim whitespace
                sanitized[key] = value.strip()
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    item.strip() if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def mask_sensitive_data(self, data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """
        Mask sensitive data fields for logging/display purposes.
        
        Args:
            data: Extracted data
            document_type: Type of document
            
        Returns:
            Data with sensitive fields masked
        """
        masked = data.copy()
        
        sensitive_fields = {
            'pan': ['pan_number', 'pan'],
            'aadhaar': ['aadhaar_number', 'aadhaar', 'uid'],
            'all': ['password', 'pin', 'ssn', 'credit_card']
        }
        
        # Determine which fields to mask based on document type
        fields_to_mask = sensitive_fields.get(document_type, []) + sensitive_fields.get('all', [])
        
        for field in fields_to_mask:
            if field in masked and masked[field]:
                value = str(masked[field])
                # Show first 2 and last 2 characters
                if len(value) > 4:
                    masked[field] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked[field] = '*' * len(value)
        
        return masked


# Global validation service instance
validation_service = ValidationService()
