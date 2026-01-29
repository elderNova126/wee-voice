"""
OpenAI Realtime API Service for Voice Conversations

This service provides real-time voice conversations using OpenAI's Realtime API.
It supports bidirectional audio streaming via WebSocket.

Key features:
- Real-time voice conversations with low latency
- g711_ulaw format (native 8kHz telephony - no resampling!)
- Function calling support
- Input/output transcription via Whisper
- Server-side VAD (Voice Activity Detection)

Audio format:
- g711_ulaw: 8-bit μ-law encoded at 8kHz (telephone standard)
- EAGI converts: PCM16 <-> μ-law (simple encoding, no sample rate change)

Supported voices (Jan 2026):
- alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
"""

import asyncio
import base64
import json
import logging
from typing import Dict, Any, AsyncGenerator, Optional, List
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.models import Call, CallStatus, VoiceAgent
from app.services.call_followup_service import update_call_follow_up_data
from app.prompts import load_prompt

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# OpenAI Realtime API endpoint
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"

# OpenAI Realtime voices (updated Jan 2026)
# Supported: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
OPENAI_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"]

# Audio configuration - G.711 μ-law @ 8kHz (OpenAI native support!)
# Reference: sip-to-ai project uses audio/pcmu for ZERO resampling
# Flow: Asterisk 8kHz PCM16 → μ-law 8kHz → OpenAI → μ-law 8kHz → PCM16 8kHz
# NO RESAMPLING = NO CHOPPY AUDIO!
AUDIO_FORMAT = "g711_ulaw"     # G.711 μ-law @ 8kHz (telephony native)
INPUT_SAMPLE_RATE = 8000       # 8kHz input (same as Asterisk)
OUTPUT_SAMPLE_RATE = 8000      # 8kHz output (same as Asterisk)

# Use Python's audioop for proven μ-law conversion
import audioop


