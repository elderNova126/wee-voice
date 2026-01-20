from typing import List, Optional, Any
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.security import get_current_active_user
from app.core.permissions import check_agent_access, get_user_permissions, can_manage_collaborators
from app.models import get_db, User, VoiceAgent, AgentCollaborator

router = APIRouter()


class WorkflowQuestion(BaseModel):
    """A single question in the workflow questionnaire"""
    id: int
    question: str  # The actual question to ask
    key: str  # Identifier for the answer (e.g., "budget", "timeline", "decision_maker")
    required: bool = True  # Whether this question must be answered


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    language: str = "fr-FR"
    voice_id: str = "Charon"  # Gemini 2.5 voice (Charon/Kore/Fenrir/Aoede/Puck only)
    voice_gender: str = "male"  # Voice gender: male, female, neutral
    system_prompt: str
    greeting: Optional[str] = None
    email_request_enabled: bool = False
    email_request_message: Optional[str] = None
    manager_contact: Optional[str] = None  # Manager contact for escalation
    tools_enabled: List[str] = []
    crm_webhook_url: Optional[str] = None
    crm_enabled: bool = False
    is_public: bool = False
    interaction_mode: str = "voice"  # "voice", "text", or "both"
    # Workflow/Questionnaire settings for outbound calls
    call_direction: str = "inbound"  # "inbound" or "outbound"
    workflow_enabled: bool = False  # Enable structured questionnaire
    workflow_questions: List[WorkflowQuestion] = []  # Questions to ask in order
    workflow_intro: Optional[str] = None  # Message before starting questions
    workflow_outro: Optional[str] = None  # Message after all questions answered


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    voice_id: Optional[str] = None
    voice_gender: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting: Optional[str] = None
    email_request_enabled: Optional[bool] = None
    email_request_message: Optional[str] = None
    manager_contact: Optional[str] = None  # Manager contact for escalation
    tools_enabled: Optional[List[str]] = None
    crm_webhook_url: Optional[str] = None
    crm_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    interaction_mode: Optional[str] = None
    # Workflow/Questionnaire settings for outbound calls
    call_direction: Optional[str] = None
    workflow_enabled: Optional[bool] = None
    workflow_questions: Optional[List[WorkflowQuestion]] = None
    workflow_intro: Optional[str] = None
    workflow_outro: Optional[str] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    language: str
    voice_id: str
    voice_gender: str
    system_prompt: str
    greeting: Optional[str] = None
    email_request_enabled: bool = False
    email_request_message: Optional[str] = None
    manager_contact: Optional[str] = None  # Manager contact for escalation
    tools_enabled: List[str] = Field(default_factory=list)
    is_active: bool
    is_public: bool
    rag_enabled: bool = False  # RAG/Knowledge Base enabled status
    interaction_mode: str = "voice"  # "voice", "text", or "both"
    # Workflow/Questionnaire settings
    call_direction: str = "inbound"
    workflow_enabled: bool = False
    workflow_questions: List[WorkflowQuestion] = Field(default_factory=list)
    workflow_intro: Optional[str] = None
    workflow_outro: Optional[str] = None
    # Metadata
    created_at: Any
    phone_number: Optional[str] = None
    phone_number_status: Optional[str] = None
    is_owner: Optional[bool] = True  # Whether current user is owner
    role: Optional[str] = "owner"  # "owner" or "collaborator"
    permissions: Optional[List[str]] = Field(default_factory=list)  # User's permissions
    
    class Config:
        from_attributes = True


