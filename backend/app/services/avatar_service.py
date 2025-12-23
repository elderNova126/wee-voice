"""
Avatar Animation Service
Integrates with AI video generation APIs to create animated avatars from photos
"""
import logging
import base64
import os
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class AvatarAnimationService:
    """
    Service for animating avatar photos using AI video generation
    
    Supports multiple providers:
    - D-ID (https://www.d-id.com/)
    - HeyGen (https://www.heygen.com/)
    - Synthesia (https://www.synthesia.io/)
    - Custom/Local solutions
    """
    
    def __init__(self):
        self.provider = os.getenv('AVATAR_PROVIDER', 'mock')  # 'did', 'heygen', 'synthesia', 'mock'
        self.api_key = os.getenv('AVATAR_API_KEY', '')
        self.api_url = self._get_api_url()
        
    def _get_api_url(self) -> str:
        """Get API URL based on provider"""
        urls = {
            'did': 'https://api.d-id.com/talks',
            'heygen': 'https://api.heygen.com/v1/video',
            'synthesia': 'https://api.synthesia.io/v2/videos',
            'mock': 'http://localhost:8000/mock-avatar'  # For testing
        }
        return urls.get(self.provider, '')
    
    async def create_talking_avatar(
        self,
        photo_url: str,
        audio_url: Optional[str] = None,
        text: Optional[str] = None,
        voice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a talking avatar video from a photo
        
        Args:
            photo_url: URL or base64 of the source photo
            audio_url: Optional URL to audio file to lip-sync
            text: Optional text to synthesize speech from
            voice_id: Optional voice ID for text-to-speech
            
        Returns:
            Dict with video_url, status, and other metadata
        """
        try:
            if self.provider == 'mock':
                return await self._mock_create_avatar(photo_url, audio_url, text)
            elif self.provider == 'did':
                return await self._did_create_avatar(photo_url, audio_url, text, voice_id)
            elif self.provider == 'heygen':
                return await self._heygen_create_avatar(photo_url, audio_url, text, voice_id)
            elif self.provider == 'synthesia':
                return await self._synthesia_create_avatar(photo_url, text, voice_id)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"Error creating talking avatar: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _mock_create_avatar(
        self,
        photo_url: str,
        audio_url: Optional[str],
        text: Optional[str]
    ) -> Dict[str, Any]:
        """Mock implementation for testing"""
        logger.info(f"Mock avatar creation - photo: {photo_url[:50]}...")
        return {
            "success": True,
            "video_url": photo_url,  # Return the photo as-is for now
            "status": "completed",
            "provider": "mock",
            "message": "Mock avatar created (using static photo)"
        }
    
    async def _did_create_avatar(
        self,
        photo_url: str,
        audio_url: Optional[str],
        text: Optional[str],
        voice_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create avatar using D-ID API
        https://docs.d-id.com/reference/talks
        """
        if not self.api_key:
            raise ValueError("D-ID API key not configured")
        
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "source_url": photo_url if photo_url.startswith('http') else None,
            "script": {}
        }
        
        # Add audio or text
        if audio_url:
            payload["script"]["type"] = "audio"
            payload["script"]["audio_url"] = audio_url
        elif text:
            payload["script"]["type"] = "text"
            payload["script"]["input"] = text
            if voice_id:
                payload["script"]["provider"] = {"type": "microsoft", "voice_id": voice_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "video_id": data.get("id"),
                "video_url": data.get("result_url"),
                "status": data.get("status"),
                "provider": "did"
            }
    
    async def _heygen_create_avatar(
        self,
        photo_url: str,
        audio_url: Optional[str],
        text: Optional[str],
        voice_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create avatar using HeyGen API
        https://docs.heygen.com/reference/create-an-avatar-video-v2
        """
        if not self.api_key:
            raise ValueError("HeyGen API key not configured")
        
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "avatar_image": photo_url,
            "voice": {
                "voice_id": voice_id or "default"
            }
        }
        
        if audio_url:
            payload["audio_url"] = audio_url
        elif text:
            payload["script"] = text
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "video_id": data.get("video_id"),
                "video_url": data.get("video_url"),
                "status": data.get("status"),
                "provider": "heygen"
            }
    
    async def _synthesia_create_avatar(
        self,
        photo_url: str,
        text: Optional[str],
        voice_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create avatar using Synthesia API
        https://docs.synthesia.io/reference/create-video
        """
        if not self.api_key:
            raise ValueError("Synthesia API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": [
                {
                    "avatarSettings": {
                        "customAvatar": photo_url
                    },
                    "scriptText": text or "Hello, I'm your AI assistant.",
                    "voice": voice_id or "en-US-Neural2-A"
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "video_id": data.get("id"),
                "video_url": data.get("download"),
                "status": data.get("status"),
                "provider": "synthesia"
            }
    
    async def get_avatar_status(self, video_id: str) -> Dict[str, Any]:
        """
        Check the status of avatar video generation
        
        Args:
            video_id: ID of the video generation job
            
        Returns:
            Dict with status, video_url if completed, and other metadata
        """
        try:
            if self.provider == 'mock':
                return {
                    "success": True,
                    "status": "completed",
                    "video_url": "mock_video_url"
                }
            
            # Implement status checking for each provider
            # This would make API calls to check job status
            
            return {
                "success": True,
                "status": "processing",
                "message": "Status checking not yet implemented for this provider"
            }
            
        except Exception as e:
            logger.error(f"Error checking avatar status: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def is_configured(self) -> bool:
        """Check if avatar service is properly configured"""
        if self.provider == 'mock':
            return True
        return bool(self.api_key and self.api_url)
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider"""
        return {
            "provider": self.provider,
            "configured": self.is_configured(),
            "api_url": self.api_url if self.is_configured() else None,
            "features": self._get_provider_features()
        }
    
    def _get_provider_features(self) -> Dict[str, bool]:
        """Get features supported by current provider"""
        features = {
            'did': {
                'audio_input': True,
                'text_to_speech': True,
                'real_time': False,
                'custom_voices': True
            },
            'heygen': {
                'audio_input': True,
                'text_to_speech': True,
                'real_time': False,
                'custom_voices': True
            },
            'synthesia': {
                'audio_input': False,
                'text_to_speech': True,
                'real_time': False,
                'custom_voices': True
            },
            'mock': {
                'audio_input': True,
                'text_to_speech': True,
                'real_time': True,
                'custom_voices': False
            }
        }
        return features.get(self.provider, {})


# Global instance
avatar_service = AvatarAnimationService()

