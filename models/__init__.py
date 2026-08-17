"""
Models package - Contains all model implementations.
"""

from models.base import BaseModel, BaseOCR, BaseLLM, BaseADI, BaseDocument
from models.ocr import GLMOCR, AzureOCR, UnlimitedOCR
from models.llm import OpenAIModel, GeminiModel
from models.adi import AzureDocumentIntelligence, LegacyADI
from models.documents import Agreement, Invoice, PAN, Aadhaar

__all__ = [
    # Base classes
    'BaseModel',
    'BaseOCR',
    'BaseLLM',
    'BaseADI',
    'BaseDocument',
    
    # OCR implementations
    'GLMOCR',
    'AzureOCR',
    'UnlimitedOCR',
    
    # LLM implementations
    'OpenAIModel',
    'GeminiModel',
    
    # ADI implementations
    'AzureDocumentIntelligence',
    'LegacyADI',
    
    # Document implementations
    'Agreement',
    'Invoice',
    'PAN',
    'Aadhaar'
]
