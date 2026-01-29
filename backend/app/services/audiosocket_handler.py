"""
Asterisk AudioSocket Handler - Pure 8kHz End-to-End

NO RESAMPLING for OpenAI models:
- Asterisk: 8kHz PCM16
- OpenAI: 8kHz G.711 μ-law (converted to PCM16)
- Result: Zero quality loss, zero latency from resampling

Frame size: 320 bytes = 20ms @ 8kHz PCM16
"""
import asyncio
import socket
import struct
import logging
import uuid as uuid_lib
import time
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.api.websocket import auto_summarize_call
from app.services.greeting_tts_service import get_greeting_tts_service, get_cached_greeting_sync

logger = logging.getLogger(__name__)

# ============================================================================
# AUDIO CONSTANTS - Pure 8kHz
# ============================================================================
SAMPLE_RATE = 8000          # 8kHz everywhere
FRAME_SIZE = 320            # 20ms @ 8kHz PCM16 (8000 * 0.02 * 2 bytes)
FRAME_MS = 20               # 20ms per frame
SILENCE = b'\x00' * FRAME_SIZE

# Buffer limits - OpenAI sends in bursts, need larger buffer
# Don't drop frames - just warn if buffer gets large
MAX_PENDING_BYTES = 64000   # 4 seconds max (warn only, don't drop)
WARN_PENDING_BYTES = 16000  # 1 second - warn threshold

# AudioSocket message types
MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

# Track active calls
_active_calls: dict[int, str] = {}
_active_calls_lock = asyncio.Lock()


def normalize_audio(pcm: bytes, target_rms: int = 1400, max_gain_db: float = 18.0) -> bytes:
    """Simple RMS normalization."""
    import math
    import array
    
    if len(pcm) < 4:
        return pcm
    
    try:
        buf = array.array('h')
        buf.frombytes(pcm)
        if not buf:
            return pcm
        
        rms = math.sqrt(sum(s*s for s in buf) / len(buf))
        if rms < 1:
            return pcm
        
        gain = min(target_rms / rms, 10 ** (max_gain_db / 20))
        if gain <= 1.01:
            return pcm
        
        for i, s in enumerate(buf):
            buf[i] = int(max(-32768, min(32767, s * gain)))
        
        return buf.tobytes()
    except:
        return pcm


