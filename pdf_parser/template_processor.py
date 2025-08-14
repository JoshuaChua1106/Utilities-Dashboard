"""
Template processor for parsing utility invoices using provider-specific patterns.
Handles regex-based data extraction and validation.
"""

import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class TemplateProcessor:
    """
    Processes utility invoice text using provider-specific templates.
    Handles pattern matching, data validation, and error recovery.
    """
    
    def __init__(self, templates_path: str = "./config/templates"):
        self.templates_path = Path(templates_path)
        self.templates = {}
        self.load_templates()
    
    def load_templates(self):
        """Load all parsing templates from the templates directory."""
        try:
            if not self.templates_path.exists():
                logger.error(f"Templates directory not found: {self.templates_path}")
                return
            
            for template_file in self.templates_path.glob("*.json"):
                try:
                    with open(template_file, 'r') as f:
                        template_data = json.load(f)
                    
                    provider = template_data.get('provider')
                    if provider:
                        self.templates[provider] = template_data
                        logger.info(f"Loaded template for {provider}")
                    else:
                        logger.warning(f"Template missing provider name: {template_file}")
                        
                except Exception as e:
                    logger.error(f"Failed to load template {template_file}: {e}")
            
            logger.info(f"Loaded {len(self.templates)} parsing templates")
            
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
    
    def get_available_providers(self) -> List[str]:
        """Get list of providers with available templates."""
        return list(self.templates.keys())
    
    def parse_invoice(self, text: str, provider: str) -> Dict[str, Any]:
        """
        Parse invoice text using provider-specific template.
        
        Args:
            text: Extracted text from PDF
            provider: Provider name (must match template)
            
        Returns:
            Dictionary with parsed invoice data
        """
        if provider not in self.templates:
            raise ValueError(f"No template available for provider: {provider}")
        
        template = self.templates[provider]
        patterns = template.get('patterns', {})
        
        result = {
            'provider_name': provider,
            'service_type': template.get('service_type', 'Unknown'),
            'parsing_confidence': 0.0,
            'extracted_data': {},
            'validation_errors': [],
            'parsing_warnings': [],
            'template_version': template.get('version', '1.0')
        }
        
        # Extract data using patterns
        extracted_data = {}
        confidence_scores = []
        
        for field_name, pattern_config in patterns.items():
            field_result = self._extract_field(text, field_name, pattern_config)
            
            if field_result['value'] is not None:
                extracted_data[field_name] = field_result['value']
                confidence_scores.append(field_result['confidence'])
            elif pattern_config.get('required', False):
                result['validation_errors'].append(f"Required field '{field_name}' not found")
            
            if field_result['warnings']:
                result['parsing_warnings'].extend(field_result['warnings'])
        
        result['extracted_data'] = extracted_data
        result['parsing_confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Apply post-processing
        post_processing = template.get('post_processing', {})
        processed_data = self._apply_post_processing(extracted_data, post_processing)
        result['extracted_data'] = processed_data
        
        # Validate extracted data
        validation_errors = self._validate_extracted_data(processed_data, template)
        result['validation_errors'].extend(validation_errors)
        
        return result
    
    def _extract_field(self, text: str, field_name: str, pattern_config: Dict) -> Dict:
        """Extract a single field using its pattern configuration."""
        result = {
            'value': None,
            'confidence': 0.0,
            'warnings': []
        }
        
        regex_patterns = pattern_config.get('regex', [])
        field_type = pattern_config.get('type', 'string')
        required = pattern_config.get('required', False)
        
        # Try each regex pattern
        for pattern in regex_patterns:
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                
                if match:
                    raw_value = match.group(1)
                    
                    # Convert to appropriate type
                    converted_value = self._convert_value(raw_value, field_type, pattern_config)
                    
                    if converted_value is not None:
                        result['value'] = converted_value
                        result['confidence'] = 1.0  # Full confidence for successful regex match
                        
                        logger.debug(f"Extracted {field_name}: {converted_value} using pattern: {pattern}")
                        break
                    else:
                        result['warnings'].append(f"Failed to convert '{raw_value}' for field '{field_name}'")
                
            except re.error as e:
                logger.error(f"Invalid regex pattern for {field_name}: {pattern} - {e}")
                result['warnings'].append(f"Invalid regex pattern: {e}")
            except Exception as e:
                logger.error(f"Error extracting {field_name}: {e}")
                result['warnings'].append(f"Extraction error: {e}")
        
        # If no pattern matched and it's required, try fuzzy matching
        if result['value'] is None and required:
            fuzzy_result = self._fuzzy_extract_field(text, field_name, pattern_config)
            if fuzzy_result['value'] is not None:
                result.update(fuzzy_result)
                result['warnings'].append(f"Used fuzzy matching for {field_name}")
        
        return result
    
    def _convert_value(self, raw_value: str, field_type: str, config: Dict) -> Any:
        """Convert raw string value to appropriate Python type."""
        try:
            raw_value = raw_value.strip()
            
            if field_type == 'decimal':
                # Remove commas and currency symbols
                cleaned = re.sub(r'[,$\s]', '', raw_value)
                value = float(cleaned)
                
                # Apply validation if specified
                validation = config.get('validation', {})
                min_val = validation.get('min')
                max_val = validation.get('max')
                
                if min_val is not None and value < min_val:
                    logger.warning(f"Value {value} below minimum {min_val}")
                    return None
                
                if max_val is not None and value > max_val:
                    logger.warning(f"Value {value} above maximum {max_val}")
                    return None
                
                return value
            
            elif field_type == 'date':
                date_format = config.get('format', '%d/%m/%Y')
                return datetime.strptime(raw_value, date_format).date()
            
            elif field_type == 'integer':
                cleaned = re.sub(r'[,\s]', '', raw_value)
                return int(cleaned)
            
            elif field_type == 'string':
                return raw_value
            
            else:
                logger.warning(f"Unknown field type: {field_type}")
                return raw_value
        
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Failed to convert '{raw_value}' to {field_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Conversion error for '{raw_value}': {e}")
            return None
    
    def _fuzzy_extract_field(self, text: str, field_name: str, config: Dict) -> Dict:
        """Attempt fuzzy extraction for required fields that weren't found."""
        result = {
            'value': None,
            'confidence': 0.0,
            'warnings': []
        }
        
        # Define fuzzy patterns for common fields
        fuzzy_patterns = {
            'total_amount': [
                r'total[:\s]*\$?([0-9,]+\.?[0-9]*)',
                r'amount[:\s]*\$?([0-9,]+\.?[0-9]*)',
                r'due[:\s]*\$?([0-9,]+\.?[0-9]*)',
                r'\$([0-9,]+\.[0-9]{2})\s*(?:total|due|amount)'
            ],
            'invoice_date': [
                r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                r'(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})'
            ],
            'usage_quantity': [
                r'([0-9,]+\.?[0-9]*)\s*kwh',
                r'usage[:\s]*([0-9,]+\.?[0-9]*)',
                r'consumption[:\s]*([0-9,]+\.?[0-9]*)'
            ]
        }
        
        if field_name in fuzzy_patterns:
            for pattern in fuzzy_patterns[field_name]:
                try:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        raw_value = match.group(1)
                        converted_value = self._convert_value(raw_value, config.get('type', 'string'), config)
                        
                        if converted_value is not None:
                            result['value'] = converted_value
                            result['confidence'] = 0.6  # Lower confidence for fuzzy matches
                            logger.info(f"Fuzzy extraction for {field_name}: {converted_value}")
                            break
                
                except Exception as e:
                    logger.warning(f"Fuzzy extraction error for {field_name}: {e}")
        
        return result
    
    def _apply_post_processing(self, data: Dict, post_config: Dict) -> Dict:
        """Apply post-processing rules to extracted data."""
        processed = data.copy()
        
        try:
            # Apply amount multiplier
            amount_multiplier = post_config.get('amount_multiplier', 1.0)
            if amount_multiplier != 1.0 and 'total_amount' in processed:
                processed['total_amount'] *= amount_multiplier
                
            if amount_multiplier != 1.0 and 'service_charge' in processed:
                processed['service_charge'] *= amount_multiplier
            
            # Round decimal values
            round_decimals = post_config.get('round_decimals', 2)
            for field in ['total_amount', 'usage_rate', 'service_charge']:
                if field in processed and isinstance(processed[field], (int, float)):
                    processed[field] = round(processed[field], round_decimals)
            
            # Ensure date fields are strings for JSON serialization
            date_format = post_config.get('date_format', '%Y-%m-%d')
            for field in ['invoice_date', 'billing_period_start', 'billing_period_end']:
                if field in processed and hasattr(processed[field], 'strftime'):
                    processed[field] = processed[field].strftime(date_format)
            
        except Exception as e:
            logger.error(f"Post-processing error: {e}")
        
        return processed
    
    def _validate_extracted_data(self, data: Dict, template: Dict) -> List[str]:
        """Validate extracted data against template rules."""
        errors = []
        
        try:
            validation_rules = template.get('post_processing', {}).get('validation_rules', {})
            
            # Check amount-usage correlation
            if validation_rules.get('amount_usage_correlation', False):
                if 'total_amount' in data and 'usage_quantity' in data and 'usage_rate' in data:
                    expected_amount = data['usage_quantity'] * data['usage_rate']
                    actual_amount = data['total_amount']
                    
                    # Allow 20% variance for service charges etc.
                    if abs(expected_amount - actual_amount) / actual_amount > 0.2:
                        errors.append(f"Amount/usage correlation check failed: expected ~${expected_amount:.2f}, got ${actual_amount:.2f}")
            
            # Check date sequence
            if validation_rules.get('date_sequence_check', False):
                if 'billing_period_start' in data and 'billing_period_end' in data:
                    try:
                        start_date = datetime.strptime(data['billing_period_start'], '%Y-%m-%d').date()
                        end_date = datetime.strptime(data['billing_period_end'], '%Y-%m-%d').date()
                        
                        if start_date >= end_date:
                            errors.append("Billing period start date is not before end date")
                        
                        # Check if period is reasonable (1-100 days)
                        period_days = (end_date - start_date).days
                        if period_days < 1 or period_days > 100:
                            errors.append(f"Billing period length unusual: {period_days} days")
                    
                    except ValueError as e:
                        errors.append(f"Date validation error: {e}")
            
            # Check reasonable rates
            if validation_rules.get('reasonable_rates_check', False):
                if 'usage_rate' in data:
                    rate = data['usage_rate']
                    service_type = template.get('service_type', '').lower()
                    
                    # Define reasonable rate ranges by service type
                    reasonable_ranges = {
                        'electricity': (0.10, 0.60),  # $/kWh
                        'gas': (0.02, 0.10),          # $/MJ
                        'water': (0.001, 0.01)        # $/L
                    }
                    
                    if service_type in reasonable_ranges:
                        min_rate, max_rate = reasonable_ranges[service_type]
                        if not (min_rate <= rate <= max_rate):
                            errors.append(f"Usage rate ${rate:.3f} outside reasonable range for {service_type}")
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            errors.append(f"Validation process error: {e}")
        
        return errors
    
    def get_template_info(self, provider: str) -> Dict:
        """Get information about a specific template."""
        if provider not in self.templates:
            return {}
        
        template = self.templates[provider]
        patterns = template.get('patterns', {})
        
        return {
            'provider': provider,
            'service_type': template.get('service_type'),
            'version': template.get('version'),
            'fields': list(patterns.keys()),
            'required_fields': [name for name, config in patterns.items() if config.get('required', False)],
            'optional_fields': [name for name, config in patterns.items() if not config.get('required', False)],
            'has_validation': bool(template.get('post_processing', {}).get('validation_rules')),
            'ocr_settings': template.get('ocr_settings', {})
        }
    
    def test_template(self, provider: str, sample_text: str) -> Dict:
        """
        Test a template against sample text for debugging.
        
        Args:
            provider: Provider name
            sample_text: Sample invoice text
            
        Returns:
            Detailed parsing results for debugging
        """
        if provider not in self.templates:
            return {'error': f'Template not found for provider: {provider}'}
        
        result = self.parse_invoice(sample_text, provider)
        
        # Add debugging information
        template = self.templates[provider]
        patterns = template.get('patterns', {})
        
        debug_info = {
            'template_info': self.get_template_info(provider),
            'parsing_result': result,
            'field_details': {}
        }
        
        # Test each pattern individually
        for field_name, pattern_config in patterns.items():
            field_debug = {
                'patterns_tested': pattern_config.get('regex', []),
                'matches_found': [],
                'conversion_attempts': []
            }
            
            for pattern in pattern_config.get('regex', []):
                try:
                    matches = re.findall(pattern, sample_text, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        field_debug['matches_found'].append({
                            'pattern': pattern,
                            'matches': matches
                        })
                except re.error as e:
                    field_debug['matches_found'].append({
                        'pattern': pattern,
                        'error': str(e)
                    })
            
            debug_info['field_details'][field_name] = field_debug
        
        return debug_info