"""
EAGI API Endpoints

Provides WebSocket-based real-time voice streaming for EAGI.
Uses the same FrenchVoiceAgentService as the web agent.
"""

import asyncio
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["eagi"])


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
    - Client sends: {"type": "audio", "data": "<base64 PCM 16kHz>"}
    - Server sends: {"type": "audio", "data": "<base64 PCM 24kHz>"}
    - Server sends: {"type": "transcript", "role": "user|assistant", "text": "..."}
    - Client sends: {"type": "end"}
    """
    await websocket.accept()
    logger.info("EAGI WebSocket connected")
    
    db = SessionLocal()
    agent = None
    call = None
    agent_service = None
    audio_task = None
    receive_task = None
    
    try:
        # Wait for start message
        start_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        
        if start_msg.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected start message"})
            return
        
        caller_id = start_msg.get("caller_id", "unknown")
        session_id = start_msg.get("session_id", f"eagi_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        logger.info(f"EAGI session starting: {session_id}, caller: {caller_id}")
        
        # Get agent
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
        
        logger.info(f"Using agent: {agent.name} (ID: {agent.id})")
        
        # Create call record
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
        
        logger.info(f"Call record created: {call.id}")
        
        # Create agent service (same as web agent)
        agent_service = FrenchVoiceAgentService(
            agent,
            call,
            skip_greeting_trigger=False
        )
        
        # Start Gemini session
        if not await agent_service.start_session():
            await websocket.send_json({"type": "error", "message": "Failed to start AI session"})
            return
        
        logger.info("Gemini session started")
        await websocket.send_json({"type": "ready", "agent": agent.name})
        
        # Task to send audio from Gemini to client
        async def send_audio_to_client():
            try:
                async for response in agent_service.session.receive():
                    # Audio data
                    if hasattr(response, 'data') and response.data:
                        audio_b64 = base64.b64encode(response.data).decode()
                        await websocket.send_json({
                            "type": "audio",
                            "data": audio_b64
                        })
                    
                    # Transcriptions
                    if hasattr(response, 'server_content'):
                        sc = response.server_content
                        if hasattr(sc, 'output_transcription') and sc.output_transcription:
                            text = getattr(sc.output_transcription, 'text', '')
                            if text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": text
                                })
                        if hasattr(sc, 'input_transcription') and sc.input_transcription:
                            text = getattr(sc.input_transcription, 'text', '')
                            if text:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "user",
                                    "text": text
                                })
            except Exception as e:
                if "closed" not in str(e).lower():
                    logger.error(f"Send audio error: {e}")
        
        # Task to forward audio to Gemini
        async def forward_audio_to_gemini():
            try:
                await agent_service.send_realtime_input()
            except Exception as e:
                if "cancel" not in str(e).lower():
                    logger.error(f"Forward audio error: {e}")
        
        # Start background tasks
        audio_task = asyncio.create_task(send_audio_to_client())
        receive_task = asyncio.create_task(forward_audio_to_gemini())
        
        # Main loop - receive audio from client
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
                
                elif msg_type == "end":
                    logger.info("Client requested end")
                    break
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break
        
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for start message")
    except Exception as e:
        logger.error(f"EAGI stream error: {e}", exc_info=True)
    finally:
        # Cleanup
        if audio_task:
            audio_task.cancel()
        if receive_task:
            receive_task.cancel()
        
        if agent_service:
            try:
                await agent_service.stop_session()
            except:
                pass
        
        if call:
            call.status = CallStatus.COMPLETED
            call.ended_at = datetime.utcnow()
            if call.started_at:
                call.duration = int((call.ended_at - call.started_at).total_seconds())
            db.commit()
            logger.info(f"Call {call.id} ended, duration: {call.duration}s")
        
        db.close()
        
        try:
            await websocket.close()
        except:
            pass
        
        logger.info("EAGI session ended")
