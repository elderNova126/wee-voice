import asyncio
import json
import logging
import base64
import audioop
from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.models import get_db, User, VoiceAgent, Call, CallStatus, CallMessage
from app.core.security import verify_api_key, decode_token
from app.services.agent_service import FrenchVoiceAgentService, CallSummaryService
from app.services.crm_service import CRMIntegrationService

# Note: Using asyncio.gather for Python 3.10+ compatibility instead of TaskGroup (3.11+)

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True

GEMINI_INPUT_SAMPLE_RATE = 16000   # Audio rate expected by Gemini Live input
GEMINI_OUTPUT_SAMPLE_RATE = 24000  # Audio rate produced by Gemini Live output


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


async def auto_summarize_call(call_id: int):
    """Background task to automatically summarize a call"""
    from app.models.database import SessionLocal
    
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            logger.error(f"Call {call_id} not found for summarization")
            return
        
        # Build transcript from messages if transcript doesn't exist
        if not call.transcript:
            messages = db.query(CallMessage).filter(
                CallMessage.call_id == call_id
            ).order_by(CallMessage.timestamp).all()
            
            if messages:
                # Build transcript from messages
                transcript_lines = []
                for msg in messages:
                    transcript_lines.append(f"{msg.role.upper()}: {msg.content}")
                call.transcript = "\n\n".join(transcript_lines)
                logger.info(f"Built transcript from {len(messages)} messages for call {call_id}")
            else:
                logger.warning(f"Call {call_id} has no transcript or messages, marking as not_summarized")
                call.summarization_status = "not_summarized"
                call.status = CallStatus.COMPLETED
                db.commit()
                
                # Broadcast update to monitoring connections
                try:
                    call_data = {
                        "id": call.id,
                        "status": call.status.value,
                        "summarization_status": call.summarization_status
                    }
                    await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
                except Exception as e:
                    logger.error(f"Error broadcasting call update: {e}")
                return
        
        # Generate summary
        try:
            summary_service = CallSummaryService()
            result = await summary_service.generate_summary(call)
            
            if result.get("error"):
                logger.error(f"Summarization failed for call {call_id}: {result.get('error')}")
                call.summarization_status = "not_summarized"
            else:
                logger.info(f"Call {call_id} summarized successfully")
                call.summarization_status = "summarized"
            
            # Update status to completed
            call.status = CallStatus.COMPLETED
            db.commit()
            logger.info(f"Call {call_id} summarization completed, status updated to completed")
            
            # Broadcast update to monitoring connections
            try:
                call_data = {
                    "id": call.id,
                    "status": call.status.value,
                    "summarization_status": call.summarization_status,
                    "summary": call.summary,
                    "sentiment": call.sentiment,
                    "action_items": call.action_items,
                    "action_tags": call.action_tags
                }
                await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
            except Exception as e:
                logger.error(f"Error broadcasting call update: {e}")
        except Exception as e:
            logger.error(f"Error during summarization for call {call_id}: {e}", exc_info=True)
            call.summarization_status = "not_summarized"
            call.status = CallStatus.COMPLETED
            db.commit()
            
            # Broadcast update to monitoring connections even on error
            try:
                call_data = {
                    "id": call.id,
                    "status": call.status.value,
                    "summarization_status": call.summarization_status
                }
                await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
            except Exception as e:
                logger.error(f"Error broadcasting call update: {e}")
    except Exception as e:
        logger.error(f"Error in auto_summarize_call for call {call_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


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
        
        # Broadcast new call to monitoring connections
        try:
            call_data = {
                "id": call.id,
                "status": call.status.value,
                "agent_id": call.agent_id,
                "session_id": call.session_id,
                "created_at": call.created_at.isoformat() if call.created_at else None
            }
            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        except Exception as e:
            logger.error(f"Error broadcasting new call: {e}")
        
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
        
        # Broadcast call start to monitoring connections
        try:
            call_data = {
                "id": call.id,
                "status": call.status.value,
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "agent_id": call.agent_id
            }
            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        except Exception as e:
            logger.error(f"Error broadcasting call start: {e}")
        
        # Send session started message
        logger.info(f"📤 Sending session_started message to client")
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "call_id": call.id,
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
                    try:
                        data = await websocket.receive()
                    except RuntimeError as e:
                        # Handle "Cannot call receive once a disconnect message has been received"
                        if "disconnect" in str(e).lower() or "receive" in str(e).lower():
                            logger.info(f"WebSocket disconnected (RuntimeError): {session_id}")
                            break
                        raise
                    
                    # Check for disconnect message
                    if "type" in data and data["type"] == "websocket.disconnect":
                        logger.info(f"Received disconnect message: {session_id}")
                        break
                    
                    if "bytes" in data:
                        # Regular WebSocket: binary audio data
                        audio_data = data["bytes"]
                        await agent_service.send_audio(audio_data)
                    
                    elif "text" in data:
                        # Control messages (for regular WebSocket clients)
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
                            
                            # Update status to summarizing immediately
                            if call.status in [CallStatus.IN_PROGRESS, CallStatus.INITIATED]:
                                call.status = CallStatus.SUMMARIZING
                                logger.info(f"Call {call.id} status set to summarizing (end_session message)")
                            
                            # Save changes immediately
                            try:
                                db.commit()
                                db.refresh(call)
                                
                                # Broadcast status update immediately
                                try:
                                    call_data = {
                                        "id": call.id,
                                        "status": call.status.value,
                                        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                                        "summarization_status": call.summarization_status
                                    }
                                    await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
                                    logger.info(f"Broadcasted call status update: {call.status.value}")
                                except Exception as e:
                                    logger.error(f"Error broadcasting call update: {e}")
                            except Exception as e:
                                logger.error(f"Error saving ended_at: {e}")
                            
                            stop_flag.set()
                            break
                        elif message.get("type") == "interrupt":
                            # Handle interruption
                            pass
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected (WebSocketDisconnect): {session_id}")
                # Update call status immediately on disconnect
                try:
                    if call and call.status in [CallStatus.IN_PROGRESS, CallStatus.INITIATED]:
                        call.status = CallStatus.SUMMARIZING
                        if not call.ended_at:
                            call.ended_at = datetime.utcnow()
                        db.commit()
                        db.refresh(call)
                        
                        # Broadcast status update immediately
                        try:
                            call_data = {
                                "id": call.id,
                                "status": call.status.value,
                                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                                "summarization_status": call.summarization_status
                            }
                            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
                            logger.info(f"Broadcasted call status update on disconnect: {call.status.value}")
                        except Exception as e:
                            logger.error(f"Error broadcasting call update on disconnect: {e}")
                except Exception as e:
                    logger.error(f"Error updating call status on disconnect: {e}")
                stop_flag.set()
            except RuntimeError as e:
                # Handle "Cannot call receive once a disconnect message has been received"
                if "disconnect" in str(e).lower() or "receive" in str(e).lower():
                    logger.info(f"WebSocket disconnected (RuntimeError in outer handler): {session_id}")
                    stop_flag.set()
                else:
                    logger.error(f"RuntimeError receiving from client: {e}", exc_info=True)
                    stop_flag.set()
            except Exception as e:
                logger.error(f"Error receiving from client: {e}", exc_info=True)
                stop_flag.set()
        
        async def send_audio_to_client():
            """Receive audio from agent and send to client"""
            try:
                async for audio_data in agent_service.receive_audio():
                    if stop_flag.is_set():
                        logger.info(f"Stop flag set in send_audio_to_client, breaking loop")
                        break
                    try:
                        await manager.send_audio(session_id, audio_data)
                    except Exception as send_error:
                        logger.error(f"Error sending audio to client: {send_error}")
                        if stop_flag.is_set():
                            break
                        # Continue even on error
            except asyncio.CancelledError:
                logger.info("send_audio_to_client cancelled")
                raise
            except Exception as e:
                logger.error(f"Error sending to client: {e}", exc_info=True)
                # Set stop flag on error so other tasks can exit
                if not stop_flag.is_set():
                    stop_flag.set()
        
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
        tasks = []
        try:
            logger.info(f"Starting concurrent tasks for session {session_id}")
            # Create tasks
            tasks = [
                asyncio.create_task(receive_audio_from_client(), name="receive_audio"),
                asyncio.create_task(send_audio_to_client(), name="send_audio"),
                asyncio.create_task(send_realtime_input(), name="realtime_input")
            ]
            
            logger.info(f"All tasks created for session {session_id}, waiting for completion...")
            
            # Wait for any task to complete or raise exception
            # Use FIRST_COMPLETED so we can handle stop_flag and cancel others
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=None
            )
            
            logger.info(f"First task completed for session {session_id}, done: {len(done)}, pending: {len(pending)}")
            
            # When any task completes, check if stop_flag is set
            # If so, cancel all remaining tasks
            if stop_flag.is_set():
                logger.info(f"Stop flag set, cancelling all pending tasks for session {session_id}")
                for task in pending:
                    task.cancel()
                # Wait for cancelled tasks to finish
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            
            # Check for exceptions in completed tasks
            for task in done:
                if task.exception():
                    logger.error(f"Task {task.get_name()} raised exception: {task.exception()}")
                    # If a task failed and stop_flag isn't set, set it to stop other tasks
                    if not stop_flag.is_set():
                        logger.info(f"Task {task.get_name()} failed, setting stop flag")
                        stop_flag.set()
                        for t in pending:
                            t.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
            
            # Always ensure all tasks are done before proceeding
            # If stop_flag is set, cancel any remaining tasks
            if stop_flag.is_set():
                logger.info(f"Stop flag is set, ensuring all tasks complete for session {session_id}")
                remaining = [t for t in tasks if not t.done()]
                if remaining:
                    logger.info(f"Cancelling {len(remaining)} remaining tasks")
                    # Cancel remaining tasks
                    for t in remaining:
                        t.cancel()
                    # Wait for them to finish (with timeout)
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*remaining, return_exceptions=True),
                            timeout=3.0
                        )
                        logger.info(f"All remaining tasks completed for session {session_id}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Some tasks didn't complete within timeout for session {session_id}")
            else:
                # If stop_flag is not set but a task completed, wait for others
                remaining = [t for t in tasks if not t.done()]
                if remaining:
                    logger.info(f"Waiting for {len(remaining)} remaining tasks to complete for session {session_id}")
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*remaining, return_exceptions=True),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Remaining tasks didn't complete, setting stop flag")
                        stop_flag.set()
                        for t in remaining:
                            if not t.done():
                                t.cancel()
                        await asyncio.gather(*remaining, return_exceptions=True)
            
            logger.info(f"All tasks finished for session {session_id}, proceeding to finally block")
                        
        except Exception as e:
            logger.error(f"Error in concurrent tasks: {e}", exc_info=True)
            # Ensure stop_flag is set and cancel all tasks
            stop_flag.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
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
        print("================================================================")
        # Cleanup - ensure call end is recorded even if there are errors
        if agent_service:
            try:
                await agent_service.end_session()
            except Exception as e:
                logger.error(f"Error ending agent session: {e}")
        
        # Handle call cleanup - use a fresh DB session to ensure it's valid
        if call:
            call_id = call.id  # Store ID before any potential detachment
            
            # Create a new database session for cleanup to ensure it's valid
            from app.models.database import SessionLocal
            cleanup_db = SessionLocal()
            
            try:
                # Get a fresh call object from DB
                fresh_call = cleanup_db.query(Call).filter(Call.id == call_id).first()
                
                if fresh_call:
                    # Set end time if not already set
                    if not fresh_call.ended_at:
                        fresh_call.ended_at = datetime.utcnow()
                    
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
                    
                    # Set status to summarizing immediately when call ends
                    if fresh_call.status in [CallStatus.IN_PROGRESS, CallStatus.INITIATED]:
                        fresh_call.status = CallStatus.SUMMARIZING
                        logger.info(f"Call {fresh_call.id} status set to summarizing")
                    
                    # Commit status change first
                    cleanup_db.commit()
                    
                    # Broadcast status update to monitoring connections
                    try:
                        call_data = {
                            "id": fresh_call.id,
                            "status": fresh_call.status.value,
                            "summarization_status": fresh_call.summarization_status
                        }
                        await call_monitor_manager.broadcast_call_update(fresh_call.user_id, call_data)
                    except Exception as e:
                        logger.error(f"Error broadcasting call update: {e}")
                    
                    # Start background summarization task
                    asyncio.create_task(auto_summarize_call(fresh_call.id))
                    logger.info(f"Started background summarization task for call {fresh_call.id}")
                    
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
                    
                    # Commit all changes
                    cleanup_db.commit()
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


