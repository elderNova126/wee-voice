"""
SIP Call Handler Service
Bridges SIP calls with Gemini voice agent service

This version loads SIP credentials from phone_numbers table in the database,
registering each phone number's SIP client separately.
"""
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber, PhoneNumberStatus
from app.models.database import SessionLocal
from app.services.agent_service import FrenchVoiceAgentService
from app.services.sip_client_service import SIPClientService, SIPCallSession
from app.api.websocket import call_monitor_manager, auto_summarize_call

logger = logging.getLogger(__name__)


class SIPCallHandler:
    """
    Handles SIP call lifecycle and bridges audio with Gemini agent.
    Loads SIP credentials from database phone_numbers table.
    """
    
    def __init__(self):
        # Map: phone_number -> SIPClientService
        self.sip_clients: Dict[str, SIPClientService] = {}
        # Map: phone_number -> PhoneNumber record
        self.phone_records: Dict[str, PhoneNumber] = {}
        # Map: call_id -> SIPCallBridge
        self.active_handlers: Dict[str, 'SIPCallBridge'] = {}
        logger.info("SIP Call Handler initialized (database mode)")
    
    async def start(self) -> bool:
        """Start the SIP call handler - loads phone numbers from database"""
        print("[SIP Handler] start() called")
        logger.info("=" * 50)
        logger.info("SIP Call Handler starting...")
        logger.info("=" * 50)
        try:
            db = SessionLocal()
            try:
                # Load all phone numbers with SIP configuration
                print("[SIP Handler] Loading phone numbers from DB...")
                logger.info("Loading phone numbers with SIP config from database...")
                phone_numbers = await self._load_phone_numbers_with_sip(db)
                print(f"[SIP Handler] Found {len(phone_numbers) if phone_numbers else 0} phone numbers")
                
                if not phone_numbers:
                    logger.warning("⚠️ No phone numbers with SIP configuration found in database")
                    return False
                
                logger.info(f"Found {len(phone_numbers)} phone number(s) with SIP configuration")
                
                # Register each phone number's SIP client
                success_count = 0
                for phone in phone_numbers:
                    if await self._register_phone_number(phone):
                        success_count += 1
                
                if success_count > 0:
                    logger.info(f"✅ SIP Call Handler started: {success_count}/{len(phone_numbers)} phone numbers registered")
                    return True
                else:
                    logger.error("❌ No phone numbers successfully registered")
                    return False
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error starting SIP call handler: {e}", exc_info=True)
            return False
    
    async def _load_phone_numbers_with_sip(self, db: Session) -> list:
        """Load all phone numbers that have SIP configuration from database"""
        try:
            # Query phone numbers with SIP config
            result = db.execute(text("""
                SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                       sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                       status, status_message, monthly_cost, per_minute_cost,
                       business_name, business_type, business_address,
                       created_at, updated_at, activated_at
                FROM phone_numbers
                WHERE sip_websocket_url IS NOT NULL 
                  AND sip_username IS NOT NULL 
                  AND sip_password IS NOT NULL
                  AND sip_domain IS NOT NULL
            """)).fetchall()
            
            phone_numbers = []
            for row in result:
                phone = PhoneNumber()
                phone.id = row[0]
                phone.user_id = row[1]
                phone.agent_id = row[2]
                phone.phone_number = row[3]
                phone.country_code = row[4]
                phone.number_type = row[5]
                phone.sip_websocket_url = row[6]
                phone.sip_transport = row[7]
                phone.sip_username = row[8]
                phone.sip_password = row[9]
                phone.sip_domain = row[10]
                phone.status = row[11]
                phone.status_message = row[12]
                phone.monthly_cost = row[13]
                phone.per_minute_cost = row[14]
                phone.business_name = row[15]
                phone.business_type = row[16]
                phone.business_address = row[17]
                phone.created_at = row[18]
                phone.updated_at = row[19]
                phone.activated_at = row[20]
                phone_numbers.append(phone)
            
            return phone_numbers
            
        except Exception as e:
            logger.error(f"Error loading phone numbers: {e}", exc_info=True)
            return []
    
    async def _register_phone_number(self, phone: PhoneNumber) -> bool:
        """Register a single phone number's SIP client"""
        try:
            logger.info(f"📞 Registering SIP for {phone.phone_number} ({phone.sip_username}@{phone.sip_domain})")
            logger.info(f"   WebSocket: {phone.sip_websocket_url}")
            
            # Validate WebSocket URL
            if not phone.sip_websocket_url:
                logger.error(f"   ❌ No WebSocket URL configured for {phone.phone_number}")
                return False
            
            # Log helpful info
            from urllib.parse import urlparse
            parsed = urlparse(phone.sip_websocket_url)
            if parsed.hostname in ['weevoice.weedoo.com', 'your-server.com']:
                logger.warning(f"   ⚠️ WebSocket URL uses placeholder hostname. Update to actual server address.")
                logger.warning(f"   💡 If Asterisk is on same server, use: ws://localhost:8089/ws")
            
            # Create SIP client for this phone number
            sip_client = SIPClientService(
                ws_url=phone.sip_websocket_url,
                username=phone.sip_username,
                password=phone.sip_password,
                domain=phone.sip_domain
            )
            
            # Set callbacks for inbound and outbound calls
            sip_client.on_incoming_call = lambda call: self.handle_incoming_call(call, phone)
            sip_client.on_call_answered = lambda call: self.handle_call_answered(call, phone)
            sip_client.on_call_ended = self.handle_call_ended
            sip_client.on_call_ringing = self.handle_call_ringing
            sip_client.on_call_failed = self.handle_call_failed
            
            # Connect and register
            success = await sip_client.connect()
            
            if success:
                # Store the client and phone record
                self.sip_clients[phone.phone_number] = sip_client
                self.phone_records[phone.phone_number] = phone
                logger.info(f"✅ Registered: {phone.phone_number} ({phone.sip_username})")
                return True
            else:
                logger.error(f"❌ Failed to register: {phone.phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering phone {phone.phone_number}: {e}", exc_info=True)
            return False
    
    async def stop(self):
        """Stop the SIP call handler"""
        logger.info("Stopping SIP Call Handler...")
        
        # End all active calls
        for handler in list(self.active_handlers.values()):
            try:
                await handler.stop()
            except Exception as e:
                logger.error(f"Error stopping call handler: {e}")
        
        # Disconnect all SIP clients
        for phone_number, sip_client in self.sip_clients.items():
            try:
                await sip_client.disconnect()
                logger.info(f"Disconnected SIP client for {phone_number}")
            except Exception as e:
                logger.error(f"Error disconnecting {phone_number}: {e}")
        
        self.sip_clients.clear()
        self.phone_records.clear()
        self.active_handlers.clear()
        
        logger.info("SIP Call Handler stopped")
    
    async def reload_phone_numbers(self):
        """Reload phone numbers from database (for dynamic updates)"""
        logger.info("Reloading phone numbers from database...")
        
        db = SessionLocal()
        try:
            phone_numbers = await self._load_phone_numbers_with_sip(db)
            
            # Find new phone numbers to register
            current_numbers = set(self.sip_clients.keys())
            db_numbers = {p.phone_number for p in phone_numbers}
            
            # Register new phone numbers
            new_numbers = db_numbers - current_numbers
            for phone in phone_numbers:
                if phone.phone_number in new_numbers:
                    await self._register_phone_number(phone)
            
            # Optionally disconnect removed phone numbers
            removed_numbers = current_numbers - db_numbers
            for number in removed_numbers:
                if number in self.sip_clients:
                    await self.sip_clients[number].disconnect()
                    del self.sip_clients[number]
                    del self.phone_records[number]
                    logger.info(f"Removed SIP client for {number}")
            
            logger.info(f"Phone numbers reloaded: {len(self.sip_clients)} active")
            
        finally:
            db.close()
    
    async def handle_incoming_call(self, sip_call: SIPCallSession, phone: PhoneNumber):
        """Handle incoming SIP call"""
        try:
            logger.info(f"📞 Incoming call on {phone.phone_number}: {sip_call.from_number} -> {sip_call.to_number}")
            
            db = SessionLocal()
            try:
                # Get the agent for this phone number
                agent = None
                if phone.agent_id:
                    agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
                
                if not agent:
                    logger.error(f"No agent assigned to phone number {phone.phone_number}")
                    # Hangup call
                    sip_client = self.sip_clients.get(phone.phone_number)
                    if sip_client:
                        await sip_client.hangup_call(sip_call.call_id)
                    return
                
                # Create call record
                call = Call(
                    user_id=phone.user_id,
                    agent_id=agent.id,
                    caller_phone=sip_call.from_number,
                    caller_name=sip_call.from_number,
                    direction="inbound",
                    status=CallStatus.INITIATED,
                    zadarma_call_id=sip_call.call_id,
                    session_id=f"sip_{sip_call.call_id}",
                    started_at=datetime.utcnow()
                )
                db.add(call)
                db.commit()
                db.refresh(call)
                
                logger.info(f"✅ Created call record: ID={call.id} for agent {agent.id} ({agent.name})")
                
                # Get the SIP client for this phone number
                sip_client = self.sip_clients.get(phone.phone_number)
                
                # Create bridge between SIP and Gemini
                bridge = SIPCallBridge(sip_call, sip_client, agent, call, db, phone)
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
    
    async def handle_call_answered(self, sip_call: SIPCallSession, phone: PhoneNumber):
        """Handle call answered event (for both inbound and outbound)"""
        logger.info(f"✅ SIP call answered: {sip_call.call_id} (direction: {sip_call.direction})")
        
        if sip_call.call_id in self.active_handlers:
            # Call bridge already exists (inbound calls)
            bridge = self.active_handlers[sip_call.call_id]
            await bridge.on_answered()
        elif sip_call.direction == 'outbound':
            # Outbound call answered - need to create bridge and start Gemini
            await self._setup_outbound_call_bridge(sip_call, phone)
    
    async def handle_call_ringing(self, sip_call: SIPCallSession):
        """Handle outbound call ringing event"""
        logger.info(f"🔔 Outbound call ringing: {sip_call.call_id} -> {sip_call.to_number}")
        
        # Update call status if we have a pending call record
        if sip_call.call_id in self.active_handlers:
            bridge = self.active_handlers[sip_call.call_id]
            try:
                bridge.call.status = CallStatus.INITIATED
                bridge.db.commit()
            except Exception as e:
                logger.error(f"Error updating call status to ringing: {e}")
    
    async def handle_call_failed(self, sip_call: SIPCallSession, reason: str):
        """Handle outbound call failed event"""
        logger.warning(f"❌ Outbound call failed: {sip_call.call_id} - {reason}")
        
        if sip_call.call_id in self.active_handlers:
            bridge = self.active_handlers[sip_call.call_id]
            try:
                # Update call record
                bridge.call.status = CallStatus.FAILED
                bridge.call.ended_at = datetime.utcnow()
                bridge.db.commit()
                
                # Broadcast update
                call_data = {
                    "id": bridge.call.id,
                    "status": "failed",
                    "reason": reason
                }
                await call_monitor_manager.broadcast_call_update(bridge.call.user_id, call_data)
                
            except Exception as e:
                logger.error(f"Error updating failed call: {e}")
            finally:
                del self.active_handlers[sip_call.call_id]
    
    async def handle_call_ended(self, sip_call: SIPCallSession):
        """Handle call ended event"""
        logger.info(f"📞 SIP call ended: {sip_call.call_id}")
        
        if sip_call.call_id in self.active_handlers:
            bridge = self.active_handlers[sip_call.call_id]
            await bridge.stop()
            del self.active_handlers[sip_call.call_id]
    
    async def make_outbound_call(
        self, 
        from_phone_number: str, 
        to_number: str, 
        agent_id: int,
        user_id: int,
        script_data: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Initiate an outbound call
        
        Args:
            from_phone_number: The phone number to call from (must be registered)
            to_number: The number to call
            agent_id: The AI agent to use for the call
            user_id: The user initiating the call
            script_data: Optional outbound script data (opening_message, main_content, etc.)
            
        Returns:
            dict with call info if successful, None if failed
        """
        try:
            logger.info(f"📤 Initiating outbound call: {from_phone_number} -> {to_number}")
            
            # Get SIP client for the from number
            sip_client = self.sip_clients.get(from_phone_number)
            phone_record = self.phone_records.get(from_phone_number)
            
            if not sip_client or not phone_record:
                logger.error(f"No SIP client registered for {from_phone_number}")
                return None
            
            if not sip_client.is_registered:
                logger.error(f"SIP client for {from_phone_number} is not registered")
                return None
            
            db = SessionLocal()
            try:
                # Get the agent
                agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
                if not agent:
                    logger.error(f"Agent {agent_id} not found")
                    return None
                
                # Initiate the SIP call
                sip_call = await sip_client.make_call(to_number, from_phone_number)
                if not sip_call:
                    logger.error("Failed to initiate SIP call")
                    return None
                
                # Create call record
                call = Call(
                    user_id=user_id,
                    agent_id=agent_id,
                    caller_phone=to_number,  # The person being called
                    caller_name=to_number,
                    direction="outbound",
                    status=CallStatus.INITIATED,
                    zadarma_call_id=sip_call.call_id,
                    session_id=f"sip_{sip_call.call_id}",
                    started_at=datetime.utcnow()
                )
                db.add(call)
                db.commit()
                db.refresh(call)
                
                logger.info(f"✅ Created outbound call record: ID={call.id}")
                
                # Create bridge (will start when call is answered)
                bridge = SIPCallBridge(sip_call, sip_client, agent, call, db, phone_record, script_data=script_data)
                bridge.is_outbound = True  # Mark as outbound
                self.active_handlers[sip_call.call_id] = bridge
                
                # Broadcast call creation
                try:
                    call_data = {
                        "id": call.id,
                        "status": call.status.value,
                        "direction": "outbound",
                        "agent_id": call.agent_id,
                        "to_number": to_number,
                        "from_number": from_phone_number,
                        "session_id": call.session_id,
                        "started_at": call.started_at.isoformat() if call.started_at else None
                    }
                    await call_monitor_manager.broadcast_call_update(user_id, call_data)
                except Exception as e:
                    logger.error(f"Error broadcasting call update: {e}")
                
                return {
                    "call_id": call.id,
                    "sip_call_id": sip_call.call_id,
                    "status": "calling",
                    "from_number": from_phone_number,
                    "to_number": to_number,
                    "agent_id": agent_id
                }
                
            except Exception as e:
                logger.error(f"Error creating outbound call: {e}", exc_info=True)
                db.close()
                return None
                
        except Exception as e:
            logger.error(f"Error making outbound call: {e}", exc_info=True)
            return None
    
    async def _setup_outbound_call_bridge(self, sip_call: SIPCallSession, phone: PhoneNumber):
        """Set up bridge for an outbound call that was just answered"""
        try:
            if sip_call.call_id not in self.active_handlers:
                logger.error(f"No handler found for answered outbound call {sip_call.call_id}")
                return
            
            bridge = self.active_handlers[sip_call.call_id]
            
            # Update call status
            bridge.call.status = CallStatus.IN_PROGRESS
            bridge.db.commit()
            
            # Start the Gemini bridge
            await bridge.start()
            
            logger.info(f"✅ Outbound call bridge started: {sip_call.call_id}")
            
            # Broadcast update
            try:
                call_data = {
                    "id": bridge.call.id,
                    "status": "in_progress",
                    "direction": "outbound"
                }
                await call_monitor_manager.broadcast_call_update(bridge.call.user_id, call_data)
            except Exception as e:
                logger.error(f"Error broadcasting call update: {e}")
                
        except Exception as e:
            logger.error(f"Error setting up outbound call bridge: {e}", exc_info=True)
    
    def get_registered_phone_numbers(self) -> list:
        """Get list of registered phone numbers that can make outbound calls"""
        return [
            {
                "phone_number": phone,
                "is_registered": self.sip_clients[phone].is_registered,
                "agent_id": self.phone_records[phone].agent_id
            }
            for phone in self.sip_clients.keys()
        ]


class SIPCallBridge:
    """
    Bridges a single SIP call with Gemini voice agent.
    Handles bidirectional audio streaming.
    """
    
    def __init__(self, sip_call: SIPCallSession, sip_client: SIPClientService, 
                 agent: VoiceAgent, call: Call, db: Session, 
                 phone_record: PhoneNumber, script_data: Optional[dict] = None):
        self.sip_call = sip_call
        self.sip_client = sip_client
        self.agent = agent
        self.call = call
        self.db = db
        self.phone_record = phone_record
        self.script_data = script_data  # Outbound script for the call
        
        self.agent_service: Optional[FrenchVoiceAgentService] = None
        self.is_running = False
        self.tasks = []
        
        logger.info(f"Created SIP bridge for call {call.id}")
        logger.info(f"  Phone: {phone_record.phone_number}")
        logger.info(f"  Agent: {agent.name} (ID: {agent.id})")
        if script_data:
            logger.info(f"  Script: {script_data.get('name', 'unnamed')}")
    
    async def start(self):
        """Start the audio bridge"""
        try:
            # Initialize Gemini agent service with optional script
            self.agent_service = FrenchVoiceAgentService(
                self.agent, 
                self.call,
                script_data=self.script_data
            )
            
            # Start Gemini session
            success = await self.agent_service.start_session()
            if not success:
                logger.error(f"Failed to start Gemini session for call {self.call.id}")
                return
            
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
            # Receive audio from Gemini
            async for audio_data in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                
                # Send to SIP client (24kHz PCM16 -> will be converted to 8kHz)
                if self.sip_client:
                    await self.sip_client.send_audio(self.sip_call.call_id, audio_data)
                
        except asyncio.CancelledError:
            logger.debug("_forward_gemini_to_sip cancelled")
        except Exception as e:
            logger.error(f"Error forwarding Gemini to SIP: {e}", exc_info=True)


# Global SIP call handler instance
sip_call_handler = SIPCallHandler()
