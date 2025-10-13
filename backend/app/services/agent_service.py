import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
import logging
from datetime import datetime
import json

from google import genai
from google.genai import types

# Import langchain components properly to avoid Pydantic issues
try:
    # Import BaseCache first to ensure it's defined
    from langchain_core.caches import BaseCache
    from langchain_core.language_models import BaseChatModel
    
    # Force rebuild of base models
    BaseChatModel.model_rebuild()
    
    # Now import ChatGoogleGenerativeAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.memory import ConversationBufferMemory
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langgraph.graph import StateGraph, END
    from langchain.schema import HumanMessage, AIMessage
    
    # Rebuild model to fix Pydantic v2 compatibility
    ChatGoogleGenerativeAI.model_rebuild()
    
    LANGCHAIN_AVAILABLE = True
except Exception as e:
    logging.warning(f"LangChain import warning: {e}")
    LANGCHAIN_AVAILABLE = False

from app.core.config import settings
from app.models import Call, CallMessage, CallStatus, VoiceAgent
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


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
        
        # RAG service (if enabled)
        self.rag_service = get_rag_service() if agent.rag_enabled else None
        self.conversation_buffer = []  # Store recent conversation for context
        
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
    
    def _build_config(self) -> Dict[str, Any]:
        """Build configuration for Gemini Live API (simplified, matching test.py)"""
        # Language-specific system instructions
        if self.agent.language.startswith('fr'):
            language_instruction = """Réponds TOUJOURS en français de manière naturelle et fluide.
Utilise un ton amical et professionnel. Sois concis mais informatif."""
            greeting = "Tu es un assistant vocal intelligent qui parle français."
            rag_instruction = """

IMPORTANT - Utilisation des documents:
Tu as accès à des documents qui seront fournis dans le contexte quand l'utilisateur pose une question.
Quand tu reçois un contexte documentaire:
- Utilise ces informations pour répondre de manière précise
- Cite les sources quand c'est pertinent (numéro de document ou page)
- Si l'information n'est pas dans les documents, dis-le clairement
- Ne fabrique pas d'informations qui ne sont pas dans les documents fournis
"""
        else:  # English
            language_instruction = """Always respond in English in a natural and fluent manner.
Use a friendly and professional tone. Be concise but informative."""
            greeting = "You are an intelligent voice assistant that speaks English."
            rag_instruction = """

IMPORTANT - Using documents:
You have access to documents that will be provided in the context when the user asks a question.
When you receive document context:
- Use this information to answer accurately
- Cite sources when relevant (document number or page)
- If information is not in the documents, say so clearly
- Do not fabricate information that is not in the provided documents
"""
        
        # Add RAG instructions if enabled
        rag_note = rag_instruction if self.agent.rag_enabled else ""
        
        system_instruction = f"""{greeting}

{self.agent.system_prompt}

{language_instruction}{rag_note}
"""
        
        # Simplified config matching test.py (no speech_config or voice_config)
        # Gemini will auto-select voice based on language in system instruction
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": types.Content(
                parts=[types.Part(text=system_instruction)]
            ),
        }
        
        # Add tools if enabled and available
        if self.agent.tools_enabled and len(self.agent.tools_enabled) > 0:
            tools = self._load_tools()
            if tools:  # Only add if we actually have tools
                config["tools"] = tools
        
        return config
    
    def _load_tools(self):
        """Load and configure tools for the agent"""
        tools = []
        
        # RAG Document Search Tool (if RAG is enabled)
        if self.agent.rag_enabled and self.rag_service:
            async def search_documents(query: str) -> dict:
                """Recherche dans les documents pour trouver des informations pertinentes"""
                try:
                    # Import db session
                    from app.models.database import SessionLocal
                    db = SessionLocal()
                    try:
                        chunks = await self.rag_service.search_similar_chunks(
                            db=db,
                            agent_id=self.agent.id,
                            query=query,
                            top_k=3,
                            min_similarity=0.3
                        )
                    finally:
                        db.close()
                    
                    if not chunks:
                        return {"found": False, "message": "Aucun document pertinent trouvé"}
                    
                    # Format results
                    results = []
                    for chunk in chunks:
                        results.append({
                            "content": chunk['content'][:500],  # Limit content length
                            "source": f"Document {chunk['document_id']}, Page {chunk['page_number']}",
                            "relevance": round(chunk['similarity'], 2)
                        })
                    
                    return {
                        "found": True,
                        "results": results,
                        "count": len(results)
                    }
                except Exception as e:
                    logger.error(f"Error searching documents: {e}")
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
            # Note: Status and started_at are now set in websocket.py after this returns successfully
            return True
        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            self.call.status = CallStatus.FAILED
            return False
    
    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm"):
        """Send audio chunk to the agent"""
        try:
            await self.audio_out_queue.put({"data": audio_data, "mime_type": mime_type})
        except Exception as e:
            logger.error(f"Error sending audio: {e}", exc_info=True)
    
    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """Receive audio responses from the agent"""
        logger.info(f"Starting audio reception for call {self.call.session_id}")
        response_count = 0
        
        # Give the session a moment to fully initialize
        # This prevents error 1011 from calling receive() before session is ready
        await asyncio.sleep(0.5)
        
        
        try:
            while True:
                try:
                    turn = self.session.receive()
                    async for response in turn:
                        response_count += 1
                        print("------------", response)
                        # Handle audio data (inline_data)
                        if data := response.data:
                            yield data
                        
                        # Handle text (for transcript)
                        if text := response.text:
                            logger.info(f"Gemini response: {text}")
                            await self._save_message("agent", text)
                            # Add to conversation buffer for RAG
                            self.conversation_buffer.append({"role": "agent", "text": text})
                        
                        # Handle tool calls
                        if function_call := response.tool_call:
                            logger.info(f"Gemini tool call: {function_call}")
                            await self._handle_tool_calls(function_call)
                
                except StopAsyncIteration:
                    # Turn completed, ready for next turn
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
                        logger.error(f"Error in turn: {turn_error}", exc_info=True)
                        # Wait a bit before retrying
                        await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            logger.info(f"Audio reception cancelled for call {self.call.session_id}")
            raise
        except Exception as e:
            logger.error(f"Error receiving audio: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"Audio reception ended for call {self.call.session_id} ({response_count} responses)")
    
    async def _save_message(self, role: str, content: str):
        """Save message to database and build transcript"""
        from app.models.database import SessionLocal
        
        logger.info(f"Message [{role}]: {content}")
        
        # Save to call_messages table and build transcript
        try:
            db = SessionLocal()
            
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
            
            # Also append to call.transcript as plain text
            from app.models.call import Call as CallModel
            call = db.query(CallModel).filter(CallModel.id == self.call.id).first()
            if call:
                if call.transcript:
                    call.transcript += f"\n\n{role.upper()}: {content}"
                else:
                    call.transcript = f"{role.upper()}: {content}"
            
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Error saving message: {e}")
    
    async def _handle_tool_calls(self, function_call):
        """Handle tool/function calls from the agent"""
        func_responses = []
        
        for call in function_call.function_calls:
            logger.info(f"Tool call: {call.name} with args: {call.args}")
            
            # Execute the tool
            # This is a simplified example - you'd expand this based on your tools
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
        # Use native Google Genai client instead of LangChain
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    async def generate_summary(self, call: Call) -> Dict[str, Any]:
        """Generate a comprehensive summary of the call"""
        if not call.transcript:
            return {"error": "No transcript available"}
        
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
            # Use native Gemini API for summarization
            response = await self.client.aio.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config={
                    "temperature": 0.3,
                    "response_mime_type": "application/json"
                }
            )
            
            result = json.loads(response.text)
            
            # Update call record
            call.summary = result.get("summary")
            call.sentiment = result.get("sentiment")
            call.key_points = result.get("key_points", [])
            
            return result
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {"error": str(e)}

