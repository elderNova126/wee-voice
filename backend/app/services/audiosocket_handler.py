"""
Asterisk AudioSocket Handler

Uses asyncio with TCP_NODELAY to ensure immediate frame delivery.
"""
import asyncio
import socket
import struct
import logging
import audioop
import uuid as uuid_lib
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.services.agent_service import FrenchVoiceAgentService
from app.api.websocket import auto_summarize_call

logger = logging.getLogger(__name__)

MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

FRAME_SIZE = 320  # 160 samples * 2 bytes = 20ms at 8kHz
SILENCE_FRAME = b'\x00' * FRAME_SIZE

# Track active calls per phone number
_active_calls: dict[int, str] = {}  # phone_number_id -> call_uuid
_active_calls_lock = asyncio.Lock()


class AudioSocketSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.call_uuid = None
        self.call = None
        self.agent = None
        self.agent_service = None
        self.is_running = False
        self.db = None
        self.send_task = None
        self.ai_ready = asyncio.Event()
        self.ai_audio_queue = asyncio.Queue()  # AI audio to send to Asterisk
        self.caller_audio_queue = asyncio.Queue(maxsize=100)  # Caller audio to send to Gemini
        self._write_lock = asyncio.Lock()
        self.phone_number_id = None  # Track which phone number this call is using
        self.is_busy_response = False  # Flag for busy response mode
        self.busy_config = None  # Store busy action config (busy_tone/voicemail)
        
    async def handle(self):
        import time
        import traceback
        t0 = time.time()
        def ts():
            return f"[{(time.time()-t0)*1000:.1f}ms]"
        
        addr = self.writer.get_extra_info('peername')
        print(f"{ts()} === AudioSocket CONNECTED from {addr} ===", flush=True)
        
        try:
            self.is_running = True
            print(f"{ts()} is_running set", flush=True)
            
            # Get the raw socket for direct operations
            sock = self.writer.get_extra_info('socket')
            print(f"{ts()} Got socket: {sock}", flush=True)
            if not sock:
                print(f"{ts()} ERROR: Could not get socket!", flush=True)
                return
            
            # CRITICAL: Set TCP_NODELAY
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"{ts()} TCP_NODELAY set", flush=True)
            except Exception as e:
                print(f"{ts()} TCP_NODELAY failed: {e}", flush=True)
            
            # Send first frames directly via writer (simpler approach)
            header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
            for i in range(5):
                self.writer.write(header + SILENCE_FRAME)
            await self.writer.drain()
            print(f"{ts()} 5 silence frames sent via writer.drain()", flush=True)
            
            # Start the continuous send task
            self.send_task = asyncio.create_task(self._send_loop())
            print(f"{ts()} Send task CREATED", flush=True)
            
            # Read UUID
            print(f"{ts()} Starting UUID read...", flush=True)
            await self._read_uuid()
            print(f"{ts()} UUID read complete: {self.call_uuid}", flush=True)
            
            if not self.call_uuid:
                logger.error("No UUID")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # Setup call (takes time for Gemini init)
            print(f"[HANDLE] Starting _setup_call...", flush=True)
            if not await self._setup_call():
                print(f"[HANDLE] _setup_call FAILED", flush=True)
                
                # Check if this was due to busy line
                if self.is_busy_response:
                    print(f"[HANDLE] Playing BUSY message...", flush=True)
                    await self._play_busy_message()
                return
            
            # Signal AI is ready
            self.ai_ready.set()
            print(f"[HANDLE] AI READY - will now process caller audio", flush=True)
            
            # Start AI tasks - CRITICAL: must start send_realtime_input to consume audio queue!
            ai_receive_task = asyncio.create_task(self._ai_receive_loop())
            caller_to_ai_task = asyncio.create_task(self._caller_audio_to_gemini_loop())
            gemini_input_task = asyncio.create_task(self.agent_service.send_realtime_input())
            print(f"[HANDLE] Gemini input task STARTED", flush=True)
            
            # Main receive loop
            await self._receive_loop()
            
            # Cancel all tasks
            for task in [caller_to_ai_task, gemini_input_task, ai_receive_task]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            print(f"[HANDLE] EXCEPTION: {e}", flush=True)
            import traceback
            traceback.print_exc()
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            print(f"[HANDLE] Cleanup starting...", flush=True)
            await self._cleanup()
            print(f"[HANDLE] Cleanup done", flush=True)
    
    async def _send_loop(self):
        """Continuously send audio frames to Asterisk"""
        import time
        t0 = time.time()
        print(f"[SEND] Loop STARTED", flush=True)
        
        frames_sent = 0
        transport = self.writer.transport
        try:
            while self.is_running:
                # Get AI audio if available, otherwise use silence
                try:
                    audio_data = self.ai_audio_queue.get_nowait()
                    is_ai = True
                except asyncio.QueueEmpty:
                    audio_data = SILENCE_FRAME
                    is_ai = False
                
                # Send frame directly via transport
                header = struct.pack('>BH', MSG_AUDIO, len(audio_data))
                try:
                    transport.write(header + audio_data)
                except Exception as e:
                    print(f"[SEND] Transport write FAILED: {e}", flush=True)
                    break
                
                frames_sent += 1
                elapsed = (time.time() - t0) * 1000
                if frames_sent <= 5:
                    print(f"[SEND] Frame #{frames_sent} at {elapsed:.1f}ms", flush=True)
                if frames_sent % 100 == 0:
                    print(f"[SEND] {frames_sent} frames", flush=True)
                
                # 20ms per frame = 50fps
                await asyncio.sleep(0.02)
                
        except asyncio.CancelledError:
            print(f"[SEND] CANCELLED after {frames_sent}", flush=True)
        except Exception as e:
            print(f"[SEND] ERROR: {e}", flush=True)
        
        print(f"[SEND] ENDED: {frames_sent} total", flush=True)
    
    async def _receive_loop(self):
        """Receive audio from Asterisk"""
        import time
        t0 = time.time()
        print(f"[RECV] Loop STARTED")
        
        frames = 0
        try:
            while self.is_running:
                # Read header
                try:
                    header = await asyncio.wait_for(
                        self.reader.readexactly(3),
                        timeout=60.0
                    )
                except asyncio.IncompleteReadError as e:
                    print(f"[RECV] IncompleteReadError: {e}")
                    break
                except asyncio.TimeoutError:
                    print(f"[RECV] Timeout after {frames} frames")
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload
                if payload_len > 0:
                    try:
                        payload = await self.reader.readexactly(payload_len)
                    except asyncio.IncompleteReadError:
                        print(f"[RECV] Payload incomplete")
                        break
                else:
                    payload = b''
                
                if msg_type == MSG_AUDIO:
                    frames += 1
                    elapsed = (time.time() - t0) * 1000
                    if frames <= 10 or frames % 50 == 0:
                        print(f"[RECV] Frame #{frames} at {elapsed:.0f}ms", flush=True)
                    await self._process_audio(payload)
                elif msg_type == MSG_HANGUP:
                    print(f"[RECV] HANGUP received")
                    break
                elif msg_type == MSG_ERROR:
                    print(f"[RECV] ERROR from Asterisk")
                    break
                else:
                    print(f"[RECV] Unknown type: 0x{msg_type:02x}")
                    
        except Exception as e:
            print(f"[RECV] Exception: {e}")
        
        print(f"[RECV] Loop ENDED: {frames} frames total")
    
    async def _read_uuid(self):
        """Read UUID packet"""
        import time
        t0 = time.time()
        try:
            print(f"[UUID] Waiting for header...")
            header = await asyncio.wait_for(
                self.reader.readexactly(3), 
                timeout=5.0
            )
            elapsed = (time.time() - t0) * 1000
            print(f"[UUID] Header received at {elapsed:.1f}ms: {header.hex()}")
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            print(f"[UUID] type=0x{msg_type:02x}, len={payload_len}")
            
            if msg_type == MSG_UUID and payload_len > 0:
                uuid_bytes = await asyncio.wait_for(
                    self.reader.readexactly(payload_len),
                    timeout=5.0
                )
                print(f"[UUID] Payload received: {uuid_bytes[:50]}...")
                try:
                    self.call_uuid = uuid_bytes.decode('ascii').strip()
                    if len(self.call_uuid) == 36:
                        print(f"[UUID] Valid: {self.call_uuid}")
                        return
                except:
                    pass
            
            self.call_uuid = str(uuid_lib.uuid4())
            print(f"[UUID] Generated: {self.call_uuid}")
            
        except asyncio.TimeoutError:
            print(f"[UUID] TIMEOUT waiting for header!")
            self.call_uuid = str(uuid_lib.uuid4())
        except Exception as e:
            print(f"[UUID] ERROR: {e}")
            self.call_uuid = str(uuid_lib.uuid4())
    
    async def _setup_call(self) -> bool:
        """Setup call record and AI"""
        self.db = SessionLocal()
        try:
            # Find phone number with Zadarma/SIP config (the one receiving calls)
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)  # Has SIP config = receives calls
            ).first()
            
            if not phone:
                logger.error("No phone number with SIP config found")
                return False
            
            print(f"[SETUP] Found phone: {phone.phone_number}, agent_id: {phone.agent_id}", flush=True)
            self.phone_number_id = phone.id
            
            # Check if line is busy
            async with _active_calls_lock:
                if phone.id in _active_calls:
                    existing_uuid = _active_calls[phone.id]
                    print(f"[SETUP] LINE BUSY! Phone {phone.phone_number} already has active call: {existing_uuid}", flush=True)
                    logger.info(f"Line busy for {phone.phone_number}, active call: {existing_uuid}")
                    self.is_busy_response = True
                    # Store busy config for message
                    self.busy_config = {
                        'action': phone.busy_action or 'busy_tone',
                        'audio_file_url': phone.busy_audio_file_url
                    }
                    print(f"[SETUP] Busy action: {self.busy_config['action']}, audio_url: {self.busy_config.get('audio_file_url', 'none')}", flush=True)
                    return False  # Will trigger busy response
                
                # Reserve this line
                _active_calls[phone.id] = self.call_uuid
                print(f"[SETUP] Reserved line for call {self.call_uuid}", flush=True)
            
            # Get agent
            self.agent = self.db.query(VoiceAgent).filter(
                VoiceAgent.id == phone.agent_id
            ).first()
            
            if self.agent:
                print(f"[SETUP] Using agent: {self.agent.name} (ID: {self.agent.id})", flush=True)
            
            if not self.agent:
                # Fallback to first agent
                self.agent = self.db.query(VoiceAgent).first()
                print(f"[SETUP] Fallback to first agent: {self.agent.name if self.agent else 'None'}", flush=True)
            
            if not self.agent:
                logger.error("No agent")
                await self._release_line()
                return False
            
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone="unknown",
                caller_name="Caller",
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"Created call {self.call.id}")
            
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            if not await self.agent_service.start_session():
                logger.error("Gemini failed")
                await self._release_line()
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            logger.info(f"Call {self.call.id} ready")
            return True
            
        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            await self._release_line()
            return False
    
    async def _release_line(self):
        """Release the phone line when call ends"""
        if self.phone_number_id:
            async with _active_calls_lock:
                if self.phone_number_id in _active_calls:
                    del _active_calls[self.phone_number_id]
                    print(f"[SETUP] Released line for phone_id {self.phone_number_id}", flush=True)
    
    async def _process_audio(self, audio_8k: bytes):
        """Process audio from Asterisk, queue for sending to AI"""
        if not self.ai_ready.is_set():
            return
        if len(audio_8k) < 2:
            return
        
        try:
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            
            # Check audio level (for debugging)
            if not hasattr(self, '_audio_level_count'):
                self._audio_level_count = 0
            self._audio_level_count += 1
            
            try:
                rms = audioop.rms(audio_8k, 2)
                max_val = audioop.max(audio_8k, 2)
                if self._audio_level_count <= 20 or self._audio_level_count % 100 == 0:
                    print(f"[AUDIO-LEVEL] #{self._audio_level_count} RMS={rms}, MAX={max_val}", flush=True)
            except:
                pass
            
            # Upsample 8kHz to 16kHz for Gemini
            audio_16k, _ = audioop.ratecv(audio_8k, 2, 1, 8000, 16000, None)
            
            # Queue for sending (non-blocking, drop if queue full)
            try:
                self.caller_audio_queue.put_nowait(audio_16k)
            except asyncio.QueueFull:
                pass  # Drop audio if queue is full (backpressure)
        except Exception as e:
            print(f"[AUDIO→AI] Queue ERROR: {e}", flush=True)
    
    async def _caller_audio_to_gemini_loop(self):
        """Forward caller audio to Gemini"""
        packets_sent = 0
        audio_buffer = b''
        BATCH_SIZE = 3200  # ~100ms of 16kHz audio
        
        print(f"[AUDIO→AI] Queue loop STARTED", flush=True)
        try:
            while self.is_running:
                try:
                    # Get audio from queue with short timeout
                    audio_16k = await asyncio.wait_for(
                        self.caller_audio_queue.get(),
                        timeout=0.1
                    )
                    audio_buffer += audio_16k
                except asyncio.TimeoutError:
                    pass
                
                # Send when buffer is big enough
                if len(audio_buffer) >= BATCH_SIZE and self.agent_service:
                    packets_sent += 1
                    # send_audio just queues, send_realtime_input sends to Gemini
                    await self.agent_service.send_audio(audio_buffer)
                    
                    if packets_sent <= 10 or packets_sent % 50 == 0:
                        print(f"[AUDIO→AI] #{packets_sent} queued ({len(audio_buffer)} bytes)", flush=True)
                    audio_buffer = b''
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AUDIO→AI] Queue loop ERROR: {e}", flush=True)
        print(f"[AUDIO→AI] Queue loop ENDED, {packets_sent} packets", flush=True)
    
    async def _ai_receive_loop(self):
        """Receive audio from AI and queue for sending"""
        ai_packets = 0
        print(f"[AI→AUDIO] Receive loop STARTED", flush=True)
        try:
            async for audio_24k in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                if not audio_24k or len(audio_24k) < 2:
                    continue
                
                if len(audio_24k) % 2:
                    audio_24k = audio_24k[:-1]
                
                audio_8k, _ = audioop.ratecv(audio_24k, 2, 1, 24000, 8000, None)
                await self.ai_audio_queue.put(audio_8k)
                
                ai_packets += 1
                if ai_packets <= 5 or ai_packets % 50 == 0:
                    print(f"[AI→AUDIO] #{ai_packets}, {len(audio_8k)} bytes from Gemini", flush=True)
                
        except asyncio.CancelledError:
            print(f"[AI→AUDIO] Cancelled after {ai_packets} packets", flush=True)
        except Exception as e:
            print(f"[AI→AUDIO] ERROR: {e}", flush=True)
        print(f"[AI→AUDIO] ENDED, total {ai_packets} packets", flush=True)
    
    async def _play_busy_message(self):
        """Play a busy message (tone or voicemail audio) and hangup"""
        try:
            action = self.busy_config.get('action', 'busy_tone') if self.busy_config else 'busy_tone'
            audio_file_url = self.busy_config.get('audio_file_url') if self.busy_config else None
            
            if action == 'voicemail' and audio_file_url:
                print(f"[BUSY] Playing voicemail audio from: {audio_file_url}", flush=True)
                await self._play_audio_file(audio_file_url)
            else:
                print(f"[BUSY] Playing busy tone", flush=True)
                await self._play_busy_tone()
            
            # Send hangup
            hangup_header = struct.pack('>BH', MSG_HANGUP, 0)
            self.writer.write(hangup_header)
            await self.writer.drain()
            print(f"[BUSY] Sent hangup, closing connection", flush=True)
            
        except Exception as e:
            print(f"[BUSY] Error playing busy message: {e}", flush=True)
        finally:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
    
    async def _play_busy_tone(self):
        """Play standard busy signal tone"""
        import math
        
        sample_rate = 8000
        duration_on = 0.5  # 500ms tone
        duration_off = 0.5  # 500ms silence
        num_cycles = 3  # Play 3 beeps
        
        samples_on = int(sample_rate * duration_on)
        samples_off = int(sample_rate * duration_off)
        
        # Create tone (480Hz)
        tone_data = b''
        for i in range(samples_on):
            value = int(16000 * math.sin(2 * math.pi * 480 * i / sample_rate))
            tone_data += struct.pack('<h', max(-32768, min(32767, value)))
        
        silence_data = b'\x00' * (samples_off * 2)
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        for cycle in range(num_cycles):
            # Send tone in chunks
            for i in range(0, len(tone_data), FRAME_SIZE):
                chunk = tone_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
            await self.writer.drain()
            
            # Send silence
            for i in range(0, len(silence_data), FRAME_SIZE):
                chunk = silence_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
            await self.writer.drain()
    
    async def _play_audio_file(self, audio_url: str):
        """Download and play an audio file"""
        try:
            import httpx
            import tempfile
            import subprocess
            import os
            
            print(f"[BUSY] Downloading audio from: {audio_url}", flush=True)
            
            # Download the audio file
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url, timeout=10.0)
                if response.status_code != 200:
                    print(f"[BUSY] Failed to download audio: HTTP {response.status_code}", flush=True)
                    await self._play_busy_tone()
                    return
                audio_content = response.content
            
            print(f"[BUSY] Downloaded {len(audio_content)} bytes", flush=True)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as f:
                input_path = f.name
                f.write(audio_content)
            
            # Convert to 8kHz mono PCM using ffmpeg
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
                raw_path = f.name
            
            result = subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-ar', '8000', '-ac', '1', '-f', 's16le', raw_path
            ], capture_output=True)
            
            if result.returncode != 0:
                print(f"[BUSY] FFmpeg conversion failed: {result.stderr.decode()[:200]}", flush=True)
                os.unlink(input_path)
                await self._play_busy_tone()
                return
            
            # Read converted audio
            with open(raw_path, 'rb') as f:
                audio_data = f.read()
            
            # Cleanup temp files
            os.unlink(input_path)
            os.unlink(raw_path)
            
            print(f"[BUSY] Converted to {len(audio_data)} bytes of 8kHz PCM", flush=True)
            
            # Send audio to Asterisk
            header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
            for i in range(0, len(audio_data), FRAME_SIZE):
                chunk = audio_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
                if i % (FRAME_SIZE * 10) == 0:  # Drain every 10 frames
                    await self.writer.drain()
            await self.writer.drain()
            
            print(f"[BUSY] Finished playing audio file", flush=True)
            
        except Exception as e:
            print(f"[BUSY] Audio file error, falling back to tone: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await self._play_busy_tone()
    
    async def _cleanup(self):
        """Cleanup"""
        logger.info(f"Cleanup {self.call_uuid}")
        self.is_running = False
        
        # Release the phone line
        await self._release_line()
        
        if self.send_task:
            self.send_task.cancel()
            try:
                await self.send_task
            except:
                pass
        
        if self.agent_service:
            try:
                await self.agent_service.end_session()
            except:
                pass
        
        if self.call and self.db:
            try:
                self.db.refresh(self.call)
                self.call.ended_at = datetime.utcnow()
                self.call.calculate_duration_and_cost()
                self.call.status = CallStatus.SUMMARIZING
                self.db.commit()
                asyncio.create_task(auto_summarize_call(self.call.id))
            except:
                pass
            finally:
                self.db.close()
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class AudioSocketServer:
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server = None
    
    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, self.host, self.port
        )
        logger.info(f"AudioSocket on {self.host}:{self.port}")
        print(f"[AudioSocket] Starting AudioSocket server...")
        print(f"[AudioSocket] ✅ AudioSocket server started on port {self.port}")
        asyncio.create_task(self._serve())
    
    async def _serve(self):
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _handle(self, reader, writer):
        import time
        print(f"\n{'='*60}", flush=True)
        print(f"[SERVER] New connection at {time.strftime('%H:%M:%S')}", flush=True)
        print(f"{'='*60}", flush=True)
        session = AudioSocketSession(reader, writer)
        await session.handle()
        print(f"[SERVER] Connection handler finished", flush=True)


audiosocket_server = AudioSocketServer()