def _serialize_agent(agent: VoiceAgent, current_user_id: Optional[int] = None, db: Optional[Session] = None) -> AgentResponse:
    """Convert a VoiceAgent model instance into an AgentResponse."""
    phone_record = getattr(agent, "phone_number", None)
    phone_number = None
    phone_status = None
    
    if phone_record:
        phone_number = phone_record.phone_number
        status = getattr(phone_record, "status", None)
        phone_status = getattr(status, "value", status) if status else None
    
    # Determine role and permissions
    is_owner = current_user_id is not None and agent.user_id == current_user_id
    role = "owner" if is_owner else "collaborator"
    permissions = []
    
    if current_user_id:
        if is_owner:
            permissions = ["view", "edit", "delete", "manage_collaborators"]
        else:
            # Get collaborator permissions
            if db:
                collaborator = db.query(AgentCollaborator).filter(
                    AgentCollaborator.agent_id == agent.id,
                    AgentCollaborator.user_id == current_user_id,
                    AgentCollaborator.is_active == True
                ).first()
                if collaborator:
                    permissions = collaborator.permissions.split(",")
            else:
                from app.core.permissions import get_user_permissions
                from app.models.database import SessionLocal
                temp_db = SessionLocal()
                try:
                    permissions = get_user_permissions(temp_db, agent.id, current_user_id)
                finally:
                    temp_db.close()
    
    # Parse workflow questions if stored as JSON
    workflow_questions = getattr(agent, 'workflow_questions', None) or []
    if workflow_questions and isinstance(workflow_questions, list):
        workflow_questions = [
            WorkflowQuestion(**q) if isinstance(q, dict) else q 
            for q in workflow_questions
        ]
    
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        language=agent.language,
        voice_id=agent.voice_id,
        voice_gender=agent.voice_gender,
        system_prompt=agent.system_prompt,
        greeting=agent.greeting,
        email_request_enabled=agent.email_request_enabled or False,
        email_request_message=agent.email_request_message,
        tools_enabled=agent.tools_enabled or [],
        is_active=agent.is_active,
        is_public=agent.is_public,
        rag_enabled=agent.rag_enabled,
        interaction_mode=getattr(agent, 'interaction_mode', 'voice'),
        # Workflow fields
        call_direction=getattr(agent, 'call_direction', 'inbound') or 'inbound',
        workflow_enabled=getattr(agent, 'workflow_enabled', False) or False,
        workflow_questions=workflow_questions,
        workflow_intro=getattr(agent, 'workflow_intro', None),
        workflow_outro=getattr(agent, 'workflow_outro', None),
        # Metadata
        created_at=agent.created_at,
        phone_number=phone_number,
        phone_number_status=phone_status,
        is_owner=is_owner,
        role=role,
        permissions=permissions,
    )


def _regenerate_greeting_background(greeting: str, language: str, gender: str):
    """Background task to regenerate greeting using Gemini (same voice as conversation)"""
    try:
        from app.services.greeting_tts_service import generate_greeting_with_gemini, GEMINI_AVAILABLE
        if GEMINI_AVAILABLE and greeting:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    generate_greeting_with_gemini(greeting, language, gender)
                )
            finally:
                loop.close()
    except Exception as e:
        print(f"[GREETING] Background regeneration failed: {e}", flush=True)


@router.post("/", response_model=AgentResponse)
def create_agent(
    agent_data: AgentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new voice agent"""
    agent = VoiceAgent(
        user_id=current_user.id,
        **agent_data.model_dump()
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    # Pre-generate TTS greeting in background for instant playback
    if agent.greeting:
        background_tasks.add_task(
            _regenerate_greeting_background,
            agent.greeting,
            agent.language or "fr-FR",
            agent.voice_gender or "male"
        )
    
    return _serialize_agent(agent, current_user.id, db)


@router.get("/", response_model=List[AgentResponse])
def list_agents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all agents for current user (owned and collaborated)"""
    # Get owned agents
    owned_agents = db.query(VoiceAgent).filter(
        VoiceAgent.user_id == current_user.id
    ).all()
    
    # Get collaborated agents
    collaborations = db.query(AgentCollaborator).filter(
        AgentCollaborator.user_id == current_user.id,
        AgentCollaborator.is_active == True
    ).all()
    
    collaborated_agents = [collab.agent for collab in collaborations if collab.agent]
    
    # Combine and deduplicate (in case user is both owner and collaborator)
    all_agents = {agent.id: agent for agent in owned_agents + collaborated_agents}
    
    return [_serialize_agent(agent, current_user.id, db) for agent in all_agents.values()]


@router.get("/public/list", response_model=List[AgentResponse])
def list_public_agents(db: Session = Depends(get_db)):
    """Get all public agents (no authentication required)"""
    agents = db.query(VoiceAgent).filter(
        VoiceAgent.is_public == True,
        VoiceAgent.is_active == True
    ).order_by(VoiceAgent.created_at.desc()).all()
    
    return [_serialize_agent(agent, None, db) for agent in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent (owner or collaborator with view permission)"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return _serialize_agent(agent, current_user.id, db)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an agent (owner or collaborator with edit permission)"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "edit")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found or insufficient permissions")
    
    # Check if greeting changed
    old_greeting = agent.greeting
    
    # Update fields
    update_data = agent_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    
    db.commit()
    db.refresh(agent)
    
    # Regenerate TTS greeting if it changed
    new_greeting = agent.greeting
    if new_greeting and new_greeting != old_greeting:
        background_tasks.add_task(
            _regenerate_greeting_background,
            new_greeting,
            agent.language or "fr-FR",
            agent.voice_gender or "male"
        )
    
    return _serialize_agent(agent, current_user.id, db)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an agent (owner or collaborator with delete permission)"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "delete")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found or insufficient permissions")
    
    db.delete(agent)
    db.commit()
    
    return {"message": "Agent deleted successfully"}


