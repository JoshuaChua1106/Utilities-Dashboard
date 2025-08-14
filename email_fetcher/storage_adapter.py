"""
Storage adapter for handling file storage across local and AWS environments.
Provides abstraction layer for PDF storage and retrieval.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import hashlib

logger = logging.getLogger(__name__)


class StorageAdapter:
    """
    Handles file storage operations with support for both local filesystem and AWS S3.
    Automatically switches between storage backends based on environment configuration.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.aws_mode = os.getenv('AWS_MODE', 'false').lower() == 'true'
        self.local_base_path = Path(config.get('local_storage_path', './data/invoices'))
        
        # Ensure local directories exist
        if not self.aws_mode:
            self._ensure_local_directories()
    
    def _ensure_local_directories(self):
        """Create necessary local directory structure."""
        providers = ['energy_australia', 'origin_energy', 'sydney_water']
        for provider in providers:
            provider_path = self.local_base_path / provider
            provider_path.mkdir(parents=True, exist_ok=True)
        
        # Create processed and backup directories
        (self.local_base_path.parent / 'processed').mkdir(exist_ok=True)
        (self.local_base_path.parent / 'backups').mkdir(exist_ok=True)
    
    def save_pdf(self, pdf_data: bytes, filename: str, provider: str) -> str:
        """
        Save PDF file to appropriate storage backend.
        
        Args:
            pdf_data: Raw PDF binary data
            filename: Original filename from email
            provider: Provider name for organization
            
        Returns:
            Storage path/key where file was saved
        """
        if self.aws_mode:
            return self._save_to_s3(pdf_data, filename, provider)
        else:
            return self._save_to_local(pdf_data, filename, provider)
    
    def _save_to_local(self, pdf_data: bytes, filename: str, provider: str) -> str:
        """Save PDF to local filesystem."""
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name_without_ext = Path(filename).stem
        safe_filename = f"{timestamp}_{name_without_ext}.pdf"
        
        # Organize by provider
        provider_folder = provider.lower().replace(' ', '_')
        file_path = self.local_base_path / provider_folder / safe_filename
        
        try:
            with open(file_path, 'wb') as f:
                f.write(pdf_data)
            
            logger.info(f"PDF saved locally: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save PDF locally: {e}")
            raise
    
    def _save_to_s3(self, pdf_data: bytes, filename: str, provider: str) -> str:
        """Save PDF to AWS S3 (placeholder for AWS implementation)."""
        # This will be implemented when AWS deployment is approved
        raise NotImplementedError("S3 storage not yet implemented - use local mode")
    
    def get_file_info(self, file_path: str) -> Dict:
        """Get information about a stored file."""
        if self.aws_mode:
            return self._get_s3_file_info(file_path)
        else:
            return self._get_local_file_info(file_path)
    
    def _get_local_file_info(self, file_path: str) -> Dict:
        """Get local file information."""
        path = Path(file_path)
        if not path.exists():
            return {}
        
        stat = path.stat()
        return {
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'exists': True,
            'path': str(path)
        }
    
    def _get_s3_file_info(self, file_path: str) -> Dict:
        """Get S3 file information (placeholder)."""
        raise NotImplementedError("S3 file info not yet implemented")
    
    def list_files(self, provider: Optional[str] = None) -> List[Dict]:
        """List stored files, optionally filtered by provider."""
        if self.aws_mode:
            return self._list_s3_files(provider)
        else:
            return self._list_local_files(provider)
    
    def _list_local_files(self, provider: Optional[str] = None) -> List[Dict]:
        """List local files."""
        files = []
        
        if provider:
            provider_folder = provider.lower().replace(' ', '_')
            search_path = self.local_base_path / provider_folder
            if search_path.exists():
                for pdf_file in search_path.glob('*.pdf'):
                    files.append({
                        'name': pdf_file.name,
                        'path': str(pdf_file),
                        'provider': provider,
                        'size': pdf_file.stat().st_size,
                        'created': datetime.fromtimestamp(pdf_file.stat().st_ctime)
                    })
        else:
            # List all providers
            for provider_dir in self.local_base_path.iterdir():
                if provider_dir.is_dir():
                    for pdf_file in provider_dir.glob('*.pdf'):
                        files.append({
                            'name': pdf_file.name,
                            'path': str(pdf_file),
                            'provider': provider_dir.name,
                            'size': pdf_file.stat().st_size,
                            'created': datetime.fromtimestamp(pdf_file.stat().st_ctime)
                        })
        
        return sorted(files, key=lambda x: x['created'], reverse=True)
    
    def _list_s3_files(self, provider: Optional[str] = None) -> List[Dict]:
        """List S3 files (placeholder)."""
        raise NotImplementedError("S3 file listing not yet implemented")
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a stored file."""
        if self.aws_mode:
            return self._delete_s3_file(file_path)
        else:
            return self._delete_local_file(file_path)
    
    def _delete_local_file(self, file_path: str) -> bool:
        """Delete local file."""
        try:
            Path(file_path).unlink()
            logger.info(f"Deleted local file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete local file {file_path}: {e}")
            return False
    
    def _delete_s3_file(self, file_path: str) -> bool:
        """Delete S3 file (placeholder)."""
        raise NotImplementedError("S3 file deletion not yet implemented")
    
    def backup_file(self, file_path: str) -> str:
        """Create a backup copy of a file."""
        if self.aws_mode:
            return self._backup_s3_file(file_path)
        else:
            return self._backup_local_file(file_path)
    
    def _backup_local_file(self, file_path: str) -> str:
        """Create local backup copy."""
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        
        backup_dir = self.local_base_path.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{timestamp}_{source.name}"
        backup_path = backup_dir / backup_name
        
        # Copy file
        import shutil
        shutil.copy2(source, backup_path)
        
        logger.info(f"Created backup: {backup_path}")
        return str(backup_path)
    
    def _backup_s3_file(self, file_path: str) -> str:
        """Create S3 backup copy (placeholder)."""
        raise NotImplementedError("S3 backup not yet implemented")
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file for duplicate detection."""
        if self.aws_mode:
            return self._calculate_s3_hash(file_path)
        else:
            return self._calculate_local_hash(file_path)
    
    def _calculate_local_hash(self, file_path: str) -> str:
        """Calculate hash of local file."""
        hash_sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def _calculate_s3_hash(self, file_path: str) -> str:
        """Calculate hash of S3 file (placeholder)."""
        raise NotImplementedError("S3 hash calculation not yet implemented")