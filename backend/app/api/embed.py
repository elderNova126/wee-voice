"""
Website Embed API
Generates embed code for integrating voice agents into websites
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.models import get_db, User, VoiceAgent
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter()


# Pydantic models
class EmbedConfigUpdate(BaseModel):
    embed_enabled: bool
    embed_widget_color: Optional[str] = "#4F46E5"
    embed_position: Optional[str] = "bottom-right"
    embed_greeting_message: Optional[str] = None
    allowed_domains: Optional[list] = []


class EmbedCodeResponse(BaseModel):
    embed_code: str
    script_url: str
    agent_id: int
    configuration: dict


@router.get("/agents/{agent_id}/embed-config")
async def get_embed_config(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get embed configuration for an agent"""
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return {
        "embed_enabled": agent.embed_enabled,
        "embed_widget_color": agent.embed_widget_color,
        "embed_position": agent.embed_position,
        "embed_greeting_message": agent.embed_greeting_message,
        "allowed_domains": agent.allowed_domains or []
    }


@router.put("/agents/{agent_id}/embed-config")
async def update_embed_config(
    agent_id: int,
    config: EmbedConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update embed configuration for an agent"""
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Update configuration
    agent.embed_enabled = config.embed_enabled
    agent.embed_widget_color = config.embed_widget_color
    agent.embed_position = config.embed_position
    agent.embed_greeting_message = config.embed_greeting_message
    agent.allowed_domains = config.allowed_domains or []
    
    db.commit()
    db.refresh(agent)
    
    return {
        "message": "Embed configuration updated",
        "embed_enabled": agent.embed_enabled
    }


@router.get("/agents/{agent_id}/embed-code", response_model=EmbedCodeResponse)
async def generate_embed_code(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate embed code for an agent"""
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if not agent.embed_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embed is not enabled for this agent"
        )
    
    # Get backend URL from settings
    backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000')
    
    # Generate embed code
    embed_code = f"""<!-- WeeVoice Agent Widget -->
<script>
  (function() {{
    var config = {{
      agentId: {agent_id},
      apiUrl: '{backend_url}',
      color: '{agent.embed_widget_color}',
      position: '{agent.embed_position}',
      greeting: '{agent.embed_greeting_message or f"Hi! I'm {agent.name}. How can I help you?"}',
      agentName: '{agent.name}'
    }};
    
    var script = document.createElement('script');
    script.src = '{backend_url}/static/js/voice-widget.js';
    script.async = true;
    script.onload = function() {{
      if (window.WeeVoiceWidget) {{
        window.WeeVoiceWidget.init(config);
      }}
    }};
    document.head.appendChild(script);
    
    var styles = document.createElement('link');
    styles.rel = 'stylesheet';
    styles.href = '{backend_url}/static/css/voice-widget.css';
    document.head.appendChild(styles);
  }})();
</script>
<!-- End WeeVoice Agent Widget -->"""
    
    return {
        "embed_code": embed_code,
        "script_url": f"{backend_url}/static/js/voice-widget.js",
        "agent_id": agent.id,
        "configuration": {
            "color": agent.embed_widget_color,
            "position": agent.embed_position,
            "greeting": agent.embed_greeting_message or f"Hi! I'm {agent.name}. How can I help you?",
            "agent_name": agent.name
        }
    }


@router.get("/widget/{agent_id}/config")
async def get_widget_config(
    agent_id: int,
    origin: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get widget configuration (public endpoint for embedded widget)"""
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.embed_enabled == True
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or embed not enabled"
        )
    
    # Check domain restrictions
    if origin and agent.allowed_domains:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        domain = parsed.netloc
        
        if domain not in agent.allowed_domains:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Domain not allowed"
            )
    
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "color": agent.embed_widget_color,
        "position": agent.embed_position,
        "greeting": agent.embed_greeting_message or f"Hi! I'm {agent.name}. How can I help you?",
        "language": agent.language
    }