@router.get("/{agent_id}/stats")
def get_agent_stats(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific agent (calls, leads, analytics)"""
    from sqlalchemy import func, distinct
    from app.models import Call
    
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Base query for this agent's calls
    calls_query = db.query(Call).filter(Call.agent_id == agent_id)
    
    # Total calls
    total_calls = calls_query.count()
    
    # Total duration and cost
    totals = calls_query.with_entities(
        func.sum(Call.duration_minutes).label('total_minutes'),
        func.sum(Call.cost).label('total_cost')
    ).first()
    
    # Calls by status
    status_counts = calls_query.with_entities(
        Call.status,
        func.count(Call.id)
    ).group_by(Call.status).all()
    
    # Sentiment breakdown
    sentiment_counts = calls_query.filter(
        Call.sentiment.isnot(None)
    ).with_entities(
        Call.sentiment,
        func.count(Call.id)
    ).group_by(Call.sentiment).all()
    
    # Unique leads (callers with phone numbers)
    unique_leads = calls_query.filter(
        Call.caller_phone.isnot(None)
    ).with_entities(
        func.count(distinct(Call.caller_phone))
    ).scalar() or 0
    
    # Calls with action required
    action_required_count = calls_query.filter(
        Call.callback_requested == True
    ).count()
    
    return {
        "agent_id": agent_id,
        "total_calls": total_calls,
        "total_minutes": round(float(totals.total_minutes or 0), 2),
        "total_cost": round(float(totals.total_cost or 0), 2),
        "unique_leads": unique_leads,
        "action_required": action_required_count,
        "status_breakdown": {str(status.value if hasattr(status, 'value') else status): count for status, count in status_counts},
        "sentiment_breakdown": {sentiment: count for sentiment, count in sentiment_counts if sentiment}
    }


@router.get("/{agent_id}/leads")
def get_agent_leads(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get potential customers (leads) for a specific agent"""
    from sqlalchemy import func, desc
    from app.models import Call
    
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get unique callers with their last call info
    leads_query = db.query(
        Call.caller_phone,
        Call.caller_name,
        func.count(Call.id).label('call_count'),
        func.max(Call.started_at).label('last_contact'),
        func.sum(Call.duration_minutes).label('total_duration')
    ).filter(
        Call.agent_id == agent_id,
        Call.caller_phone.isnot(None)
    ).group_by(
        Call.caller_phone,
        Call.caller_name
    ).order_by(desc('last_contact')).all()
    
    leads = []
    for lead in leads_query:
        # Get the last call's sentiment and action status
        last_call = db.query(Call).filter(
            Call.agent_id == agent_id,
            Call.caller_phone == lead.caller_phone
        ).order_by(desc(Call.started_at)).first()
        
        leads.append({
            "phone": lead.caller_phone,
            "name": lead.caller_name,
            "call_count": lead.call_count,
            "last_contact": last_call.started_at if last_call else None,
            "total_duration": round(float(lead.total_duration or 0), 2),
            "last_sentiment": last_call.sentiment if last_call else None,
            "has_action_required": last_call.callback_requested if last_call else False
        })
    
    return {"leads": leads, "total": len(leads)}


@router.get("/public/demo")
def get_demo_agents(db: Session = Depends(get_db)):
    """Get all public demo agents (no auth required)"""
    agents = db.query(VoiceAgent).filter(
        VoiceAgent.is_public == True,
        VoiceAgent.is_active == True
    ).all()
    
    if not agents:
        raise HTTPException(status_code=404, detail="No demo agents available")
    
    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "language": agent.language,
                "phone_number": agent.phone_number.phone_number if agent.phone_number else None,
                "phone_number_status": getattr(agent.phone_number.status, "value", agent.phone_number.status) if agent.phone_number and agent.phone_number.status else None,
            }
            for agent in agents
        ]
    }

