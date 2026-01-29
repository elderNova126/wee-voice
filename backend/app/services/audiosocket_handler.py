"""
Asterisk AudioSocket Handler - Simplified Architecture

Based on sip-to-ai reference: simple pass-through without complex buffering.
Audio flows continuously from AI to Asterisk with minimal processing.
"""
import asyncio
import socket
import struct
import logging
import uuid as uuid_lib
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.api.websocket import auto_summarize_call
from app.services.greeting_tts_service import get_greeting_tts_service, get_cached_greeting_sync
from app.services.audio_utils import (
    INPUT_SAMPLE_RATE, OUTPUT_SAMPLE_RATE, GEMINI_INPUT_RATE, OPENAI_SAMPLE_RATE,
    INPUT_FRAME_SIZE, SILENCE_8K, normalize_audio, apply_attack_envelope, simple_resample,
    AUDIO_TARGET_RMS, AUDIO_MAX_GAIN_DB, AUDIO_ATTACK_MS
)

logger = logging.getLogger(__name__)

# AudioSocket message types
MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

# Track active calls per phone number
_active_calls: dict[int, str] = {}
_active_calls_lock = asyncio.Lock()


class AudioSocketSession:
    """
    Handles a single AudioSocket call session.
    
    Simplified architecture based on sip-to-ai:
    - Simple accumulation buffer for frame alignment
    - No complex jitter buffer or rebuffering
    - Continuous audio flow from AI to Asterisk
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
        self.greeting_played = False
        self.llm_model = 'gemini'
        self.caller_id = None
        
    async def handle(self):
        """Main entry point for handling a call."""
        import time
        t0 = time.time()
        
        addr = self.writer.get_extra_info('peername')
        print(f"[{self._ts(t0)}] === AudioSocket CONNECTED from {addr} ===", flush=True)
        
        try:
            self.is_running = True
            
            # Set TCP_NODELAY for low latency
            sock = self.writer.get_extra_info('socket')
            if sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Send initial silence frames
            header = struct.pack('>BH', MSG_AUDIO, INPUT_FRAME_SIZE)
            for _ in range(5):
                self.writer.write(header + SILENCE_8K)
            await self.writer.drain()
            
            # Read UUID
            await self._read_uuid()
            if not self.call_uuid:
                return
            
            # Setup call (DB, agent, restrictions)
            if not await self._setup_call_quick():
                if self.is_busy_response:
                    await self._play_busy_message()
                return
            
            # Start receiving from Asterisk (drain buffer during setup)
            receive_task = asyncio.create_task(self._receive_loop())
            
            # Handle greeting based on model
            greeting_task = None
            if self.llm_model.startswith('gpt-'):
                # OpenAI: Let AI generate greeting (same voice)
                print(f"[{self._ts(t0)}] 🔵 OpenAI: AI will generate greeting", flush=True)
                self.greeting_audio = None
            elif self.greeting_audio:
                # Gemini: Use TTS greeting
                greeting_task = asyncio.create_task(self._play_tts_greeting())
            
            # Connect to AI
            if not await self._connect_ai():
                if greeting_task:
                    greeting_task.cancel()
                receive_task.cancel()
                return
            
            # Wait for greeting to finish
            if greeting_task:
                try:
                    await greeting_task
                except asyncio.CancelledError:
                    pass
            
            # Signal AI is ready
            self.ai_ready.set()
            print(f"[{self._ts(t0)}] AI READY", flush=True)
            
            # Start audio loops
            audio_task = asyncio.create_task(self._audio_loop())
            caller_task = asyncio.create_task(self._caller_to_ai_loop())
            input_task = asyncio.create_task(self.agent_service.send_realtime_input())
            
            # Wait for call to end
            await receive_task
            
            # Cleanup tasks
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
    
    def _ts(self, t0):
        """Timestamp helper."""
        import time
        return f"{(time.time()-t0)*1000:.0f}ms"
    
    # =========================================================================
    # SIMPLIFIED AUDIO LOOP - Based on sip-to-ai approach
    # =========================================================================
    
    async def _audio_loop(self):
        """
        Simple audio loop: receive from AI, send to Asterisk.
        
        Key insight from sip-to-ai: Don't over-engineer buffering.
        AI services provide reasonably-timed audio. Just:
        1. Receive chunks from AI
        2. Accumulate into 20ms frames
        3. Send immediately
        """
        import time
        print(f"[AUDIO] Starting simple audio loop", flush=True)
        
        frame_size = INPUT_FRAME_SIZE  # 320 bytes (20ms at 8kHz)
        header = struct.pack('>BH', MSG_AUDIO, frame_size)
        
        # Simple accumulation buffer (like sip-to-ai's AudioAdapter)
        pending = b''
        frames_sent = 0
        chunks_recv = 0
        
        # Determine AI output rate
        if self.llm_model.startswith('gpt-'):
            ai_rate = OPENAI_SAMPLE_RATE  # 8kHz
        else:
            ai_rate = OUTPUT_SAMPLE_RATE  # 24kHz
        
        resample_state = None
        attack_state = None
        attack_done = False
        
        # Pacer timing
        TICK = 0.02  # 20ms
        next_tick = time.perf_counter()
        
        print(f"[AUDIO] AI rate: {ai_rate}Hz → Asterisk 8kHz", flush=True)
        
        try:
            # Create receiver task to fill pending buffer
            recv_queue = asyncio.Queue(maxsize=50)
            
            async def receiver():
                nonlocal chunks_recv
                try:
                    async for audio in self.agent_service.receive_audio():
                        if not self.is_running:
                            break
                        if audio and len(audio) >= 2:
                            chunks_recv += 1
                            await recv_queue.put(audio)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"[AUDIO] Receiver error: {e}", flush=True)
                await recv_queue.put(None)  # Sentinel
            
            recv_task = asyncio.create_task(receiver())
            
            # Main pacer loop - emit frames at 20ms cadence
            while self.is_running:
                # Wait for next tick
                now = time.perf_counter()
                sleep_for = next_tick - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                
                # Drain all available audio from queue into pending
                while True:
                    try:
                        chunk = recv_queue.get_nowait()
                        if chunk is None:
                            # End of stream
                            if pending:
                                # Send remaining with padding
                                frame = pending.ljust(frame_size, b'\x00')
                                self.writer.write(header + frame)
                                frames_sent += 1
                            await self.writer.drain()
                            print(f"[AUDIO] Done: {frames_sent} frames, {chunks_recv} chunks", flush=True)
                            recv_task.cancel()
                            return
                        
                        # Resample to 8kHz if needed
                        if ai_rate != INPUT_SAMPLE_RATE:
                            chunk, resample_state = simple_resample(
                                chunk, ai_rate, INPUT_SAMPLE_RATE, resample_state
                            )
                        
                        # Skip empty chunks
                        if len(chunk) < 2:
                            continue
                        
                        # Apply attack envelope at start
                        if not attack_done:
                            chunk, attack_state = apply_attack_envelope(
                                chunk, INPUT_SAMPLE_RATE, AUDIO_ATTACK_MS, attack_state
                            )
                            if attack_state and attack_state.get('bytes_remaining', 0) <= 0:
                                attack_done = True
                        
                        # Normalize
                        chunk = normalize_audio(chunk, AUDIO_TARGET_RMS, AUDIO_MAX_GAIN_DB)
                        
                        pending += chunk
                        
                    except asyncio.QueueEmpty:
                        break
                
                # Emit frame
                if len(pending) >= frame_size:
                    frame = pending[:frame_size]
                    pending = pending[frame_size:]
                    self.writer.write(header + frame)
                    frames_sent += 1
                else:
                    # Not enough audio - send silence
                    self.writer.write(header + SILENCE_8K)
                    frames_sent += 1
                
                # Drain writer periodically
                if frames_sent % 25 == 0:
                    try:
                        await self.writer.drain()
                    except:
                        break
                
                # Log progress
                if frames_sent == 1 or frames_sent % 500 == 0:
                    print(f"[AUDIO] {frames_sent} frames, pending={len(pending)}b, chunks={chunks_recv}", flush=True)
                
                next_tick += TICK
                
                # Reset if behind
                if next_tick < time.perf_counter() - 0.1:
                    next_tick = time.perf_counter()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AUDIO] Error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        print(f"[AUDIO] Ended: {frames_sent} frames sent", flush=True)
    
    # =========================================================================
    # ASTERISK RECEIVE LOOP
    # =========================================================================
    
    async def _receive_loop(self):
        """Receive audio from Asterisk."""
        frames = 0
        try:
            while self.is_running:
                try:
                    header = await asyncio.wait_for(self.reader.readexactly(3), timeout=60.0)
                except asyncio.IncompleteReadError:
                    break
                except asyncio.TimeoutError:
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                if payload_len > 0:
                    try:
                        payload = await self.reader.readexactly(payload_len)
                    except asyncio.IncompleteReadError:
                        break
                else:
                    payload = b''
                
                if msg_type == MSG_AUDIO:
                    frames += 1
                    if frames <= 10 or frames % 50 == 0:
                        print(f"[RECV] Frame #{frames}", flush=True)
                    await self._process_audio(payload)
                elif msg_type == MSG_HANGUP:
                    print(f"[RECV] HANGUP", flush=True)
                    break
                elif msg_type == MSG_ERROR:
                    print(f"[RECV] ERROR", flush=True)
                    break
                    
        except Exception as e:
            print(f"[RECV] Exception: {e}", flush=True)
        
        print(f"[RECV] Ended: {frames} frames", flush=True)
    
    async def _process_audio(self, audio_8k: bytes):
        """Process audio from Asterisk and queue for AI."""
        if not self.ai_ready.is_set() or len(audio_8k) < 2:
            return
        
        try:
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            
            # OpenAI: 8kHz passthrough, Gemini: 8kHz → 16kHz
            if self.llm_model.startswith('gpt-'):
                audio_for_ai = audio_8k
            else:
                if not hasattr(self, '_caller_resample_state'):
                    self._caller_resample_state = None
                audio_for_ai, self._caller_resample_state = simple_resample(
                    audio_8k, INPUT_SAMPLE_RATE, GEMINI_INPUT_RATE, self._caller_resample_state
                )
            
            try:
                self.caller_audio_queue.put_nowait(audio_for_ai)
            except asyncio.QueueFull:
                pass
        except Exception as e:
            print(f"[PROCESS] Error: {e}", flush=True)
    
    async def _caller_to_ai_loop(self):
        """Forward caller audio to AI."""
        import time
        packets = 0
        audio_buffer = b''
        
        if self.llm_model.startswith('gpt-'):
            audio_rate = OPENAI_SAMPLE_RATE
            batch_size = 640  # 40ms at 8kHz
        else:
            audio_rate = GEMINI_INPUT_RATE
            batch_size = 1280  # 40ms at 16kHz
        
        print(f"[CALLER→AI] Started ({audio_rate}Hz)", flush=True)
        
        try:
            while self.is_running:
                try:
                    chunk = await asyncio.wait_for(self.caller_audio_queue.get(), timeout=0.04)
                    audio_buffer += chunk
                except asyncio.TimeoutError:
                    # Send what we have
                    if len(audio_buffer) >= 320 and self.agent_service:
                        packets += 1
                        await self.agent_service.send_audio(audio_buffer)
                        audio_buffer = b''
                    continue
                
                if len(audio_buffer) >= batch_size and self.agent_service:
                    packets += 1
                    await self.agent_service.send_audio(audio_buffer, 
                        mime_type=f"audio/pcm;rate={audio_rate}")
                    audio_buffer = b''
                    
                    if packets <= 10 or packets % 100 == 0:
                        print(f"[CALLER→AI] #{packets}", flush=True)
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[CALLER→AI] Error: {e}", flush=True)
        
        print(f"[CALLER→AI] Ended: {packets} packets", flush=True)
    
    # =========================================================================
    # CALL SETUP
    # =========================================================================
    
    async def _read_uuid(self):
        """Read UUID from AudioSocket."""
        import os
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
            
            # Read caller ID file
            if self.call_uuid:
                await asyncio.sleep(0.1)
                self._read_caller_id_file()
                
            print(f"[UUID] {self.call_uuid}, caller={self.caller_id}", flush=True)
            
        except Exception as e:
            print(f"[UUID] Error: {e}", flush=True)
            self.call_uuid = str(uuid_lib.uuid4())
    
    def _read_caller_id_file(self):
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
        except Exception as e:
            print(f"[CALLER_ID] Error: {e}", flush=True)
    
    async def _setup_call_quick(self) -> bool:
        """Quick setup: DB, agent, restrictions."""
        self.db = SessionLocal()
        try:
            # Find phone with SIP config
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)
            ).first()
            
            if not phone:
                print(f"[SETUP] No phone with SIP config", flush=True)
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
            self.agent = self.db.query(VoiceAgent).filter(
                VoiceAgent.id == phone.agent_id
            ).first()
            
            if not self.agent:
                self.agent = self.db.query(VoiceAgent).first()
            
            if not self.agent:
                await self._release_line()
                return False
            
            # Check restrictions
            caller_phone = self.caller_id or "Unknown"
            if self._is_caller_blocked(phone, caller_phone):
                self.is_busy_response = True
                self.busy_config = {'action': 'busy_tone'}
                await self._release_line()
                return False
            
            # Create call record
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone=caller_phone,
                caller_name=caller_phone,
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            # Get cached greeting (for Gemini only)
            if self.agent.greeting and not self.llm_model.startswith('gpt-'):
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
    
    def _is_caller_blocked(self, phone, caller_phone: str) -> bool:
        """Check if caller is blocked."""
        import json
        
        mode = phone.restriction_mode or 'none'
        if mode == 'none':
            return False
        
        def parse_list(val):
            if not val:
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                if val.startswith('{') and val.endswith('}') and not val.startswith('{"'):
                    return [x.strip().strip('"') for x in val[1:-1].split(',') if x.strip()]
                try:
                    return json.loads(val) if val else []
                except:
                    return []
            return []
        
        blocked_countries = parse_list(phone.blocked_countries)
        blocked_numbers = parse_list(phone.blocked_numbers)
        allowed_countries = parse_list(phone.allowed_countries)
        
        # Get country from number
        country = ''
        prefixes = {'+1': 'US', '+44': 'UK', '+33': 'FR', '+49': 'DE', '+32': 'BE',
                    '+84': 'VN', '+81': 'JP', '+86': 'CN', '+91': 'IN'}
        for prefix, code in sorted(prefixes.items(), key=lambda x: -len(x[0])):
            if caller_phone.startswith(prefix):
                country = code
                break
        
        if mode == 'blacklist':
            if country and country.upper() in [c.upper() for c in blocked_countries]:
                return True
            for pattern in blocked_numbers:
                if caller_phone == pattern or (pattern.endswith('*') and caller_phone.startswith(pattern[:-1])):
                    return True
            return False
        
        elif mode == 'whitelist':
            if not allowed_countries:
                return True
            return not (country and country.upper() in [c.upper() for c in allowed_countries])
        
        return False
    
    async def _connect_ai(self) -> bool:
        """Connect to AI service."""
        try:
            from app.services.openai_realtime_service import get_voice_agent_service, is_openai_model
            
            if is_openai_model(self.llm_model):
                print(f"[AI] 🔵 OpenAI Realtime ({self.llm_model})", flush=True)
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
    
    # =========================================================================
    # GREETING & BUSY
    # =========================================================================
    
    async def _play_tts_greeting(self):
        """Play pre-generated greeting."""
        if not self.greeting_audio:
            return
        
        import time
        
        # Normalize and apply attack envelope
        audio = normalize_audio(self.greeting_audio, AUDIO_TARGET_RMS, AUDIO_MAX_GAIN_DB)
        audio, _ = apply_attack_envelope(audio, INPUT_SAMPLE_RATE, AUDIO_ATTACK_MS, None)
        
        header = struct.pack('>BH', MSG_AUDIO, INPUT_FRAME_SIZE)
        frames = 0
        
        # Lead-in silence
        for _ in range(8):
            self.writer.write(header + SILENCE_8K)
        await self.writer.drain()
        
        # Send audio
        TICK = 0.02
        next_tick = time.perf_counter()
        
        for i in range(0, len(audio), INPUT_FRAME_SIZE):
            if not self.is_running:
                break
            
            chunk = audio[i:i + INPUT_FRAME_SIZE]
            if len(chunk) < INPUT_FRAME_SIZE:
                chunk += b'\x00' * (INPUT_FRAME_SIZE - len(chunk))
            
            self.writer.write(header + chunk)
            frames += 1
            
            if frames % 25 == 0:
                await self.writer.drain()
            
            next_tick += TICK
            sleep = next_tick - time.perf_counter()
            if sleep > 0:
                await asyncio.sleep(sleep)
        
        await self.writer.drain()
        self.greeting_played = True
        print(f"[GREETING] Done: {frames} frames", flush=True)
    
    async def _play_busy_message(self):
        """Play busy tone and hangup."""
        import math
        import time
        
        # Generate busy tone (480Hz + 620Hz)
        sample_rate = INPUT_SAMPLE_RATE
        duration = 0.5
        samples = int(sample_rate * duration)
        
        tone = b''
        for i in range(samples):
            val = int(8000 * (math.sin(2 * math.pi * 480 * i / sample_rate) +
                              math.sin(2 * math.pi * 620 * i / sample_rate)))
            tone += struct.pack('<h', max(-32768, min(32767, val)))
        
        silence = b'\x00' * (samples * 2)
        header = struct.pack('>BH', MSG_AUDIO, INPUT_FRAME_SIZE)
        
        TICK = 0.02
        next_tick = time.perf_counter()
        
        for _ in range(3):  # 3 beeps
            for audio in [tone, silence]:
                for i in range(0, len(audio), INPUT_FRAME_SIZE):
                    chunk = audio[i:i + INPUT_FRAME_SIZE]
                    if len(chunk) < INPUT_FRAME_SIZE:
                        chunk += b'\x00' * (INPUT_FRAME_SIZE - len(chunk))
                    self.writer.write(header + chunk)
                    
                    next_tick += TICK
                    sleep = next_tick - time.perf_counter()
                    if sleep > 0:
                        await asyncio.sleep(sleep)
        
        await self.writer.drain()
        
        # Send hangup
        self.writer.write(struct.pack('>BH', MSG_HANGUP, 0))
        await self.writer.drain()
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    
    async def _release_line(self):
        """Release phone line."""
        if self.phone_number_id:
            async with _active_calls_lock:
                if self.phone_number_id in _active_calls:
                    del _active_calls[self.phone_number_id]
    
    async def _cleanup(self):
        """Cleanup resources."""
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
    """AudioSocket server for handling incoming calls."""
    
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server = None
        self._greetings_prewarmed = False
    
    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        print(f"[AudioSocket] ✅ Server started on port {self.port}", flush=True)
        
        if not self._greetings_prewarmed:
            asyncio.create_task(self._prewarm_greetings())
        
        asyncio.create_task(self._serve())
    
    async def _prewarm_greetings(self):
        try:
            from app.services.greeting_tts_service import prewarm_all_agent_greetings
            await prewarm_all_agent_greetings()
            self._greetings_prewarmed = True
        except Exception as e:
            print(f"[AudioSocket] Greeting prewarm failed: {e}", flush=True)
    
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
