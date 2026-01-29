"""
SIP Client Service for WebSocket SIP (RFC 7118)
Handles SIP registration and call management using proper SIP protocol over WebSocket
"""
import asyncio
import logging
import hashlib
import audioop
import re
import random
import string
from typing import Optional, Dict, Callable
from datetime import datetime
import uuid

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


def generate_branch():
    """Generate a unique branch parameter for Via header"""
    return "z9hG4bK" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))


def generate_tag():
    """Generate a unique tag for From/To headers"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def generate_call_id():
    """Generate a unique Call-ID"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))


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
        
        # SIP dialog info
        self.sip_call_id = None
        self.local_tag = None
        self.remote_tag = None
    
    def end(self):
        """Mark call as ended"""
        self.status = 'ended'
        self.ended_at = datetime.utcnow()


class SIPClientService:
    """
    SIP WebSocket client implementing RFC 7118 (SIP over WebSocket)
    Handles SIP signaling and audio streaming
    """
    
    def __init__(self, ws_url: str, username: str, password: str, domain: str):
        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_registered = False
        
        # SIP credentials
        self.username = username
        self.password = password
        self.domain = domain
        self.ws_url = ws_url
        
        # Extract host from ws_url for Via header
        self.local_ip = "127.0.0.1"  # Will be updated on connection
        self.local_port = 4783
        
        # SIP state
        self.cseq = 1
        self.register_call_id = generate_call_id()
        self.from_tag = generate_tag()
        
        # Active calls: call_id -> SIPCallSession
        self.active_calls: Dict[str, SIPCallSession] = {}
        
        # Response queue for registration and other requests
        self.response_queue: asyncio.Queue = asyncio.Queue()
        
        # Callbacks for application
        self.on_incoming_call: Optional[Callable] = None
        self.on_call_answered: Optional[Callable] = None
        self.on_call_ended: Optional[Callable] = None
        self.on_call_ringing: Optional[Callable] = None
        self.on_call_failed: Optional[Callable] = None
        
        # Background tasks
        self.message_handler_task = None
        self.keepalive_task = None
        self.register_refresh_task = None
        
        logger.info(f"Initialized SIP client for {self.username}@{self.domain}")
    
    async def connect(self) -> bool:
        """Connect to SIP WebSocket server"""
        import ssl
        import socket
        
        try:
            print(f"[SIP Client] Connecting to: {self.ws_url}")
            logger.info(f"Connecting to SIP server: {self.ws_url}")
            
            # Parse URL to check host resolution
            from urllib.parse import urlparse
            parsed = urlparse(self.ws_url)
            host = parsed.hostname
            
            # Check if host is resolvable
            try:
                socket.gethostbyname(host)
                logger.info(f"DNS resolved: {host}")
            except socket.gaierror as dns_error:
                logger.error(f"DNS resolution failed for {host}: {dns_error}")
                logger.error(f"HINT: If Asterisk is on the same server, use ws://localhost:8089/ws")
                logger.error(f"HINT: Or use the server's IP address instead of hostname")
                return False
            
            # Configure SSL for WSS connections
            ssl_context = None
            if self.ws_url.startswith("wss://"):
                ssl_context = ssl.create_default_context()
                # Allow self-signed certificates for internal servers
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.info("Using WSS with relaxed SSL verification (for self-signed certs)")
            
            # SIP over WebSocket requires the 'sip' subprotocol
            connect_kwargs = {
                "subprotocols": ["sip"],
                "ping_interval": 30,
                "ping_timeout": 10,
                "close_timeout": 5
            }
            if ssl_context:
                connect_kwargs["ssl"] = ssl_context
            
            self.ws = await websockets.connect(self.ws_url, **connect_kwargs)
            self.is_connected = True
            print("[SIP Client] ✅ WebSocket connected!")
            logger.info("✅ Connected to SIP WebSocket server")
            
            # Start message handler FIRST (handles all incoming messages)
            self.message_handler_task = asyncio.create_task(self._message_handler())
            
            # Small delay to ensure message handler is running
            await asyncio.sleep(0.1)
            
            # Register with SIP server
            success = await self.register()
            
            if success:
                # Start keepalive/re-registration
                self.register_refresh_task = asyncio.create_task(self._register_refresh())
            
            return success
            
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for SIP server: {e}")
            logger.error(f"URL: {self.ws_url}")
            logger.error(f"SOLUTION: Use ws://localhost:8089/ws if Asterisk is on same server")
            self.is_connected = False
            return False
        except ConnectionRefusedError as e:
            logger.error(f"Connection refused to SIP server: {e}")
            logger.error(f"URL: {self.ws_url}")
            logger.error(f"SOLUTION: Check that Asterisk is running and WebSocket transport is enabled on port 8089")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to SIP server: {e}")
            logger.error(f"URL: {self.ws_url}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from SIP server"""
        try:
            # Cancel background tasks
            if self.register_refresh_task:
                self.register_refresh_task.cancel()
                try:
                    await self.register_refresh_task
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
    
    def _build_sip_uri(self, user: str = None) -> str:
        """Build a SIP URI"""
        if user:
            return f"sip:{user}@{self.domain}"
        return f"sip:{self.domain}"
    
    def _build_register_request(self, auth_header: str = None) -> str:
        """Build a SIP REGISTER request"""
        branch = generate_branch()
        self.cseq += 1
        
        # Build headers
        headers = [
            f"REGISTER {self._build_sip_uri()} SIP/2.0",
            f"Via: SIP/2.0/WSS {self.domain};branch={branch};rport",
            f"Max-Forwards: 70",
            f"From: <{self._build_sip_uri(self.username)}>;tag={self.from_tag}",
            f"To: <{self._build_sip_uri(self.username)}>",
            f"Call-ID: {self.register_call_id}",
            f"CSeq: {self.cseq} REGISTER",
            f"Contact: <sip:{self.username}@{self.domain};transport=ws>",
            f"Expires: 600",
            f"Allow: INVITE, ACK, CANCEL, BYE, NOTIFY, REFER, MESSAGE, OPTIONS, INFO, SUBSCRIBE",
            f"Supported: outbound, path, gruu",
            f"User-Agent: WeeVoice/1.0",
            f"Content-Length: 0",
        ]
        
        # Add authorization if provided
        if auth_header:
            headers.insert(-1, auth_header)
        
        return "\r\n".join(headers) + "\r\n\r\n"
    
    def _build_auth_header(self, challenge: dict, method: str = "REGISTER") -> str:
        """Build Authorization header for digest authentication"""
        realm = challenge.get('realm', self.domain)
        nonce = challenge.get('nonce', '')
        opaque = challenge.get('opaque', '')
        qop = challenge.get('qop', '')
        uri = self._build_sip_uri()
        
        # Calculate digest response
        ha1 = hashlib.md5(f"{self.username}:{realm}:{self.password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        
        if qop:
            # QoP (Quality of Protection) requires cnonce and nc
            cnonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
            nc = "00000001"  # nonce count
            response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
            
            auth = f'Authorization: Digest username="{self.username}", realm="{realm}", '
            auth += f'nonce="{nonce}", uri="{uri}", response="{response}", algorithm=MD5, '
            auth += f'cnonce="{cnonce}", nc={nc}, qop={qop}'
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
            auth = f'Authorization: Digest username="{self.username}", realm="{realm}", '
            auth += f'nonce="{nonce}", uri="{uri}", response="{response}", algorithm=MD5'
        
        # Add opaque if present
        if opaque:
            auth += f', opaque="{opaque}"'
        
        return auth
    
    def _parse_challenge(self, www_authenticate: str) -> dict:
        """Parse WWW-Authenticate header"""
        challenge = {}
        
        # Remove "Digest " prefix
        if www_authenticate.lower().startswith("digest "):
            www_authenticate = www_authenticate[7:]
        
        # Parse parameters
        pattern = r'(\w+)=["\']?([^"\'>,]+)["\']?'
        matches = re.findall(pattern, www_authenticate)
        for key, value in matches:
            challenge[key.lower()] = value
        
        return challenge
    
    def _parse_sip_response(self, message: str) -> dict:
        """Parse a SIP response message"""
        lines = message.split("\r\n")
        if not lines:
            return {}
        
        result = {
            "headers": {},
            "body": ""
        }
        
        # Parse status line
        status_line = lines[0]
        if status_line.startswith("SIP/2.0"):
            parts = status_line.split(" ", 2)
            if len(parts) >= 2:
                result["status_code"] = int(parts[1])
                result["status_text"] = parts[2] if len(parts) > 2 else ""
        elif " SIP/2.0" in status_line:
            # This is a request, not a response
            parts = status_line.split(" ")
            result["method"] = parts[0]
            result["request_uri"] = parts[1] if len(parts) > 1 else ""
        
        # Parse headers
        body_start = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                result["headers"][key.strip().lower()] = value.strip()
        
        # Parse body
        if body_start < len(lines):
            result["body"] = "\r\n".join(lines[body_start:])
        
        return result
    
    async def register(self) -> bool:
        """Register with SIP server"""
        try:
            print(f"[SIP Client] Sending REGISTER for {self.username}@{self.domain}")
            logger.info(f"Sending REGISTER for {self.username}@{self.domain}")
            
            # Clear any old responses in queue
            while not self.response_queue.empty():
                try:
                    self.response_queue.get_nowait()
                except:
                    break
            
            # Send initial REGISTER
            register_msg = self._build_register_request()
            logger.debug(f"REGISTER message:\n{register_msg[:500]}...")
            await self._send_message(register_msg)
            
            # Wait for response
            response = await self._wait_for_response(timeout=10)
            
            if not response:
                logger.error("No response to REGISTER (timeout)")
                return False
            
            status_code = response.get("status_code", 0)
            logger.info(f"REGISTER response: {status_code}")
            
            if status_code == 200:
                self.is_registered = True
                logger.info("✅ SIP registration successful")
                return True
            
            elif status_code == 401 or status_code == 407:
                # Authentication required
                www_auth = response["headers"].get("www-authenticate", "")
                if not www_auth:
                    www_auth = response["headers"].get("proxy-authenticate", "")
                
                logger.info(f"Auth challenge: {www_auth[:100]}...")
                
                if www_auth:
                    logger.info("Authentication required, sending credentials...")
                    challenge = self._parse_challenge(www_auth)
                    logger.info(f"Parsed challenge: {challenge}")
                    auth_header = self._build_auth_header(challenge)
                    logger.info(f"Auth header: {auth_header[:100]}...")
                    
                    # Resend with auth
                    register_msg = self._build_register_request(auth_header)
                    logger.info(f"Sending authenticated REGISTER:\n{register_msg[:500]}...")
                    await self._send_message(register_msg)
                    
                    # Wait for response
                    response = await self._wait_for_response(timeout=10)
                    
                    if response and response.get("status_code") == 200:
                        self.is_registered = True
                        logger.info("✅ SIP registration successful (with auth)")
                        return True
                    else:
                        status = response.get("status_code") if response else "timeout"
                        logger.error(f"Registration failed after auth: {status}")
                        if response:
                            logger.error(f"Response headers: {response.get('headers', {})}")
                            logger.error(f"Full response: {response}")
                        return False
                else:
                    logger.error("401 response but no WWW-Authenticate header")
                    logger.error(f"Headers received: {response.get('headers', {})}")
                    return False
            
            else:
                logger.error(f"Registration failed with status {status_code}")
                logger.error(f"Response: {response}")
                return False
            
        except Exception as e:
            logger.error(f"SIP registration failed: {e}", exc_info=True)
            return False
    
    async def _send_unregister(self):
        """Unregister from SIP server (Expires: 0)"""
        try:
            self.cseq += 1
            branch = generate_branch()
            
            headers = [
                f"REGISTER {self._build_sip_uri()} SIP/2.0",
                f"Via: SIP/2.0/WSS {self.domain};branch={branch};rport",
                f"Max-Forwards: 70",
                f"From: <{self._build_sip_uri(self.username)}>;tag={self.from_tag}",
                f"To: <{self._build_sip_uri(self.username)}>",
                f"Call-ID: {self.register_call_id}",
                f"CSeq: {self.cseq} REGISTER",
                f"Contact: *",
                f"Expires: 0",
                f"Content-Length: 0",
            ]
            
            msg = "\r\n".join(headers) + "\r\n\r\n"
            await self._send_message(msg)
            logger.info("Sent UNREGISTER")
        except Exception as e:
            logger.error(f"Error sending UNREGISTER: {e}")
    
    async def _send_message(self, message: str):
        """Send SIP message to server"""
        if not self.ws or not self.is_connected:
            logger.error("Cannot send message: not connected")
            return
        
        try:
            await self.ws.send(message)
            # Log first line of message
            first_line = message.split("\r\n")[0]
            logger.info(f"📤 Sent: {first_line}")
        except Exception as e:
            logger.error(f"Error sending SIP message: {e}")
    
    async def _wait_for_response(self, timeout: float = 5) -> Optional[dict]:
        """Wait for a SIP response from the response queue"""
        try:
            response = await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for SIP response")
            return None
        except Exception as e:
            logger.error(f"Error waiting for response: {e}")
            return None
    
    async def _register_refresh(self):
        """Periodically refresh registration"""
        try:
            while self.is_connected and self.is_registered:
                await asyncio.sleep(300)  # Re-register every 5 minutes
                if self.is_connected:
                    logger.info("Refreshing SIP registration...")
                    await self.register()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in register refresh: {e}")
    
    async def _message_handler(self):
        """Handle incoming SIP messages"""
        logger.info("Message handler started")
        try:
            async for message in self.ws:
                if isinstance(message, str):
                    # Log first line of received message
                    first_line = message.split("\r\n")[0] if message else "(empty)"
                    logger.info(f"📨 Received: {first_line}")
                    await self._handle_sip_message(message)
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
    
    async def _handle_sip_message(self, message: str):
        """Handle incoming SIP message"""
        parsed = self._parse_sip_response(message)
        
        if "method" in parsed:
            # This is a SIP request
            method = parsed["method"]
            logger.info(f"📨 Received SIP {method}")
            
            if method == "INVITE":
                await self._handle_invite(parsed, message)
            elif method == "BYE":
                await self._handle_bye(parsed, message)
            elif method == "ACK":
                pass  # ACK doesn't need response
            elif method == "CANCEL":
                await self._handle_cancel(parsed, message)
            elif method == "OPTIONS":
                await self._send_options_response(parsed, message)
        else:
            # This is a SIP response - put it in the queue for waiting callers
            status_code = parsed.get("status_code", 0)
            logger.debug(f"📨 Received SIP {status_code} response")
            
            # Put response in queue (non-blocking)
            try:
                self.response_queue.put_nowait(parsed)
            except asyncio.QueueFull:
                logger.warning("Response queue full, discarding response")
    
    async def _handle_invite(self, parsed: dict, raw_message: str):
        """Handle incoming INVITE (incoming call)"""
        try:
            headers = parsed.get("headers", {})
            
            # Extract call info
            from_header = headers.get("from", "")
            to_header = headers.get("to", "")
            call_id = headers.get("call-id", str(uuid.uuid4()))
            
            # Parse From header to get caller number
            from_match = re.search(r'<sip:([^@>]+)', from_header)
            from_number = from_match.group(1) if from_match else "unknown"
            
            # Parse To header to get called number
            to_match = re.search(r'<sip:([^@>]+)', to_header)
            to_number = to_match.group(1) if to_match else self.username
            
            logger.info(f"📞 Incoming call: {from_number} -> {to_number}")
            
            # Send 100 Trying
            await self._send_response(parsed, raw_message, 100, "Trying")
            
            # Send 180 Ringing
            await self._send_response(parsed, raw_message, 180, "Ringing")
            
            # Create call session
            session = SIPCallSession(call_id, from_number, to_number, 'inbound')
            session.sip_call_id = call_id
            
            # Extract tags
            from_tag_match = re.search(r'tag=([^;>\s]+)', from_header)
            if from_tag_match:
                session.remote_tag = from_tag_match.group(1)
            session.local_tag = generate_tag()
            
            self.active_calls[call_id] = session
            
            # Notify application
            if self.on_incoming_call:
                try:
                    await self.on_incoming_call(session)
                except Exception as e:
                    logger.error(f"Error in on_incoming_call callback: {e}")
            
            # Auto-answer with 200 OK
            await self._send_answer(parsed, raw_message, session)
            
        except Exception as e:
            logger.error(f"Error handling INVITE: {e}", exc_info=True)
    
    async def _send_response(self, parsed: dict, raw_message: str, status_code: int, status_text: str):
        """Send a SIP response"""
        headers = parsed.get("headers", {})
        
        # Build response
        via = headers.get("via", "")
        from_h = headers.get("from", "")
        to_h = headers.get("to", "")
        call_id = headers.get("call-id", "")
        cseq = headers.get("cseq", "")
        
        response_lines = [
            f"SIP/2.0 {status_code} {status_text}",
            f"Via: {via}",
            f"From: {from_h}",
            f"To: {to_h}",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq}",
            f"Content-Length: 0",
        ]
        
        response = "\r\n".join(response_lines) + "\r\n\r\n"
        await self._send_message(response)
    
    async def _send_answer(self, parsed: dict, raw_message: str, session: SIPCallSession):
        """Send 200 OK to answer a call"""
        headers = parsed.get("headers", {})
        
        via = headers.get("via", "")
        from_h = headers.get("from", "")
        to_h = headers.get("to", "")
        call_id = headers.get("call-id", "")
        cseq = headers.get("cseq", "")
        
        # Add tag to To header if not present
        if "tag=" not in to_h:
            to_h = f"{to_h};tag={session.local_tag}"
        
        # Simple SDP for audio
        sdp = self._build_sdp()
        
        response_lines = [
            f"SIP/2.0 200 OK",
            f"Via: {via}",
            f"From: {from_h}",
            f"To: {to_h}",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq}",
            f"Contact: <sip:{self.username}@{self.domain};transport=ws>",
            f"Content-Type: application/sdp",
            f"Content-Length: {len(sdp)}",
        ]
        
        response = "\r\n".join(response_lines) + "\r\n\r\n" + sdp
        await self._send_message(response)
        
        session.status = 'in_progress'
        logger.info(f"✅ Answered call {call_id}")
        
        if self.on_call_answered:
            try:
                await self.on_call_answered(session)
            except Exception as e:
                logger.error(f"Error in on_call_answered callback: {e}")
    
    def _build_sdp(self) -> str:
        """Build SDP for audio"""
        # Simple SDP offering audio
        sdp_lines = [
            "v=0",
            f"o=- {int(datetime.utcnow().timestamp())} 1 IN IP4 127.0.0.1",
            "s=WeeVoice",
            "c=IN IP4 0.0.0.0",
            "t=0 0",
            "m=audio 9 UDP/TLS/RTP/SAVPF 0 8 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:8 PCMA/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=sendrecv",
        ]
        return "\r\n".join(sdp_lines) + "\r\n"
    
    async def _handle_bye(self, parsed: dict, raw_message: str):
        """Handle BYE (call ended)"""
        headers = parsed.get("headers", {})
        call_id = headers.get("call-id", "")
        
        # Send 200 OK
        await self._send_response(parsed, raw_message, 200, "OK")
        
        if call_id in self.active_calls:
            session = self.active_calls[call_id]
            session.end()
            
            logger.info(f"📞 Call {call_id} ended (BYE received)")
            
            if self.on_call_ended:
                try:
                    await self.on_call_ended(session)
                except Exception as e:
                    logger.error(f"Error in on_call_ended callback: {e}")
            
            del self.active_calls[call_id]
    
    async def _handle_cancel(self, parsed: dict, raw_message: str):
        """Handle CANCEL"""
        headers = parsed.get("headers", {})
        call_id = headers.get("call-id", "")
        
        # Send 200 OK to CANCEL
        await self._send_response(parsed, raw_message, 200, "OK")
        
        if call_id in self.active_calls:
            session = self.active_calls[call_id]
            session.status = 'cancelled'
            session.end()
            
            logger.info(f"📞 Call {call_id} cancelled")
            
            if self.on_call_ended:
                try:
                    await self.on_call_ended(session)
                except Exception as e:
                    logger.error(f"Error in on_call_ended callback: {e}")
            
            del self.active_calls[call_id]
    
    async def _send_options_response(self, parsed: dict, raw_message: str):
        """Respond to OPTIONS (keepalive/ping)"""
        await self._send_response(parsed, raw_message, 200, "OK")
    
    async def answer_call(self, call_id: str) -> bool:
        """Answer an incoming call (already handled in _handle_invite)"""
        return call_id in self.active_calls
    
    async def hangup_call(self, call_id: str) -> bool:
        """Hangup a call by sending BYE"""
        try:
            if call_id not in self.active_calls:
                return False
            
            session = self.active_calls[call_id]
            
            # Build BYE request
            self.cseq += 1
            branch = generate_branch()
            
            bye_lines = [
                f"BYE {self._build_sip_uri(session.from_number if session.direction == 'inbound' else session.to_number)} SIP/2.0",
                f"Via: SIP/2.0/WSS {self.domain};branch={branch};rport",
                f"Max-Forwards: 70",
                f"From: <{self._build_sip_uri(self.username)}>;tag={session.local_tag}",
                f"To: <{self._build_sip_uri(session.from_number if session.direction == 'inbound' else session.to_number)}>;tag={session.remote_tag}",
                f"Call-ID: {session.sip_call_id}",
                f"CSeq: {self.cseq} BYE",
                f"Content-Length: 0",
            ]
            
            bye_msg = "\r\n".join(bye_lines) + "\r\n\r\n"
            await self._send_message(bye_msg)
            
            session.end()
            logger.info(f"Sent BYE for call {call_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            return False
    
    async def make_call(self, to_number: str, from_number: Optional[str] = None) -> Optional[SIPCallSession]:
        """Initiate an outbound call"""
        if not self.is_connected or not self.is_registered:
            logger.error("Cannot make call: not connected or registered")
            return None
        
        try:
            call_id = generate_call_id()
            local_tag = generate_tag()
            branch = generate_branch()
            self.cseq += 1
            
            caller_id = from_number or self.username
            
            logger.info(f"📞 Initiating outbound call: {caller_id} -> {to_number}")
            
            # Build SDP
            sdp = self._build_sdp()
            
            # Build INVITE
            invite_lines = [
                f"INVITE {self._build_sip_uri(to_number)} SIP/2.0",
                f"Via: SIP/2.0/WSS {self.domain};branch={branch};rport",
                f"Max-Forwards: 70",
                f"From: <{self._build_sip_uri(caller_id)}>;tag={local_tag}",
                f"To: <{self._build_sip_uri(to_number)}>",
                f"Call-ID: {call_id}",
                f"CSeq: {self.cseq} INVITE",
                f"Contact: <sip:{self.username}@{self.domain};transport=ws>",
                f"Content-Type: application/sdp",
                f"Allow: INVITE, ACK, CANCEL, BYE, NOTIFY, REFER, MESSAGE, OPTIONS, INFO, SUBSCRIBE",
                f"Supported: outbound, path, gruu",
                f"User-Agent: WeeVoice/1.0",
                f"Content-Length: {len(sdp)}",
            ]
            
            invite_msg = "\r\n".join(invite_lines) + "\r\n\r\n" + sdp
            
            # Create session
            session = SIPCallSession(call_id, caller_id, to_number, 'outbound')
            session.sip_call_id = call_id
            session.local_tag = local_tag
            session.status = 'calling'
            
            self.active_calls[call_id] = session
            
            # Send INVITE
            await self._send_message(invite_msg)
            
            logger.info(f"📤 Sent INVITE for outbound call {call_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error making outbound call: {e}", exc_info=True)
            return None
    
    async def _handle_audio(self, audio_data: bytes):
        """Handle incoming audio from SIP"""
        # Route to active call's inbound queue
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
    """
    if not (hasattr(phone_number, 'sip_websocket_url') and phone_number.sip_websocket_url):
        raise ValueError(f"Phone number {phone_number.phone_number} has no SIP configuration")
    
    return SIPClientService(
        ws_url=phone_number.sip_websocket_url,
        username=phone_number.sip_username,
        password=phone_number.sip_password,
        domain=phone_number.sip_domain
    )