class OpenAIRealtimeService:
    """
    Service for handling voice conversations using OpenAI Realtime API.
    
    This provides the same interface as FrenchVoiceAgentService but uses
    OpenAI's Realtime API instead of Google Gemini.
    """
    
    def __init__(self, agent: VoiceAgent, call: Call, skip_greeting_trigger: bool = False,
                 script_data: Optional[Dict[str, Any]] = None, model: str = "gpt-4o-realtime-preview"):
        self.agent = agent
        self.call = call
        self.skip_greeting_trigger = skip_greeting_trigger
        self.script_data = script_data
        self.model = model  # e.g., "gpt-4o-realtime-preview"
        
        # Validate API key
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Please check your .env file.")
        
        logger.info(f"Initializing OpenAIRealtimeService with model: {self.model}")
        
        # WebSocket connection
        self.ws = None
        self._running = False
        
        # Audio queues (same interface as FrenchVoiceAgentService)
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue(maxsize=100)
        
        # Transcript buffers
        self._agent_transcript_buffer: List[str] = []
        self._user_transcript_buffer: List[str] = []
        self.conversation_buffer = []
        
        # Build configuration
        self.config = self._build_config()
    
    def _get_voice_name(self) -> str:
        """Select OpenAI voice based on agent configuration"""
        voice_gender = getattr(self.agent, 'voice_gender', None)
        voice_id = getattr(self.agent, 'voice_id', None)
        
        # If voice_id is a valid OpenAI voice, use it
        if voice_id and voice_id.lower() in [v.lower() for v in OPENAI_VOICES]:
            return voice_id.lower()
        
        # Map gender to voice (using new OpenAI voices)
        if voice_gender == "female":
            return "shimmer"  # Female voice (clear, warm)
        elif voice_gender == "male":
            return "ash"  # Male voice (deep, resonant)
        elif voice_gender == "neutral":
            return "alloy"  # Neutral voice
        
        # Default based on language
        if self.agent.language.startswith('fr'):
            return "coral"  # Coral handles multiple languages well
        else:
            return "alloy"  # Default English voice
    
    def _build_config(self) -> Dict[str, Any]:
        """Build configuration for OpenAI Realtime API session"""
        
        # Determine language
        is_french = self.agent.language.startswith('fr')
        lang_suffix = 'fr' if is_french else 'en'
        
        # Load prompt templates
        conversation_style = load_prompt(f'conversation_style_{lang_suffix}.txt')
        rag_instruction = load_prompt(f'rag_instructions_{lang_suffix}.txt') if self.agent.rag_enabled else ""
        callback_instruction = load_prompt(f'escalation_{lang_suffix}.txt')
        identity_enforcement = load_prompt('identity_rules.txt')
        context_rules = load_prompt('conversation_context_rules.txt')
        
        # Get manager contact info
        manager_contact = getattr(self.agent, 'manager_contact', None)
        if not manager_contact:
            manager_contact = 'email: contact@company.com or phone: +1234567890'
        
        # Variable substitution
        conversation_style = conversation_style.replace("{agent_name}", self.agent.name)
        callback_note = callback_instruction.replace("{manager_contact}", manager_contact)
        
        # Build greeting instruction
        greeting_instruction = ""
        safe_greeting = ""
        if self.agent.greeting:
            safe_greeting = self.agent.greeting.replace('"', '\\"')
        
        if safe_greeting:
            if self.skip_greeting_trigger:
                greeting_instruction = f"""
GREETING ALREADY COMPLETED:
- The greeting "{safe_greeting}" has ALREADY been played to the caller
- Do NOT repeat the greeting or introduce yourself again
- Wait for the user to speak and respond naturally
"""
            else:
                greeting_instruction = f"""
GREETING PROTOCOL:
- Say this greeting immediately when the session starts: "{safe_greeting}"
- Use natural, friendly tone
- Then continue conversation normally
"""
        
        # Select voice
        voice_name = self._get_voice_name()
        
        # Language and voice quality instruction - CRITICAL for consistency
        language_name = "French" if is_french else "English"
        if is_french:
            voice_instruction = f"""
=== LANGUAGE REQUIREMENT (MANDATORY) ===
YOU MUST SPEAK ONLY IN FRENCH. This is non-negotiable.
- ALWAYS respond in French, regardless of what language the user speaks
- If the user speaks English, respond in French anyway
- Never switch to English under any circumstances
- Use standard French pronunciation

=== VOICE QUALITY ===
- Speed: Moderate pace - NEVER rush
- Clarity: Articulate every syllable clearly
- Maintain consistent volume
"""
        else:
            voice_instruction = f"""
=== LANGUAGE REQUIREMENT (MANDATORY) ===
YOU MUST SPEAK ONLY IN ENGLISH. This is non-negotiable.
- ALWAYS respond in English, regardless of what language the user speaks
- Never switch to another language under any circumstances
- Use clear, standard pronunciation

=== VOICE QUALITY ===
- Speed: Moderate pace - NEVER rush  
- Clarity: Articulate every word clearly
- Maintain consistent volume
"""
        
        # Build system instruction
        system_instruction = f"""=== YOUR IDENTITY AND ROLE ===
{self.agent.system_prompt}

=== CONVERSATION STYLE GUIDELINES ===
{conversation_style}

=== CONVERSATION CONTEXT ===
{context_rules}

{rag_instruction}

{callback_note}

{identity_enforcement}

{voice_instruction}

{greeting_instruction}

=== CRITICAL REMINDER ===
- SPEAK ONLY IN {language_name.upper()} - this is mandatory
- Your identity and role are defined above
- Never use generic responses
- Respond naturally to what the user says
- NO EMOJIS in voice responses
- INTRODUCE YOURSELF ONLY ONCE
- MAINTAIN {language_name.upper()} throughout the entire conversation
"""
        
        logger.info(f"Voice selection for OpenAI agent {self.agent.id}:")
        logger.info(f"  - Voice: {voice_name}")
        logger.info(f"  - Language: {self.agent.language}")
        logger.info(f"  - Model: {self.model}")
        
        # Build session config for OpenAI Realtime API
        # Using G.711 μ-law @ 8kHz - NO RESAMPLING needed!
        # Reference: sip-to-ai project uses this for perfect audio quality
        config = {
            "modalities": ["text", "audio"],
            "instructions": system_instruction,
            "voice": voice_name,
            "input_audio_format": AUDIO_FORMAT,    # "g711_ulaw" @ 8kHz
            "output_audio_format": AUDIO_FORMAT,   # "g711_ulaw" @ 8kHz
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            },
            "temperature": float(self.agent.temperature) if hasattr(self.agent, 'temperature') else 0.7,
        }
        
        # Add tools if needed
        tools = self._build_tools()
        if tools:
            config["tools"] = tools
        
        return config
    
    def _build_tools(self) -> List[Dict[str, Any]]:
        """Build function tools for OpenAI Realtime API"""
        tools = []
        
        # Request callback tool - always available
        tools.append({
            "type": "function",
            "name": "request_callback",
            "description": "Request a human callback when the AI cannot fully resolve the issue",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why a callback is needed"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["urgent", "high", "normal", "low"],
                        "description": "Priority level"
                    },
                    "caller_name": {
                        "type": "string",
                        "description": "The caller's name"
                    },
                    "caller_phone": {
                        "type": "string",
                        "description": "The caller's phone number"
                    }
                },
                "required": ["reason"]
            }
        })
        
        return tools
    
    async def start_session(self) -> bool:
        """Start a new voice session with OpenAI Realtime API"""
        try:
            logger.info(f"Connecting to OpenAI Realtime API (model: {self.model})")
            
            # Build WebSocket URL with model parameter
            url = f"{OPENAI_REALTIME_URL}?model={self.model}"
            
            # Connect with authorization header
            headers = [
                ("Authorization", f"Bearer {settings.OPENAI_API_KEY}"),
                ("OpenAI-Beta", "realtime=v1")
            ]
            
            self.ws = await websockets.connect(url, additional_headers=headers)
            self._running = True
            
            logger.info("WebSocket connected to OpenAI Realtime API")
            
            # Send session configuration
            await self.ws.send(json.dumps({
                "type": "session.update",
                "session": self.config
            }))
            
            # Wait for session.created or session.updated confirmation
            while True:
                response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                msg = json.loads(response)
                msg_type = msg.get("type", "")
                
                logger.info(f"OpenAI Realtime: {msg_type}")
                
                if msg_type == "session.created":
                    logger.info("OpenAI Realtime session created")
                    break
                elif msg_type == "session.updated":
                    logger.info("OpenAI Realtime session configured")
                    break
                elif msg_type == "error":
                    error = msg.get("error", {})
                    logger.error(f"OpenAI Realtime error: {error}")
                    return False
            
            # Push initial silence to warm up VAD (from reference implementation)
            # 0.5 seconds @ 24kHz x 2 bytes = 24000 bytes
            silence = bytes(INPUT_SAMPLE_RATE)  # 0.5s silence at 24kHz
            await self.ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(silence).decode()
            }))
            logger.info(f"Sent initial silence buffer for VAD warm-up ({len(silence)} bytes @ {INPUT_SAMPLE_RATE}Hz)")
            
            # If greeting should be triggered, send it
            if self.agent.greeting and not self.skip_greeting_trigger:
                logger.info("Triggering greeting via response.create")
                await self.ws.send(json.dumps({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"],
                        "instructions": f"Say this greeting: {self.agent.greeting}"
                    }
                }))
            
            logger.info(f"Successfully started OpenAI Realtime session for call {self.call.session_id}")
            return True
            
        except asyncio.TimeoutError:
            logger.error("Timeout connecting to OpenAI Realtime API")
            return False
        except Exception as e:
            logger.error(f"Failed to start OpenAI Realtime session: {e}", exc_info=True)
            self.call.status = CallStatus.FAILED
            return False
    
    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm;rate=8000"):
        """Send audio chunk to OpenAI Realtime API"""
        try:
            await self.audio_out_queue.put({"data": audio_data, "mime_type": mime_type})
        except Exception as e:
            logger.error(f"Error queuing audio: {e}", exc_info=True)
    
    async def send_realtime_input(self):
        """Send queued audio to OpenAI Realtime API
        
        Input: Linear PCM16 at 8kHz (from Asterisk via audiosocket_handler)
        Output: G.711 μ-law at 8kHz (OpenAI native - NO RESAMPLING!)
        
        Reference: sip-to-ai project uses this approach for perfect quality
        """
        logger.info(f"[OPENAI-IN] Starting audio input loop (PCM16→μ-law @ 8kHz)")
        audio_sent_count = 0
        
        # Batch audio for 20ms frames @ 8kHz
        # PCM16: 8000 * 2 bytes * 0.02s = 320 bytes (20ms)
        MIN_BATCH_SIZE = 320  # 20ms of PCM16 @ 8kHz
        audio_buffer = b''
        
        try:
            while self._running and self.ws:
                try:
                    msg = await asyncio.wait_for(self.audio_out_queue.get(), timeout=0.025)
                    
                    if isinstance(msg, dict) and "data" in msg:
                        audio_buffer += msg["data"]
                    
                    # Send when we have enough audio (20ms)
                    if len(audio_buffer) >= MIN_BATCH_SIZE:
                        audio_sent_count += 1
                        
                        # Convert PCM16 → G.711 μ-law using audioop (proven, fast)
                        # 320 bytes PCM16 → 160 bytes μ-law
                        ulaw_data = audioop.lin2ulaw(audio_buffer, 2)
                        
                        # Encode as base64 for WebSocket
                        audio_b64 = base64.b64encode(ulaw_data).decode('utf-8')
                        
                        await self.ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64
                        }))
                        
                        if audio_sent_count <= 5 or audio_sent_count % 100 == 0:
                            logger.info(f"[OPENAI-IN] Sent #{audio_sent_count}: {len(audio_buffer)}→{len(ulaw_data)} bytes (PCM16→μ-law)")
                        
                        audio_buffer = b''
                        
                except asyncio.TimeoutError:
                    # Flush any remaining audio (160 bytes = 10ms for PCM16 @ 8kHz)
                    if len(audio_buffer) >= 160:
                        audio_sent_count += 1
                        ulaw_data = audioop.lin2ulaw(audio_buffer, 2)
                        audio_b64 = base64.b64encode(ulaw_data).decode('utf-8')
                        
                        try:
                            await self.ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": audio_b64
                            }))
                        except:
                            pass
                        audio_buffer = b''
                    continue
                    
                except asyncio.CancelledError:
                    logger.info(f"[OPENAI-IN] Cancelled after {audio_sent_count} packets")
                    break
                except ConnectionClosed:
                    logger.info("[OPENAI-IN] WebSocket closed")
                    break
                except Exception as e:
                    logger.error(f"[OPENAI-IN] Error: {e}")
                    await asyncio.sleep(0.1)
                    
        finally:
            logger.info(f"[OPENAI-IN] ENDED, {audio_sent_count} packets sent")
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """Receive audio responses from OpenAI Realtime API
        
        ZERO BUFFERING: Yield audio immediately as received.
        audiosocket_handler does all buffering and pacing.
        
        Input: G.711 μ-law at 8kHz (OpenAI native)
        Output: PCM16 at 8kHz (direct to audiosocket_handler)
        """
        logger.info(f"Starting audio reception (μ-law→PCM16 @ 8kHz, zero buffering)")
        chunk_count = 0
        
        try:
            while self._running and self.ws:
                try:
                    msg_str = await asyncio.wait_for(self.ws.recv(), timeout=0.05)
                    msg = json.loads(msg_str)
                    msg_type = msg.get("type", "")
                    
                    # Handle audio delta - YIELD IMMEDIATELY
                    if msg_type == "response.audio.delta":
                        audio_b64 = msg.get("delta", "")
                        if audio_b64:
                            ulaw_data = base64.b64decode(audio_b64)
                            pcm16_data = audioop.ulaw2lin(ulaw_data, 2)
                            chunk_count += 1
                            yield pcm16_data
                    
                    # Handle transcripts
                    elif msg_type == "response.audio_transcript.delta":
                        text = msg.get("delta", "")
                        if text:
                            self._agent_transcript_buffer.append(text)
                    
                    elif msg_type == "response.audio_transcript.done":
                        transcript = msg.get("transcript", "")
                        if transcript:
                            logger.info(f"💬 Agent said: {transcript[:100]}...")
                            await self._save_message("agent", transcript)
                            self.conversation_buffer.append({"role": "agent", "text": transcript})
                        self._agent_transcript_buffer.clear()
                    
                    elif msg_type == "conversation.item.input_audio_transcription.completed":
                        transcript = msg.get("transcript", "")
                        if transcript:
                            logger.info(f"🎤 User said: {transcript[:100]}...")
                            await self._save_message("user", transcript)
                            self.conversation_buffer.append({"role": "user", "text": transcript})
                    
                    elif msg_type == "response.done":
                        logger.debug("Response complete")
                    
                    elif msg_type == "response.function_call_arguments.done":
                        await self._handle_function_call(msg)
                    
                    elif msg_type == "error":
                        error = msg.get("error", {})
                        logger.error(f"OpenAI Realtime error: {error}")
                    
                except asyncio.TimeoutError:
                    continue
                except ConnectionClosed:
                    logger.info("OpenAI Realtime WebSocket closed")
                    break
                except asyncio.CancelledError:
                    logger.info("Audio reception cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error receiving from OpenAI: {e}")
                    await asyncio.sleep(0.01)
                    
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
        finally:
            logger.info(f"Audio reception ended ({response_count} audio chunks)")
    
    async def _handle_function_call(self, msg: Dict[str, Any]):
        """Handle function calls from OpenAI Realtime"""
        try:
            call_id = msg.get("call_id", "")
            name = msg.get("name", "")
            arguments = json.loads(msg.get("arguments", "{}"))
            
            logger.info(f"Function call: {name} with args: {arguments}")
            
            result = {}
            
            if name == "request_callback":
                # Create callback request
                from app.models.database import SessionLocal
                from app.models import CallbackRequest
                
                reason = arguments.get("reason", "Callback requested")
                priority = arguments.get("priority", "normal")
                
                db = SessionLocal()
                try:
                    callback_request = CallbackRequest(
                        call_id=self.call.id,
                        user_id=self.agent.user_id,
                        agent_id=self.agent.id,
                        reason=reason,
                        priority=priority,
                        caller_name=arguments.get("caller_name", self.call.caller_name),
                        caller_phone=arguments.get("caller_phone", self.call.caller_phone),
                        status="pending"
                    )
                    db.add(callback_request)
                    db.commit()
                    db.refresh(callback_request)
                    
                    result = {
                        "success": True,
                        "callback_id": callback_request.id,
                        "message": "Callback request created. A team member will follow up."
                    }
                    logger.info(f"✅ Callback created: {callback_request.id}")
                finally:
                    db.close()
            else:
                result = {"status": "success", "message": "Tool executed"}
            
            # Send function result back
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result)
                }
            }))
            
            # Trigger response after function call
            await self.ws.send(json.dumps({
                "type": "response.create"
            }))
            
        except Exception as e:
            logger.error(f"Error handling function call: {e}")
    
    async def _save_message(self, role: str, content: str):
        """Save message to database and build transcript"""
        from app.models.database import SessionLocal
        
        db = None
        try:
            db = SessionLocal()
            
            # Verify call exists
            from app.models.call import Call as CallModel
            call = db.query(CallModel).filter(CallModel.id == self.call.id).first()
            if not call:
                logger.error(f"Call {self.call.id} not found")
                return
            
            # Save message
            from app.models.call import CallMessage
            from datetime import datetime as dt
            message = CallMessage(
                call_id=self.call.id,
                role=role,
                content=content,
                timestamp=dt.utcnow()
            )
            db.add(message)
            
            # Update transcript
            if call.transcript:
                call.transcript += f"\n\n{role.upper()}: {content}"
            else:
                call.transcript = f"{role.upper()}: {content}"
            
            db.commit()
            logger.debug(f"Message saved: [{role}] {content[:50]}...")
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    async def end_session(self):
        """End the voice session"""
        try:
            self._running = False
            
            if self.ws:
                try:
                    await self.ws.close()
                except:
                    pass
                self.ws = None
            
            self.call.status = CallStatus.COMPLETED
            logger.info(f"Ended OpenAI Realtime session for call {self.call.session_id}")
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
    
    async def stop_session(self):
        """Stop the session and clean up resources"""
        logger.info(f"Stopping OpenAI Realtime session for call {self.call.session_id}")
        
        try:
            # Clear queues
            while not self.audio_in_queue.empty():
                try:
                    self.audio_in_queue.get_nowait()
                except:
                    break
            
            while not self.audio_out_queue.empty():
                try:
                    self.audio_out_queue.get_nowait()
                except:
                    break
            
            await self.end_session()
            
        except Exception as e:
            logger.error(f"Error stopping session: {e}")


