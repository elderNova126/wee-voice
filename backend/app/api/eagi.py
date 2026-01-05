"""
EAGI API Endpoints

Provides WebSocket-based real-time voice streaming for EAGI.
Uses the same FrenchVoiceAgentService as the web agent.

OPTIMIZATION: Pre-cached greeting is sent IMMEDIATELY on WebSocket connect,
while Gemini session starts in parallel. This reduces initial delay from 5+ seconds to <1 second.
"""

import asyncio
import audioop
import base64
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db, SessionLocal
from app.models import VoiceAgent, PhoneNumber, Call, CallStatus
from app.core.config import settings
from app.services.agent_service import FrenchVoiceAgentService
from app.services.greeting_tts_service import get_cached_greeting_sync, get_gemini_voice_name, GreetingTTSService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["eagi"])

# Greeting TTS service instance for background generation
_greeting_service = GreetingTTSService()


class AgentConfigResponse(BaseModel):
    """Agent configuration for EAGI"""
    agent_id: int
    agent_name: str
    greeting: str
    language: str
    voice_id: str


@router.get("/config")
async def get_agent_config(db: Session = Depends(get_db)) -> AgentConfigResponse:
    """Get agent configuration"""
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.agent_id.isnot(None),
        PhoneNumber.sip_username.isnot(None)
    ).first()
    
    if phone:
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
    else:
        agent = db.query(VoiceAgent).filter(VoiceAgent.is_active == True).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="No agent configured")
    
    return AgentConfigResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        greeting=agent.greeting or "Hello!",
        language=agent.language or "en-US",
        voice_id=agent.voice_id or "Aoede"
    )


