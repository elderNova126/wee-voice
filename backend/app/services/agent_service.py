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

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True


class FrenchVoiceAgentService:
    """Service for handling French voice agent conversations with ultra-low latency"""
    
    def __init__(self, agent: VoiceAgent, call: Call):
        self.agent = agent
        self.call = call
        
        # Validate API key
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set. Please check your .env file.")
        
        logger.info(f"Initializing FrenchVoiceAgentService with API key: {settings.GOOGLE_API_KEY[:20]}...")
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.session = None
        self.session_context = None
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue(maxsize=5)
        
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
        # Language-specific technical notes (minimal, non-intrusive)
        if self.agent.language.startswith('fr'):
            language_note = "\n\n[Note: Réponds en français]"
            rag_instruction = """

[OUTIL DISPONIBLE: search_documents]
Si l'utilisateur pose une question nécessitant des informations spécifiques des documents téléchargés, utilise l'outil 'search_documents' pour chercher l'information avant de répondre.
"""
        else:  # English
            language_note = "\n\n[Note: Respond in English]"
            rag_instruction = """

[AVAILABLE TOOL: search_documents]
If the user asks a question requiring specific information from uploaded documents, use the 'search_documents' tool to find the information before answering.
"""
        
        # Add RAG instructions if enabled (minimal)
        rag_note = rag_instruction if self.agent.rag_enabled else ""
        
        # Build system instruction with USER'S PROMPT as PRIMARY identity
        # Add strong identity enforcement to prevent model from defaulting to "I am Gemini"
        identity_enforcement = """
CRITICAL INSTRUCTION: Follow the system prompt above EXACTLY. You are NOT Gemini, you are NOT an AI assistant by Google. Your identity, personality, and behavior are defined by the instructions above. Stay in character at all times.
"""

        greeting_instruction = ""
        if self.agent.greeting:
            safe_greeting = self.agent.greeting.replace('"', '\\"')
            greeting_instruction = f"""

INITIAL_GREETING PROTOCOL:
- When the conversation begins you will receive the marker "<CALL_START>".
- Immediately respond to "<CALL_START>" by speaking this exact sentence, in a natural tone, before anything else: "{safe_greeting}"
- Do NOT repeat, explain, or mention the marker or these instructions. After speaking the greeting you can continue the conversation normally.
"""
        
        # Only add minimal technical notes that don't override user's intent
        system_instruction = f"""{self.agent.system_prompt}

{identity_enforcement}{greeting_instruction}{language_note}{rag_note}"""
        
        # Log the system prompt for debugging
        logger.info(f"System prompt for agent {self.agent.id} ({self.agent.name}):")
        logger.info(f"  Custom prompt: {self.agent.system_prompt[:100]}...")
        logger.info(f"  RAG enabled: {self.agent.rag_enabled}")
        logger.info(f"  Full instruction length: {len(system_instruction)} chars")
        
        # Build config matching the working test.py
        # Include both AUDIO and TEXT responses for better interaction
        # The model will automatically transcribe and understand user input
        config = {
            "response_modalities": ["AUDIO"],  # Match test.py exactly
            "system_instruction": system_instruction,  # Use plain string like test.py
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
            if self.agent.language.startswith('fr'):
                voice_name = "Charon"  # Deeper voice for French
            elif self.agent.language.startswith('es'):
                voice_name = "Kore"  # Female voice for Spanish
            else:
                voice_name = "Puck"  # Default English voice
        
        # Add voice config
        config["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name
                }
            }
        }
        
        logger.info(f"Voice selection for agent {self.agent.id}:")
        logger.info(f"  - Language: {self.agent.language}")
        logger.info(f"  - Voice Gender: {voice_gender}")
        logger.info(f"  - Voice ID: {self.agent.voice_id}")
        logger.info(f"  - Selected Voice: {voice_name}")
        
        # Add tools if enabled and available
        # Always check for RAG tools if RAG is enabled, even if tools_enabled is empty
        tools = self._load_tools()
        if tools:  # Only add if we actually have tools
            config["tools"] = tools
            logger.info(f"Loaded {len(tools)} tools for agent")
        
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
            
            # Send greeting trigger if configured
            if self.agent.greeting:
                try:
                    logger.info("Sending greeting trigger <CALL_START>")
                    await self.session.send(input="<CALL_START>", end_of_turn=True)
                except Exception as e:
                    logger.warning(f"Failed to send greeting trigger: {e}")
            
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
                try:
                    turn_count += 1
                    logger.debug(f"Listening for turn {turn_count}...")
                    turn = self.session.receive()
                    async for response in turn:
                        response_count += 1
                        logger.info(f"📥 Received response #{response_count}: {type(response).__name__}")
                        
                        # Debug: Log all attributes of the response
                        logger.info(f"🔍 Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                        
                        # Log the actual response object for debugging
                        try:
                            logger.info(f"🔍 Response content: {response}")
                        except:
                            pass
                        
                        # Handle audio data (inline_data) - check for 'data' attribute
                        if hasattr(response, 'data') and response.data:
                            logger.debug(f"🔊 Yielding audio data: {len(response.data)} bytes")
                            yield response.data
                        
                        # Handle server content (contains transcripts)
                        if hasattr(response, 'server_content'):
                            server_content = response.server_content
                            logger.info(f"📋 Server content received: {type(server_content)}")
                            
                            # Capture output transcripts (agent speech) - accumulate until generation complete
                            if hasattr(server_content, "output_transcription") and server_content.output_transcription:
                                text = getattr(server_content.output_transcription, "text", None)
                                if text:
                                    logger.info(f"🗣️ Agent transcript fragment: {text}")
                                    self._agent_transcript_buffer.append(text.strip())
                            
                            # Check for model turn (contains text and audio)
                            if hasattr(server_content, 'model_turn') and server_content.model_turn:
                                model_turn = server_content.model_turn
                                logger.info(f"🤖 Model turn: {model_turn}")
                                
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
                                        await self._save_message("agent", agent_text)
                                    self._agent_transcript_buffer.clear()
                            
                            # When turn completes, persist any buffered user transcript
                            if getattr(server_content, 'turn_complete', False):
                                logger.info(f"✅ Turn complete")
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
                    # Check if it's a connection closure
                    if "1011" in error_msg or "websocket" in error_msg.lower() or "ConnectionClosed" in error_msg:
                        logger.info(f"Gemini connection closed: {turn_error}")
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
        if func_responses:
            await self.session.send_tool_response(function_responses=func_responses)
    
    async def send_realtime_input(self):
        """Send queued audio to Gemini"""
        logger.info(f"Starting audio input for call {self.call.session_id}")
        audio_sent_count = 0
        
        try:
            while True:
                try:
                    # Use wait_for with timeout to allow cancellation
                    msg = await asyncio.wait_for(self.audio_out_queue.get(), timeout=1.0)
                    audio_sent_count += 1
                    
                    # Send audio input to Gemini Live API
                    # Format matches test.py: dict with "data" and "mime_type" keys
                    await self.session.send_realtime_input(audio=msg)
                except asyncio.TimeoutError:
                    # No audio in queue, continue waiting
                    continue
                except asyncio.CancelledError:
                    logger.info("Audio input cancelled")
                    break
                except Exception as e:
                    error_msg = str(e)
                    if "1011" in error_msg or "websocket" in error_msg.lower() or "ConnectionClosed" in error_msg or "closed" in error_msg.lower():
                        logger.info("Session closed, stopping audio input")
                        break
                    else:
                        logger.error(f"Error sending audio input: {e}", exc_info=True)
                        # For non-fatal errors, wait and continue
                        await asyncio.sleep(0.1)
        finally:
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
    
    async def generate_summary(self, call: Call) -> Dict[str, Any]:
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
        
        prompt = f"""Analyse cette conversation téléphonique en français et fournis:

1. Un résumé concis (2-3 phrases)
2. Les points clés discutés
3. Le sentiment général (positif, négatif, neutre)
4. Les actions à suivre (s'il y en a)

Conversation:
{call.transcript}

Réponds en JSON avec les clés: summary, key_points (liste), sentiment, action_items (liste)
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