def is_openai_model(model_name: str) -> bool:
    """Check if the model name is an OpenAI model"""
    if not model_name:
        return False
    return model_name.lower().startswith('gpt-') or model_name.lower().startswith('openai')


def get_voice_agent_service(agent: VoiceAgent, call: Call, llm_model: str = "gemini",
                            skip_greeting_trigger: bool = False, script_data: Optional[Dict[str, Any]] = None):
    """
    Factory function to get the appropriate voice agent service based on LLM model.
    
    Args:
        agent: The VoiceAgent configuration
        call: The Call record
        llm_model: The LLM model to use ('gemini', 'gpt-4o', 'gpt-4-turbo', etc.)
        skip_greeting_trigger: Whether to skip the greeting trigger
        script_data: Optional script data for outbound calls
    
    Returns:
        Either FrenchVoiceAgentService (Gemini) or OpenAIRealtimeService (OpenAI)
    """
    if is_openai_model(llm_model):
        # Map model names to OpenAI Realtime compatible models
        # OpenAI Realtime requires specific model names
        realtime_model = "gpt-4o-realtime-preview"
        
        # gpt-4o and variants use gpt-4o-realtime-preview
        if "gpt-4o" in llm_model.lower():
            realtime_model = "gpt-4o-realtime-preview"
        elif "gpt-4-turbo" in llm_model.lower():
            realtime_model = "gpt-4o-realtime-preview"  # Fallback to available model
        elif "gpt-4.1" in llm_model.lower():
            realtime_model = "gpt-4o-realtime-preview"  # Fallback
        elif "gpt-5" in llm_model.lower():
            realtime_model = "gpt-4o-realtime-preview"  # Fallback
        
        logger.info(f"🔵 Using OpenAI Realtime API (model: {realtime_model})")
        return OpenAIRealtimeService(
            agent=agent,
            call=call,
            skip_greeting_trigger=skip_greeting_trigger,
            script_data=script_data,
            model=realtime_model
        )
    else:
        # Default to Gemini
        from app.services.agent_service import FrenchVoiceAgentService
        logger.info(f"🟢 Using Gemini Live API")
        return FrenchVoiceAgentService(
            agent=agent,
            call=call,
            skip_greeting_trigger=skip_greeting_trigger,
            script_data=script_data
        )