@router.websocket("/stream")
async def eagi_stream(websocket: WebSocket):
    """
    WebSocket endpoint for EAGI real-time audio streaming.
    
    Protocol:
    - Client sends: {"type": "start", "caller_id": "...", "session_id": "..."}
    - Server sends: {"type": "greeting", "data": "<base64 PCM 8kHz>"}  # IMMEDIATE - before Gemini ready
    - Server sends: {"type": "ready", "agent": "..."}  # After Gemini connected
    - Client sends: {"type": "audio", "data": "<base64 PCM 16kHz>"}
    - Server sends: {"type": "audio", "data": "<base64 PCM 24kHz>"}
    - Server sends: {"type": "transcript", "role": "user|assistant", "text": "..."}
    - Client sends: {"type": "end"}
    """
    await websocket.accept()
    print("[EAGI-WS] WebSocket connected", flush=True)
    logger.info("[EAGI-WS] WebSocket connected")
    
    db = SessionLocal()
    agent = None
    call = None
    agent_service = None
    audio_task = None
    receive_task = None
    greeting_sent = False  # Track if pre-cached greeting was successfully sent
    
    try:
        # Wait for start message
        start_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        
        if start_msg.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected start message"})
            return
        
        caller_id = start_msg.get("caller_id", "unknown")
        session_id = start_msg.get("session_id", f"eagi_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        print(f"[EAGI-WS] Session starting: {session_id}, caller: {caller_id}", flush=True)
        logger.info(f"[EAGI-WS] Session starting: {session_id}, caller: {caller_id}")
        
        # Get agent IMMEDIATELY
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.agent_id.isnot(None),
            PhoneNumber.sip_username.isnot(None)
        ).first()
        
        if phone:
            agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
        
        if not agent:
            agent = db.query(VoiceAgent).filter(VoiceAgent.is_active == True).first()
        
        if not agent:
            await websocket.send_json({"type": "error", "message": "No agent configured"})
            return
        
        print(f"[EAGI-WS] Using agent: {agent.name} (ID: {agent.id})", flush=True)
        logger.info(f"[EAGI-WS] Using agent: {agent.name} (ID: {agent.id})")
        
        # =====================================================================
        # OPTIMIZATION: Send pre-cached greeting IMMEDIATELY before Gemini starts
        # This eliminates the 5+ second delay!
        # =====================================================================
        if agent.greeting:
            import time
            t0 = time.perf_counter()
            
            language = getattr(agent, 'language', 'fr-FR') or 'fr-FR'
            gender = getattr(agent, 'voice_gender', 'male') or 'male'
            voice_id = getattr(agent, 'voice_id', None)  # Specific voice takes priority
            
            print(f"[EAGI-WS] Looking for cached greeting (lang={language}, gender={gender}, voice_id={voice_id})", flush=True)
            
            # Get cached greeting (instant - just a file read)
            # IMPORTANT: Pass voice_id to ensure greeting uses same voice as conversation
            greeting_audio = get_cached_greeting_sync(agent.greeting, language, gender, voice_id)
            
            if greeting_audio:
                # The cached greeting is 8kHz PCM16 - convert to 24kHz for EAGI
                # (EAGI expects 24kHz from backend for playback)
                try:
                    greeting_24k, _ = audioop.ratecv(greeting_audio, 2, 1, 8000, 24000, None)
                    
                    # Send greeting in chunks to avoid WebSocket message size limit
                    # Each chunk should be ~50KB to stay well under 1MB limit
                    CHUNK_SIZE = 48000  # ~1 second of 24kHz audio (24000 * 2 bytes)
                    total_chunks = (len(greeting_24k) + CHUNK_SIZE - 1) // CHUNK_SIZE
                    
                    print(f"[EAGI-WS] Sending greeting: {len(greeting_24k)} bytes in {total_chunks} chunks", flush=True)
                    
                    # Send greeting start marker
                    await websocket.send_json({
                        "type": "greeting_start",
                        "total_bytes": len(greeting_24k),
                        "chunks": total_chunks
                    })
                    
                    # Send greeting audio in chunks
                    for i in range(0, len(greeting_24k), CHUNK_SIZE):
                        chunk = greeting_24k[i:i + CHUNK_SIZE]
                        chunk_b64 = base64.b64encode(chunk).decode()
                        await websocket.send_json({
                            "type": "greeting_chunk",
                            "data": chunk_b64,
                            "index": i // CHUNK_SIZE
                        })
                    
                    # Send greeting end marker
                    await websocket.send_json({"type": "greeting_end"})
                    
                    # Mark greeting as successfully sent - IMPORTANT!
                    greeting_sent = True
                    
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    print(f"[EAGI-WS] ✅ Greeting sent in {elapsed_ms:.0f}ms ({len(greeting_24k)} bytes)", flush=True)
                    logger.info(f"[EAGI-WS] Greeting sent in {elapsed_ms:.0f}ms")
                except Exception as e:
                    print(f"[EAGI-WS] ⚠ Greeting conversion error: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    greeting_sent = False
            else:
                print(f"[EAGI-WS] ⚠ No cached greeting found, Gemini will generate it", flush=True)
                # Trigger background generation for next call
                _greeting_service.trigger_background_generation(agent.greeting, language, gender)
        
        # Create call record (can be done while Gemini is starting)
        call = Call(
            user_id=agent.user_id,
            agent_id=agent.id,
            caller_phone=caller_id,
            caller_name=caller_id,
            direction="inbound",
            status=CallStatus.IN_PROGRESS,
            session_id=session_id,
            started_at=datetime.utcnow()
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        
        print(f"[EAGI-WS] Call record created: {call.id}", flush=True)
        logger.info(f"[EAGI-WS] Call record created: {call.id}")
        
        # Create agent service - skip greeting trigger if we already sent cached greeting
        print(f"[EAGI-WS] Creating agent service (skip_greeting_trigger={greeting_sent})", flush=True)
        agent_service = FrenchVoiceAgentService(
            agent,
            call,
            skip_greeting_trigger=greeting_sent  # Skip Gemini greeting if cached was sent
        )
        
        # Start Gemini session (this is the slow part - 2-4 seconds)
        # But the caller is already hearing the greeting!
        print("[EAGI-WS] Starting Gemini session...", flush=True)
        logger.info("[EAGI-WS] Starting Gemini session...")
        if not await agent_service.start_session():
            print("[EAGI-WS] Failed to start Gemini session", flush=True)
            logger.error("[EAGI-WS] Failed to start Gemini session")
            await websocket.send_json({"type": "error", "message": "Failed to start AI session"})
            return
        
        print(f"[EAGI-WS] Gemini session started for agent {agent.name}", flush=True)
        logger.info(f"[EAGI-WS] Gemini session started for agent {agent.name}")
        
        await websocket.send_json({"type": "ready", "agent": agent.name})
        
        # Task to receive audio from Gemini and send to client
        # Uses receive_audio() which is the proper method (same as audiosocket_handler uses)
        async def send_audio_to_client():
            audio_chunks_sent = 0
            print("[EAGI-OUT] Starting Gemini audio receiver (using receive_audio)", flush=True)
            logger.info("[EAGI-OUT] Starting Gemini audio receiver (using receive_audio)")
            
            try:
                # Use receive_audio() - the proper method that handles session.receive() internally
                async for audio_data in agent_service.receive_audio():
                    if not audio_data or len(audio_data) < 2:
                        continue
                    
                    # Ensure even byte count for 16-bit audio
                    if len(audio_data) % 2:
                        audio_data = audio_data[:-1]
                    
                    audio_b64 = base64.b64encode(audio_data).decode()
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_b64
                    })
                    audio_chunks_sent += 1
                    
                    if audio_chunks_sent == 1:
                        print(f"[EAGI-OUT] First audio chunk sent! Size: {len(audio_data)}", flush=True)
                        logger.info(f"[EAGI-OUT] First audio chunk sent! Size: {len(audio_data)}")
                    elif audio_chunks_sent % 50 == 0:
                        print(f"[EAGI-OUT] Sent {audio_chunks_sent} audio chunks", flush=True)
                        
            except asyncio.CancelledError:
                print("[EAGI-OUT] Task cancelled", flush=True)
                logger.info("[EAGI-OUT] Task cancelled")
            except Exception as e:
                if "closed" not in str(e).lower():
                    print(f"[EAGI-OUT] Error: {e}", flush=True)
                    logger.error(f"[EAGI-OUT] Error: {e}", exc_info=True)
            print(f"[EAGI-OUT] Ended, sent {audio_chunks_sent} chunks total", flush=True)
            logger.info(f"[EAGI-OUT] Ended, sent {audio_chunks_sent} chunks total")
        
        # Task to forward audio to Gemini (using send_realtime_input)
        async def forward_audio_to_gemini():
            print("[EAGI-FWD] Starting Gemini audio sender task", flush=True)
            logger.info("[EAGI-FWD] Starting Gemini audio sender task")
            try:
                await agent_service.send_realtime_input()
            except asyncio.CancelledError:
                print("[EAGI-FWD] Task cancelled", flush=True)
                logger.info("[EAGI-FWD] Task cancelled")
            except Exception as e:
                if "cancel" not in str(e).lower():
                    print(f"[EAGI-FWD] Error: {e}", flush=True)
                    logger.error(f"[EAGI-FWD] Error: {e}", exc_info=True)
            print("[EAGI-FWD] Ended", flush=True)
            logger.info("[EAGI-FWD] Ended")
        
        # Start background tasks
        print("[EAGI-WS] Creating background tasks...", flush=True)
        logger.info("[EAGI-WS] Creating background tasks...")
        audio_task = asyncio.create_task(send_audio_to_client())
        receive_task = asyncio.create_task(forward_audio_to_gemini())
        print("[EAGI-WS] Background tasks started", flush=True)
        logger.info("[EAGI-WS] Background tasks started")
        
        # Main loop - receive audio from client and queue for Gemini
        audio_received = 0
        print("[EAGI-WS] Starting main audio receive loop", flush=True)
        logger.info("[EAGI-WS] Starting main audio receive loop")
        while True:
            try:
                msg = await websocket.receive_json()
                msg_type = msg.get("type")
                
                if msg_type == "audio":
                    # Decode and queue audio for Gemini
                    audio_data = base64.b64decode(msg.get("data", ""))
                    if audio_data:
                        await agent_service.audio_out_queue.put({
                            "data": audio_data,
                            "mime_type": "audio/pcm;rate=16000"
                        })
                        audio_received += 1
                        if audio_received == 1:
                            print(f"[EAGI-WS] First audio from EAGI: {len(audio_data)} bytes", flush=True)
                            logger.info(f"[EAGI-WS] First audio from EAGI: {len(audio_data)} bytes")
                        elif audio_received % 100 == 0:
                            print(f"[EAGI-WS] Received {audio_received} audio chunks from EAGI", flush=True)
                            logger.info(f"[EAGI-WS] Received {audio_received} audio chunks from EAGI")
                
                elif msg_type == "end":
                    print("[EAGI-WS] Client requested end", flush=True)
                    logger.info("[EAGI-WS] Client requested end")
                    break
                    
            except WebSocketDisconnect:
                print("[EAGI-WS] WebSocket disconnected", flush=True)
                logger.info("[EAGI-WS] WebSocket disconnected")
                break
            except Exception as e:
                print(f"[EAGI-WS] Receive error: {e}", flush=True)
                logger.error(f"[EAGI-WS] Receive error: {e}", exc_info=True)
                break
        
        print(f"[EAGI-WS] Main loop ended, received {audio_received} total chunks", flush=True)
        logger.info(f"[EAGI-WS] Main loop ended, received {audio_received} total chunks")
        
    except asyncio.TimeoutError:
        print("[EAGI-WS] Timeout waiting for start message", flush=True)
        logger.error("[EAGI-WS] Timeout waiting for start message")
    except Exception as e:
        print(f"[EAGI-WS] Stream error: {e}", flush=True)
        logger.error(f"[EAGI-WS] Stream error: {e}", exc_info=True)
    finally:
        # Cleanup
        print("[EAGI-WS] Cleaning up...", flush=True)
        logger.info("[EAGI-WS] Cleaning up...")
        if audio_task:
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass
        if receive_task:
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        
        if agent_service:
            try:
                await agent_service.stop_session()
            except Exception as e:
                print(f"[EAGI-WS] Stop session error: {e}", flush=True)
                logger.error(f"[EAGI-WS] Stop session error: {e}")
        
        if call:
            call.status = CallStatus.COMPLETED
            call.ended_at = datetime.utcnow()
            if call.started_at:
                call.duration = int((call.ended_at - call.started_at).total_seconds())
            db.commit()
            print(f"[EAGI-WS] Call {call.id} ended, duration: {call.duration}s", flush=True)
            logger.info(f"[EAGI-WS] Call {call.id} ended, duration: {call.duration}s")
        
        db.close()
        
        try:
            await websocket.close()
        except:
            pass
        
        print("[EAGI-WS] Session ended", flush=True)
        logger.info("[EAGI-WS] Session ended")
