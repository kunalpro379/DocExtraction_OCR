"""
Registry - Model registration and resolution system.
Manages available model implementations and resolves them based on settings.
"""

from typing import Dict, Type, Any, Optional
from abc import ABC, abstractmethod


class ModelRegistry:
    """
    Central registry for model implementations.
    Allows registration and dynamic resolution of models based on configuration.
    """
    
    def __init__(self):
        """Initialize empty registries for different model types."""
        self._ocr_models: Dict[str, Type] = {}
        self._llm_models: Dict[str, Type] = {}
        self._adi_models: Dict[str, Type] = {}
        self._document_models: Dict[str, Type] = {}
        
    def register_ocr(self, name: str, model_class: Type):
        """
        Register an OCR model implementation.
        
        Args:
            name: Unique identifier for the OCR model (e.g., 'glm', 'azure')
            model_class: The OCR model class (must inherit from BaseOCR)
        """
        self._ocr_models[name] = model_class
    
    def register_llm(self, name: str, model_class: Type):
        """
        Register an LLM model implementation.
        
        Args:
            name: Unique identifier for the LLM model (e.g., 'openai', 'gemini')
            model_class: The LLM model class (must inherit from BaseLLM)
        """
        self._llm_models[name] = model_class
    
    def register_adi(self, name: str, model_class: Type):
        """
        Register a Document Intelligence model implementation.
        
        Args:
            name: Unique identifier for the ADI model (e.g., 'azure')
            model_class: The ADI model class (must inherit from BaseADI)
        """
        self._adi_models[name] = model_class
    
    def register_document(self, name: str, document_class: Type):
        """
        Register a document model implementation.
        
        Args:
            name: Unique identifier for the document type (e.g., 'agreement', 'invoice')
            document_class: The document class (must inherit from BaseDocument)
        """
        self._document_models[name] = document_class
    
    def get_ocr(self, name: str, **kwargs) -> Any:
        """
        Get an instance of the registered OCR model.
        
        Args:
            name: Identifier of the OCR model to instantiate
            **kwargs: Arguments to pass to the model constructor
            
        Returns:
            Instance of the requested OCR model
            
        Raises:
            ValueError: If the model is not registered
        """
        if name not in self._ocr_models:
            raise ValueError(f"OCR model '{name}' not registered. Available: {list(self._ocr_models.keys())}")
        return self._ocr_models[name](**kwargs)
    
    def get_llm(self, name: str, **kwargs) -> Any:
        """
        Get an instance of the registered LLM model.
        
        Args:
            name: Identifier of the LLM model to instantiate
            **kwargs: Arguments to pass to the model constructor
            
        Returns:
            Instance of the requested LLM model
            
        Raises:
            ValueError: If the model is not registered
        """
        if name not in self._llm_models:
            raise ValueError(f"LLM model '{name}' not registered. Available: {list(self._llm_models.keys())}")
        return self._llm_models[name](**kwargs)
    
    def get_adi(self, name: str, **kwargs) -> Any:
        """
        Get an instance of the registered ADI model.
        
        Args:
            name: Identifier of the ADI model to instantiate
            **kwargs: Arguments to pass to the model constructor
            
        Returns:
            Instance of the requested ADI model
            
        Raises:
            ValueError: If the model is not registered
        """
        if name not in self._adi_models:
            raise ValueError(f"ADI model '{name}' not registered. Available: {list(self._adi_models.keys())}")
        return self._adi_models[name](**kwargs)
    
    def get_document(self, name: str, **kwargs) -> Any:
        """
        Get an instance of the registered document model.
        
        Args:
            name: Identifier of the document type to instantiate
            **kwargs: Arguments to pass to the document constructor
            
        Returns:
            Instance of the requested document model
            
        Raises:
            ValueError: If the document type is not registered
        """
        if name not in self._document_models:
            raise ValueError(f"Document type '{name}' not registered. Available: {list(self._document_models.keys())}")
        return self._document_models[name](**kwargs)
    
    def list_ocr_models(self) -> list:
        """Return list of registered OCR model names."""
        return list(self._ocr_models.keys())
    
    def list_llm_models(self) -> list:
        """Return list of registered LLM model names."""
        return list(self._llm_models.keys())
    
    def list_adi_models(self) -> list:
        """Return list of registered ADI model names."""
        return list(self._adi_models.keys())
    
    def list_document_models(self) -> list:
        """Return list of registered document type names."""
        return list(self._document_models.keys())


# Global registry instance
registry = ModelRegistry()


def register_models():
    """
    Register all available model implementations.
    This function should be called during application initialization.
    Import and register all model implementations here.
    """
    # Import model implementations
    from models.ocr import GLMOCR, AzureOCR, UnlimitedOCR
    from models.llm import OpenAIModel, GeminiModel
    from models.adi import AzureDocumentIntelligence
    from models.documents import Agreement, Invoice, PAN, Aadhaar
    
    # Register OCR models
    registry.register_ocr("glm", GLMOCR)
    registry.register_ocr("azure", AzureOCR)
    registry.register_ocr("unlimited", UnlimitedOCR)
    
    # Register LLM models
    registry.register_llm("openai", OpenAIModel)
    registry.register_llm("gemini", GeminiModel)
    
    # Register ADI models
    registry.register_adi("azure", AzureDocumentIntelligence)
    
    # Register document types
    registry.register_document("agreement", Agreement)
    registry.register_document("invoice", Invoice)
    registry.register_document("pan", PAN)
    registry.register_document("aadhaar", Aadhaar)
