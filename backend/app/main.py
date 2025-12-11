import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.models.database import engine, Base
from app.api import auth, agents, calls, websocket, billing, usage, security, profile, documents, phone_numbers, callbacks, embed, zadarma_webhook, admin, integrations, libraries, collaborators, phone_audio, phone_debug, performance
from app.middleware.rate_limit import RateLimitMiddleware, cleanup_rate_limits

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Background tasks
_cleanup_task = None
_sip_handler = None
_audiosocket_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global _cleanup_task, _sip_handler
    
    # Startup
    logger.info("Starting VoiceAgent SaaS application...")
    logger.info("Skipping automatic table creation - use database SQL schema instead")
    
    # Start background cleanup task
    _cleanup_task = asyncio.create_task(cleanup_rate_limits())
    logger.info("Started rate limit cleanup background task")
    
    # Start AudioSocket server for Asterisk audio streaming
    global _audiosocket_server
    print("[AudioSocket] Starting AudioSocket server...")
    try:
        from app.services.audiosocket_handler import audiosocket_server
        _audiosocket_server = audiosocket_server
        await _audiosocket_server.start()
        print("[AudioSocket] ✅ AudioSocket server started on port 9092")
        logger.info("✅ AudioSocket server started on port 9092")
    except Exception as e:
        print(f"[AudioSocket] ❌ Error: {e}")
        logger.error(f"Error starting AudioSocket server: {e}", exc_info=True)
    
    # Start SIP call handler - loads phone numbers with SIP config from database
    print(f"[SIP] SIP_ENABLED setting: {settings.SIP_ENABLED}")
    logger.info(f"SIP_ENABLED setting: {settings.SIP_ENABLED}")
    if settings.SIP_ENABLED:
        print("[SIP] Starting SIP call handler...")
        logger.info("Starting SIP call handler...")
        try:
            from app.services.sip_call_handler import sip_call_handler
            print("[SIP] SIP call handler imported successfully")
            logger.info("SIP call handler imported successfully")
            _sip_handler = sip_call_handler
            success = await _sip_handler.start()
            print(f"[SIP] Handler start result: {success}")
            if success:
                print("[SIP] ✅ SIP call handler started successfully")
                logger.info("✅ SIP call handler started - phone numbers loaded from database")
            else:
                print("[SIP] ⚠️ SIP call handler failed to start")
                logger.warning("⚠️ SIP call handler: No phone numbers with SIP config found in database")
                logger.info("   Add phone numbers with SIP credentials via the Phone Numbers page")
        except Exception as e:
            print(f"[SIP] ❌ Error: {e}")
            logger.error(f"Error starting SIP call handler: {e}", exc_info=True)
    else:
        print("[SIP] SIP call handler disabled (SIP_ENABLED=false)")
        logger.info("SIP call handler disabled (SIP_ENABLED=false)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop AudioSocket server
    if _audiosocket_server:
        try:
            await _audiosocket_server.stop()
            logger.info("AudioSocket server stopped")
        except Exception as e:
            logger.error(f"Error stopping AudioSocket server: {e}")
    
    # Stop SIP handler
    if _sip_handler:
        try:
            await _sip_handler.stop()
            logger.info("SIP call handler stopped")
        except Exception as e:
            logger.error(f"Error stopping SIP handler: {e}")
    
    # Stop cleanup task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            logger.info("Rate limit cleanup task cancelled")
    
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (if enabled)
if getattr(settings, 'ENABLE_RATE_LIMITING', True):
    rate_limit = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 100)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)
    logger.info(f"Rate limiting enabled: {rate_limit} requests/minute")

# Mount static files for voice widget
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    logger.info(f"Static files mounted from: {static_path}")
else:
    logger.warning(f"Static files directory not found: {static_path}")


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "VoiceAgent SaaS API",
        "version": settings.VERSION,
        "docs": "/api/docs"
    }


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2025-10-08T12:00:00Z"
    }


# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(agents.router, prefix=f"{settings.API_V1_STR}/agents", tags=["Agents"])
app.include_router(calls.router, prefix=f"{settings.API_V1_STR}/calls", tags=["Calls"])
app.include_router(websocket.router, prefix=f"{settings.API_V1_STR}/ws", tags=["WebSocket"])
app.include_router(billing.router, prefix=f"{settings.API_V1_STR}/billing", tags=["Billing"])
app.include_router(usage.router, prefix=f"{settings.API_V1_STR}/usage", tags=["Usage"])
app.include_router(security.router, prefix=f"{settings.API_V1_STR}/security", tags=["Security"])
app.include_router(profile.router, prefix=f"{settings.API_V1_STR}/profile", tags=["Profile"])
app.include_router(integrations.router, prefix=f"{settings.API_V1_STR}/integrations", tags=["Integrations"])
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/agents", tags=["Documents & RAG"])  # Routes: /{agent_id}/documents, /{agent_id}/documents/website
app.include_router(phone_numbers.router, prefix=f"{settings.API_V1_STR}/phone-numbers", tags=["Phone Numbers"])
app.include_router(phone_debug.router, prefix=f"{settings.API_V1_STR}/phone-numbers", tags=["Phone Debug"])
app.include_router(callbacks.router, prefix=f"{settings.API_V1_STR}/callbacks", tags=["Callbacks"])
app.include_router(embed.router, prefix=f"{settings.API_V1_STR}/embed", tags=["Embed Widget"])
app.include_router(zadarma_webhook.router, prefix=f"{settings.API_V1_STR}/zadarma", tags=["Zadarma Webhooks"])
app.include_router(phone_audio.router, prefix=f"{settings.API_V1_STR}/phone", tags=["Phone Audio"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])
app.include_router(libraries.router, prefix=f"{settings.API_V1_STR}/libraries", tags=["Agent Libraries"])
app.include_router(collaborators.router, prefix=f"{settings.API_V1_STR}", tags=["Collaborators"])
app.include_router(performance.router, prefix=f"{settings.API_V1_STR}/performance", tags=["Performance"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )

