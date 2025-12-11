"""
SIP Call Handler Service
Bridges SIP calls with Gemini voice agent service
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.services.agent_service import FrenchVoiceAgentService
from app.services.sip_client_service import sip_client, SIPCallSession, create_sip_client_from_phone_number
from app.api.websocket import call_monitor_manager, auto_summarize_call
from sqlalchemy import text

logger = logging.getLogger(__name__)


class SIPCallHandler:
    """
    Handles SIP call lifecycle and bridges audio with Gemini agent
    """
    
    def __init__(self):
        self.active_handlers: dict[str, 'SIPCallBridge'] = {}
        logger.info("SIP Call Handler initialized")
    
    async def start(self):
        """Start the SIP call handler"""
        # Register callbacks with SIP client
        sip_client.on_incoming_call = self.handle_incoming_call
        sip_client.on_call_answered = self.handle_call_answered
        sip_client.on_call_ended = self.handle_call_ended
        
        # Connect to SIP server
        success = await sip_client.connect()
        if success:
            logger.info("✅ SIP Call Handler started and connected to SIP server")
        else:
            logger.error("❌ Failed to connect to SIP server")
        
        return success
    
    async def stop(self):
        """Stop the SIP call handler"""
        # End all active calls
        for handler in list(self.active_handlers.values()):
            await handler.stop()
        
        # Disconnect from SIP server
        await sip_client.disconnect()
        logger.info("SIP Call Handler stopped")
    
    async def handle_incoming_call(self, sip_call: SIPCallSession):
        """Handle incoming SIP call"""
        try:
            logger.info(f"📞 Handling incoming SIP call: {sip_call.from_number} -> {sip_call.to_number}")
            
            # Find agent and phone config for the called number
            db = SessionLocal()
            try:
                agent, phone_record = await self._get_agent_and_phone_for_number(db, sip_call.to_number)
                
                if not agent:
                    logger.error(f"No agent found for number {sip_call.to_number}")
                    # Hangup call
                    await sip_client.hangup_call(sip_call.call_id)
                    return
                
                # Log SIP configuration status
                if phone_record and phone_record.sip_websocket_url:
                    logger.info(f"✅ Using phone-specific SIP config: {phone_record.sip_websocket_url}")
                else:
                    logger.info("⚠️ Using default SIP configuration")
                
                # Create call record
                call = Call(
                    user_id=agent.user_id,
                    agent_id=agent.id,
                    caller_phone=sip_call.from_number,
                    caller_name=sip_call.from_number,
                    direction="inbound",
                    status=CallStatus.INITIATED,
                    zadarma_call_id=sip_call.call_id,  # Use SIP call_id
                    session_id=f"sip_{sip_call.call_id}",
                    started_at=datetime.utcnow()
                )
                db.add(call)
                db.commit()
                db.refresh(call)
                
                logger.info(f"✅ Created call record: ID={call.id} for agent {agent.id}")
                
                # Create bridge between SIP and Gemini, passing phone record for SIP config
                bridge = SIPCallBridge(sip_call, agent, call, db, phone_record)
                self.active_handlers[sip_call.call_id] = bridge
                
                # Start the bridge
                await bridge.start()
                
                # Broadcast call creation
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
                    logger.error(f"Error broadcasting call update: {e}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling incoming SIP call: {e}", exc_info=True)
    
    async def handle_call_answered(self, sip_call: SIPCallSession):
        """Handle call answered event"""
        logger.info(f"✅ SIP call answered: {sip_call.call_id}")
        
        if sip_call.call_id in self.active_handlers:
            bridge = self.active_handlers[sip_call.call_id]
            await bridge.on_answered()
    
    async def handle_call_ended(self, sip_call: SIPCallSession):
        """Handle call ended event"""
        logger.info(f"📞 SIP call ended: {sip_call.call_id}")
        
        if sip_call.call_id in self.active_handlers:
            bridge = self.active_handlers[sip_call.call_id]
            await bridge.stop()
            del self.active_handlers[sip_call.call_id]
    
    async def _get_agent_and_phone_for_number(self, db: Session, phone_number: str) -> tuple[Optional[VoiceAgent], Optional[PhoneNumber]]:
        """Get agent and phone record for a phone number"""
        # Normalize phone number
        normalized = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Try to find phone number record with SIP config using raw SQL
        try:
            result = db.execute(text("""
                SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                       sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                       status, status_message, monthly_cost, per_minute_cost,
                       business_name, business_type, business_address,
                       created_at, updated_at, activated_at
                FROM phone_numbers
                WHERE phone_number = :phone_number
                LIMIT 1
            """), {"phone_number": normalized}).first()
            
            if result and result[2]:  # agent_id exists
                phone_record = PhoneNumber()
                phone_record.id = result[0]
                phone_record.user_id = result[1]
                phone_record.agent_id = result[2]
                phone_record.phone_number = result[3]
                phone_record.country_code = result[4]
                phone_record.number_type = result[5]
                phone_record.sip_websocket_url = result[6]
                phone_record.sip_transport = result[7]
                phone_record.sip_username = result[8]
                phone_record.sip_password = result[9]
                phone_record.sip_domain = result[10]
                phone_record.status = result[11]
                phone_record.status_message = result[12]
                phone_record.monthly_cost = result[13]
                phone_record.per_minute_cost = result[14]
                phone_record.business_name = result[15]
                phone_record.business_type = result[16]
                phone_record.business_address = result[17]
                phone_record.created_at = result[18]
                phone_record.updated_at = result[19]
                phone_record.activated_at = result[20]
                
                agent = db.query(VoiceAgent).filter(
                    VoiceAgent.id == phone_record.agent_id
                ).first()
                
                if agent:
                    return agent, phone_record
        except Exception as e:
            logger.error(f"Error getting agent for phone number: {e}")
        
        logger.warning(f"No agent found for phone number: {phone_number}")
        return None, None


class SIPCallBridge:
    """
    Bridges a single SIP call with Gemini voice agent
    Handles bidirectional audio streaming
    """
    
    def __init__(self, sip_call: SIPCallSession, agent: VoiceAgent, call: Call, db: Session, 
                 phone_record: Optional[PhoneNumber] = None):
        self.sip_call = sip_call
        self.agent = agent
        self.call = call
        self.db = db
        self.phone_record = phone_record
        
        self.agent_service: Optional[FrenchVoiceAgentService] = None
        self.is_running = False
        self.tasks = []
        self.custom_sip_client = None
        
        # Log SIP configuration
        if phone_record and phone_record.sip_websocket_url:
            logger.info(f"Created SIP bridge for call {call.id} with custom SIP config")
            logger.info(f"  WebSocket: {phone_record.sip_websocket_url}")
            logger.info(f"  Username: {phone_record.sip_username}")
            logger.info(f"  Domain: {phone_record.sip_domain}")
        else:
            logger.info(f"Created SIP bridge for call {call.id} (using default SIP config)")
    
    async def start(self):
        """Start the audio bridge"""
        try:
            # Initialize Gemini agent service
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            
            # Start Gemini session
            success = await self.agent_service.start_session()
            if not success:
                logger.error(f"Failed to start Gemini session for call {self.call.id}")
                return
            
            # Create custom SIP client if phone has specific config
            if self.phone_record and self.phone_record.sip_websocket_url:
                logger.info(f"🔌 Creating custom SIP client for call {self.call.id}")
                self.custom_sip_client = create_sip_client_from_phone_number(self.phone_record)
                
                # Connect to phone-specific SIP server
                connected = await self.custom_sip_client.connect()
                if connected:
                    logger.info(f"✅ Custom SIP client connected: {self.phone_record.sip_websocket_url}")
                else:
                    logger.error(f"❌ Failed to connect custom SIP client")
            
            # Update call status
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            self.is_running = True
            
            # Start bidirectional audio forwarding
            self.tasks = [
                asyncio.create_task(self._forward_sip_to_gemini()),
                asyncio.create_task(self._forward_gemini_to_sip())
            ]
            
            logger.info(f"✅ SIP bridge started for call {self.call.id}")
            
        except Exception as e:
            logger.error(f"Error starting SIP bridge: {e}", exc_info=True)
    
    async def on_answered(self):
        """Called when call is answered"""
        logger.info(f"Call {self.call.id} answered")
    
    async def stop(self):
        """Stop the audio bridge"""
        try:
            self.is_running = False
            
            # Cancel all tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            self.tasks = []
            
            # End Gemini session
            if self.agent_service:
                try:
                    await self.agent_service.end_session()
                except Exception as e:
                    logger.error(f"Error ending Gemini session: {e}")
            
            # Disconnect custom SIP client if used
            if self.custom_sip_client:
                try:
                    await self.custom_sip_client.disconnect()
                    logger.info(f"Disconnected custom SIP client for call {self.call.id}")
                except Exception as e:
                    logger.error(f"Error disconnecting custom SIP client: {e}")
            
            # Update call record
            try:
                # Refresh call from DB
                self.db.refresh(self.call)
                
                if not self.call.ended_at:
                    self.call.ended_at = datetime.utcnow()
                
                # Calculate duration
                self.call.calculate_duration_and_cost()
                
                # Set to summarizing
                self.call.status = CallStatus.SUMMARIZING
                self.db.commit()
                
                # Start background summarization
                asyncio.create_task(auto_summarize_call(self.call.id))
                
                logger.info(f"✅ SIP bridge stopped for call {self.call.id}")
                
            except Exception as e:
                logger.error(f"Error updating call record: {e}")
                
        except Exception as e:
            logger.error(f"Error stopping SIP bridge: {e}", exc_info=True)
    
    async def _forward_sip_to_gemini(self):
        """Forward audio from SIP caller to Gemini"""
        try:
            while self.is_running:
                # Get audio from SIP call's inbound queue (16kHz PCM16)
                audio_data = await self.sip_call.inbound_audio_queue.get()
                
                # Send to Gemini agent
                if self.agent_service:
                    await self.agent_service.send_audio(audio_data)
                
        except asyncio.CancelledError:
            logger.debug("_forward_sip_to_gemini cancelled")
        except Exception as e:
            logger.error(f"Error forwarding SIP to Gemini: {e}", exc_info=True)
    
    async def _forward_gemini_to_sip(self):
        """Forward audio from Gemini to SIP caller"""
        try:
            # Use custom SIP client if available, otherwise use global
            active_sip_client = self.custom_sip_client or sip_client
            
            # Receive audio from Gemini
            async for audio_data in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                
                # Send to SIP client (24kHz PCM16 -> will be converted to 8kHz)
                await active_sip_client.send_audio(self.sip_call.call_id, audio_data)
                
        except asyncio.CancelledError:
            logger.debug("_forward_gemini_to_sip cancelled")
        except Exception as e:
            logger.error(f"Error forwarding Gemini to SIP: {e}", exc_info=True)


# Global SIP call handler instance
sip_call_handler = SIPCallHandler()



