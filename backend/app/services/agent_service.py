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
        else:  # English
            language_instruction = """Always respond in English in a natural and fluent manner.
Use a friendly and professional tone. Be concise but informative."""
            greeting = "You are an intelligent voice assistant that speaks English."
        
        system_instruction = f"""{greeting}

{self.agent.system_prompt}

{language_instruction}
"""
        
        # Simplified config matching test.py (no speech_config or voice_config)
        # Gemini will auto-select voice based on language in system instruction
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": types.Content(
                parts=[types.Part(text=system_instruction)]
            ),
        }
        
        # Add tools if enabled
        if self.agent.tools_enabled:
            config["tools"] = self._load_tools()
        
        return config
    
    def _load_tools(self):
        """Load and configure tools for the agent"""
        tools = []
        
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
            logger.info(f"Connecting to Gemini model: {settings.GEMINI_MODEL}")
            logger.info(f"Config: {self.config}")
            
            # Store the context manager to properly close it later
            self.session_context = self.client.aio.live.connect(
                model=settings.GEMINI_MODEL,
                config=self.config
            )
            self.session = await self.session_context.__aenter__()
            
            logger.info(f"✅ Successfully started voice session for call {self.call.session_id}")
            self.call.status = CallStatus.IN_PROGRESS
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start session: {e}", exc_info=True)
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
        try:
            print(f"🎧 Starting to receive audio from Gemini for call {self.call.session_id}")
            logger.info(f"Starting to receive audio for call {self.call.session_id}")
            response_count = 0
            while True:
                turn = self.session.receive()
                async for response in turn:
                    response_count += 1
                    if response_count % 10 == 0:
                        logger.debug(f"Received {response_count} responses from Gemini")
                    
                    # Handle audio data (inline_data)
                    if data := response.data:
                        print(f"🔊 Received audio data from Gemini: {len(data)} bytes")
                        logger.debug(f"Received audio data: {len(data)} bytes")
                        yield data
                    
                    # Handle text (for transcript)
                    if text := response.text:
                        print(f"\n💬 GEMINI TEXT RESPONSE: {text}\n")
                        logger.info(f"Gemini text response: {text}")
                        await self._save_message("agent", text)
                    
                    # Handle tool calls
                    if function_call := response.tool_call:
                        logger.info(f"Gemini tool call: {function_call}")
                        await self._handle_tool_calls(function_call)
                
        except Exception as e:
            logger.error(f"Error receiving audio: {e}", exc_info=True)
    
    async def _save_message(self, role: str, content: str):
        """Save message to database"""
        message = CallMessage(
            call_id=self.call.id,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        # This should be saved through the database session
        logger.info(f"Message [{role}]: {content}")
    
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
        logger.info(f"Starting realtime input loop for call {self.call.session_id}")
        audio_sent_count = 0
        while True:
            try:
                msg = await self.audio_out_queue.get()
                audio_sent_count += 1
                if audio_sent_count % 50 == 0:
                    print(f"📤 Sent {audio_sent_count} audio chunks to Gemini")
                    logger.info(f"Sent {audio_sent_count} audio chunks to Gemini ({len(msg.get('data', b''))} bytes)")
                # Send audio input to Gemini Live API (matching test.py format)
                await self.session.send_realtime_input(audio=msg)
            except Exception as e:
                logger.error(f"Error in send_realtime_input: {e}", exc_info=True)
                break
        logger.info(f"Realtime input loop ended for call {self.call.session_id}")
    
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
            
            self.call.status = CallStatus.COMPLETED
            self.call.ended_at = datetime.utcnow()
            
            # Calculate duration
            duration = (self.call.ended_at - self.call.started_at).total_seconds()
            self.call.duration_seconds = duration
            self.call.duration_minutes = duration / 60.0
            
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

