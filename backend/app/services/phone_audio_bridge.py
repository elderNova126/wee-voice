"""
Phone Call Audio Bridge Service
Bridges audio between Zadarma phone calls and Gemini API
Similar to WebSocket audio handling but for phone calls via HTTP
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PhoneAudioBridge:
    """
    Bridges audio between phone calls (via HTTP) and Gemini API
    
    This service handles:
    - Receiving audio from Zadarma (caller's voice) → Send to Gemini
    - Receiving audio from Gemini (AI responses) → Send to Zadarma (via HTTP callback)
    """
    
    def __init__(self, agent_service, call_id: str, zadarma_call_id: str):
        """
        Initialize phone audio bridge
        
        Args:
            agent_service: FrenchVoiceAgentService instance
            call_id: Internal call ID
            zadarma_call_id: Zadarma's call ID
        """
        self.agent_service = agent_service
        self.call_id = call_id
        self.zadarma_call_id = zadarma_call_id
        self.is_running = False
        self.audio_tasks = []
        
        # Audio format: PCM16, 16kHz for input (caller), 24kHz for output (Gemini)
        self.input_sample_rate = 16000
        self.output_sample_rate = 24000
        
        # Queue for audio from Gemini to send to Zadarma
        self.gemini_audio_queue = asyncio.Queue()
        
        logger.info(f"Initialized phone audio bridge for call {call_id}")
    
    async def start(self):
        """Start the audio bridge"""
        if self.is_running:
            logger.warning(f"Audio bridge already running for call {self.call_id}")
            return
        
        self.is_running = True
        logger.info(f"Starting phone audio bridge for call {self.call_id}")
        
        # Start audio streaming task: Receive audio from Gemini and queue it
        task = asyncio.create_task(self._stream_gemini_audio())
        self.audio_tasks = [task]
        
        logger.info(f"Phone audio bridge started for call {self.call_id}")
    
    async def stop(self):
        """Stop the audio bridge"""
        if not self.is_running:
            return
        
        logger.info(f"Stopping phone audio bridge for call {self.call_id}")
        self.is_running = False
        
        # Cancel all tasks
        for task in self.audio_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.audio_tasks = []
        logger.info(f"Phone audio bridge stopped for call {self.call_id}")
    
    async def _stream_gemini_audio(self):
        """
        Stream audio from Gemini API and queue it for sending to Zadarma
        This includes the greeting and all AI responses
        """
        logger.info(f"Starting Gemini audio stream for call {self.call_id}")
        
        try:
            async for audio_data in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                
                # Queue audio for sending to Zadarma
                await self.gemini_audio_queue.put(audio_data)
                logger.debug(f"Queued {len(audio_data)} bytes from Gemini for call {self.call_id}")
                
        except asyncio.CancelledError:
            logger.info(f"Gemini audio stream cancelled for call {self.call_id}")
        except Exception as e:
            logger.error(f"Error in Gemini audio stream: {e}", exc_info=True)
        finally:
            logger.info(f"Gemini audio stream ended for call {self.call_id}")
    
    async def receive_phone_audio(self, audio_data: bytes):
        """
        Receive audio packet from Zadarma (caller's voice)
        This is called by the HTTP endpoint when audio arrives
        
        Args:
            audio_data: PCM16 audio data at 16kHz
        """
        if not self.is_running:
            logger.warning(f"Audio bridge not running, ignoring audio for call {self.call_id}")
            return
        
        try:
            # Send audio to Gemini via agent service
            await self.agent_service.send_audio(
                audio_data,
                mime_type="audio/pcm;rate=16000"
            )
            logger.debug(f"Forwarded {len(audio_data)} bytes from phone to Gemini for call {self.call_id}")
        except Exception as e:
            logger.error(f"Error forwarding audio to Gemini: {e}", exc_info=True)
    
    async def get_gemini_audio(self) -> Optional[bytes]:
        """
        Get next audio chunk from Gemini (for sending to Zadarma)
        This is called by the HTTP endpoint when Zadarma requests audio
        
        Returns:
            Audio data bytes or None if no audio available
        """
        if not self.is_running:
            return None
        
        try:
            # Get audio from queue with timeout
            audio_data = await asyncio.wait_for(
                self.gemini_audio_queue.get(),
                timeout=0.1
            )
            return audio_data
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error getting Gemini audio: {e}", exc_info=True)
            return None


class PhoneCallAudioManager:
    """
    Manages phone call audio bridges for multiple concurrent calls
    """
    
    def __init__(self):
        self.active_bridges: dict[str, PhoneAudioBridge] = {}
        logger.info("Phone call audio manager initialized")
    
    async def create_bridge(
        self,
        agent_service,
        call_id: str,
        zadarma_call_id: str
    ) -> PhoneAudioBridge:
        """
        Create and start an audio bridge for a phone call
        
        Args:
            agent_service: FrenchVoiceAgentService instance
            call_id: Internal call ID
            zadarma_call_id: Zadarma's call ID
            
        Returns:
            PhoneAudioBridge instance
        """
        logger.info(f"Creating phone audio bridge: call_id={call_id}, zadarma_call_id={zadarma_call_id}")
        
        # Create audio bridge
        bridge = PhoneAudioBridge(agent_service, call_id, zadarma_call_id)
        self.active_bridges[call_id] = bridge
        
        # Start the bridge
        await bridge.start()
        
        return bridge
    
    async def end_bridge(self, call_id: str):
        """End an audio bridge and clean up"""
        if call_id in self.active_bridges:
            bridge = self.active_bridges[call_id]
            await bridge.stop()
            del self.active_bridges[call_id]
            logger.info(f"Ended phone audio bridge: {call_id}")
    
    def get_bridge(self, call_id: str) -> Optional[PhoneAudioBridge]:
        """Get active bridge for a call"""
        return self.active_bridges.get(call_id)
    
    def get_bridge_by_zadarma_id(self, zadarma_call_id: str) -> Optional[PhoneAudioBridge]:
        """Get active bridge by Zadarma call ID"""
        for bridge in self.active_bridges.values():
            if bridge.zadarma_call_id == zadarma_call_id:
                return bridge
        return None


# Global phone call audio manager instance
phone_audio_manager = PhoneCallAudioManager()