class CallMonitorManager:
    """Manage WebSocket connections for call status monitoring"""
    
    def __init__(self):
        self.monitor_connections: dict[int, list[WebSocket]] = {}  # user_id -> list of websockets
    
    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.monitor_connections:
            self.monitor_connections[user_id] = []
        self.monitor_connections[user_id].append(websocket)
        logger.info(f"Call monitor connected for user {user_id}")
    
    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.monitor_connections:
            try:
                self.monitor_connections[user_id].remove(websocket)
                if not self.monitor_connections[user_id]:
                    del self.monitor_connections[user_id]
            except ValueError:
                pass
        logger.info(f"Call monitor disconnected for user {user_id}")
    
    async def broadcast_call_update(self, user_id: int, call_data: dict):
        """Broadcast call status update to all monitoring connections for a user"""
        if user_id in self.monitor_connections:
            disconnected = []
            for ws in self.monitor_connections[user_id]:
                try:
                    await ws.send_json({
                        "type": "call_update",
                        "call": call_data
                    })
                except Exception as e:
                    logger.error(f"Error broadcasting to monitor: {e}")
                    disconnected.append(ws)
            
            # Remove disconnected websockets
            for ws in disconnected:
                self.disconnect(user_id, ws)


call_monitor_manager = CallMonitorManager()