class AudioSocketSession:
    """
    Pure 8kHz AudioSocket session.
    
    Audio flow (OpenAI):
        Asterisk 8kHz PCM → OpenAI 8kHz μ-law → Asterisk 8kHz PCM
        NO RESAMPLING!
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.call_uuid = None
        self.call = None
        self.agent = None
        self.agent_service = None
        self.is_running = False
        self.db = None
        self.ai_ready = asyncio.Event()
        self.caller_audio_queue = asyncio.Queue(maxsize=100)
        self.phone_number_id = None
        self.is_busy_response = False
        self.busy_config = None
        self.greeting_audio = None
        self.llm_model = 'gemini'
        self.caller_id = None
        
    async def handle(self):
        """Main entry point."""
        t0 = time.perf_counter()
        addr = self.writer.get_extra_info('peername')
        print(f"[{self._ms(t0)}] === AudioSocket from {addr} ===", flush=True)
        
        try:
            self.is_running = True
            
            # TCP_NODELAY for low latency
            sock = self.writer.get_extra_info('socket')
            if sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Minimal initial silence (just 2 frames = 40ms)
            header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
            for _ in range(2):
                self.writer.write(header + SILENCE)
            await self.writer.drain()
            
            # Read UUID
            await self._read_uuid()
            if not self.call_uuid:
                return
            
            # Setup
            if not await self._setup_call():
                if self.is_busy_response:
                    await self._play_busy()
                return
            
            # Start receive loop
            recv_task = asyncio.create_task(self._receive_loop())
            
            # Play cached greeting IMMEDIATELY (for both OpenAI and Gemini)
            # This ensures fast response - AI takes over for conversation
            greeting_task = None
            if self.greeting_audio:
                print(f"[{self._ms(t0)}] 🎵 Playing cached greeting", flush=True)
                greeting_task = asyncio.create_task(self._play_greeting())
            
            # Connect AI in parallel with greeting
            ai_connect_task = asyncio.create_task(self._connect_ai())
            
            # Wait for greeting to finish
            if greeting_task:
                try:
                    await greeting_task
                except asyncio.CancelledError:
                    pass
            
            # Wait for AI connection
            ai_connected = await ai_connect_task
            if not ai_connected:
                recv_task.cancel()
                return
            
            self.ai_ready.set()
            print(f"[{self._ms(t0)}] ✅ AI READY (pure 8kHz)", flush=True)
            
            # Start audio tasks
            audio_task = asyncio.create_task(self._audio_loop())
            caller_task = asyncio.create_task(self._caller_to_ai())
            input_task = asyncio.create_task(self.agent_service.send_realtime_input())
            
            await recv_task
            
            for task in [audio_task, caller_task, input_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
        except Exception as e:
            print(f"[HANDLE] ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()
    
    def _ms(self, t0):
        return f"{(time.perf_counter()-t0)*1000:.0f}ms"
    
    # ========================================================================
    # PURE 8kHz AUDIO LOOP - NO RESAMPLING
    # ========================================================================
    
    async def _audio_loop(self):
        """
        Pure 8kHz audio loop.
        
        - Receives 8kHz PCM from OpenAI (converted from μ-law)
        - Sends 8kHz PCM to Asterisk
        - NO RESAMPLING
        - Strict 20ms frame timing
        - Buffer capped at 500ms to prevent buildup
        """
        print(f"[AUDIO] Starting pure 8kHz loop (NO resampling)", flush=True)
        
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        pending = b''
        frames_sent = 0
        chunks_recv = 0
        last_frame_time = time.perf_counter()
        
        # Stats
        max_pending_seen = 0
        warned_large_buffer = False
        
        # Queue for receiving from AI
        recv_queue = asyncio.Queue(maxsize=50)
        
        async def receiver():
            """Receive from AI - pass through directly."""
            nonlocal chunks_recv
            try:
                async for audio in self.agent_service.receive_audio():
                    if not self.is_running:
                        break
                    if audio and len(audio) >= 2:
                        # Pass through directly - no processing
                        chunks_recv += 1
                        await recv_queue.put(audio)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[AUDIO] Recv error: {e}", flush=True)
            await recv_queue.put(None)
        
        recv_task = asyncio.create_task(receiver())
        
        # Startup gate - buffer before playing to prevent choppy starts
        STARTUP_MS = 500   # Buffer 500ms before starting playback
        REBUFFER_MS = 300  # If buffer empties, wait for 300ms before resuming
        STARTUP_BYTES = STARTUP_MS * SAMPLE_RATE * 2 // 1000  # 8000 bytes
        REBUFFER_BYTES = REBUFFER_MS * SAMPLE_RATE * 2 // 1000  # 4800 bytes
        
        playing = False  # True after startup buffer is filled
        
        # Pacer - strict 20ms cadence
        TICK = FRAME_MS / 1000.0  # 0.02s
        next_tick = time.perf_counter()
        
        try:
            while self.is_running:
                # Wait for next tick
                now = time.perf_counter()
                sleep_for = next_tick - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                
                # Drain queue into pending
                stream_ended = False
                while True:
                    try:
                        chunk = recv_queue.get_nowait()
                        if chunk is None:
                            stream_ended = True
                            break
                        pending += chunk
                    except asyncio.QueueEmpty:
                        break
                
                # Handle end of stream
                if stream_ended:
                    # Flush remaining audio
                    while len(pending) >= FRAME_SIZE:
                        frame = pending[:FRAME_SIZE]
                        pending = pending[FRAME_SIZE:]
                        self.writer.write(header + frame)
                        frames_sent += 1
                    if pending:
                        frame = pending.ljust(FRAME_SIZE, b'\x00')
                        self.writer.write(header + frame)
                        frames_sent += 1
                    await self.writer.drain()
                    print(f"[AUDIO] Done: {frames_sent} frames, {chunks_recv} chunks", flush=True)
                    return
                
                # Track max pending
                if len(pending) > max_pending_seen:
                    max_pending_seen = len(pending)
                
                pending_ms = len(pending) * 1000 // (SAMPLE_RATE * 2)
                
                # Large buffer warning (just informational)
                if len(pending) > WARN_PENDING_BYTES and not warned_large_buffer:
                    print(f"[AUDIO] ℹ Large buffer: {pending_ms}ms (AI burst)", flush=True)
                    warned_large_buffer = True
                elif len(pending) < WARN_PENDING_BYTES:
                    warned_large_buffer = False
                
                # STARTUP GATE: Wait for buffer to fill before playing
                if not playing:
                    if len(pending) >= STARTUP_BYTES:
                        playing = True
                        print(f"[AUDIO] ▶ START: {pending_ms}ms buffered", flush=True)
                    else:
                        # Still buffering - send silence
                        self.writer.write(header + SILENCE)
                        frames_sent += 1
                        next_tick += TICK
                        if next_tick < time.perf_counter() - 0.1:
                            next_tick = time.perf_counter()
                        continue
                
                # REBUFFER GATE: If buffer empties, wait for refill
                if len(pending) < FRAME_SIZE:
                    # Buffer empty - need to rebuffer
                    playing = False
                    self.writer.write(header + SILENCE)
                    frames_sent += 1
                    next_tick += TICK
                    if next_tick < time.perf_counter() - 0.1:
                        next_tick = time.perf_counter()
                    continue
                
                # PLAYING: Send audio frame
                frame_time = time.perf_counter()
                delta_ms = (frame_time - last_frame_time) * 1000
                last_frame_time = frame_time
                
                frame = pending[:FRAME_SIZE]
                pending = pending[FRAME_SIZE:]
                self.writer.write(header + frame)
                frames_sent += 1
                
                # Drain writer periodically
                if frames_sent % 25 == 0:
                    try:
                        await self.writer.drain()
                    except:
                        break
                
                # Timing log
                if frames_sent <= 5 or frames_sent % 500 == 0:
                    print(f"[AUDIO] #{frames_sent}: pending={pending_ms}ms, delta={delta_ms:.1f}ms, chunks={chunks_recv}", flush=True)
                
                next_tick += TICK
                
                # Reset if way behind
                if next_tick < time.perf_counter() - 0.1:
                    next_tick = time.perf_counter()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AUDIO] Error: {e}", flush=True)
        finally:
            recv_task.cancel()
        
        print(f"[AUDIO] Ended: {frames_sent} frames, max_pending={max_pending_seen}b", flush=True)
    
    # ========================================================================
    # RECEIVE FROM ASTERISK
    # ========================================================================
    
    async def _receive_loop(self):
        """Receive 8kHz PCM from Asterisk."""
        frames = 0
        try:
            while self.is_running:
                try:
                    header = await asyncio.wait_for(self.reader.readexactly(3), timeout=60.0)
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                payload = b''
                if payload_len > 0:
                    try:
                        payload = await self.reader.readexactly(payload_len)
                    except asyncio.IncompleteReadError:
                        break
                
                if msg_type == MSG_AUDIO:
                    frames += 1
                    if frames <= 10 or frames % 100 == 0:
                        print(f"[RECV] #{frames} ({payload_len}b)", flush=True)
                    await self._process_audio(payload)
                elif msg_type in (MSG_HANGUP, MSG_ERROR):
                    print(f"[RECV] {'HANGUP' if msg_type == MSG_HANGUP else 'ERROR'}", flush=True)
                    break
                    
        except Exception as e:
            print(f"[RECV] Error: {e}", flush=True)
        
        print(f"[RECV] Ended: {frames} frames", flush=True)
    
    async def _process_audio(self, audio: bytes):
        """Queue 8kHz PCM for AI - NO RESAMPLING."""
        if not self.ai_ready.is_set() or len(audio) < 2:
            return
        
        # Ensure even length
        if len(audio) % 2:
            audio = audio[:-1]
        
        # Direct passthrough - NO RESAMPLING for OpenAI
        try:
            self.caller_audio_queue.put_nowait(audio)
        except asyncio.QueueFull:
            pass
    
    async def _caller_to_ai(self):
        """Send caller audio to AI - pure 8kHz."""
        packets = 0
        buffer = b''
        BATCH = 640  # 40ms @ 8kHz
        
        print(f"[CALLER→AI] Started (8kHz, batch={BATCH}b)", flush=True)
        
        try:
            while self.is_running:
                try:
                    chunk = await asyncio.wait_for(self.caller_audio_queue.get(), timeout=0.04)
                    buffer += chunk
                except asyncio.TimeoutError:
                    if len(buffer) >= 320 and self.agent_service:
                        packets += 1
                        await self.agent_service.send_audio(buffer)
                        buffer = b''
                    continue
                
                if len(buffer) >= BATCH and self.agent_service:
                    packets += 1
                    await self.agent_service.send_audio(buffer)
                    buffer = b''
                    
                    if packets <= 10 or packets % 100 == 0:
                        print(f"[CALLER→AI] #{packets}", flush=True)
                        
        except asyncio.CancelledError:
            pass
        
        print(f"[CALLER→AI] Ended: {packets}", flush=True)
    
    # ========================================================================
    # SETUP
    # ========================================================================
    
    async def _read_uuid(self):
        """Read UUID from AudioSocket."""
        try:
            header = await asyncio.wait_for(self.reader.readexactly(3), timeout=5.0)
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            if msg_type == MSG_UUID and payload_len > 0:
                uuid_bytes = await asyncio.wait_for(self.reader.readexactly(payload_len), timeout=5.0)
                try:
                    decoded = uuid_bytes.decode('ascii').strip().replace('\x00', '')
                    if len(decoded) == 36 and '-' in decoded:
                        self.call_uuid = decoded
                except:
                    pass
                
                if not self.call_uuid and len(uuid_bytes) == 16:
                    try:
                        self.call_uuid = str(uuid_lib.UUID(bytes=uuid_bytes))
                    except:
                        pass
            
            if not self.call_uuid:
                self.call_uuid = str(uuid_lib.uuid4())
            
            # Read caller ID (no delay needed)
            self._read_caller_id()
            
            print(f"[UUID] {self.call_uuid}", flush=True)
            
        except Exception as e:
            print(f"[UUID] Error: {e}", flush=True)
            self.call_uuid = str(uuid_lib.uuid4())
    
    def _read_caller_id(self):
        """Read caller ID from temp file."""
        import os
        try:
            path = f"/tmp/callerid_{self.call_uuid}"
            if os.path.exists(path):
                with open(path, 'r') as f:
                    raw = f.read().strip().strip('"\'')
                try:
                    os.unlink(path)
                except:
                    pass
                if raw and raw.lower() not in ('none', 'null', 'unknown', ''):
                    self.caller_id = raw
                    if self.caller_id[0].isdigit() and len(self.caller_id) > 9:
                        self.caller_id = '+' + self.caller_id
        except:
            pass
    
    async def _setup_call(self) -> bool:
        """Setup call: DB, agent, restrictions."""
        self.db = SessionLocal()
        try:
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)
            ).first()
            
            if not phone:
                print(f"[SETUP] No phone with SIP", flush=True)
                return False
            
            self.db.refresh(phone)
            self.phone_number_id = phone.id
            self.llm_model = getattr(phone, 'llm_model', 'gemini') or 'gemini'
            
            print(f"[SETUP] Phone: {phone.phone_number}, Model: {self.llm_model}", flush=True)
            
            # Check busy
            async with _active_calls_lock:
                if phone.id in _active_calls:
                    self.is_busy_response = True
                    self.busy_config = {'action': phone.busy_action or 'busy_tone'}
                    return False
                _active_calls[phone.id] = self.call_uuid
            
            # Get agent
            self.agent = self.db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
            if not self.agent:
                self.agent = self.db.query(VoiceAgent).first()
            if not self.agent:
                await self._release_line()
                return False
            
            # Check restrictions
            caller = self.caller_id or "Unknown"
            if self._is_blocked(phone, caller):
                self.is_busy_response = True
                self.busy_config = {'action': 'busy_tone'}
                await self._release_line()
                return False
            
            # Create call
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone=caller,
                caller_name=caller,
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            # Cached greeting (for BOTH Gemini and OpenAI)
            # Play pre-cached TTS greeting immediately for fast response
            # AI then handles conversation (with skip_greeting_trigger=True)
            if self.agent.greeting:
                self.greeting_audio = get_cached_greeting_sync(
                    self.agent.greeting,
                    language=getattr(self.agent, 'language', 'fr-FR'),
                    gender=getattr(self.agent, 'voice_gender', 'male'),
                    voice_id=getattr(self.agent, 'voice_id', None)
                )
            
            print(f"[SETUP] Agent: {self.agent.name}, Call: {self.call.id}", flush=True)
            return True
            
        except Exception as e:
            print(f"[SETUP] Error: {e}", flush=True)
            await self._release_line()
            return False
    
    def _is_blocked(self, phone, caller: str) -> bool:
        """Check if caller is blocked."""
        import json
        mode = phone.restriction_mode or 'none'
        if mode == 'none':
            return False
        
        def parse(val):
            if not val:
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                if val.startswith('{') and not val.startswith('{"'):
                    return [x.strip().strip('"') for x in val[1:-1].split(',') if x.strip()]
                try:
                    return json.loads(val) if val else []
                except:
                    return []
            return []
        
        blocked = parse(phone.blocked_countries)
        allowed = parse(phone.allowed_countries)
        
        # Simple country detection
        country = ''
        for prefix, code in {'+1': 'US', '+44': 'UK', '+33': 'FR', '+32': 'BE', '+84': 'VN'}.items():
            if caller.startswith(prefix):
                country = code
                break
        
        if mode == 'blacklist':
            return country.upper() in [c.upper() for c in blocked]
        elif mode == 'whitelist':
            return not (country.upper() in [c.upper() for c in allowed]) if allowed else True
        return False
    
    async def _connect_ai(self) -> bool:
        """Connect to AI."""
        try:
            from app.services.openai_realtime_service import get_voice_agent_service, is_openai_model
            
            if is_openai_model(self.llm_model):
                print(f"[AI] 🔵 OpenAI Realtime - pure 8kHz", flush=True)
            else:
                print(f"[AI] 🟢 Gemini Live", flush=True)
            
            self.agent_service = get_voice_agent_service(
                agent=self.agent,
                call=self.call,
                llm_model=self.llm_model,
                skip_greeting_trigger=bool(self.greeting_audio)
            )
            
            if not await self.agent_service.start_session():
                await self._release_line()
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            print(f"[AI] Session started", flush=True)
            return True
            
        except Exception as e:
            print(f"[AI] Error: {e}", flush=True)
            await self._release_line()
            return False
    
    # ========================================================================
    # GREETING & BUSY
    # ========================================================================
    
    async def _play_greeting(self):
        """Play cached greeting (8kHz)."""
        if not self.greeting_audio:
            return
        
        audio = normalize_audio(self.greeting_audio)
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        # Minimal lead-in silence (3 frames = 60ms)
        for _ in range(3):
            self.writer.write(header + SILENCE)
        await self.writer.drain()
        
        # Send frames
        TICK = FRAME_MS / 1000.0
        next_tick = time.perf_counter()
        frames = 0
        
        for i in range(0, len(audio), FRAME_SIZE):
            if not self.is_running:
                break
            
            frame = audio[i:i + FRAME_SIZE].ljust(FRAME_SIZE, b'\x00')
            self.writer.write(header + frame)
            frames += 1
            
            if frames % 25 == 0:
                await self.writer.drain()
            
            next_tick += TICK
            sleep = next_tick - time.perf_counter()
            if sleep > 0:
                await asyncio.sleep(sleep)
        
        await self.writer.drain()
        print(f"[GREETING] {frames} frames", flush=True)
    
    async def _play_busy(self):
        """Play busy tone."""
        import math
        
        # 480Hz + 620Hz busy tone
        samples = int(SAMPLE_RATE * 0.5)
        tone = b''
        for i in range(samples):
            val = int(8000 * (math.sin(2 * math.pi * 480 * i / SAMPLE_RATE) +
                              math.sin(2 * math.pi * 620 * i / SAMPLE_RATE)))
            tone += struct.pack('<h', max(-32768, min(32767, val)))
        
        silence = SILENCE * 25  # 500ms silence
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        TICK = FRAME_MS / 1000.0
        next_tick = time.perf_counter()
        
        for _ in range(3):
            for audio in [tone, silence]:
                for i in range(0, len(audio), FRAME_SIZE):
                    frame = audio[i:i + FRAME_SIZE].ljust(FRAME_SIZE, b'\x00')
                    self.writer.write(header + frame)
                    next_tick += TICK
                    sleep = next_tick - time.perf_counter()
                    if sleep > 0:
                        await asyncio.sleep(sleep)
        
        await self.writer.drain()
        self.writer.write(struct.pack('>BH', MSG_HANGUP, 0))
        await self.writer.drain()
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def _release_line(self):
        if self.phone_number_id:
            async with _active_calls_lock:
                _active_calls.pop(self.phone_number_id, None)
    
    async def _cleanup(self):
        self.is_running = False
        await self._release_line()
        
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
    """AudioSocket server."""
    
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server = None
        self._prewarmed = False
    
    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        print(f"[AudioSocket] ✅ Server on port {self.port} (pure 8kHz)", flush=True)
        
        if not self._prewarmed:
            asyncio.create_task(self._prewarm())
        asyncio.create_task(self._serve())
    
    async def _prewarm(self):
        try:
            from app.services.greeting_tts_service import prewarm_all_agent_greetings
            await prewarm_all_agent_greetings()
            self._prewarmed = True
        except:
            pass
    
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
        session = AudioSocketSession(reader, writer)
        await session.handle()


audiosocket_server = AudioSocketServer()
