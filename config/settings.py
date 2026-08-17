"""
Settings - Configuration management for the document extraction system.
Controls which OCR, LLM, and Document Intelligence models are active.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


class Settings:
    """Central configuration for model selection and system settings."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize settings from config file or defaults.
        
        Args:
            config_path: Path to JSON config file. If None, uses defaults.
        """
        self.config_path = config_path or "config.json"
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                return self._get_default_config()
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "models": {
                "ocr": "glm",  # Options: glm, azure, unlimited
                "llm": "openai",  # Options: openai, gemini
                "document_intelligence": "azure"  # Options: azure
            },
            "paths": {
                "input": "Input",
                "output": "output",
                "extracted": "Extracted",
                "output_raw": "OutputRaw"
            },
            "processing": {
                "batch_size": 10,
                "timeout": 300,
                "retry_attempts": 3
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports nested keys with dots)."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_ocr_model(self) -> str:
        """Get the selected OCR model name."""
        return self.get("models.ocr", "glm")
    
    def get_llm_model(self) -> str:
        """Get the selected LLM model name."""
        return self.get("models.llm", "openai")
    
    def get_document_intelligence_model(self) -> str:
        """Get the selected Document Intelligence model name."""
        return self.get("models.document_intelligence", "azure")
    
    def get_input_dir(self) -> str:
        """Get input directory path."""
        return self.get("paths.input", "Input")
    
    def get_output_dir(self) -> str:
        """Get output directory path."""
        return self.get("paths.output", "output")
    
    def get_extracted_dir(self) -> str:
        """Get extracted directory path."""
        return self.get("paths.extracted", "Extracted")
    
    def get_output_raw_dir(self) -> str:
        """Get output raw directory path."""
        return self.get("paths.output_raw", "OutputRaw")
    
    def save(self):
        """Save current configuration to file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def set_ocr_model(self, model_name: str):
        """Set the OCR model to use."""
        self._config.setdefault("models", {})["ocr"] = model_name
    
    def set_llm_model(self, model_name: str):
        """Set the LLM model to use."""
        self._config.setdefault("models", {})["llm"] = model_name
    
    def set_document_intelligence_model(self, model_name: str):
        """Set the Document Intelligence model to use."""
        self._config.setdefault("models", {})["document_intelligence"] = model_name


# Global settings instance
settings = Settings()
