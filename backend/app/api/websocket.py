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
logger.setLevel(logging.INFO)
logger.propagate = True


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
    
    logger.info(f"🔌 New WebSocket connection for agent_id={agent_id}, session_id={session_id}")
    print(f"🔌 New WebSocket connection for agent_id={agent_id}, session_id={session_id}")
    try:
        # Verify authentication (API key or JWT token)
        logger.info(f"🔐 Checking authentication...")
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
        logger.info(f"✅ Authentication successful, accepting WebSocket connection")
        print(f"✅ Authentication successful, accepting WebSocket connection")
        await manager.connect(session_id, websocket)
        
        # Create call record (without started_at yet)
        logger.info(f"📞 Creating call record...")
        call = Call(
            user_id=user.id if user else agent.user_id,
            agent_id=agent_id,
            session_id=session_id,
            status=CallStatus.INITIATED
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        logger.info(f"✅ Call record created: ID={call.id}")
        
        # Initialize agent service
        logger.info(f"🤖 Initializing agent service...")
        agent_service = FrenchVoiceAgentService(agent, call)
        manager.agent_services[session_id] = agent_service
        
        # Start agent session
        logger.info(f"🚀 Starting Gemini session...")
        success = await agent_service.start_session()
        if not success:
            logger.error(f"❌ Failed to start agent session")
            await websocket.send_json({
                "type": "error",
                "message": "Failed to start agent session"
            })
            await websocket.close()
            return
        
        # Set started_at AFTER session is successfully established
        call.started_at = datetime.utcnow()
        call.status = CallStatus.IN_PROGRESS
        db.commit()
        db.refresh(call)
        logger.info(f"✅ Session started successfully, call status: IN_PROGRESS")
        
        # Send session started message
        logger.info(f"📤 Sending session_started message to client")
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "agent_name": agent.name,
            "language": agent.language
        })
        logger.info(f"🎧 Starting audio processing tasks...")
        
        # Create tasks for bidirectional communication
        # Flag to signal all tasks to stop
        stop_flag = asyncio.Event()
        
        async def receive_audio_from_client():
            """Receive audio from client and send to agent"""
            try:
                while not stop_flag.is_set():
                    data = await websocket.receive()
                    
                    if "bytes" in data:
                        # Audio data
                        audio_data = data["bytes"]
                        await agent_service.send_audio(audio_data)
                    
                    elif "text" in data:
                        # Control messages
                        message = json.loads(data["text"])
                        
                        if message.get("type") == "end_session":
                            # Get ended_at from frontend if provided
                            ended_at_str = message.get("ended_at")
                            if ended_at_str:
                                try:
                                    from datetime import datetime as dt
                                    call.ended_at = dt.fromisoformat(ended_at_str.replace('Z', '+00:00'))
                                except Exception as e:
                                    logger.error(f"Error parsing ended_at: {e}")
                                    call.ended_at = datetime.utcnow()
                            else:
                                call.ended_at = datetime.utcnow()
                            
                            # Save ended_at immediately
                            try:
                                db.commit()
                            except Exception as e:
                                logger.error(f"Error saving ended_at: {e}")
                            
                            stop_flag.set()
                            break
                        elif message.get("type") == "interrupt":
                            # Handle interruption
                            pass
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {session_id}")
                stop_flag.set()
            except Exception as e:
                logger.error(f"Error receiving from client: {e}", exc_info=True)
                stop_flag.set()
        
        async def send_audio_to_client():
            """Receive audio from agent and send to client"""
            try:
                async for audio_data in agent_service.receive_audio():
                    if stop_flag.is_set():
                        break
                    await manager.send_audio(session_id, audio_data)
            except Exception as e:
                logger.error(f"Error sending to client: {e}", exc_info=True)
        
        async def send_realtime_input():
            """Send queued audio to agent"""
            try:
                # This is a long-running task, so we need to monitor stop_flag
                # The agent_service.send_realtime_input() is a blocking call
                # We'll wrap it in a task and cancel it when stop_flag is set
                task = asyncio.create_task(agent_service.send_realtime_input())
                
                # Monitor stop_flag while task runs
                while not task.done() and not stop_flag.is_set():
                    await asyncio.sleep(0.1)
                print(f"stop_flag.is_set(): {stop_flag.is_set()}, task.done(): {task.done()}")
                if stop_flag.is_set() and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                elif task.done():
                    await task  # Re-raise any exception
            except asyncio.CancelledError:
                logger.info("Realtime input cancelled")
            except Exception as e:
                logger.error(f"Error in realtime input: {e}", exc_info=True)
        
        # Run all tasks concurrently (compatible with Python 3.10+)
        try:
            await asyncio.gather(
                receive_audio_from_client(),
                send_audio_to_client(),
                send_realtime_input(),
                return_exceptions=True
            )
        except Exception as e:
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
        except Exception:
            pass
    
    finally:
        # Cleanup - ensure call end is recorded even if there are errors
        logger.info(f"🧹 Starting cleanup for session: {session_id}")
        print(f"🧹 Starting cleanup for session: {session_id}")
        
        # Update status immediately when connection closes (before full cleanup)
        call_id = None
        if call:
            call_id = call.id
            # Quick status update in the original session
            try:
                if call.status != CallStatus.COMPLETED and call.status != CallStatus.SUMMARIZING:
                    call.status = CallStatus.SUMMARIZING
                    if not call.ended_at:
                        call.ended_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"⚡ Quick status update: Call {call_id} → SUMMARIZING")
            except Exception as e:
                logger.error(f"Error in quick status update: {e}")
        
        if agent_service:
            try:
                await agent_service.end_session()
                logger.info(f"✅ Agent session ended for: {session_id}")
            except Exception as e:
                logger.error(f"Error ending agent session: {e}")
        
        # Handle full call cleanup - use a fresh DB session to ensure it's valid
        if call_id:
            logger.info(f"📞 Starting full call cleanup for call ID: {call_id}")
        else:
            logger.warning(f"⚠️ No call ID available for cleanup (session: {session_id})")
        
        if call_id:
            # Create a new database session for cleanup to ensure it's valid
            from app.models.database import SessionLocal
            cleanup_db = SessionLocal()
            
            try:
                # Get a fresh call object from DB
                fresh_call = cleanup_db.query(Call).filter(Call.id == call_id).first()
                
                if not fresh_call:
                    logger.warning(f"⚠️ Call {call_id} not found in database during cleanup")
                
                if fresh_call:
                    # Set end time and status FIRST - commit immediately so it's visible
                    status_changed = False
                    if not fresh_call.ended_at:
                        fresh_call.ended_at = datetime.utcnow()
                        status_changed = True
                    
                    # Update status to SUMMARIZING first (will change to COMPLETED after summary)
                    current_status = fresh_call.status.value if hasattr(fresh_call.status, 'value') else str(fresh_call.status)
                    logger.info(f"🔍 Call {fresh_call.id} current status: '{current_status}' (type: {type(fresh_call.status)})")
                    
                    # Always update to SUMMARIZING unless already completed or summarizing
                    if current_status not in ["completed", "summarizing"]:
                        fresh_call.status = CallStatus.SUMMARIZING
                        status_changed = True
                        logger.info(f"📞 Updating call {fresh_call.id} status from '{current_status}' to SUMMARIZING")
                    else:
                        logger.info(f"ℹ️ Call {fresh_call.id} already has status '{current_status}', skipping status update")
                    
                    # Commit status change immediately so it's visible in UI
                    if status_changed:
                        try:
                            cleanup_db.flush()  # Ensure changes are written to DB
                            cleanup_db.commit()
                            cleanup_db.refresh(fresh_call)
                            final_status = fresh_call.status.value if hasattr(fresh_call.status, 'value') else str(fresh_call.status)
                            logger.info(f"✅ Call {fresh_call.id} status updated to: {final_status} (committed to DB)")
                        except Exception as e:
                            logger.error(f"❌ Error committing status update: {e}", exc_info=True)
                            cleanup_db.rollback()
                    
                    # Ensure transcript is complete from messages if not already set
                    if not fresh_call.transcript:
                        messages = cleanup_db.query(CallMessage).filter(
                            CallMessage.call_id == fresh_call.id
                        ).order_by(CallMessage.timestamp).all()
                        
                        if messages:
                            transcript_lines = []
                            for msg in messages:
                                transcript_lines.append(f"{msg.role.upper()}: {msg.content}")
                            fresh_call.transcript = "\n\n".join(transcript_lines)
                            logger.info(f"Built transcript from {len(messages)} messages for call {fresh_call.id}")
                    
                    # Log transcript status
                    if fresh_call.transcript:
                        logger.info(f"Call {fresh_call.id} transcript saved: {len(fresh_call.transcript)} characters")
                    else:
                        logger.warning(f"Call {fresh_call.id} has no transcript")
                    
                    # Calculate duration
                    if not fresh_call.calculate_duration_and_cost():
                        logger.warning(f"Could not calculate duration for call {fresh_call.id}")
                    
                    # Update user usage
                    if user and fresh_call.duration_minutes > 0:
                        try:
                            fresh_user = cleanup_db.query(User).filter(User.id == user.id).first()
                            if fresh_user:
                                fresh_user.total_minutes_used += fresh_call.duration_minutes
                                fresh_user.monthly_minutes_used += fresh_call.duration_minutes
                        except Exception as e:
                            logger.error(f"Error updating user usage: {e}")
                    
                    # Sync to CRM if enabled
                    if agent and agent.crm_enabled and agent.crm_webhook_url:
                        try:
                            crm_service = CRMIntegrationService(agent)
                            await crm_service.sync_call(fresh_call)
                        except Exception as e:
                            logger.error(f"CRM sync failed: {e}")
                    
                    # Commit transcript and status changes first
                    cleanup_db.commit()
                    cleanup_db.refresh(fresh_call)
                    
                    # Auto-generate summary if transcript exists and no summary yet
                    summary_success = False
                    if fresh_call.transcript and len(fresh_call.transcript.strip()) > 50 and not fresh_call.summary:
                        try:
                            logger.info(f"🤖 Auto-generating summary for call {fresh_call.id} (transcript: {len(fresh_call.transcript)} chars)")
                            from app.services.agent_service import CallSummaryService
                            summary_service = CallSummaryService()
                            # Pass fresh call object to ensure it's attached to the session
                            result = await summary_service.generate_summary(fresh_call)
                            if result.get("error"):
                                logger.warning(f"Summary generation failed: {result.get('error')}")
                                summary_success = False
                            else:
                                # Ensure summary is saved
                                cleanup_db.commit()
                                cleanup_db.refresh(fresh_call)
                                summary_success = True
                                logger.info(f"✅ Auto-generated summary for call {fresh_call.id}: {fresh_call.summary[:100] if fresh_call.summary else 'None'}...")
                        except Exception as e:
                            logger.error(f"Error auto-generating summary: {e}", exc_info=True)
                            cleanup_db.rollback()
                            summary_success = False
                    elif not fresh_call.transcript or len(fresh_call.transcript.strip()) <= 50:
                        # No transcript or transcript too short
                        summary_success = False
                        logger.info(f"⚠️ No transcript available for call {fresh_call.id}, skipping summary")
                    
                    # Update status to COMPLETED and add summary tags
                    current_tags = fresh_call.action_tags or []
                    
                    if summary_success:
                        # Summary generated successfully
                        fresh_call.status = CallStatus.COMPLETED
                        if "Summarized" not in current_tags:
                            current_tags.append("Summarized")
                        if "No summarized" in current_tags:
                            current_tags.remove("No summarized")
                    else:
                        # Summary failed or no transcript
                        fresh_call.status = CallStatus.COMPLETED
                        if "No summarized" not in current_tags:
                            current_tags.append("No summarized")
                        if "Summarized" in current_tags:
                            current_tags.remove("Summarized")
                    
                    fresh_call.action_tags = current_tags
                    logger.info(f"📊 Call {fresh_call.id} status: {fresh_call.status.value}, tags: {fresh_call.action_tags}")
                    
                    # Final commit for status and tags
                    cleanup_db.commit()
                    cleanup_db.refresh(fresh_call)
                else:
                    logger.error(f"Could not find call {call_id} for cleanup")
                    
            except Exception as e:
                logger.error(f"Error during call cleanup: {e}", exc_info=True)
                cleanup_db.rollback()
            finally:
                cleanup_db.close()
        
        # Disconnect and close
        manager.disconnect(session_id)
        
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Check if a session is active"""
    is_active = session_id in manager.active_connections
    return {
        "session_id": session_id,
        "is_active": is_active
    }

