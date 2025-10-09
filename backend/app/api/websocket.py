import asyncio
import json
import logging
from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.models import get_db, User, VoiceAgent, Call, CallStatus
from app.core.security import verify_api_key, decode_token
from app.services.agent_service import FrenchVoiceAgentService
from app.services.crm_service import CRMIntegrationService

# Note: Using asyncio.gather for Python 3.10+ compatibility instead of TaskGroup (3.11+)

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for voice sessions"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agent_services: dict[str, FrenchVoiceAgentService] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.agent_services:
            del self.agent_services[session_id]
        logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)
    
    async def send_audio(self, session_id: str, audio_data: bytes):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_bytes(audio_data)


manager = ConnectionManager()


@router.websocket("/voice/{agent_id}")
async def voice_websocket(
    websocket: WebSocket,
    agent_id: int,
    api_key: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time voice conversations"""
    session_id = str(uuid.uuid4())
    user: Optional[User] = None
    call: Optional[Call] = None
    agent_service: Optional[FrenchVoiceAgentService] = None
    
    print(f"\n{'='*60}")
    print(f"🔌 NEW WEBSOCKET CONNECTION")
    print(f"   Agent ID: {agent_id}")
    print(f"   Session ID: {session_id}")
    print(f"{'='*60}\n")
    logger.info(f"🔌 New WebSocket connection request for agent_id={agent_id}, session_id={session_id}")
    
    try:
        # Verify authentication (API key or JWT token)
        if api_key:
            logger.info(f"API key provided: {api_key[:20]}...")
            user = await verify_api_key(api_key, db)
            if not user:
                logger.warning(f"Invalid API key: {api_key[:20]}...")
                await websocket.close(code=4001, reason="Invalid API key")
                return
            logger.info(f"User authenticated via API key: {user.email}")
        elif token:
            logger.info(f"JWT token provided: {token[:20]}...")
            payload = decode_token(token)
            if not payload:
                logger.warning("Invalid JWT token")
                await websocket.close(code=4001, reason="Invalid token")
                return
            user_id = payload.get("sub")
            if not user_id:
                logger.warning("No user ID in token")
                await websocket.close(code=4001, reason="Invalid token")
                return
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                logger.warning(f"User not found: {user_id}")
                await websocket.close(code=4001, reason="User not found")
                return
            logger.info(f"User authenticated via JWT: {user.email}")
        else:
            # For demo purposes, allow public agents without auth
            logger.info("No authentication provided - accessing public agent")
        
        # Get agent
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
        if not agent:
            logger.error(f"Agent {agent_id} not found")
            await websocket.close(code=4004, reason="Agent not found")
            return
        
        logger.info(f"Found agent: {agent.name} (language: {agent.language}, public: {agent.is_public})")
        
        # Check permissions
        if not agent.is_public and (not user or agent.user_id != user.id):
            logger.warning(f"Access denied for agent {agent_id}")
            await websocket.close(code=4003, reason="Access denied")
            return
        
        # Accept connection
        logger.info(f"Accepting WebSocket connection for session {session_id}")
        await manager.connect(session_id, websocket)
        
        # Create call record
        call = Call(
            user_id=user.id if user else agent.user_id,
            agent_id=agent_id,
            session_id=session_id,
            status=CallStatus.INITIATED,
            started_at=datetime.utcnow()
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Initialize agent service
        agent_service = FrenchVoiceAgentService(agent, call)
        manager.agent_services[session_id] = agent_service
        
        # Start agent session
        success = await agent_service.start_session()
        if not success:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to start agent session"
            })
            await websocket.close()
            return
        
        # Send session started message
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "agent_name": agent.name,
            "language": agent.language
        })
        
        # Create tasks for bidirectional communication
        async def receive_audio_from_client():
            """Receive audio from client and send to agent"""
            try:
                audio_chunks_received = 0
                while True:
                    data = await websocket.receive()
                    
                    if "bytes" in data:
                        # Audio data
                        audio_data = data["bytes"]
                        audio_chunks_received += 1
                        if audio_chunks_received % 50 == 0:  # Log every 50 chunks
                            print(f"📥 Received {audio_chunks_received} audio chunks from client")
                            logger.info(f"Session {session_id}: Received {audio_chunks_received} audio chunks ({len(audio_data)} bytes)")
                        await agent_service.send_audio(audio_data)
                    
                    elif "text" in data:
                        # Control messages
                        message = json.loads(data["text"])
                        logger.info(f"Session {session_id}: Received control message: {message.get('type')}")
                        
                        if message.get("type") == "end_session":
                            break
                        elif message.get("type") == "interrupt":
                            # Handle interruption
                            pass
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {session_id}")
            except Exception as e:
                logger.error(f"Error receiving from client: {e}", exc_info=True)
        
        async def send_audio_to_client():
            """Receive audio from agent and send to client"""
            print(f"🎧 send_audio_to_client task started for session {session_id}")
            try:
                audio_chunks_sent = 0
                print(f"🔄 Starting to iterate over agent_service.receive_audio()...")
                async for audio_data in agent_service.receive_audio():
                    audio_chunks_sent += 1
                    if audio_chunks_sent == 1:
                        print(f"📢 FIRST AUDIO CHUNK RECEIVED IN TASK! Size: {len(audio_data)} bytes")
                    if audio_chunks_sent % 10 == 0:  # Log every 10 chunks
                        print(f"📢 Sent {audio_chunks_sent} audio chunks to client")
                        logger.info(f"Session {session_id}: Sent {audio_chunks_sent} audio chunks to client")
                    print(f"📤 Sending audio chunk {audio_chunks_sent} ({len(audio_data)} bytes) to client...")
                    await manager.send_audio(session_id, audio_data)
                    print(f"✅ Audio chunk {audio_chunks_sent} sent successfully")
                print(f"⚠️ receive_audio() iterator ended")
            except Exception as e:
                print(f"❌ ERROR in send_audio_to_client: {e}")
                logger.error(f"Error sending to client: {e}", exc_info=True)
        
        async def send_realtime_input():
            """Send queued audio to agent"""
            try:
                logger.info(f"Session {session_id}: Starting realtime input sender")
                await agent_service.send_realtime_input()
            except Exception as e:
                logger.error(f"Error in realtime input: {e}", exc_info=True)
        
        # Run all tasks concurrently (compatible with Python 3.10+)
        print(f"\n🚀 Starting 3 concurrent tasks:")
        print(f"   1. receive_audio_from_client")
        print(f"   2. send_audio_to_client")
        print(f"   3. send_realtime_input\n")
        try:
            results = await asyncio.gather(
                receive_audio_from_client(),
                send_audio_to_client(),
                send_realtime_input(),
                return_exceptions=True
            )
            print(f"\n⚠️ All tasks completed. Results: {results}\n")
        except Exception as e:
            print(f"❌ Error in concurrent tasks: {e}")
            logger.error(f"Error in concurrent tasks: {e}")
    
    except asyncio.CancelledError:
        logger.info(f"Tasks cancelled for session: {session_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    
    finally:
        # Cleanup
        if agent_service:
            await agent_service.end_session()
        
        if call:
            call.status = CallStatus.COMPLETED
            call.ended_at = datetime.utcnow()
            
            # Calculate duration
            duration = (call.ended_at - call.started_at).total_seconds()
            call.duration_seconds = duration
            call.duration_minutes = duration / 60.0
            
            # Calculate cost (example: $0.05 per minute)
            call.cost = call.duration_minutes * 0.05
            
            # Update user usage
            if user:
                user.total_minutes_used += call.duration_minutes
                user.monthly_minutes_used += call.duration_minutes
            
            # Sync to CRM if enabled
            if agent.crm_enabled and agent.crm_webhook_url:
                try:
                    crm_service = CRMIntegrationService(agent)
                    await crm_service.sync_call(call)
                except Exception as e:
                    logger.error(f"CRM sync failed: {e}")
            
            db.commit()
        
        manager.disconnect(session_id)
        
        try:
            await websocket.close()
        except:
            pass


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Check if a session is active"""
    is_active = session_id in manager.active_connections
    return {
        "session_id": session_id,
        "is_active": is_active
    }

