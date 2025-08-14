"""
OCR adapter for handling text extraction from PDFs.
Provides abstraction layer between local OCR and AWS Textract.
"""

import os
import logging
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRAdapter:
    """
    Handles OCR operations with support for both local tools and AWS Textract.
    Automatically switches between backends based on environment configuration.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.aws_mode = os.getenv('AWS_MODE', 'false').lower() == 'true'
        self.tesseract_available = self._check_tesseract_availability()
        
        if not self.aws_mode and not self.tesseract_available:
            logger.warning("Neither Tesseract nor AWS mode available - OCR functionality limited")
    
    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract OCR is available on the system."""
        try:
            import pytesseract
            # Try to get version to verify it's working
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            return False
    
    def extract_text(self, pdf_path: str) -> Dict[str, any]:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        if self.aws_mode:
            return self._textract_extract(pdf_path)
        else:
            return self._local_extract(pdf_path)
    
    def _local_extract(self, pdf_path: str) -> Dict[str, any]:
        """Extract text using local tools (pdfplumber + pytesseract)."""
        try:
            import pdfplumber
            
            result = {
                'text': '',
                'pages': [],
                'method': 'local',
                'confidence': 0.0,
                'error': None
            }
            
            # First try pdfplumber for text-based PDFs
            text_content = self._extract_with_pdfplumber(pdf_path)
            
            if text_content and len(text_content.strip()) > 50:
                # Good text extraction
                result['text'] = text_content
                result['confidence'] = 0.95
                result['pages'] = [{'text': text_content, 'method': 'pdfplumber'}]
                logger.info(f"Text extracted with pdfplumber: {len(text_content)} characters")
                
            elif self.tesseract_available:
                # Fallback to OCR for scanned PDFs
                ocr_result = self._extract_with_tesseract(pdf_path)
                result.update(ocr_result)
                logger.info(f"Text extracted with OCR: {len(result['text'])} characters")
                
            else:
                result['error'] = "No suitable extraction method available"
                logger.error(f"Failed to extract text from {pdf_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Local text extraction failed for {pdf_path}: {e}")
            return {
                'text': '',
                'pages': [],
                'method': 'local',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """Extract text using pdfplumber."""
        try:
            import pdfplumber
            
            text_content = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    page_text = page.extract_text()
                    
                    if page_text:
                        text_content.append(f"--- Page {page_num + 1} ---")
                        text_content.append(page_text)
                        
                        # Also try to extract tables
                        tables = page.extract_tables()
                        for table_num, table in enumerate(tables):
                            text_content.append(f"--- Table {table_num + 1} ---")
                            for row in table:
                                if row:
                                    text_content.append(" | ".join(str(cell) if cell else "" for cell in row))
            
            return "\n".join(text_content)
            
        except Exception as e:
            logger.error(f"PDFplumber extraction failed: {e}")
            return ""
    
    def _extract_with_tesseract(self, pdf_path: str) -> Dict[str, any]:
        """Extract text using Tesseract OCR."""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            
            result = {
                'text': '',
                'pages': [],
                'method': 'tesseract',
                'confidence': 0.0,
                'error': None
            }
            
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=300)
            
            all_text = []
            total_confidence = 0
            
            for page_num, image in enumerate(images):
                # Extract text with confidence scores
                ocr_data = pytesseract.image_to_data(
                    image, 
                    output_type=pytesseract.Output.DICT,
                    config='--psm 6'  # Assume uniform block of text
                )
                
                # Filter confident text
                page_text = []
                confidences = []
                
                for i, word in enumerate(ocr_data['text']):
                    if word.strip():
                        confidence = int(ocr_data['conf'][i])
                        if confidence > 30:  # Only include confident words
                            page_text.append(word)
                            confidences.append(confidence)
                
                page_content = " ".join(page_text)
                page_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                result['pages'].append({
                    'text': page_content,
                    'confidence': page_confidence,
                    'method': 'tesseract'
                })
                
                all_text.append(f"--- Page {page_num + 1} ---")
                all_text.append(page_content)
                total_confidence += page_confidence
            
            result['text'] = "\n".join(all_text)
            result['confidence'] = total_confidence / len(images) if images else 0
            
            return result
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return {
                'text': '',
                'pages': [],
                'method': 'tesseract',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _textract_extract(self, pdf_path: str) -> Dict[str, any]:
        """Extract text using AWS Textract (placeholder)."""
        # This will be implemented when AWS deployment is approved
        raise NotImplementedError("AWS Textract not yet implemented - use local mode")
    
    def preprocess_text(self, text: str) -> str:
        """
        Clean and preprocess extracted text for better parsing.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors
        text = self._fix_common_ocr_errors(text)
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n', text)
        
        return text.strip()
    
    def _fix_common_ocr_errors(self, text: str) -> str:
        """Fix common OCR misrecognitions."""
        
        # Common number confusions
        replacements = {
            # Letters confused with numbers
            'O': '0',  # in numeric contexts
            'l': '1',  # in numeric contexts
            'I': '1',  # in numeric contexts
            'S': '5',  # in numeric contexts
            
            # Common currency symbol errors
            '$5': '$',
            'AU$': 'AUD',
            'A$': 'AUD',
            
            # Common words
            'arnount': 'amount',
            'arnount': 'amount',
            'bil1': 'bill',
            'bi11': 'bill',
            'tota1': 'total',
            'tot al': 'total',
            'KWH': 'kWh',
            'kwh': 'kWh',
            'KW H': 'kWh',
        }
        
        # Apply replacements with context sensitivity
        for wrong, correct in replacements.items():
            # For number replacements, only apply in numeric contexts
            if wrong in ['O', 'l', 'I', 'S'] and correct.isdigit():
                # Look for patterns like "$O.00" or "1l.50"
                pattern = r'(\$|AUD|AUD\$)([0-9]*' + re.escape(wrong) + r'[0-9]*\.?[0-9]*)'
                text = re.sub(pattern, lambda m: m.group(1) + m.group(2).replace(wrong, correct), text)
            else:
                text = text.replace(wrong, correct)
        
        return text
    
    def extract_text_regions(self, pdf_path: str, regions: List[Dict]) -> Dict[str, str]:
        """
        Extract text from specific regions of the PDF.
        
        Args:
            pdf_path: Path to PDF file
            regions: List of region definitions with coordinates
            
        Returns:
            Dictionary mapping region names to extracted text
        """
        if self.aws_mode:
            return self._textract_extract_regions(pdf_path, regions)
        else:
            return self._local_extract_regions(pdf_path, regions)
    
    def _local_extract_regions(self, pdf_path: str, regions: List[Dict]) -> Dict[str, str]:
        """Extract text from regions using local tools."""
        try:
            import pdfplumber
            
            results = {}
            
            with pdfplumber.open(pdf_path) as pdf:
                for region in regions:
                    region_name = region.get('name', 'unknown')
                    page_num = region.get('page', 0)
                    bbox = region.get('bbox')  # (x0, y0, x1, y1)
                    
                    if page_num < len(pdf.pages) and bbox:
                        page = pdf.pages[page_num]
                        
                        # Crop page to region
                        cropped = page.within_bbox(bbox)
                        text = cropped.extract_text()
                        
                        results[region_name] = text or ""
                    else:
                        results[region_name] = ""
            
            return results
            
        except Exception as e:
            logger.error(f"Region extraction failed: {e}")
            return {region.get('name', 'unknown'): "" for region in regions}
    
    def _textract_extract_regions(self, pdf_path: str, regions: List[Dict]) -> Dict[str, str]:
        """Extract text from regions using AWS Textract (placeholder)."""
        raise NotImplementedError("Textract region extraction not yet implemented")
    
    def get_extraction_confidence(self, pdf_path: str) -> float:
        """
        Get confidence score for text extraction quality.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            result = self.extract_text(pdf_path)
            return result.get('confidence', 0.0)
        except Exception as e:
            logger.error(f"Failed to get extraction confidence: {e}")
            return 0.0