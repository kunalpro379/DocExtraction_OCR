"""
OCR - OCR model implementations.
Contains concrete implementations for different OCR services.
"""

import os
import tempfile
from typing import Dict, Any, List
from models.base import BaseOCR


class GLMOCR(BaseOCR):
    """GLM-based OCR implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = None
        self.tokenizer = None
    
    def initialize(self):
        """Initialize GLM OCR model."""
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
            
            model_name = self.config.get('model_name', 'baidu/Unlimited-OCR')
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_safetensors=True,
                torch_dtype=torch.bfloat16,
            )
            self.model = self.model.eval().cuda()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GLM OCR: {e}")
    
    def cleanup(self):
        """Clean up GLM OCR resources."""
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process a single image using GLM OCR."""
        if not self.model or not self.tokenizer:
            self.initialize()
        
        output_dir = self.config.get('output_dir', tempfile.gettempdir())
        
        try:
            self.model.infer(
                self.tokenizer,
                prompt='<image>document parsing.',
                image_file=image_path,
                output_path=output_dir,
                base_size=1024, 
                image_size=640, 
                crop_mode=True,
                max_length=32768,
                no_repeat_ngram_size=35, 
                ngram_window=128,
                save_results=True,
            )
            
            # Read the output file
            result_file = os.path.join(output_dir, os.path.basename(image_path).replace('.jpg', '.txt').replace('.png', '.txt'))
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                return {
                    'text': text,
                    'source': 'glm_ocr',
                    'file_path': image_path
                }
            else:
                return {
                    'text': '',
                    'source': 'glm_ocr',
                    'file_path': image_path,
                    'error': 'Output file not found'
                }
        except Exception as e:
            return {
                'text': '',
                'source': 'glm_ocr',
                'file_path': image_path,
                'error': str(e)
            }
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF by converting to images first."""
        try:
            import fitz  # PyMuPDF
            
            image_paths = self._pdf_to_images(pdf_path)
            
            results = []
            for img_path in image_paths:
                result = self.process_image(img_path)
                results.append(result)
            
            combined_text = '\n\n'.join([r.get('text', '') for r in results])
            
            return {
                'text': combined_text,
                'source': 'glm_ocr',
                'file_path': pdf_path,
                'pages': len(results)
            }
        except Exception as e:
            return {
                'text': '',
                'source': 'glm_ocr',
                'file_path': pdf_path,
                'error': str(e)
            }
    
    def process_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple files."""
        results = []
        for file_path in file_paths:
            if file_path.lower().endswith('.pdf'):
                result = self.process_pdf(file_path)
            else:
                result = self.process_image(file_path)
            results.append(result)
        return results
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[str]:
        """Convert PDF pages to images."""
        import fitz
        
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix='pdf_ocr_')
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        paths = []
        
        for i, page in enumerate(doc):
            out = os.path.join(tmp_dir, f'page_{i+1:04d}.png')
            page.get_pixmap(matrix=mat).save(out)
            paths.append(out)
        
        doc.close()
        return paths


