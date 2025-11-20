"""
Phone Call Audio API
Handles audio streaming for phone calls via HTTP endpoints
Zadarma can POST audio here and GET audio from here
"""
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from app.models import get_db, Call
from app.services.phone_audio_bridge import phone_audio_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/audio/{call_id}/input")
async def receive_phone_audio(
    call_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receive audio from Zadarma (caller's voice)
    
    This endpoint receives audio chunks from the phone call and forwards them to Gemini.
    Zadarma should POST audio data here during an active call.
    
    Args:
        call_id: Internal call ID
    """
    try:
        # Get audio data from request body
        audio_data = await request.body()
        
        if not audio_data:
            return {"status": "ok", "message": "No audio data"}
        
        # Get the audio bridge for this call
        bridge = phone_audio_manager.get_bridge(call_id)
        if not bridge:
            logger.warning(f"No audio bridge found for call {call_id}")
            return {"status": "error", "message": "Call not active"}
        
        # Forward audio to Gemini
        await bridge.receive_phone_audio(audio_data)
        
        return {
            "status": "ok",
            "bytes_received": len(audio_data),
            "call_id": call_id
        }
    
    except Exception as e:
        logger.error(f"Error receiving phone audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{call_id}/output")
async def get_phone_audio(
    call_id: str,
    db: Session = Depends(get_db)
):
    """
    Get audio from Gemini (AI responses) to send to Zadarma
    
    This endpoint provides audio chunks that Zadarma should play to the caller.
    Zadarma should periodically GET from this endpoint during an active call.
    
    Args:
        call_id: Internal call ID
    """
    try:
        # Get the audio bridge for this call
        bridge = phone_audio_manager.get_bridge(call_id)
        if not bridge:
            logger.warning(f"No audio bridge found for call {call_id}")
            return {"status": "error", "message": "Call not active"}
        
        # Get next audio chunk from Gemini
        audio_data = await bridge.get_gemini_audio()
        
        if audio_data:
            from fastapi.responses import Response
            return Response(
                content=audio_data,
                media_type="audio/pcm;rate=24000",
                headers={
                    "X-Audio-Length": str(len(audio_data)),
                    "X-Call-ID": call_id
                }
            )
        else:
            # No audio available yet, return empty response
            return Response(
                content=b"",
                media_type="audio/pcm;rate=24000",
                status_code=204  # No Content
            )
    
    except Exception as e:
        logger.error(f"Error getting phone audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/{call_id}/end")
async def end_phone_audio(
    call_id: str,
    db: Session = Depends(get_db)
):
    """End audio streaming for a phone call"""
    logger.info(f"Ending phone audio for call: {call_id}")
    
    # Stop audio bridge
    await phone_audio_manager.end_bridge(call_id)
    
    # Update call status
    call = db.query(Call).filter(Call.id == int(call_id)).first()
    if call:
        from app.models.call import CallStatus
        from datetime import datetime
        call.status = CallStatus.COMPLETED
        call.ended_at = datetime.utcnow()
        db.commit()
    
    return {"status": "ok", "message": "Audio streaming ended"}


@router.get("/audio/{call_id}/status")
async def get_phone_audio_status(call_id: str):
    """Get status of phone audio streaming"""
    bridge = phone_audio_manager.get_bridge(call_id)
    if bridge:
        return {
            "status": "active",
            "call_id": call_id,
            "zadarma_call_id": bridge.zadarma_call_id,
            "is_running": bridge.is_running,
            "queue_size": bridge.gemini_audio_queue.qsize()
        }
    return {
        "status": "inactive",
        "call_id": call_id
    }

