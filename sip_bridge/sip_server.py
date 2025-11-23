"""
SIP Server for Zadarma Call Bridge
Accepts incoming SIP calls and bridges audio to WebSocket backend
"""
import asyncio
import logging
import json
import uuid
from typing import Optional, Dict
from datetime import datetime

import av
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay, MediaPlayer, MediaRecorder
from aiortc.rtcrtpsender import RTCRtpSender
from aioice import Candidate
import websockets

from config import (
    SIP_HOST, SIP_PORT, SIP_USERNAME, SIP_PASSWORD,
    BACKEND_WS_URL, BACKEND_API_KEY,
    INPUT_SAMPLE_RATE, OUTPUT_SAMPLE_RATE,
    LOG_LEVEL
)

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioBridge:
    """
    Bridges audio between SIP call (RTP) and WebSocket backend
    """
    
    def __init__(self, call_id: str, agent_id: int):
        self.call_id = call_id
        self.agent_id = agent_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running = False
        
        # Audio queues
        self.sip_to_backend_queue = asyncio.Queue()
        self.backend_to_sip_queue = asyncio.Queue()
        
        logger.info(f"Created AudioBridge for call {call_id}")
    
    async def connect_backend(self):
        """Connect to Railway backend WebSocket"""
        try:
            # Build WebSocket URL with agent_id and auth
            ws_url = f"{BACKEND_WS_URL}/{self.agent_id}"
            if BACKEND_API_KEY:
                ws_url += f"?api_key={BACKEND_API_KEY}"
            
            logger.info(f"Connecting to backend: {ws_url}")
            self.ws = await websockets.connect(ws_url)
            logger.info(f"✅ Connected to backend for call {self.call_id}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to backend: {e}")
            return False
    
    async def start(self):
        """Start the audio bridge"""
        if not await self.connect_backend():
            raise Exception("Failed to connect to backend")
        
        self.is_running = True
        
        # Start bidirectional audio forwarding
        asyncio.create_task(self._forward_sip_to_backend())
        asyncio.create_task(self._forward_backend_to_sip())
        
        logger.info(f"✅ Audio bridge started for call {self.call_id}")
    
    async def stop(self):
        """Stop the audio bridge"""
        self.is_running = False
        
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        logger.info(f"Audio bridge stopped for call {self.call_id}")
    
    async def _forward_sip_to_backend(self):
        """Forward audio from SIP (caller) to backend (Gemini)"""
        try:
            while self.is_running and self.ws:
                # Get audio from SIP
                audio_data = await self.sip_to_backend_queue.get()
                
                # Send to backend via WebSocket
                await self.ws.send(audio_data)
                
                logger.debug(f"Forwarded {len(audio_data)} bytes from SIP to backend")
        except Exception as e:
            logger.error(f"Error forwarding SIP to backend: {e}")
    
    async def _forward_backend_to_sip(self):
        """Forward audio from backend (Gemini) to SIP (caller)"""
        try:
            while self.is_running and self.ws:
                # Receive audio from backend
                audio_data = await self.ws.recv()
                
                # Queue for sending to SIP
                await self.backend_to_sip_queue.put(audio_data)
                
                logger.debug(f"Forwarded {len(audio_data)} bytes from backend to SIP")
        except Exception as e:
            logger.error(f"Error forwarding backend to SIP: {e}")
    
    async def send_sip_audio(self, audio_data: bytes):
        """Receive audio from SIP call and queue for backend"""
        if self.is_running:
            await self.sip_to_backend_queue.put(audio_data)
    
    async def get_backend_audio(self) -> Optional[bytes]:
        """Get audio from backend to send to SIP"""
        try:
            return await asyncio.wait_for(self.backend_to_sip_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None


class SIPCallHandler:
    """
    Handles individual SIP calls
    """
    
    def __init__(self, peer_connection: RTCPeerConnection, call_id: str, agent_id: int):
        self.pc = peer_connection
        self.call_id = call_id
        self.agent_id = agent_id
        self.bridge: Optional[AudioBridge] = None
        
        logger.info(f"Created SIPCallHandler for call {call_id}")
    
    async def handle_call(self, offer: RTCSessionDescription):
        """Handle incoming SIP call"""
        try:
            # Create audio bridge
            self.bridge = AudioBridge(self.call_id, self.agent_id)
            await self.bridge.start()
            
            # Set up audio track handlers
            @self.pc.on("track")
            async def on_track(track):
                logger.info(f"📞 Received {track.kind} track from caller")
                
                if track.kind == "audio":
                    # Start processing incoming audio
                    asyncio.create_task(self._process_incoming_audio(track))
            
            # Set remote description (SIP INVITE offer)
            await self.pc.setRemoteDescription(offer)
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            logger.info(f"✅ SIP call answered for {self.call_id}")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error handling call: {e}")
            raise
    
    async def _process_incoming_audio(self, track: MediaStreamTrack):
        """Process incoming audio from caller"""
        try:
            while True:
                # Get audio frame from RTP
                frame = await track.recv()
                
                # Convert to PCM16 at 16kHz
                audio_data = self._convert_audio(frame, INPUT_SAMPLE_RATE)
                
                # Send to backend via bridge
                if self.bridge:
                    await self.bridge.send_sip_audio(audio_data)
                
        except Exception as e:
            logger.error(f"Error processing incoming audio: {e}")
    
    def _convert_audio(self, frame, target_sample_rate: int) -> bytes:
        """Convert audio frame to PCM16 at target sample rate"""
        # Convert av.AudioFrame to numpy array
        audio_array = frame.to_ndarray()
        
        # Resample if needed
        if frame.sample_rate != target_sample_rate:
            # Simple resampling (for production, use proper resampling)
            ratio = target_sample_rate / frame.sample_rate
            new_length = int(len(audio_array) * ratio)
            audio_array = np.interp(
                np.linspace(0, len(audio_array), new_length),
                np.arange(len(audio_array)),
                audio_array
            )
        
        # Convert to int16
        audio_int16 = (audio_array * 32767).astype(np.int16)
        
        return audio_int16.tobytes()
    
    async def close(self):
        """Close the call"""
        if self.bridge:
            await self.bridge.stop()
        
        await self.pc.close()
        logger.info(f"Call {self.call_id} closed")


class SimpleSIPServer:
    """
    Simplified SIP server that handles basic SIP signaling
    Note: This is a basic implementation. For production, consider using
    a full SIP stack like PJSIP or FreeSWITCH
    """
    
    def __init__(self):
        self.active_calls: Dict[str, SIPCallHandler] = {}
        logger.info("SimpleSIPServer initialized")
    
    async def start(self):
        """Start the SIP server"""
        logger.info(f"🚀 Starting SIP server on {SIP_HOST}:{SIP_PORT}")
        
        # Note: aiortc doesn't include a built-in SIP server
        # This would need to be implemented with a proper SIP library
        # like PJSIP or using a SIP proxy like Kamailio
        
        logger.warning("⚠️  Full SIP implementation requires PJSIP or similar")
        logger.warning("⚠️  This is a WebRTC/RTP handler only")
        logger.warning("⚠️  Consider using FreeSWITCH or Asterisk for production SIP")
        
        # For now, we'll need to use a different approach
        # See README for deployment options
    
    async def handle_invite(self, sip_message: dict):
        """Handle SIP INVITE request"""
        call_id = str(uuid.uuid4())
        
        # Extract agent_id from SIP headers or use default
        agent_id = sip_message.get("agent_id", 1)
        
        # Create peer connection for WebRTC/RTP
        pc = RTCPeerConnection()
        
        # Create call handler
        handler = SIPCallHandler(pc, call_id, agent_id)
        self.active_calls[call_id] = handler
        
        # Handle the call
        offer = RTCSessionDescription(
            sdp=sip_message.get("sdp"),
            type="offer"
        )
        
        answer = await handler.handle_call(offer)
        
        return {
            "call_id": call_id,
            "sdp": answer.sdp,
            "status": "answered"
        }


# For testing and development
async def test_websocket_connection():
    """Test connection to backend WebSocket"""
    try:
        logger.info("Testing WebSocket connection to backend...")
        
        ws_url = f"{BACKEND_WS_URL}/1"  # Test with agent_id=1
        if BACKEND_API_KEY:
            ws_url += f"?api_key={BACKEND_API_KEY}"
        
        async with websockets.connect(ws_url) as ws:
            logger.info("✅ Successfully connected to backend WebSocket")
            
            # Send test audio
            test_audio = b'\x00' * 1024  # Silent audio
            await ws.send(test_audio)
            
            logger.info("✅ Sent test audio")
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            logger.info(f"✅ Received response: {len(response)} bytes")
            
            return True
    except Exception as e:
        logger.error(f"❌ WebSocket connection test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("SIP Bridge Server Starting...")
    
    # Test WebSocket connection first
    asyncio.run(test_websocket_connection())
    
    # Note: Full SIP server requires additional implementation
    # See deployment options in README.md

