"""
Base - Abstract base classes for all model implementations.
Defines the interface that all concrete implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseModel(ABC):
    """Base class for all models."""
    
    def __init__(self, **kwargs):
        """Initialize model with configuration."""
        self.config = kwargs
    
    @abstractmethod
    def initialize(self):
        """Initialize the model (load resources, connect to services, etc.)."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources when model is no longer needed."""
        pass


class BaseOCR(BaseModel):
    """
    Abstract base class for OCR implementations.
    All OCR models must inherit from this class.
    """
    
    @abstractmethod
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        Process a single image and extract text.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        pass
    
    @abstractmethod
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a PDF document and extract text.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        pass
    
    @abstractmethod
    def process_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple files in batch.
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            List of results, one per file
        """
        pass


class BaseLLM(BaseModel):
    """
    Abstract base class for LLM implementations.
    All LLM models must inherit from this class.
    """
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text response from a prompt.
        
        Args:
            prompt: Input prompt for the LLM
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    def extract_structured_data(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured data from text using the LLM.
        
        Args:
            text: Input text to extract from
            schema: Schema defining the expected output structure
            
        Returns:
            Dictionary with extracted structured data
        """
        pass


class BaseADI(BaseModel):
    """
    Abstract base class for Document Intelligence implementations.
    All ADI models must inherit from this class.
    """
    
    @abstractmethod
    def analyze_document(self, document_path: str) -> Dict[str, Any]:
        """
        Analyze a document and extract structured information.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary containing analysis results (tables, key-value pairs, etc.)
        """
        pass
    
    @abstractmethod
    def extract_tables(self, document_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables from a document.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            List of table data
        """
        pass
    
    @abstractmethod
    def extract_key_value_pairs(self, document_path: str) -> Dict[str, str]:
        """
        Extract key-value pairs from a document.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary of key-value pairs
        """
        pass


class BaseDocument(BaseModel):
    """
    Abstract base class for document type implementations.
    All document types must inherit from this class.
    
    Documents use model interfaces through dependency injection,
    not inheritance. This allows any document to use any registered model.
    """
    
    def __init__(self, ocr_model: Optional[BaseOCR] = None, 
                 llm_model: Optional[BaseLLM] = None,
                 adi_model: Optional[BaseADI] = None,
                 **kwargs):
        """
        Initialize document with injected model dependencies.
        
        Args:
            ocr_model: OCR model instance (injected)
            llm_model: LLM model instance (injected)
            adi_model: ADI model instance (injected)
            **kwargs: Additional configuration
        """
        super().__init__(**kwargs)
        self.ocr_model = ocr_model
        self.llm_model = llm_model
        self.adi_model = adi_model
    
    @abstractmethod
    def get_document_type(self) -> str:
        """Return the document type identifier."""
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Return list of required fields for this document type."""
        pass
    
    @abstractmethod
    def get_optional_fields(self) -> List[str]:
        """Return list of optional fields for this document type."""
        pass
    
    @abstractmethod
    def extract_fields(self, document_path: str) -> Dict[str, Any]:
        """
        Extract fields specific to this document type.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary of extracted field names and values
        """
        pass
    
    @abstractmethod
    def validate_extracted_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate extracted data against document type requirements.
        
        Args:
            data: Extracted data dictionary
            
        Returns:
            True if data is valid, False otherwise
        """
        pass
    
    def set_ocr_model(self, ocr_model: BaseOCR):
        """Set or replace the OCR model."""
        self.ocr_model = ocr_model
    
    def set_llm_model(self, llm_model: BaseLLM):
        """Set or replace the LLM model."""
        self.llm_model = llm_model
    
    def set_adi_model(self, adi_model: BaseADI):
        """Set or replace the ADI model."""
        self.adi_model = adi_model
