import logging
import os
from typing import Optional, Tuple
from datetime import datetime
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage operations"""
    
    def __init__(self):
        self.storage_client: Optional[Client] = None
        self.bucket_name = getattr(settings, 'STORAGE_BUCKET', 'voice-agent-documents')
        self.initialized = False
        
        # Initialize storage client (optional - gracefully handle missing credentials)
        storage_url = getattr(settings, 'STORAGE_URL', None)
        storage_key = getattr(settings, 'STORAGE_KEY', None)
        
        if storage_url and storage_key:
            try:
                self.storage_client = create_client(storage_url, storage_key)
                logger.info("✅ Storage client initialized")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize storage client: {e}. File uploads will use local storage.")
                self.storage_client = None
        else:
            logger.warning("⚠️ Storage credentials not configured. File uploads will use local storage.")
    
    async def initialize_bucket(self) -> None:
        """Ensure storage bucket exists"""
        if self.initialized or not self.storage_client:
            return
        
        try:
            logger.info(f"🔄 Initializing storage bucket: {self.bucket_name}")
            
            # Check if bucket exists
            try:
                bucket_info = self.storage_client.storage.get_bucket(self.bucket_name)
                logger.info(f"✅ Using existing storage bucket: {self.bucket_name}")
            except Exception as bucket_error:
                # Bucket doesn't exist, create it
                logger.info(f"📦 Bucket {self.bucket_name} not found, creating...")
                
                try:
                    self.storage_client.storage.create_bucket(
                        self.bucket_name,
                        options={
                            "public": True,
                            "allowedMimeTypes": [
                                "application/pdf",
                                "application/msword",
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "text/plain"
                            ]
                        }
                    )
                    logger.info(f"✅ Created storage bucket: {self.bucket_name}")
                except Exception as create_error:
                    logger.error(f"❌ Error creating storage bucket: {create_error}")
                    raise Exception(f"Failed to create storage bucket: {str(create_error)}")
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"❌ Error initializing storage bucket: {e}")
            raise Exception(f"Failed to initialize storage bucket: {str(e)}")
    
    async def upload_file(
        self,
        file_content: bytes,
        file_path: str = None,
        filename: str = None,
        agent_id: int = None,
        user_id: int = None,
        mime_type: str = "application/pdf",
        content_type: str = None
    ) -> str:
        """
        Upload a file to storage or local storage
        
        Args:
            file_content: File content as bytes
            file_path: Optional file path to use
            filename: Original filename
            agent_id: Agent ID for organizing files
            user_id: User ID for organizing files
            mime_type: MIME type of the file
            content_type: Alternative parameter for mime_type
        
        Returns:
            File path or public URL
        """
        # Use content_type if provided (for compatibility)
        if content_type:
            mime_type = content_type
            
        # If storage client is not configured, fall back to local storage
        if not self.storage_client:
            return await self._upload_local(file_content, file_path or filename, user_id, agent_id)
        
        await self.initialize_bucket()
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_size:
            raise Exception(f"File size exceeds limit of {max_size / (1024 * 1024)}MB")
        
        # Generate unique file path  
        if not file_path:
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            safe_filename = (filename or "file").replace(" ", "_").replace("/", "-")
            if user_id and agent_id:
                file_path = f"users/{user_id}/agents/{agent_id}/{timestamp}_{safe_filename}"
            else:
                file_path = f"uploads/{timestamp}_{safe_filename}"
        
        logger.info(f"🔄 Uploading file: {filename} ({len(file_content)} bytes) to {file_path}")
        
        try:
            # Upload file with retry logic
            retry_count = 0
            max_retries = 3
            upload_error = None
            
            while retry_count < max_retries:
                try:
                    logger.info(f"🔄 Upload attempt {retry_count + 1}/{max_retries} for {file_path}")
                    
                    # Upload to storage
                    result = self.storage_client.storage.from_(self.bucket_name).upload(
                        path=file_path,
                        file=file_content,
                        file_options={
                            "content-type": mime_type,
                            "upsert": "false"
                        }
                    )
                    
                    logger.info(f"✅ Upload successful on attempt {retry_count + 1}")
                    upload_error = None
                    break
                    
                except Exception as e:
                    upload_error = e
                    retry_count += 1
                    logger.error(f"❌ Upload attempt {retry_count} failed: {str(e)}")
                    
                    if retry_count < max_retries:
                        import time
                        delay = 2 ** (retry_count - 1)  # Exponential backoff
                        logger.warning(f"⚠️ Retrying in {delay} seconds...")
                        time.sleep(delay)
            
            if upload_error:
                logger.error(f"❌ Upload failed after all retries: {upload_error}")
                raise Exception(f"Upload failed: {str(upload_error)}")
            
            # Get public URL
            public_url_response = self.storage_client.storage.from_(self.bucket_name).get_public_url(file_path)
            public_url = public_url_response
            
            if not public_url:
                raise Exception("Failed to get public URL for uploaded file")
            
            logger.info(f"✅ Uploaded: {file_path} -> {public_url}")
            
            # Return just the file path for consistency (can be local path or storage path)
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise Exception(f"Upload failed: {str(e)}")
    
    async def delete_file(self, file_path: str) -> None:
        """
        Delete a file from storage
        
        Args:
            file_path: Path to the file in the storage bucket
        """
        if not self.storage_client:
            raise Exception("Storage client not initialized")
        
        if not file_path:
            raise Exception("File path is required")
        
        await self.initialize_bucket()
        
        try:
            logger.info(f"🔄 Deleting file: {file_path}")
            
            result = self.storage_client.storage.from_(self.bucket_name).remove([file_path])
            
            logger.info(f"✅ Deleted file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Delete file failed: {e}")
            raise Exception(f"Delete failed: {str(e)}")
    
    def extract_file_path_from_url(self, url: str) -> Optional[str]:
        """
        Extract the file path from a storage public URL
        
        Args:
            url: Public URL of the file
        
        Returns:
            File path or None if invalid URL
        """
        try:
            from urllib.parse import urlparse
            
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Storage URLs format: /storage/v1/object/public/{bucket}/{path}
            prefix = f'/storage/v1/object/public/{self.bucket_name}/'
            
            if prefix in path:
                return path.split(prefix)[1]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting file path from URL: {e}")
            return None
    
    async def _upload_local(
        self,
        file_content: bytes,
        filename: str,
        user_id: int = None,
        agent_id: int = None
    ) -> str:
        """
        Upload file to local storage as fallback
        
        Args:
            file_content: File content as bytes
            filename: Filename
            user_id: User ID
            agent_id: Agent ID
            
        Returns:
            Local file path
        """
        try:
            # Create upload directory structure
            upload_dir = getattr(settings, 'UPLOAD_DIR', 'uploads')
            if user_id and agent_id:
                full_path = os.path.join(upload_dir, 'documents', str(user_id), str(agent_id))
            else:
                full_path = os.path.join(upload_dir, 'documents')
            
            os.makedirs(full_path, exist_ok=True)
            
            # Generate unique filename
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            safe_filename = filename.replace(" ", "_").replace("/", "-")
            file_path = os.path.join(full_path, f"{timestamp}_{safe_filename}")
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"✅ Uploaded to local storage: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Local upload failed: {e}")
            raise Exception(f"Local upload failed: {str(e)}")
    
    def get_public_url(self, file_path: str) -> Optional[str]:
        """
        Get the public URL for a file in storage
        
        Args:
            file_path: Path to the file in storage
        
        Returns:
            Public URL or None if storage is not enabled
        """
        if not self.storage_client:
            return None
        
        try:
            public_url_response = self.storage_client.storage.from_(self.bucket_name).get_public_url(file_path)
            return public_url_response
        except Exception as e:
            logger.error(f"❌ Error getting public URL: {e}")
            return None
    
    def is_storage_enabled(self) -> bool:
        """Check if storage is properly configured"""
        return self.storage_client is not None


# Global instance
_storage_service = None


def get_storage_service() -> StorageService:
    """
    Get or create the global storage service instance
    
    Returns:
        StorageService instance
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


# Legacy global instance for backward compatibility
storage_service = get_storage_service()

