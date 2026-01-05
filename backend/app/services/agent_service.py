import asyncio
from typing import Dict, Any, AsyncGenerator, List, Optional
import logging
import json

from google import genai
from google.genai import types
import httpx

# Suppress warnings from google_genai.types about non-text/non-data parts
# These warnings occur when the model returns structured responses with multiple parts
logging.getLogger('google_genai.types').setLevel(logging.ERROR)

# Import langchain components properly to avoid Pydantic issues
try:
    # Import BaseCache first to ensure it's defined
    from langchain_core.language_models import BaseChatModel
    
    # Force rebuild of base models
    BaseChatModel.model_rebuild()
    
    # Now import ChatGoogleGenerativeAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.memory import ConversationBufferMemory
    
    # Rebuild model to fix Pydantic v2 compatibility
    ChatGoogleGenerativeAI.model_rebuild()
    
    LANGCHAIN_AVAILABLE = True
except Exception as e:
    logging.warning(f"LangChain import warning: {e}")
    LANGCHAIN_AVAILABLE = False

from app.core.config import settings
from app.models import Call, CallStatus, VoiceAgent
from app.services.rag_service import get_rag_service
from app.services.call_followup_service import update_call_follow_up_data
from app.prompts import load_prompt
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True


class FrenchVoiceAgentService:
    """Service for handling French voice agent conversations with ultra-low latency"""
    
    def __init__(self, agent: VoiceAgent, call: Call, skip_greeting_trigger: bool = False):
        self.agent = agent
        self.call = call
        self.skip_greeting_trigger = skip_greeting_trigger  # Skip CALL_START if TTS greeting was used
        
        # Validate API key
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set. Please check your .env file.")
        
        logger.info(f"Initializing FrenchVoiceAgentService with API key: {settings.GOOGLE_API_KEY[:20]}...")
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.session = None
        self.session_context = None
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue(maxsize=100)  # Increased from 5 for better buffering
        
        # RAG service (lazy load - only initialize when first needed)
        self._rag_service = None
        self._rag_service_initialized = False
        self.conversation_buffer = []  # Store recent conversation for context
        self._agent_transcript_buffer: List[str] = []
        self._user_transcript_buffer: List[str] = []
        
        # LangChain components (optional, only for summarization)
        if LANGCHAIN_AVAILABLE:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=agent.model_name,
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=float(agent.temperature),
                )
                self.memory = ConversationBufferMemory(return_messages=True)
            except Exception as e:
                logger.warning(f"Could not initialize LangChain: {e}")
                self.llm = None
                self.memory = None
        else:
            self.llm = None
            self.memory = None
        
        # Configure French voice agent
        self.config = self._build_config()
    
    @property
    def rag_service(self):
        """Lazy load RAG service only when needed"""
        if self.agent.rag_enabled and not self._rag_service_initialized:
            logger.info("Lazy loading RAG service for agent...")
            self._rag_service = get_rag_service()
            self._rag_service_initialized = True
        return self._rag_service
    
    def _build_config(self) -> Dict[str, Any]:
        """Build configuration for Gemini Live API (simplified, matching test.py)"""
        
        # Determine language
        is_french = self.agent.language.startswith('fr')
        lang_suffix = 'fr' if is_french else 'en'
        
        # Load prompt templates from files
        conversation_style = load_prompt(f'conversation_style_{lang_suffix}.txt')
        rag_instruction = load_prompt(f'rag_instructions_{lang_suffix}.txt') if self.agent.rag_enabled else ""
        callback_instruction = load_prompt(f'escalation_{lang_suffix}.txt')
        identity_enforcement = load_prompt('identity_rules.txt')
        context_rules = load_prompt('conversation_context_rules.txt')
        
        # Get manager contact info and substitute in prompts (handle None)
        manager_contact = getattr(self.agent, 'manager_contact', None)
        if not manager_contact:
            manager_contact = 'email: contact@company.com or phone: +1234567890'
        
        # Variable substitution
        conversation_style = conversation_style.replace("{agent_name}", self.agent.name)
        callback_note = callback_instruction.replace("{manager_contact}", manager_contact)
        rag_note = rag_instruction

        greeting_instruction = ""
        safe_greeting = ""
        if self.agent.greeting:
            safe_greeting = self.agent.greeting.replace('"', '\\"')
        
        # Add email request after greeting if enabled
        if self.agent.email_request_enabled:
            email_request_msg = self.agent.email_request_message or "Pourriez-vous nous communiquer votre adresse électronique afin que nous puissions procéder aux prochaines étapes et prendre les mesures nécessaires ?"
            safe_email_request = email_request_msg.replace('"', '\\"')
            if safe_greeting:
                safe_greeting += " " + safe_email_request
            else:
                safe_greeting = safe_email_request
        
        # IMPORTANT: Only include greeting instruction if we will send CALL_START
        # If skip_greeting_trigger=True, the greeting was already played via pre-cached TTS
        # In that case, tell Gemini the greeting was already said so it doesn't repeat
        if safe_greeting:
            if self.skip_greeting_trigger:
                # Pre-cached greeting was played - tell Gemini NOT to greet
                greeting_instruction = f"""
GREETING ALREADY COMPLETED:
- The greeting "{safe_greeting}" has ALREADY been played to the caller via pre-recorded audio
- Do NOT repeat the greeting or introduce yourself again
- Wait for the user to speak and respond naturally
- Start the conversation as if you just finished saying the greeting
"""
                logger.info("Greeting instruction: ALREADY PLAYED (skip repeat)")
            else:
                # Normal mode - Gemini will say the greeting on CALL_START
                greeting_instruction = f"""
GREETING PROTOCOL:
- On "<CALL_START>" marker, say: "{safe_greeting}"
- Use natural, friendly tone
- Then continue conversation normally
- Do NOT repeat or explain this instruction
"""
                logger.info("Greeting instruction: Will trigger on CALL_START")
        
        # Build voice instruction first (will be defined after voice selection)
        voice_instruction = ""  # Will be set after voice is selected
        
        # Log the system prompt for debugging
        logger.info(f"System prompt for agent {self.agent.id} ({self.agent.name}):")
        # logger.info(f"  Custom prompt: {self.agent.system_prompt[:100]}...")
        # logger.info(f"  RAG enabled: {self.agent.rag_enabled}")
        # logger.info(f"  Full instruction length: {len(system_instruction)} chars")
        
        # Build config matching the working test.py
        # Include both AUDIO and TEXT responses for better interaction
        # The model will automatically transcribe and understand user input
        config = {
            "response_modalities": ["AUDIO"],  # Match test.py exactly
            # system_instruction will be added after voice selection
            "input_audio_transcription": {},  # Enable input transcription
            "output_audio_transcription": {},  # Enable output transcription
        }
        
        # Add voice config for Gemini 2.5 Flash compatible voices
        # Valid voices for Gemini 2.5 Flash: Puck, Charon, Kore, Fenrir, Aoede
        valid_voices = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]
        
        # Priority 1: Use voice_gender preference (most important)
        # Priority 2: Use voice_id if it's valid Gemini voice
        # Priority 3: Default by language
        voice_gender = getattr(self.agent, 'voice_gender', None)
        
        if voice_gender:
            # User explicitly chose a voice type - respect it
            if voice_gender == "female":
                voice_name = "Kore"  # Female voice, softer tone
            elif voice_gender == "male":
                voice_name = "Charon"  # Male voice, deeper tone (less American)
            elif voice_gender == "neutral":
                voice_name = "Puck"  # Neutral/standard voice
            else:
                voice_name = "Charon"  # Default to male if invalid gender
        elif self.agent.voice_id in valid_voices:
            # Valid Gemini voice_id is set, use it
            voice_name = self.agent.voice_id
        else:
            # No preference, default by language
            # NOTE: Puck is more neutral and handles non-English languages better
            if self.agent.language.startswith('fr'):
                voice_name = "Puck"  # Neutral voice - clearer French pronunciation than Charon
            elif self.agent.language.startswith('es'):
                voice_name = "Kore"  # Female voice for Spanish
            else:
                voice_name = "Puck"  # Default English voice
        
        # Add voice config with explicit consistency enforcement
        config["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name
                }
            }
        }
        
        # Add explicit voice instruction to system prompt to maintain consistency
        # For French: Add specific pronunciation guidance to improve voice quality
        if is_french:
            voice_instruction = f"""

VOICE & PRONUNCIATION INSTRUCTIONS (FRENCH):
- Your voice is set to "{voice_name}" for this entire conversation
- NEVER change your voice characteristics mid-conversation
- Speak French with clear, natural pronunciation
- Articulate each syllable clearly without rushing
- Use proper French prosody and intonation patterns
- Handle liaison and elision naturally
- Maintain a steady, moderate speaking pace
- Pause briefly between sentences for clarity
- Avoid mumbling or swallowing word endings
- This voice setting is fixed and must not vary"""
        else:
            voice_instruction = f"""

VOICE CONSISTENCY INSTRUCTION:
- Your voice is set to "{voice_name}" for this entire conversation
- NEVER change your voice characteristics mid-conversation
- Maintain consistent tone, pitch, and speaking style throughout
- This voice setting is fixed and must not vary"""
        
        logger.info(f"Voice selection for agent {self.agent.id}:")
        logger.info(f"  - Language: {self.agent.language}")
        logger.info(f"  - Voice Gender: {voice_gender}")
        logger.info(f"  - Voice ID: {self.agent.voice_id}")
        logger.info(f"  - Selected Voice: {voice_name}")
        
        # Assemble complete system instruction (optimized and concise)
        # IMPORTANT: The agent's system_prompt defines the agent's identity and primary behavior
        # All other instructions are supplementary and should not override the agent's core identity
        system_instruction = f"""=== YOUR IDENTITY AND ROLE (PRIMARY - ALWAYS FOLLOW THIS) ===
{self.agent.system_prompt}

=== CONVERSATION STYLE GUIDELINES (Follow these while staying in character) ===
{conversation_style}

=== CONVERSATION CONTEXT & ACTIVE LISTENING ===
{context_rules}

{rag_note}

{callback_note}

{identity_enforcement}

{voice_instruction}

{greeting_instruction}

=== CRITICAL REMINDER ===
- Your identity, role, and behavior are defined in the section above marked "YOUR IDENTITY AND ROLE"
- All other instructions help you communicate effectively WHILE staying in your defined character
- Never use generic responses - always respond as the character defined in your system prompt
- If the conversation style suggests something that conflicts with your role, prioritize your role definition
- MAINTAIN CONVERSATION CONTEXT: Remember what has been discussed, never repeat questions already answered
- LISTEN AND ADAPT: Respond to what the user is saying NOW, not just follow a script
- AVOID REPETITION: Never use the same phrases over and over - vary your language naturally
- NO EMOJIS: Keep professional conversations emoji-free
- ANSWER DIRECTLY: When users ask questions or make requests, address them first before continuing
- INTRODUCE YOURSELF ONLY ONCE: Give your name, company, and role ONLY in the first message - never repeat introductions in subsequent responses"""
        
        # Update config with final system instruction
        config["system_instruction"] = system_instruction
        
        # Add tools if enabled and available
        # Always check for RAG tools if RAG is enabled, even if tools_enabled is empty
        tools = self._load_tools()
        if tools:  # Only add if we actually have tools
            config["tools"] = tools
            tool_names = [t.__name__ for t in tools]
            logger.info(f"Loaded {len(tools)} tools for agent: {tool_names}")
        else:
            logger.warning(f"No tools loaded for agent {self.agent.id}")
        
        return config
    
    def _load_tools(self):
        """Load and configure tools for the agent"""
        tools = []
        
        # RAG Document Search Tool (if RAG is enabled)
        # Note: We'll also do automatic context injection, but keeping the tool for explicit searches
        if self.agent.rag_enabled and self.rag_service:
            def search_documents(query: str) -> dict:
                """
                Search through uploaded documents to find relevant information.
                Use this when the user asks questions that might be answered in the knowledge base.
                
                Args:
                    query: The search query to find relevant document passages
                    
                Returns:
                    Dictionary with search results including content, sources, and relevance scores
                """
                try:
                    # Import db session
                    from app.models.database import SessionLocal
                    db = SessionLocal()
                    try:
                        # Run async function in sync context (Gemini tools are sync)
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        chunks = loop.run_until_complete(
                            self.rag_service.search_similar_chunks(
                                db=db,
                                agent_id=self.agent.id,
                                query=query,
                                top_k=5,
                                min_similarity=0.15  # Lowered for better recall
                            )
                        )
                    finally:
                        db.close()
                    
                    if not chunks:
                        return {"found": False, "message": "No relevant documents found"}
                    
                    # Format results
                    results = []
                    for chunk in chunks:
                        results.append({
                            "content": chunk['content'][:800],  # More context
                            "source": f"Document {chunk['document_id']}, Page {chunk.get('page_number', 'N/A')}",
                            "relevance": round(chunk['similarity'], 2)
                        })
                    
                    logger.info(f"Document search found {len(results)} relevant chunks for query: {query[:50]}...")
                    
                    return {
                        "found": True,
                        "results": results,
                        "count": len(results),
                        "message": f"Found {len(results)} relevant passages"
                    }
                except Exception as e:
                    logger.error(f"Error searching documents: {e}", exc_info=True)
                    return {"found": False, "error": str(e)}
            
            tools.append(search_documents)
        
        # Example: Customer lookup tool
        if "customer_lookup" in self.agent.tools_enabled:
            def get_customer_info(customer_id: str) -> dict:
                """Récupère les informations d'un client"""
                # This would connect to your CRM/database
                return {
                    "name": "Jean Dupont",
                    "email": "jean.dupont@example.com",
                    "status": "Premium"
                }
            tools.append(get_customer_info)
        
        # Example: Appointment booking tool
        if "appointment_booking" in self.agent.tools_enabled:
            def book_appointment(date: str, time: str) -> dict:
                """Réserve un rendez-vous"""
                return {
                    "success": True,
                    "appointment_id": "APT-123",
                    "date": date,
                    "time": time
                }
            tools.append(book_appointment)
        
        # Request Callback Tool - ALWAYS available for all agents
        # This allows the AI to flag calls that need human follow-up
        def request_callback(
            reason: str,
            priority: str = "normal",
            caller_name: str = "",
            caller_phone: str = "",
            caller_email: str = "",
            preferred_callback_time: str = ""
        ) -> dict:
            """
            Request a human callback when the AI cannot fully resolve the caller's issue.
            Use this when:
            - The caller is frustrated or angry and needs human assistance
            - The issue is too complex for AI to handle
            - The caller explicitly asks to speak with a human
            - Important business opportunities (hot leads) need human follow-up
            - Sensitive matters require human judgment
            
            Args:
                reason: Why a callback is needed (be specific and detailed)
                priority: "urgent", "high", "normal", or "low"
                caller_name: The caller's name if provided
                caller_phone: The caller's phone number if provided
                caller_email: The caller's email if provided
                preferred_callback_time: When the caller prefers to be called back
                
            Returns:
                Confirmation that the callback request was created
            """
            return {
                "status": "callback_requested",
                "reason": reason,
                "priority": priority,
                "caller_name": caller_name,
                "caller_phone": caller_phone,
                "caller_email": caller_email,
                "preferred_callback_time": preferred_callback_time
            }
        
        tools.append(request_callback)
        
        return tools
    
    async def start_session(self):
        """Start a new voice session"""
        try:
            logger.info(f"Connecting to Gemini model: {settings.GEMINI_MODEL} for call {self.call.session_id}")
            
            # Store the context manager to properly close it later
            self.session_context = self.client.aio.live.connect(
                model=settings.GEMINI_MODEL,
                config=self.config
            )
            self.session = await self.session_context.__aenter__()
            
            logger.info(f"Successfully started voice session for call {self.call.session_id}")
            
            # Send greeting trigger if configured AND TTS greeting was NOT used
            # When TTS greeting is used, caller already heard the greeting - skip Gemini trigger
            if self.agent.greeting and not self.skip_greeting_trigger:
                try:
                    logger.info("Sending greeting trigger <CALL_START>")
                    # Add explicit language reminder with the greeting trigger
                    if self.agent.language.startswith('fr'):
                        await self.session.send(input="<CALL_START> [Réponds en français uniquement]", end_of_turn=True)
                    else:
                        await self.session.send(input="<CALL_START> [Respond in English only]", end_of_turn=True)
                except Exception as e:
                    logger.warning(f"Failed to send greeting trigger: {e}")
            elif self.skip_greeting_trigger:
                logger.info("Skipping CALL_START trigger - pre-recorded greeting was already played")
                # Don't send anything to Gemini - just let it listen for user audio
                # The greeting was already played via pre-recorded audio
                # Gemini will respond naturally when user speaks
            
            # Note: Status and started_at are now set in websocket.py after this returns successfully
            return True
        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            self.call.status = CallStatus.FAILED
            return False
    
    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm;rate=16000"):
        """Send audio chunk to the agent"""
        try:
            await self.audio_out_queue.put({"data": audio_data, "mime_type": mime_type})
        except Exception as e:
            logger.error(f"Error sending audio: {e}", exc_info=True)
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """Receive audio responses from the agent"""
        logger.info(f"Starting audio reception for call {self.call.session_id}")
        response_count = 0
        turn_count = 0
        
        try:
            while True:
                # Check if session is still available (may be None after stop/cleanup)
                if self.session is None:
                    logger.info("Session is None, stopping audio reception")
                    break
                
                try:
                    turn_count += 1
                    logger.debug(f"Listening for turn {turn_count}...")
                    
                    # Double-check session is still available
                    if self.session is None:
                        logger.info("Session became None, stopping audio reception")
                        break
                    
                    turn = self.session.receive()
                    async for response in turn:
                        response_count += 1
                        # logger.info(f"📥 Received response #{response_count}: {type(response).__name__}")
                        
                        # # Debug: Log all attributes of the response
                        # logger.info(f"🔍 Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                        
                        # # Log the actual response object for debugging
                        # try:
                        #     logger.info(f"🔍 Response content: {response}")
                        # except:
                        #     pass
                        
                        # Handle audio data (inline_data) - check for 'data' attribute
                        if hasattr(response, 'data') and response.data:
                            logger.debug(f"🔊 Yielding audio data: {len(response.data)} bytes")
                            yield response.data
                        
                        # Handle server content (contains transcripts)
                        if hasattr(response, 'server_content'):
                            server_content = response.server_content
                            # logger.info(f"📋 Server content received: {type(server_content)}")
                            
                            # Capture output transcripts (agent speech) - accumulate until generation complete
                            if hasattr(server_content, "output_transcription") and server_content.output_transcription:
                                text = getattr(server_content.output_transcription, "text", None)
                                if text:
                                    # logger.info(f"🗣️ Agent transcript fragment: {text}")
                                    # Only append non-empty text to avoid fragmenting sentences
                                    text_stripped = text.strip()
                                    if text_stripped:
                                        self._agent_transcript_buffer.append(text_stripped)
                            
                            # Check for model turn (contains text and audio)
                            if hasattr(server_content, 'model_turn') and server_content.model_turn:
                                model_turn = server_content.model_turn
                                # logger.info(f"🤖 Model turn: {model_turn}")
                                
                                # Extract text from parts
                                if hasattr(model_turn, 'parts'):
                                    for part in model_turn.parts:
                                        if hasattr(part, 'text') and part.text:
                                            logger.info(f"💬 Agent text: {part.text}")
                                            await self._save_message("agent", part.text)
                                            self.conversation_buffer.append({"role": "agent", "text": part.text})
                            # Check for input transcript (user speech)
                            if hasattr(server_content, "input_transcription") and server_content.input_transcription:
                                user_text = getattr(server_content.input_transcription, "text", None)
                                if user_text:
                                    logger.info(f"🎙️ User transcript fragment: {user_text}")
                                    self._user_transcript_buffer.append(user_text.strip())
                            
                            # If generation is complete, persist accumulated agent transcript
                            if getattr(server_content, "generation_complete", False):
                                if self._agent_transcript_buffer:
                                    agent_text = " ".join(self._agent_transcript_buffer).strip()
                                    if agent_text:
                                        logger.info(f"💬 Saving complete agent message: {agent_text[:100]}...")
                                        await self._save_message("agent", agent_text)
                                        # Check for callback markers and create callback if found
                                        await self._check_and_create_callback(agent_text)
                                    self._agent_transcript_buffer.clear()
                            
                            # When turn completes, persist any buffered transcripts
                            # This ensures we don't lose any messages
                            if getattr(server_content, 'turn_complete', False):
                                logger.info(f"✅ Turn complete")
                                
                                # Save any remaining agent text (shouldn't happen if generation_complete was sent)
                                if self._agent_transcript_buffer:
                                    agent_text = " ".join(self._agent_transcript_buffer).strip()
                                    if agent_text:
                                        logger.warning(f"Saving buffered agent text at turn_complete: {agent_text[:100]}...")
                                        await self._save_message("agent", agent_text)
                                        await self._check_and_create_callback(agent_text)
                                    self._agent_transcript_buffer.clear()
                                
                                # Save user transcript
                                if self._user_transcript_buffer:
                                    user_text = " ".join(self._user_transcript_buffer).strip()
                                    if user_text:
                                        await self._save_message("user", user_text)
                                    self._user_transcript_buffer.clear()
                        
                        # Handle text (for transcript) - check for 'text' attribute (legacy)
                        if hasattr(response, 'text') and response.text:
                            logger.info(f"💬 Gemini response (legacy): {response.text}")
                            await self._save_message("agent", response.text)
                            self.conversation_buffer.append({"role": "agent", "text": response.text})
                        
                        # Handle thought (model's reasoning process) - log but don't save
                        if hasattr(response, 'thought') and response.thought:
                            logger.debug(f"💭 Gemini thought: {response.thought}")
                        
                        # Handle input transcript
                        if hasattr(response, "input_transcript") and response.input_transcript:
                            logger.info(f"🎤 User said: {response.input_transcript}")
                            await self._save_message("user", response.input_transcript)
                            self.conversation_buffer.append({"role": "user", "text": response.input_transcript})
                        
                        # Handle tool calls
                        if hasattr(response, 'tool_call') and response.tool_call:
                            logger.info(f"🔧 Gemini tool call: {response.tool_call}")
                            await self._handle_tool_calls(response.tool_call)
                
                except StopAsyncIteration:
                    # Turn completed normally, ready for next turn
                    logger.debug(f"Turn {turn_count} completed, waiting for next turn...")
                    continue
                except asyncio.CancelledError:
                    logger.info("Audio reception cancelled")
                    break
                except Exception as turn_error:
                    error_msg = str(turn_error)
                    error_type = type(turn_error).__name__
                    
                    # Check for websocket closure indicators
                    is_websocket_closed = (
                        "1011" in error_msg or 
                        "1000" in error_msg or  # Normal closure code
                        "websocket" in error_msg.lower() or 
                        "ConnectionClosed" in error_msg or 
                        "closed" in error_msg.lower() or 
                        "close_exc" in error_msg or
                        "ConnectionClosed" in error_type
                    )
                    
                    if is_websocket_closed:
                        logger.info(f"Websocket closed (code 1000/1011), stopping audio reception: {error_msg[:200]}")
                        break
                    else:
                        logger.error(f"Error in turn {turn_count}: {turn_error}", exc_info=True)
                        # Wait a bit before retrying
                        await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            logger.info(f"Audio reception cancelled for call {self.call.session_id}")
            raise
        except Exception as e:
            logger.error(f"Error receiving audio: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"Audio reception ended for call {self.call.session_id} ({response_count} responses from {turn_count} turns)")
    
    async def _save_message(self, role: str, content: str):
        """Save message to database and build transcript"""
        from app.models.database import SessionLocal
        
        logger.info(f"💬 Saving message [{role}]: {content[:100]}...")
        
        # Save to call_messages table and build transcript
        db = None
        try:
            db = SessionLocal()
            
            # Verify call exists
            from app.models.call import Call as CallModel
            call = db.query(CallModel).filter(CallModel.id == self.call.id).first()
            if not call:
                logger.error(f"❌ Call {self.call.id} not found in database!")
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
            logger.info(f"✅ Added message to session for call {self.call.id}")
            
            # Also append to call.transcript as plain text
            if call.transcript:
                call.transcript += f"\n\n{role.upper()}: {content}"
            else:
                call.transcript = f"{role.upper()}: {content}"
            
            logger.info(f"📝 Updated transcript, now {len(call.transcript)} chars")
            
            # Commit changes
            db.commit()
            logger.info(f"✅ Message saved successfully to database")
            
        except Exception as e:
            logger.error(f"❌ Error saving message: {e}", exc_info=True)
            if db:
                try:
                    db.rollback()
                except:
                    pass
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
    
    async def _check_and_create_callback(self, agent_text: str):
        """Check if agent text contains callback markers and create callback request"""
        import re
        
        # Check for callback markers in the text
        callback_markers = {
            "[CALLBACK_URGENT]": "urgent",
            "[CALLBACK_HIGH]": "high", 
            "[CALLBACK_NORMAL]": "normal",
            "[CALLBACK_LOW]": "low"
        }
        
        priority = None
        for marker, prio in callback_markers.items():
            if marker in agent_text:
                priority = prio
                logger.info(f"🚨 CALLBACK MARKER DETECTED: {marker} -> priority={priority}")
                break
        
        if not priority:
            return
        
        # Create callback request
        from app.models.database import SessionLocal
        from app.models import CallbackRequest
        
        db = None
        try:
            db = SessionLocal()
            
            # Extract reason from the conversation context
            reason = f"AI agent detected callback trigger (priority: {priority})"
            
            # Try to extract more context from recent conversation
            if self.conversation_buffer:
                recent_messages = self.conversation_buffer[-5:]  # Last 5 messages
                context_parts = []
                for msg in recent_messages:
                    if msg.get("role") == "user":
                        context_parts.append(f"Caller: {msg.get('text', '')[:200]}")
                if context_parts:
                    reason = f"Callback requested. Recent context: {' | '.join(context_parts)}"
            
            # Check if callback already exists for this call
            existing = db.query(CallbackRequest).filter(
                CallbackRequest.call_id == self.call.id
            ).first()
            
            if existing:
                logger.info(f"📋 Callback already exists for call {self.call.id}, skipping duplicate")
                return
            
            # Create callback request
            callback_request = CallbackRequest(
                call_id=self.call.id,
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                reason=reason,
                priority=priority,
                caller_name=getattr(self.call, 'caller_name', None),
                caller_phone=getattr(self.call, 'caller_phone', None),
                status="pending"
            )
            db.add(callback_request)
            
            # Update call record
            from app.models.call import Call as CallModel
            call = db.query(CallModel).filter(CallModel.id == self.call.id).first()
            if call:
                call.callback_requested = True
                call.callback_reason = reason
            
            db.commit()
            db.refresh(callback_request)
            
            logger.info(f"✅ CALLBACK REQUEST CREATED: ID={callback_request.id}, priority={priority}, call={self.call.id}")
            
            # Try to send notification
            try:
                from app.services.notification_service import get_notification_service
                notification_service = get_notification_service()
                await notification_service.send_callback_notification(db, callback_request)
                logger.info(f"📧 Callback notification sent")
            except Exception as notify_error:
                logger.warning(f"Failed to send callback notification: {notify_error}")
            
        except Exception as e:
            logger.error(f"❌ Error creating callback from marker: {e}", exc_info=True)
            if db:
                try:
                    db.rollback()
                except:
                    pass
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
    
    async def _handle_tool_calls(self, function_call):
        """Handle tool/function calls from the agent"""
        func_responses = []
        
        for call in function_call.function_calls:
            logger.info(f"Tool call: {call.name} with args: {call.args}")
            
            # Handle RAG document search
            if call.name == "search_documents":
                try:
                    query = call.args.get("query", "")
                    logger.info(f"Searching documents for: {query}")
                    
                    from app.models.database import SessionLocal
                    db = SessionLocal()
                    try:
                        chunks = await self.rag_service.search_similar_chunks(
                            db=db,
                            agent_id=self.agent.id,
                            query=query,
                            top_k=5,
                            min_similarity=0.15  # Lowered for better recall
                        )
                    finally:
                        db.close()
                    
                    if chunks:
                        # Format results
                        results = []
                        for chunk in chunks:
                            results.append({
                                "content": chunk['content'][:500],
                                "source": f"Document {chunk['document_id']}, Page {chunk['page_number']}",
                                "relevance": round(chunk['similarity'], 2)
                            })
                        result = {
                            "found": True,
                            "results": results,
                            "count": len(results)
                        }
                    else:
                        result = {"found": False, "message": "No relevant documents found"}
                    
                except Exception as e:
                    logger.error(f"Error in document search: {e}")
                    result = {"found": False, "error": str(e)}
            
            # Handle callback request - creates a callback for human follow-up
            elif call.name == "request_callback":
                try:
                    from app.models.database import SessionLocal
                    from app.models import CallbackRequest
                    
                    reason = call.args.get("reason", "Callback requested by AI agent")
                    priority = call.args.get("priority", "normal")
                    caller_name = call.args.get("caller_name", "")
                    caller_phone = call.args.get("caller_phone", "")
                    caller_email = call.args.get("caller_email", "")
                    preferred_callback_time = call.args.get("preferred_callback_time", "")
                    
                    logger.info(f"Creating callback request: reason={reason}, priority={priority}")
                    
                    db = SessionLocal()
                    try:
                        # Create the callback request
                        callback_request = CallbackRequest(
                            call_id=self.call.id,
                            user_id=self.agent.user_id,  # The agent owner gets the callback
                            agent_id=self.agent.id,
                            reason=reason,
                            priority=priority,
                            caller_name=caller_name or self.call.caller_name,
                            caller_phone=caller_phone or self.call.caller_phone,
                            caller_email=caller_email,
                            preferred_callback_time=preferred_callback_time,
                            status="pending"
                        )
                        db.add(callback_request)
                        
                        # Update call record to mark callback requested
                        self.call.callback_requested = True
                        self.call.callback_reason = reason
                        db.add(self.call)
                        
                        db.commit()
                        db.refresh(callback_request)
                        
                        logger.info(f"✅ Callback request created: ID={callback_request.id} for call {self.call.id}")
                        
                        result = {
                            "success": True,
                            "callback_id": callback_request.id,
                            "message": "Callback request created successfully. A team member will follow up."
                        }
                        
                        # Try to send notification email (don't fail if it doesn't work)
                        try:
                            from app.services.notification_service import get_notification_service
                            notification_service = get_notification_service()
                            await notification_service.send_callback_notification(db, callback_request)
                        except Exception as notify_error:
                            logger.warning(f"Failed to send callback notification: {notify_error}")
                        
                    finally:
                        db.close()
                    
                except Exception as e:
                    logger.error(f"Error creating callback request: {e}", exc_info=True)
                    result = {"success": False, "error": str(e)}
            
            else:
                # Default tool response
                result = {"status": "success", "message": "Tool executed"}
            
            func_response = types.FunctionResponse(
                id=call.id,
                name=call.name,
                response=result,
            )
            func_responses.append(func_response)
        
        # Send responses back
        if func_responses and self.session is not None:
            try:
                await self.session.send_tool_response(function_responses=func_responses)
            except Exception as e:
                logger.warning(f"Error sending tool response (session may be closed): {e}")
    
    async def send_realtime_input(self):
        """Send queued audio to Gemini with batching for better VAD detection"""
        print(f"[GEMINI-IN] Starting audio input loop (with batching)", flush=True)
        logger.info(f"Starting audio input for call {self.call.session_id}")
        audio_sent_count = 0
        
        # Batch audio for better VAD - accumulate ~80ms before sending
        # 16kHz * 2 bytes * 0.08s = 2560 bytes minimum batch
        MIN_BATCH_SIZE = 2048  # ~64ms at 16kHz (matches test.py)
        audio_buffer = b''
        
        try:
            while True:
                # Check if session is still available (may be None after stop/cleanup)
                if self.session is None:
                    print(f"[GEMINI-IN] Session is None, stopping", flush=True)
                    logger.info("Session is None, stopping audio input")
                    break
                
                try:
                    # Use wait_for with timeout to allow cancellation
                    msg = await asyncio.wait_for(self.audio_out_queue.get(), timeout=0.05)  # 50ms timeout
                    
                    # Accumulate audio data
                    if isinstance(msg, dict) and "data" in msg:
                        audio_buffer += msg["data"]
                    
                    # Double-check session is still available before sending
                    if self.session is None:
                        print(f"[GEMINI-IN] Session became None", flush=True)
                        logger.info("Session became None, stopping audio input")
                        break
                    
                    # Send when we have enough audio accumulated
                    if len(audio_buffer) >= MIN_BATCH_SIZE:
                        audio_sent_count += 1
                        batch_msg = {"data": audio_buffer, "mime_type": "audio/pcm;rate=16000"}
                        await self.session.send_realtime_input(audio=batch_msg)
                        
                        if audio_sent_count <= 10 or audio_sent_count % 50 == 0:
                            print(f"[GEMINI-IN] #{audio_sent_count} sent ({len(audio_buffer)} bytes)", flush=True)
                        audio_buffer = b''
                        
                except asyncio.TimeoutError:
                    # No audio in queue, check if we should flush buffer
                    if self.session is None:
                        print(f"[GEMINI-IN] Session None during timeout", flush=True)
                        logger.info("Session is None during timeout, stopping audio input")
                        break
                    
                    # Flush any buffered audio on timeout (ensures responsiveness)
                    if len(audio_buffer) >= 640:  # At least 20ms of audio
                        audio_sent_count += 1
                        batch_msg = {"data": audio_buffer, "mime_type": "audio/pcm;rate=16000"}
                        try:
                            await self.session.send_realtime_input(audio=batch_msg)
                            if audio_sent_count <= 10 or audio_sent_count % 50 == 0:
                                print(f"[GEMINI-IN] #{audio_sent_count} flushed ({len(audio_buffer)} bytes)", flush=True)
                        except Exception as e:
                            print(f"[GEMINI-IN] Flush error: {e}", flush=True)
                        audio_buffer = b''
                    continue
                except asyncio.CancelledError:
                    print(f"[GEMINI-IN] Cancelled after {audio_sent_count} packets", flush=True)
                    logger.info("Audio input cancelled")
                    break
                except Exception as e:
                    error_msg = str(e)
                    error_type = type(e).__name__
                    
                    # Check for websocket closure indicators
                    is_websocket_closed = (
                        "1011" in error_msg or 
                        "1000" in error_msg or  # Normal closure code
                        "websocket" in error_msg.lower() or 
                        "ConnectionClosed" in error_msg or 
                        "closed" in error_msg.lower() or 
                        "close_exc" in error_msg or
                        "ConnectionClosed" in error_type or
                        "'NoneType' object has no attribute" in error_msg
                    )
                    
                    if is_websocket_closed:
                        print(f"[GEMINI-IN] WebSocket closed: {error_msg[:100]}", flush=True)
                        logger.info(f"Websocket closed (code 1000/1011), stopping audio input: {error_msg[:200]}")
                        break
                    else:
                        print(f"[GEMINI-IN] ERROR: {error_msg[:100]}", flush=True)
                        logger.error(f"Error sending audio input: {e}", exc_info=True)
                        # For non-fatal errors, wait and continue
                        await asyncio.sleep(0.1)
        finally:
            print(f"[GEMINI-IN] ENDED, {audio_sent_count} packets sent to Gemini", flush=True)
            logger.info(f"Audio input ended for call {self.call.session_id} ({audio_sent_count} chunks sent)")
    
    async def end_session(self):
        """End the voice session"""
        try:
            # Properly close the session context manager
            if self.session_context:
                try:
                    await self.session_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing session context: {e}")
            
            self.session = None
            self.session_context = None
            
            # Update call status
            self.call.status = CallStatus.COMPLETED
            # Note: ended_at and duration calculation are now handled in websocket.py
            
            logger.info(f"Ended session for call {self.call.session_id}")
        except Exception as e:
            logger.error(f"Error ending session: {e}")


class CallSummaryService:
    """Service for generating call summaries and analysis"""
    
    def __init__(self):
        self.gemini_client = None  # Force OpenAI usage unless explicitly re-enabled
        self.openai_model = settings.OPENAI_SUMMARY_MODEL
        self.openai_api_key = settings.OPENAI_API_KEY or ""
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not configured; call summaries will fall back to Gemini (if configured).")
    
    async def generate_summary(self, call: Call, db: Optional[Session] = None) -> Dict[str, Any]:
        """Generate a comprehensive summary of the call"""
        if not call.transcript:
            return {"error": "No transcript available"}
        
        def _ensure_list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(item) for item in value if item]
            if isinstance(value, (str, bytes)):
                return [str(value)]
            if isinstance(value, dict):
                # Flatten dict values while keeping readability
                return [
                    f"{key}: {val}" if val is not None else str(key)
                    for key, val in value.items()
                ]
            return [str(value)]
        
        # Get agent language to determine summary language
        agent_language = "fr-FR"  # Default to French
        if db:
            try:
                agent = db.query(VoiceAgent).filter(VoiceAgent.id == call.agent_id).first()
                if agent and agent.language:
                    agent_language = agent.language
            except Exception as e:
                logger.warning(f"Could not fetch agent language: {e}")
        
        # Determine if language is French
        is_french = agent_language.startswith('fr')
        
        if is_french:
            prompt = f"""Analyse cette conversation téléphonique en français et fournis:

1. Un résumé concis (2-3 phrases)
2. Les points clés discutés
3. Le sentiment général (positif, négatif, neutre)
4. Les actions à suivre (s'il y en a)

Conversation:
{call.transcript}

Réponds en JSON avec les clés: summary, key_points (liste), sentiment, action_items (liste)
"""
        else:
            prompt = f"""Analyze this phone conversation in English and provide:

1. A concise summary (2-3 sentences)
2. Key points discussed
3. Overall sentiment (positive, negative, neutral)
4. Follow-up actions (if any)

Conversation:
{call.transcript}

Respond in JSON with keys: summary, key_points (array), sentiment, action_items (array)
"""
        
        try:
            result: Dict[str, Any]
            if self.openai_api_key:
                logger.info(f"🧠 Generating summary with OpenAI model {self.openai_model}")
                payload = {
                    "model": self.openai_model,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an assistant that extracts structured follow-up insights from phone calls. "
                                "Return STRICT JSON with keys: summary (string), sentiment (string), "
                                "key_points (array of strings), action_items (array of strings). "
                                "Do not include any additional keys or prose."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                }
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                logger.info("📄 Summary generated using OpenAI")
            elif self.gemini_client:
                logger.info("🧠 Generating summary with Gemini fallback")
                response = await self.gemini_client.aio.models.generate_content(
                    model=getattr(settings, "GEMINI_SUMMARY_MODEL", "gemini-1.5-flash"),
                    contents=prompt,
                    config={
                        "temperature": 0.3,
                        "response_mime_type": "application/json"
                    }
                )
                result = json.loads(response.text)
                logger.info(f"📄 Summary generation raw result: {result}")
            else:
                raise RuntimeError("No summarization provider configured. Set OPENAI_API_KEY or GOOGLE_API_KEY.")
            
            # Update call record
            call.summary = result.get("summary")
            call.sentiment = result.get("sentiment")
            call.key_points = _ensure_list(result.get("key_points"))
            action_items = _ensure_list(result.get("action_items"))
            update_call_follow_up_data(call, action_items)
            result["key_points"] = call.key_points
            result["action_items"] = call.action_items
            
            return result
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {"error": str(e)}