class AzureOCR(BaseOCR):
    """Azure Computer Vision OCR implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
    
    def initialize(self):
        """Initialize Azure OCR client."""
        try:
            from azure.ai.vision.imageanalysis import ImageAnalysisClient
            from azure.core.credentials import AzureKeyCredential
            
            endpoint = self.config.get('endpoint')
            key = self.config.get('api_key')
            
            if not endpoint or not key:
                raise ValueError("Azure endpoint and api_key are required")
            
            self.client = ImageAnalysisClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(key)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure OCR: {e}")
    
    def cleanup(self):
        """Clean up Azure OCR resources."""
        self.client = None
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process image using Azure OCR."""
        if not self.client:
            self.initialize()
        
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
            
            result = self.client.analyze(
                image_data=image_data,
                visual_features=["READ"]
            )
            
            text = ""
            if result.read is not None:
                for line in result.read.blocks[0].lines:
                    text += line.text + "\n"
            
            return {
                'text': text.strip(),
                'source': 'azure_ocr',
                'file_path': image_path
            }
        except Exception as e:
            return {
                'text': '',
                'source': 'azure_ocr',
                'file_path': image_path,
                'error': str(e)
            }
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF using Azure OCR (requires PDF model)."""
        # Azure OCR with PDF support requires different API
        # For now, convert to images first
        return self._process_pdf_via_images(pdf_path)
    
    def process_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple files."""
        results = []
        for file_path in file_paths:
            if file_path.lower().endswith('.pdf'):
                result = self.process_pdf(file_path)
            else:
                result = self.process_image(file_path)
            results.append(result)
        return results
    
    def _process_pdf_via_images(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF by converting to images first."""
        try:
            import fitz
            
            image_paths = self._pdf_to_images(pdf_path)
            results = []
            
            for img_path in image_paths:
                result = self.process_image(img_path)
                results.append(result)
            
            combined_text = '\n\n'.join([r.get('text', '') for r in results])
            
            return {
                'text': combined_text,
                'source': 'azure_ocr',
                'file_path': pdf_path,
                'pages': len(results)
            }
        except Exception as e:
            return {
                'text': '',
                'source': 'azure_ocr',
                'file_path': pdf_path,
                'error': str(e)
            }
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[str]:
        """Convert PDF pages to images."""
        import fitz
        
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix='pdf_ocr_')
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        paths = []
        
        for i, page in enumerate(doc):
            out = os.path.join(tmp_dir, f'page_{i+1:04d}.png')
            page.get_pixmap(matrix=mat).save(out)
            paths.append(out)
        
        doc.close()
        return paths


class UnlimitedOCR(BaseOCR):
    """Unlimited OCR implementation (Baidu model)."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = None
        self.tokenizer = None
    
    def initialize(self):
        """Initialize Unlimited OCR model."""
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
            
            model_name = self.config.get('model_name', 'baidu/Unlimited-OCR')
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_safetensors=True,
                torch_dtype=torch.bfloat16,
            )
            self.model = self.model.eval().cuda()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Unlimited OCR: {e}")
    
    def cleanup(self):
        """Clean up Unlimited OCR resources."""
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process single image using Unlimited OCR."""
        if not self.model or not self.tokenizer:
            self.initialize()
        
        output_dir = self.config.get('output_dir', tempfile.gettempdir())
        
        try:
            self.model.infer(
                self.tokenizer,
                prompt='<image>document parsing.',
                image_file=image_path,
                output_path=output_dir,
                base_size=1024, 
                image_size=640, 
                crop_mode=True,
                max_length=32768,
                no_repeat_ngram_size=35, 
                ngram_window=128,
                save_results=True,
            )
            
            result_file = os.path.join(output_dir, os.path.basename(image_path).replace('.jpg', '.txt').replace('.png', '.txt'))
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                return {
                    'text': text,
                    'source': 'unlimited_ocr',
                    'file_path': image_path
                }
            else:
                return {
                    'text': '',
                    'source': 'unlimited_ocr',
                    'file_path': image_path,
                    'error': 'Output file not found'
                }
        except Exception as e:
            return {
                'text': '',
                'source': 'unlimited_ocr',
                'file_path': image_path,
                'error': str(e)
            }
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF using multi-page parsing."""
        if not self.model or not self.tokenizer:
            self.initialize()
        
        try:
            import fitz
            output_dir = self.config.get('output_dir', tempfile.gettempdir())
            
            image_paths = self._pdf_to_images(pdf_path)
            
            self.model.infer_multi(
                self.tokenizer,
                prompt='<image>Multi page parsing.',
                image_files=image_paths,
                output_path=output_dir,
                image_size=1024,
                max_length=32768,
                no_repeat_ngram_size=35, 
                ngram_window=1024,
                save_results=True,
            )
            
            # Read the output file
            result_file = os.path.join(output_dir, os.path.basename(pdf_path).replace('.pdf', '.txt'))
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                return {
                    'text': text,
                    'source': 'unlimited_ocr',
                    'file_path': pdf_path,
                    'pages': len(image_paths)
                }
            else:
                return {
                    'text': '',
                    'source': 'unlimited_ocr',
                    'file_path': pdf_path,
                    'error': 'Output file not found'
                }
        except Exception as e:
            return {
                'text': '',
                'source': 'unlimited_ocr',
                'file_path': pdf_path,
                'error': str(e)
            }
    
    def process_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple files."""
        results = []
        for file_path in file_paths:
            if file_path.lower().endswith('.pdf'):
                result = self.process_pdf(file_path)
            else:
                result = self.process_image(file_path)
            results.append(result)
        return results
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[str]:
        """Convert PDF pages to images."""
        import fitz
        
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix='pdf_ocr_')
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        paths = []
        
        for i, page in enumerate(doc):
            out = os.path.join(tmp_dir, f'page_{i+1:04d}.png')
            page.get_pixmap(matrix=mat).save(out)
            paths.append(out)
        
        doc.close()
        return paths