@router.websocket("/calls/monitor")
async def monitor_calls(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time call status monitoring"""
    try:
        # Authenticate user
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return
        
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return
        
        # Connect to monitor
        await call_monitor_manager.connect(user_id, websocket)
        
        try:
            # Keep connection alive and handle incoming messages
            while True:
                try:
                    # Wait for any message (ping/pong or close)
                    message = await websocket.receive_text()
                    # Echo back or handle ping
                    if message == "ping":
                        await websocket.send_text("pong")
                except Exception:
                    break
        finally:
            call_monitor_manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"Error in call monitor: {e}", exc_info=True)
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


@router.websocket("/text/{agent_id}")
async def text_chat_websocket(
    websocket: WebSocket,
    agent_id: int,
    api_key: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for text-only chat conversations"""
    session_id = str(uuid.uuid4())
    user: Optional[User] = None
    call: Optional[Call] = None
    chat_service: Optional['TextChatService'] = None
    
    logger.info(f"💬 New text chat WebSocket connection for agent_id={agent_id}, session_id={session_id}")
    
    try:
        # Verify authentication (API key or JWT token)
        if api_key:
            user = await verify_api_key(api_key, db)
            if not user:
                await websocket.close(code=4001, reason="Invalid API key")
                return
            logger.info(f"User authenticated via API key: {user.email}")
        elif token:
            payload = decode_token(token)
            if not payload:
                await websocket.close(code=4001, reason="Invalid token")
                return
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=4001, reason="Invalid token")
                return
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
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
        
        # Check if agent supports text mode
        if agent.interaction_mode not in ["text", "both"]:
            logger.warning(f"Agent {agent_id} does not support text mode")
            await websocket.close(code=4003, reason="Agent does not support text mode")
            return
        
        # Check permissions
        if not agent.is_public and (not user or agent.user_id != user.id):
            logger.warning(f"Access denied for agent {agent_id}")
            await websocket.close(code=4003, reason="Access denied")
            return
        
        # Accept connection
        await websocket.accept()
        logger.info(f"✅ Text chat WebSocket connection accepted")
        
        # Create call record
        call = Call(
            user_id=user.id if user else agent.user_id,
            agent_id=agent_id,
            session_id=session_id,
            status=CallStatus.IN_PROGRESS,
            started_at=datetime.utcnow()
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        logger.info(f"✅ Call record created: ID={call.id}")
        
        # Broadcast new call to monitoring connections
        try:
            call_data = {
                "id": call.id,
                "status": call.status.value,
                "agent_id": call.agent_id,
                "session_id": call.session_id,
                "started_at": call.started_at.isoformat() if call.started_at else None
            }
            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        except Exception as e:
            logger.error(f"Error broadcasting new call: {e}")
        
        # Initialize text chat service
        from app.services.text_chat_service import TextChatService
        try:
            chat_service = TextChatService(agent, call)
        except Exception as e:
            logger.error(f"Failed to initialize TextChatService: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to initialize chat service: {str(e)}"
            })
            await websocket.close()
            return
        
        # Send session started message
        try:
            await websocket.send_json({
                "type": "session_started",
                "session_id": session_id,
                "call_id": call.id,
                "agent_name": agent.name,
                "language": agent.language,
                "mode": "text"
            })
            logger.info(f"✅ Session started message sent")
        except Exception as e:
            logger.error(f"Failed to send session_started: {e}")
            return
        
        # Send greeting if configured
        if agent.greeting:
            try:
                greeting_response = {
                    "type": "message",
                    "role": "assistant",
                    "content": agent.greeting,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_json(greeting_response)
                
                # Save greeting to DB
                await chat_service.save_message_to_db("assistant", agent.greeting, db)
            except Exception as e:
                logger.error(f"Failed to send greeting: {e}")
        
        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                
                if data.get("type") == "message":
                    user_message = data.get("content", "").strip()
                    
                    if not user_message:
                        continue
                    
                    logger.info(f"📩 Received user message: {user_message[:100]}")
                    
                    # Save user message to DB
                    await chat_service.save_message_to_db("user", user_message, db)
                    
                    # Stream AI response in real-time
                    full_response = ""
                    needs_callback = False
                    callback_priority = None
                    
                    try:
                        async for chunk_data in chat_service.stream_message(user_message):
                            chunk_text = chunk_data.get("chunk", "")
                            is_done = chunk_data.get("done", False)
                            
                            if chunk_text:
                                full_response += chunk_text
                                
                                # Send chunk to client
                                await websocket.send_json({
                                    "type": "message_chunk",
                                    "role": "assistant",
                                    "content": chunk_text,
                                    "done": False,
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                            
                            # Update callback info if detected
                            if chunk_data.get("needs_callback"):
                                needs_callback = True
                                callback_priority = chunk_data.get("callback_priority")
                            
                            # Send final message when done
                            if is_done:
                                await websocket.send_json({
                                    "type": "message",
                                    "role": "assistant",
                                    "content": full_response,
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "needs_callback": needs_callback,
                                    "callback_priority": callback_priority,
                                    "done": True
                                })
                                
                                # Save assistant message to DB
                                await chat_service.save_message_to_db("assistant", full_response, db)
                                
                                logger.info(f"📤 Streamed AI response complete: {full_response[:100]}")
                                break
                    
                    except Exception as e:
                        logger.error(f"Error streaming response: {e}", exc_info=True)
                        # Fallback to non-streaming if streaming fails
                        try:
                            response = await chat_service.send_message(user_message)
                            await websocket.send_json({
                                "type": "message",
                                "role": "assistant",
                                "content": response["text"],
                                "timestamp": datetime.utcnow().isoformat(),
                                "needs_callback": response.get("needs_callback", False),
                                "callback_priority": response.get("callback_priority")
                            })
                            await chat_service.save_message_to_db("assistant", response["text"], db)
                        except Exception as fallback_error:
                            logger.error(f"Fallback also failed: {fallback_error}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "Failed to get response. Please try again."
                            })
                
                elif data.get("type") == "end_session":
                    logger.info(f"End session requested for {session_id}")
                    break
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {session_id}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format"
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": "An error occurred processing your message"
                })
    
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
        # Cleanup - update call record
        if call:
            from app.models.database import SessionLocal
            cleanup_db = SessionLocal()
            
            try:
                fresh_call = cleanup_db.query(Call).filter(Call.id == call.id).first()
                
                if fresh_call:
                    # Set end time
                    if not fresh_call.ended_at:
                        fresh_call.ended_at = datetime.utcnow()
                    
                    # Build transcript from conversation history
                    if chat_service:
                        history = chat_service.get_conversation_history()
                        transcript_lines = []
                        for msg in history:
                            role = msg["role"].upper()
                            content = msg["content"]
                            transcript_lines.append(f"{role}: {content}")
                        fresh_call.transcript = "\n\n".join(transcript_lines)
                    
                    # Calculate duration
                    fresh_call.calculate_duration_and_cost()
                    
                    # Set status to summarizing
                    if fresh_call.status == CallStatus.IN_PROGRESS:
                        fresh_call.status = CallStatus.SUMMARIZING
                    
                    cleanup_db.commit()
                    
                    # Broadcast status update
                    try:
                        call_data = {
                            "id": fresh_call.id,
                            "status": fresh_call.status.value,
                            "ended_at": fresh_call.ended_at.isoformat() if fresh_call.ended_at else None
                        }
                        await call_monitor_manager.broadcast_call_update(fresh_call.user_id, call_data)
                    except Exception as e:
                        logger.error(f"Error broadcasting call update: {e}")
                    
                    # Start background summarization
                    asyncio.create_task(auto_summarize_call(fresh_call.id))
                    
            except Exception as e:
                logger.error(f"Error during call cleanup: {e}", exc_info=True)
                cleanup_db.rollback()
            finally:
                cleanup_db.close()
        
        try:
            await websocket.close()
        except Exception:
            pass
        
        logger.info(f"💬 Text chat session ended: {session_id}")