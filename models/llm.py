"""
LLM - LLM model implementations.
Contains concrete implementations for different LLM services.
"""

from typing import Dict, Any
from models.base import BaseLLM


class OpenAIModel(BaseLLM):
    """OpenAI GPT model implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.model_name = None
    
    def initialize(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            
            api_key = self.config.get('api_key')
            base_url = self.config.get('base_url')
            self.model_name = self.config.get('model_name', 'gpt-4')
            
            if not api_key:
                raise ValueError("OpenAI api_key is required")
            
            client_kwargs = {'api_key': api_key}
            if base_url:
                client_kwargs['base_url'] = base_url
            
            self.client = OpenAI(**client_kwargs)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI model: {e}")
    
    def cleanup(self):
        """Clean up OpenAI resources."""
        self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI."""
        if not self.client:
            self.initialize()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 2000),
                **{k: v for k, v in kwargs.items() if k not in ['temperature', 'max_tokens']}
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
    
    def extract_structured_data(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data using OpenAI."""
        if not self.client:
            self.initialize()
        
        try:
            # Build prompt with schema
            schema_str = self._format_schema(schema)
            prompt = f"""Extract the following information from the text. Return the result as a valid JSON object.

Schema:
{schema_str}

Text:
{text}

Return only the JSON object, no other text."""
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            import json
            result_text = response.choices[0].message.content
            return json.loads(result_text)
            
        except Exception as e:
            raise RuntimeError(f"OpenAI structured extraction failed: {e}")
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format schema for prompt."""
        lines = []
        for field, field_info in schema.items():
            description = field_info.get('description', '')
            field_type = field_info.get('type', 'string')
            required = field_info.get('required', False)
            lines.append(f"- {field} ({field_type}): {description} {'(required)' if required else '(optional)'}")
        return '\n'.join(lines)


class GeminiModel(BaseLLM):
    """Google Gemini model implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.model_name = None
    
    def initialize(self):
        """Initialize Gemini client."""
        try:
            import google.generativeai as genai
            
            api_key = self.config.get('api_key')
            self.model_name = self.config.get('model_name', 'gemini-pro')
            
            if not api_key:
                raise ValueError("Gemini api_key is required")
            
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model_name)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini model: {e}")
    
    def cleanup(self):
        """Clean up Gemini resources."""
        self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Gemini."""
        if not self.client:
            self.initialize()
        
        try:
            generation_config = {
                'temperature': kwargs.get('temperature', 0.7),
                'max_output_tokens': kwargs.get('max_tokens', 2000),
            }
            
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {e}")
    
    def extract_structured_data(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data using Gemini."""
        if not self.client:
            self.initialize()
        
        try:
            # Build prompt with schema
            schema_str = self._format_schema(schema)
            prompt = f"""Extract the following information from the text. Return the result as a valid JSON object.

Schema:
{schema_str}

Text:
{text}

Return only the JSON object, no other text."""
            
            generation_config = {
                'temperature': 0.3,
                'max_output_tokens': 2000,
            }
            
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            import json
            result_text = response.text
            # Clean up any markdown code blocks
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            return json.loads(result_text)
            
        except Exception as e:
            raise RuntimeError(f"Gemini structured extraction failed: {e}")
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format schema for prompt."""
        lines = []
        for field, field_info in schema.items():
            description = field_info.get('description', '')
            field_type = field_info.get('type', 'string')
            required = field_info.get('required', False)
            lines.append(f"- {field} ({field_type}): {description} {'(required)' if required else '(optional)'}")
        return '\n'.join(lines)
