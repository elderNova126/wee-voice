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
        openai_init_success = False
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI
                
                # Try simple initialization first (most compatible)
                try:
                    self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                    logger.info("✓ OpenAI client initialized for text chat (fallback)")
                    openai_init_success = True
                except TypeError as e:
                    # If proxies error, try with explicit http_client
                    if 'proxies' in str(e):
                        logger.warning("OpenAI proxies parameter issue detected, trying alternative initialization...")
                        import httpx
                        # Create httpx client with minimal config
                        http_client = httpx.AsyncClient(timeout=30.0)
                        self.openai_client = AsyncOpenAI(
                            api_key=settings.OPENAI_API_KEY,
                            http_client=http_client
                        )
                        logger.info("✓ OpenAI client initialized (with custom http_client)")
                        openai_init_success = True
                    else:
                        raise
                        
            except Exception as e:
                logger.error(f"❌ Could not initialize OpenAI client: {e}")
                logger.error(f"OpenAI initialization error type: {type(e).__name__}")
                import traceback
                logger.error(f"OpenAI initialization traceback: {traceback.format_exc()}")
                self.openai_client = None
                openai_init_success = False
        else:
            logger.warning("⚠ OPENAI_API_KEY not set in settings")
            logger.debug(f"Settings OPENAI_API_KEY value: '{settings.OPENAI_API_KEY}' (empty: {not settings.OPENAI_API_KEY})")
            self.openai_client = None
            openai_init_success = False
        
        # Check if we have at least one working client
        if not self.anthropic_client and not self.openai_client:
            error_details = []
            diagnostics = []
            
            if not settings.ANTHROPIC_API_KEY:
                error_details.append("ANTHROPIC_API_KEY not set")
                diagnostics.append("  - Set ANTHROPIC_API_KEY in backend/.env file")
            elif not self.anthropic_client:
                error_details.append("ANTHROPIC_API_KEY set but client initialization failed")
                diagnostics.append("  - Check Anthropic API key validity")
            
            if not settings.OPENAI_API_KEY:
                error_details.append("OPENAI_API_KEY not set")
                diagnostics.append("  - Set OPENAI_API_KEY in backend/.env file")
            elif not openai_init_success:
                error_details.append("OPENAI_API_KEY set but client initialization failed")
                diagnostics.append("  - Check OpenAI API key validity")
                diagnostics.append("  - Check backend startup logs for initialization errors")
            
            error_msg = f"Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is configured properly. At least one is required for text chat.\n"
            error_msg += f"Issues: {', '.join(error_details)}\n"
            error_msg += "\nTo fix:\n"
            error_msg += "\n".join(diagnostics) if diagnostics else "  - Configure at least one API key"
            error_msg += "\n  - Restart backend server after updating .env"
            raise ValueError(error_msg)
        
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
    
    async def stream_message(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream AI response in real-time as tokens are generated
        Yields: {"chunk": "text", "done": bool, "needs_callback": bool, "callback_priority": str or None}
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
            
            # Build complete message with context
            complete_message = user_message
            if rag_context:
                complete_message = rag_context + "\n\nUser question: " + user_message
            
            # Stream AI response
            full_response = ""
            needs_callback = False
            callback_priority = None
            
            async for chunk_data in self._stream_ai_response(complete_message):
                chunk_text = chunk_data.get("chunk", "")
                full_response += chunk_text
                
                # Check for callback markers in accumulated response
                if not needs_callback:
                    for marker, priority in [
                        ("[CALLBACK_URGENT]", "urgent"),
                        ("[CALLBACK_HIGH]", "high"),
                        ("[CALLBACK_NORMAL]", "normal")
                    ]:
                        if marker in full_response:
                            needs_callback = True
                            callback_priority = priority.lower()
                            break
                
                yield {
                    "chunk": chunk_text,
                    "done": chunk_data.get("done", False),
                    "needs_callback": needs_callback,
                    "callback_priority": callback_priority
                }
            
            # Clean up callback markers from final response
            for marker in ["[CALLBACK_URGENT]", "[CALLBACK_HIGH]", "[CALLBACK_NORMAL]"]:
                full_response = full_response.replace(marker, "").strip()
            
            # Add assistant message to history (without markers)
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
            
        except Exception as e:
            logger.error(f"Error in stream_message: {e}", exc_info=True)
            yield {
                "chunk": "I apologize, but I encountered an error processing your message. Please try again.",
                "done": True,
                "needs_callback": False,
                "callback_priority": None
            }
    
    async def _get_ai_response(self, message: str) -> str:
        """Get AI response using Anthropic (primary) or OpenAI (fallback)"""
        
        anthropic_error = None
        
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
                anthropic_error = str(e)
                error_lower = anthropic_error.lower()
                
                # Check for specific error types
                if '403' in anthropic_error or 'forbidden' in error_lower or 'not allowed' in error_lower:
                    logger.error(f"Anthropic API error (403 Forbidden): {anthropic_error}")
                    logger.warning("Anthropic API key may be invalid, expired, or restricted. Falling back to OpenAI...")
                elif '401' in anthropic_error or 'unauthorized' in error_lower:
                    logger.error(f"Anthropic API error (401 Unauthorized): {anthropic_error}")
                    logger.warning("Anthropic API key is invalid. Falling back to OpenAI...")
                else:
                    logger.error(f"Anthropic API error: {anthropic_error}")
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
                openai_error = str(e)
                logger.error(f"OpenAI API error: {openai_error}")
                
                # Build comprehensive error message
                error_parts = []
                if anthropic_error:
                    error_parts.append(f"Anthropic: {anthropic_error}")
                error_parts.append(f"OpenAI: {openai_error}")
                
                raise Exception(f"Both AI providers failed. {' | '.join(error_parts)}")
        
        # No providers available - provide detailed diagnostics
        error_msg = "No AI provider available"
        if anthropic_error:
            error_msg += f". Anthropic error: {anthropic_error}"
        if not self.openai_client:
            error_msg += ". OpenAI client failed to initialize"
        raise Exception(error_msg)
    
    async def _stream_ai_response(self, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream AI response using Anthropic (primary) or OpenAI (fallback)"""
        
        anthropic_error = None
        
        # Try Anthropic first
        if self.anthropic_client:
            try:
                logger.info("Using Anthropic streaming for text chat response")
                
                # Use stream parameter for Anthropic
                async with self.anthropic_client.messages.stream(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=1024,
                    system=self.system_prompt,
                    messages=self._format_history_for_anthropic()
                ) as stream:
                    async for text_block in stream.text_stream:
                        if text_block:
                            yield {"chunk": text_block, "done": False}
                    
                    # Get final message to check for stop reason
                    final_message = await stream.get_final_message()
                    yield {"chunk": "", "done": True}
                    logger.info("✓ Anthropic streaming completed")
                    return
                    
            except Exception as e:
                anthropic_error = str(e)
                error_lower = anthropic_error.lower()
                
                # Check for specific error types
                if '403' in anthropic_error or 'forbidden' in error_lower or 'not allowed' in error_lower:
                    logger.error(f"Anthropic API error (403 Forbidden): {anthropic_error}")
                    logger.warning("Anthropic API key may be invalid, expired, or restricted. Falling back to OpenAI...")
                elif '401' in anthropic_error or 'unauthorized' in error_lower:
                    logger.error(f"Anthropic API error (401 Unauthorized): {anthropic_error}")
                    logger.warning("Anthropic API key is invalid. Falling back to OpenAI...")
                else:
                    logger.error(f"Anthropic API error: {anthropic_error}")
                    logger.info("Falling back to OpenAI...")
        
        # Fallback to OpenAI streaming
        if self.openai_client:
            try:
                logger.info("Using OpenAI streaming for text chat response")
                
                messages = [{"role": "system", "content": self.system_prompt}]
                messages.extend(self.conversation_history)
                
                stream = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_CHAT_MODEL,
                    messages=messages,
                    max_tokens=1024,
                    temperature=float(self.agent.temperature) if hasattr(self.agent, 'temperature') else 0.7,
                    stream=True
                )
                
                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            yield {"chunk": delta.content, "done": False}
                
                yield {"chunk": "", "done": True}
                logger.info("✓ OpenAI streaming completed")
                return
                
            except Exception as e:
                openai_error = str(e)
                logger.error(f"OpenAI API error: {openai_error}")
                
                # Build comprehensive error message
                error_parts = []
                if anthropic_error:
                    error_parts.append(f"Anthropic: {anthropic_error}")
                error_parts.append(f"OpenAI: {openai_error}")
                
                raise Exception(f"Both AI providers failed. {' | '.join(error_parts)}")
        
        # No providers available
        error_details = []
        diagnostics = []
        
        # Check Anthropic
        if not self.anthropic_client:
            if not settings.ANTHROPIC_API_KEY:
                error_details.append("ANTHROPIC_API_KEY not set")
                diagnostics.append("  - Set ANTHROPIC_API_KEY in backend/.env file")
            else:
                error_details.append("Anthropic client failed to initialize")
                diagnostics.append("  - Check Anthropic API key validity")
                if anthropic_error:
                    diagnostics.append(f"  - Last error: {anthropic_error}")
        
        # Check OpenAI
        if not self.openai_client:
            if not settings.OPENAI_API_KEY:
                error_details.append("OPENAI_API_KEY not set")
                diagnostics.append("  - Set OPENAI_API_KEY in backend/.env file")
            else:
                error_details.append("OpenAI client failed to initialize")
                diagnostics.append("  - Check OpenAI API key validity")
                diagnostics.append("  - Check backend startup logs for initialization errors")
                diagnostics.append(f"  - OPENAI_API_KEY length: {len(settings.OPENAI_API_KEY)} chars")
        
        error_msg = f"No AI provider available. {', '.join(error_details)}.\n"
        error_msg += "\nTo fix this:\n"
        error_msg += "\n".join(diagnostics) if diagnostics else "  - Configure at least one API key"
        error_msg += "\n  - Restart the backend server after updating .env file"
        error_msg += "\n  - Verify API keys are valid and have proper permissions"
        
        raise Exception(error_msg)
    
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

