import logging
import os
from typing import Optional, Tuple
from datetime import datetime
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage operations using Supabase Storage"""
    
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET
        self.initialized = False
        
        # Initialize Supabase client
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                self.supabase = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_ROLE_KEY
                )
                logger.info("✅ Supabase storage client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supabase client: {e}")
                raise
        else:
            logger.warning("⚠️ Supabase credentials not configured. File upload will fail.")
    
    async def initialize_bucket(self) -> None:
        """Ensure Supabase Storage bucket exists"""
        if self.initialized or not self.supabase:
            return
        
        try:
            logger.info(f"🔄 Initializing Supabase storage bucket: {self.bucket_name}")
            
            # Check if bucket exists
            try:
                bucket_info = self.supabase.storage.get_bucket(self.bucket_name)
                logger.info(f"✅ Using existing Supabase storage bucket: {self.bucket_name}")
            except Exception as bucket_error:
                # Bucket doesn't exist, create it
                logger.info(f"📦 Bucket {self.bucket_name} not found, creating...")
                
                try:
                    self.supabase.storage.create_bucket(
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
                    logger.info(f"✅ Created Supabase storage bucket: {self.bucket_name}")
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
        filename: str,
        agent_id: int,
        user_id: int,
        mime_type: str = "application/pdf"
    ) -> Tuple[str, str]:
        """
        Upload a file to Supabase Storage
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            agent_id: Agent ID for organizing files
            user_id: User ID for organizing files
            mime_type: MIME type of the file
        
        Returns:
            Tuple of (public_url, file_path)
        """
        if not self.supabase:
            raise Exception("Supabase client not initialized. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        
        await self.initialize_bucket()
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_size:
            raise Exception(f"File size exceeds limit of {max_size / (1024 * 1024)}MB")
        
        # Generate unique file path
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        safe_filename = filename.replace(" ", "_").replace("/", "-")
        file_path = f"users/{user_id}/agents/{agent_id}/{timestamp}_{safe_filename}"
        
        logger.info(f"🔄 Uploading file: {filename} ({len(file_content)} bytes) to {file_path}")
        
        try:
            # Upload file with retry logic
            retry_count = 0
            max_retries = 3
            upload_error = None
            
            while retry_count < max_retries:
                try:
                    logger.info(f"🔄 Upload attempt {retry_count + 1}/{max_retries} for {file_path}")
                    
                    # Upload to Supabase Storage
                    result = self.supabase.storage.from_(self.bucket_name).upload(
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
            public_url_response = self.supabase.storage.from_(self.bucket_name).get_public_url(file_path)
            public_url = public_url_response
            
            if not public_url:
                raise Exception("Failed to get public URL for uploaded file")
            
            logger.info(f"✅ Uploaded: {file_path} -> {public_url}")
            
            return public_url, file_path
            
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise Exception(f"Upload failed: {str(e)}")
    
    async def delete_file(self, file_path: str) -> None:
        """
        Delete a file from Supabase Storage
        
        Args:
            file_path: Path to the file in the storage bucket
        """
        if not self.supabase:
            raise Exception("Supabase client not initialized")
        
        if not file_path:
            raise Exception("File path is required")
        
        await self.initialize_bucket()
        
        try:
            logger.info(f"🔄 Deleting file: {file_path}")
            
            result = self.supabase.storage.from_(self.bucket_name).remove([file_path])
            
            logger.info(f"✅ Deleted file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Delete file failed: {e}")
            raise Exception(f"Delete failed: {str(e)}")
    
    def extract_file_path_from_url(self, url: str) -> Optional[str]:
        """
        Extract the file path from a Supabase public URL
        
        Args:
            url: Public URL of the file
        
        Returns:
            File path or None if invalid URL
        """
        try:
            from urllib.parse import urlparse
            
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Supabase storage URLs format: /storage/v1/object/public/{bucket}/{path}
            prefix = f'/storage/v1/object/public/{self.bucket_name}/'
            
            if prefix in path:
                return path.split(prefix)[1]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting file path from URL: {e}")
            return None
    
    def is_storage_enabled(self) -> bool:
        """Check if Supabase storage is properly configured"""
        return self.supabase is not None


# Global instance
storage_service = StorageService()

