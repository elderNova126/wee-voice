"""
SIP Client Service for Dialsense WebSocket SIP Server
Handles SIP registration and call management
"""
import asyncio
import logging
import json
import hashlib
import base64
import audioop
from typing import Optional, Dict, Callable
from datetime import datetime
import uuid

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class SIPCallSession:
    """Represents an active SIP call session"""
    
    def __init__(self, call_id: str, from_number: str, to_number: str, direction: str):
        self.call_id = call_id
        self.from_number = from_number
        self.to_number = to_number
        self.direction = direction  # 'inbound' or 'outbound'
        self.status = 'initiated'
        self.started_at = datetime.utcnow()
        self.ended_at = None
        
        # Audio queues for bidirectional audio
        self.inbound_audio_queue = asyncio.Queue()  # Audio from caller (to Gemini)
        self.outbound_audio_queue = asyncio.Queue()  # Audio from Gemini (to caller)
        
        # Audio state for resampling
        self.inbound_resample_state = None
        self.outbound_resample_state = None
        
        # Associated backend call and agent service
        self.backend_call_id = None
        self.agent_service = None
    
    def end(self):
        """Mark call as ended"""
        self.status = 'ended'
        self.ended_at = datetime.utcnow()


class SIPClientService:
    """
    SIP WebSocket client for Dialsense server
    Handles SIP signaling and audio streaming
    """
    
    def __init__(self, ws_url: str, username: str, password: str, domain: str):
        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_registered = False
        
        # SIP credentials - provided per phone number from database
        self.username = username
        self.password = password
        self.domain = domain
        self.ws_url = ws_url
        
        # Active calls: call_id -> SIPCallSession
        self.active_calls: Dict[str, SIPCallSession] = {}
        
        # Callbacks for application
        self.on_incoming_call: Optional[Callable] = None
        self.on_call_answered: Optional[Callable] = None  # For both inbound and outbound
        self.on_call_ended: Optional[Callable] = None
        self.on_call_ringing: Optional[Callable] = None  # Outbound call ringing
        self.on_call_failed: Optional[Callable] = None   # Outbound call failed
        
        # Background tasks
        self.message_handler_task = None
        self.keepalive_task = None
        
        logger.info(f"Initialized SIP client for {self.domain} (ws: {self.ws_url})")
    
    async def connect(self) -> bool:
        """Connect to SIP WebSocket server"""
        try:
            logger.info(f"Connecting to SIP server: {self.ws_url}")
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10
            )
            self.is_connected = True
            logger.info("✅ Connected to SIP WebSocket server")
            
            # Start message handler
            self.message_handler_task = asyncio.create_task(self._message_handler())
            
            # Start keepalive
            self.keepalive_task = asyncio.create_task(self._keepalive())
            
            # Register with SIP server
            await self.register()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to SIP server: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from SIP server"""
        try:
            # Cancel background tasks
            if self.keepalive_task:
                self.keepalive_task.cancel()
                try:
                    await self.keepalive_task
                except asyncio.CancelledError:
                    pass
            
            if self.message_handler_task:
                self.message_handler_task.cancel()
                try:
                    await self.message_handler_task
                except asyncio.CancelledError:
                    pass
            
            # Unregister
            if self.ws and self.is_registered:
                await self._send_unregister()
            
            # Close connection
            if self.ws:
                await self.ws.close()
                self.ws = None
            
            self.is_connected = False
            self.is_registered = False
            logger.info("Disconnected from SIP server")
            
        except Exception as e:
            logger.error(f"Error disconnecting from SIP server: {e}")
    
    async def register(self) -> bool:
        """Register with SIP server"""
        try:
            # Generate authentication
            register_message = {
                "type": "register",
                "username": self.username,
                "domain": self.domain,
                "auth": self._generate_auth()
            }
            
            await self._send_message(register_message)
            logger.info(f"Sent SIP REGISTER for {self.username}@{self.domain}")
            
            # Wait for registration response
            await asyncio.sleep(2)
            
            if self.is_registered:
                logger.info("✅ SIP registration successful")
                return True
            else:
                logger.warning("⚠️ SIP registration pending or failed")
                return False
            
        except Exception as e:
            logger.error(f"SIP registration failed: {e}")
            return False
    
    def _generate_auth(self, challenge: Optional[Dict] = None) -> str:
        """Generate SIP authentication"""
        if not challenge:
            # Basic auth
            credentials = f"{self.username}:{self.password}"
            return base64.b64encode(credentials.encode()).decode()
        
        # Digest authentication
        realm = challenge.get('realm', self.domain)
        nonce = challenge.get('nonce', '')
        method = 'REGISTER'
        uri = f"sip:{self.domain}"
        
        ha1 = hashlib.md5(f"{self.username}:{realm}:{self.password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        return response
    
    async def _send_unregister(self):
        """Unregister from SIP server"""
        try:
            unregister_message = {
                "type": "unregister",
                "username": self.username,
                "domain": self.domain
            }
            await self._send_message(unregister_message)
        except Exception as e:
            logger.error(f"Error sending UNREGISTER: {e}")
    
    async def _send_message(self, message: Dict):
        """Send JSON message to SIP server"""
        if not self.ws or not self.is_connected:
            logger.error("Cannot send message: not connected")
            return
        
        try:
            await self.ws.send(json.dumps(message))
            logger.debug(f"Sent SIP message: {message.get('type')}")
        except Exception as e:
            logger.error(f"Error sending SIP message: {e}")
    
    async def _keepalive(self):
        """Send periodic keepalive messages"""
        try:
            while self.is_connected:
                await asyncio.sleep(30)
                if self.ws and self.is_connected:
                    await self._send_message({"type": "keepalive"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in keepalive: {e}")
    
    async def _message_handler(self):
        """Handle incoming messages from SIP server"""
        try:
            async for message in self.ws:
                if isinstance(message, str):
                    # JSON signaling message
                    await self._handle_signaling(json.loads(message))
                elif isinstance(message, bytes):
                    # Binary audio data
                    await self._handle_audio(message)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("SIP WebSocket connection closed")
            self.is_connected = False
            self.is_registered = False
        except Exception as e:
            logger.error(f"Error in message handler: {e}", exc_info=True)
            self.is_connected = False
    
    async def _handle_signaling(self, message: Dict):
        """Handle SIP signaling messages"""
        msg_type = message.get('type')
        
        if msg_type == 'register_response':
            status = message.get('status')
            if status == 'success':
                self.is_registered = True
                logger.info("✅ SIP registration successful")
            elif status == 'challenge':
                # Re-register with digest auth
                challenge = message.get('challenge', {})
                auth_response = self._generate_auth(challenge)
                register_message = {
                    "type": "register",
                    "username": self.username,
                    "domain": self.domain,
                    "auth": auth_response,
                    "challenge": challenge
                }
                await self._send_message(register_message)
            else:
                logger.error(f"SIP registration failed: {message.get('reason')}")
        
        elif msg_type == 'invite':
            # Incoming call
            await self._handle_incoming_call(message)
        
        elif msg_type == 'ringing' or msg_type == 'progress':
            # Outbound call is ringing
            call_id = message.get('call_id')
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                call.status = 'ringing'
                logger.info(f"🔔 Outbound call {call_id} is ringing")
                if self.on_call_ringing:
                    try:
                        await self.on_call_ringing(call)
                    except Exception as e:
                        logger.error(f"Error in on_call_ringing callback: {e}")
        
        elif msg_type == 'answered':
            # Call answered (inbound auto-answer or outbound remote answered)
            call_id = message.get('call_id')
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                call.status = 'in_progress'
                logger.info(f"✅ Call {call_id} answered (direction: {call.direction})")
                if self.on_call_answered:
                    try:
                        await self.on_call_answered(call)
                    except Exception as e:
                        logger.error(f"Error in on_call_answered callback: {e}")
        
        elif msg_type == 'bye':
            # Call ended
            await self._handle_call_ended(message)
        
        elif msg_type in ('reject', 'busy', 'unavailable', 'timeout', 'failed'):
            # Outbound call failed
            call_id = message.get('call_id')
            reason = message.get('reason', msg_type)
            logger.warning(f"❌ Call {call_id} failed: {reason}")
            
            if call_id in self.active_calls:
                call = self.active_calls[call_id]
                call.status = 'failed'
                call.end()
                
                if self.on_call_failed:
                    try:
                        await self.on_call_failed(call, reason)
                    except Exception as e:
                        logger.error(f"Error in on_call_failed callback: {e}")
                
                # Cleanup
                del self.active_calls[call_id]
        
        elif msg_type == 'error':
            logger.error(f"SIP error: {message.get('reason')}")
    
    async def _handle_incoming_call(self, message: Dict):
        """Handle incoming call (INVITE)"""
        call_id = message.get('call_id', str(uuid.uuid4()))
        from_number = message.get('from')
        to_number = message.get('to')
        
        logger.info(f"📞 Incoming SIP call: {from_number} -> {to_number} (call_id: {call_id})")
        
        # Create call session
        call = SIPCallSession(call_id, from_number, to_number, 'inbound')
        self.active_calls[call_id] = call
        
        # Notify application
        if self.on_incoming_call:
            try:
                await self.on_incoming_call(call)
            except Exception as e:
                logger.error(f"Error in on_incoming_call callback: {e}")
        
        # Auto-answer
        await self.answer_call(call_id)
    
    async def answer_call(self, call_id: str) -> bool:
        """Answer an incoming call"""
        try:
            if call_id not in self.active_calls:
                logger.error(f"Cannot answer: call {call_id} not found")
                return False
            
            answer_message = {
                "type": "answer",
                "call_id": call_id
            }
            await self._send_message(answer_message)
            
            self.active_calls[call_id].status = 'answered'
            logger.info(f"✅ Answered SIP call {call_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error answering call: {e}")
            return False
    
    async def _handle_call_ended(self, message: Dict):
        """Handle call ended (BYE)"""
        call_id = message.get('call_id')
        
        if call_id in self.active_calls:
            call = self.active_calls[call_id]
            call.end()
            
            logger.info(f"📞 SIP call {call_id} ended")
            
            # Notify application
            if self.on_call_ended:
                try:
                    await self.on_call_ended(call)
                except Exception as e:
                    logger.error(f"Error in on_call_ended callback: {e}")
            
            # Cleanup
            del self.active_calls[call_id]
    
    async def hangup_call(self, call_id: str) -> bool:
        """Hangup a call"""
        try:
            if call_id not in self.active_calls:
                return False
            
            bye_message = {
                "type": "bye",
                "call_id": call_id
            }
            await self._send_message(bye_message)
            
            self.active_calls[call_id].end()
            logger.info(f"Sent BYE for call {call_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            return False
    
    async def make_call(self, to_number: str, from_number: Optional[str] = None) -> Optional[SIPCallSession]:
        """
        Initiate an outbound call
        
        Args:
            to_number: The number to call
            from_number: Caller ID (defaults to SIP username)
            
        Returns:
            SIPCallSession if call initiated successfully, None otherwise
        """
        if not self.is_connected or not self.is_registered:
            logger.error("Cannot make call: not connected or registered")
            return None
        
        try:
            call_id = str(uuid.uuid4())
            caller_id = from_number or self.username
            
            logger.info(f"📞 Initiating outbound call: {caller_id} -> {to_number}")
            
            # Create call session
            call = SIPCallSession(call_id, caller_id, to_number, 'outbound')
            call.status = 'calling'
            self.active_calls[call_id] = call
            
            # Send INVITE to SIP server
            invite_message = {
                "type": "invite",
                "call_id": call_id,
                "from": caller_id,
                "to": to_number,
                "domain": self.domain
            }
            await self._send_message(invite_message)
            
            logger.info(f"📤 Sent INVITE for outbound call {call_id}")
            return call
            
        except Exception as e:
            logger.error(f"Error making outbound call: {e}", exc_info=True)
            return None
    
    async def _handle_audio(self, audio_data: bytes):
        """Handle incoming audio from SIP (caller's voice)"""
        # Route to appropriate call's inbound queue
        for call_id, call in self.active_calls.items():
            if call.status == 'in_progress':
                try:
                    # Convert from SIP format (8kHz) to Gemini format (16kHz)
                    converted_audio = self._convert_to_gemini_format(audio_data, call)
                    if converted_audio:
                        await call.inbound_audio_queue.put(converted_audio)
                except Exception as e:
                    logger.error(f"Error processing audio for call {call_id}: {e}")
    
    def _convert_to_gemini_format(self, audio_data: bytes, call: SIPCallSession) -> bytes:
        """Convert SIP audio (8kHz) to Gemini format (16kHz PCM16)"""
        try:
            # Resample from 8kHz to 16kHz
            converted, call.inbound_resample_state = audioop.ratecv(
                audio_data,
                2,  # 2 bytes per sample (PCM16)
                1,  # mono
                8000,  # from rate (8kHz SIP)
                16000,  # to rate (16kHz Gemini)
                call.inbound_resample_state
            )
            return converted
        except Exception as e:
            logger.error(f"Error converting audio to Gemini format: {e}")
            return b''
    
    async def send_audio(self, call_id: str, audio_data: bytes) -> bool:
        """Send audio to caller (from Gemini, 24kHz -> 8kHz)"""
        try:
            if call_id not in self.active_calls:
                return False
            
            call = self.active_calls[call_id]
            
            # Convert from Gemini format (24kHz) to SIP format (8kHz)
            sip_audio = self._convert_to_sip_format(audio_data, call)
            
            if sip_audio and self.ws and self.is_connected:
                await self.ws.send(sip_audio)
                return True
            return False
                
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            return False
    
    def _convert_to_sip_format(self, audio_data: bytes, call: SIPCallSession) -> bytes:
        """Convert Gemini audio (24kHz) to SIP format (8kHz PCM16)"""
        try:
            # Resample from 24kHz to 8kHz
            converted, call.outbound_resample_state = audioop.ratecv(
                audio_data,
                2,  # 2 bytes per sample (PCM16)
                1,  # mono
                24000,  # from rate (24kHz Gemini)
                8000,  # to rate (8kHz SIP)
                call.outbound_resample_state
            )
            return converted
        except Exception as e:
            logger.error(f"Error converting audio to SIP format: {e}")
            return b''
    
    def get_call(self, call_id: str) -> Optional[SIPCallSession]:
        """Get call session by ID"""
        return self.active_calls.get(call_id)


def create_sip_client_from_phone_number(phone_number) -> SIPClientService:
    """
    Create a SIP client configured with phone number's SIP settings
    
    Args:
        phone_number: PhoneNumber object with SIP configuration
        
    Returns:
        SIPClientService configured with the phone number's credentials
    """
    if not (hasattr(phone_number, 'sip_websocket_url') and phone_number.sip_websocket_url):
        raise ValueError(f"Phone number {phone_number.phone_number} has no SIP configuration")
    
    return SIPClientService(
        ws_url=phone_number.sip_websocket_url,
        username=phone_number.sip_username,
        password=phone_number.sip_password,
        domain=phone_number.sip_domain
    )



