import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
import json
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.models import Call, CallStatus, VoiceAgent, CallMessage
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TextChatService:
    """Service for handling text-based chat conversations with Anthropic (primary) and OpenAI (fallback)"""
    
    def __init__(self, agent: VoiceAgent, call: Call):
        self.agent = agent
        self.call = call
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize API clients
        self.anthropic_client = None
        self.openai_client = None
        
        # Try to initialize Anthropic first (primary)
        if settings.ANTHROPIC_API_KEY:
            try:
                from anthropic import AsyncAnthropic
                self.anthropic_client = AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY,
                    max_retries=2,
                    timeout=30.0
                )
                logger.info("✓ Anthropic client initialized for text chat")
            except Exception as e:
                logger.warning(f"Could not initialize Anthropic client: {e}")
                self.anthropic_client = None
        else:
            logger.warning("ANTHROPIC_API_KEY not set, will use OpenAI fallback")
        
        # Initialize OpenAI as fallback
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI
                # Simple initialization without extra parameters for compatibility
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("✓ OpenAI client initialized for text chat (fallback)")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")
                self.openai_client = None
        
        # Check if we have at least one working client
        if not self.anthropic_client and not self.openai_client:
            raise ValueError("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is configured. At least one is required for text chat.")
        
        # RAG service (lazy load)
        self._rag_service = None
        self._rag_service_initialized = False
        
        # System prompt
        self.system_prompt = self._build_system_prompt()
    
    @property
    def rag_service(self):
        """Lazy load RAG service only when needed"""
        if self.agent.rag_enabled and not self._rag_service_initialized:
            logger.info("Lazy loading RAG service for text chat agent...")
            self._rag_service = get_rag_service()
            self._rag_service_initialized = True
        return self._rag_service
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for the text chat agent"""
        base_prompt = self.agent.system_prompt or "You are a helpful assistant."
        
        # Add RAG instructions if enabled
        if self.agent.rag_enabled:
            rag_note = """

[KNOWLEDGE BASE AVAILABLE]
You have access to uploaded documents. If the user asks a question that requires specific information from the knowledge base, search for relevant information before responding.
"""
            base_prompt += rag_note
        
        # Add callback instructions
        callback_note = """

[CALLBACK SYSTEM]
If you detect that the user needs to speak with a human (e.g., angry, frustrated, complex issue, or explicitly requests human contact), include one of these markers in your response:
- [CALLBACK_URGENT] - for angry/frustrated users
- [CALLBACK_HIGH] - for complex issues or explicit human requests
- [CALLBACK_NORMAL] - for sensitive topics

Example: "[CALLBACK_HIGH] I understand your concern. Let me connect you with a team member who can help. What's the best number to reach you?"
"""
        base_prompt += callback_note
        
        return base_prompt
    
    async def send_message(self, user_message: str) -> Dict[str, Any]:
        """
        Send a user message and get AI response
        Returns: {"text": "response", "needs_callback": bool, "callback_priority": str or None}
        """
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Check if RAG is enabled and search for relevant context
            rag_context = ""
            if self.agent.rag_enabled and self.rag_service:
                try:
                    logger.info(f"Searching knowledge base for: {user_message[:100]}")
                    results = await self.rag_service.search(
                        agent_id=self.agent.id,
                        query=user_message,
                        top_k=3
                    )
                    
                    if results:
                        rag_context = "\n\n[KNOWLEDGE BASE CONTEXT]\n"
                        for i, result in enumerate(results, 1):
                            rag_context += f"\nDocument {i}: {result.get('content', '')[:500]}\n"
                        logger.info(f"Found {len(results)} relevant documents")
                except Exception as e:
                    logger.error(f"RAG search error: {e}")
            
            # Build the complete user message with RAG context
            complete_message = user_message
            if rag_context:
                complete_message = f"{rag_context}\n\nUser question: {user_message}"
            
            # Get AI response (Anthropic first, then OpenAI fallback)
            response_text = await self._get_ai_response(complete_message)
            
            # Check for callback markers
            callback_priority = None
            needs_callback = False
            
            for priority in ["URGENT", "HIGH", "NORMAL"]:
                marker = f"[CALLBACK_{priority}]"
                if marker in response_text:
                    needs_callback = True
                    callback_priority = priority.lower()
                    # Remove marker from user-facing text
                    response_text = response_text.replace(marker, "").strip()
                    logger.info(f"Callback detected: {priority}")
                    break
            
            # Add assistant message to history (without markers)
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            return {
                "text": response_text,
                "needs_callback": needs_callback,
                "callback_priority": callback_priority
            }
            
        except Exception as e:
            logger.error(f"Error in send_message: {e}", exc_info=True)
            return {
                "text": "I apologize, but I encountered an error processing your message. Please try again.",
                "needs_callback": False,
                "callback_priority": None
            }
    
    async def _get_ai_response(self, message: str) -> str:
        """Get AI response using Anthropic (primary) or OpenAI (fallback)"""
        
        # Try Anthropic first
        if self.anthropic_client:
            try:
                logger.info("Using Anthropic for text chat response")
                response = await self.anthropic_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=1024,
                    system=self.system_prompt,
                    messages=self._format_history_for_anthropic()
                )
                
                # Extract text from response
                response_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        response_text += block.text
                
                logger.info("✓ Anthropic response received")
                return response_text
                
            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                logger.info("Falling back to OpenAI...")
        
        # Fallback to OpenAI
        if self.openai_client:
            try:
                logger.info("Using OpenAI for text chat response")
                
                messages = [{"role": "system", "content": self.system_prompt}]
                messages.extend(self.conversation_history)
                
                response = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_CHAT_MODEL,
                    messages=messages,
                    max_tokens=1024,
                    temperature=float(self.agent.temperature) if hasattr(self.agent, 'temperature') else 0.7
                )
                
                response_text = response.choices[0].message.content
                logger.info("✓ OpenAI response received")
                return response_text
                
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                raise Exception("Both Anthropic and OpenAI failed to respond")
        
        raise Exception("No AI provider available")
    
    def _format_history_for_anthropic(self) -> List[Dict[str, str]]:
        """Format conversation history for Anthropic API (no system messages in history)"""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_history
        ]
    
    async def save_message_to_db(self, role: str, content: str, db_session):
        """Save message to database"""
        try:
            message = CallMessage(
                call_id=self.call.id,
                role=role,
                content=content
            )
            db_session.add(message)
            db_session.commit()
        except Exception as e:
            logger.error(f"Error saving message to DB: {e}")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the full conversation history"""
        return self.conversation_history.copy()
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    async def cleanup(self):
        """Cleanup resources (clients)"""
        try:
            if self.anthropic_client:
                # Anthropic client cleanup
                if hasattr(self.anthropic_client, '_client') and hasattr(self.anthropic_client._client, 'aclose'):
                    await self.anthropic_client._client.aclose()
        except Exception as e:
            logger.debug(f"Anthropic client cleanup: {e}")
        
        try:
            if self.openai_client:
                # OpenAI client cleanup
                if hasattr(self.openai_client, 'close'):
                    await self.openai_client.close()
        except Exception as e:
            logger.debug(f"OpenAI client cleanup: {e}")

