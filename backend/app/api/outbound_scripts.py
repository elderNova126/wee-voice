from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from datetime import datetime

from app.core.security import get_current_active_user
from app.core.permissions import check_agent_access
from app.models import get_db, User, VoiceAgent, OutboundScript

router = APIRouter()


class OutboundScriptCreate(BaseModel):
    name: str
    description: Optional[str] = None
    opening_message: str
    main_content: Optional[str] = None
    closing_message: Optional[str] = None
    tone: str = "professional"
    objective: Optional[str] = None
    key_points: Optional[str] = None
    objection_handling: Optional[str] = None
    is_favorite: bool = False


class OutboundScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    opening_message: Optional[str] = None
    main_content: Optional[str] = None
    closing_message: Optional[str] = None
    tone: Optional[str] = None
    objective: Optional[str] = None
    key_points: Optional[str] = None
    objection_handling: Optional[str] = None
    is_active: Optional[bool] = None
    is_favorite: Optional[bool] = None


class OutboundScriptResponse(BaseModel):
    id: int
    agent_id: int
    name: str
    description: Optional[str]
    opening_message: str
    main_content: Optional[str]
    closing_message: Optional[str]
    tone: str
    objective: Optional[str]
    key_points: Optional[str]
    objection_handling: Optional[str]
    is_active: bool
    is_favorite: bool
    use_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/agents/{agent_id}/scripts", response_model=List[OutboundScriptResponse])
def list_scripts(
    agent_id: int,
    active_only: bool = Query(False, description="Only return active scripts"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all outbound scripts for an agent"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    query = db.query(OutboundScript).filter(OutboundScript.agent_id == agent_id)
    
    if active_only:
        query = query.filter(OutboundScript.is_active == True)
    
    # Order by favorite first, then by use count
    scripts = query.order_by(
        desc(OutboundScript.is_favorite),
        desc(OutboundScript.use_count),
        desc(OutboundScript.created_at)
    ).all()
    
    return scripts


@router.post("/agents/{agent_id}/scripts", response_model=OutboundScriptResponse)
def create_script(
    agent_id: int,
    script_data: OutboundScriptCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new outbound script for an agent"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "edit")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found or insufficient permissions")
    
    script = OutboundScript(
        agent_id=agent_id,
        user_id=current_user.id,
        **script_data.model_dump()
    )
    
    db.add(script)
    db.commit()
    db.refresh(script)
    
    return script


@router.get("/agents/{agent_id}/scripts/{script_id}", response_model=OutboundScriptResponse)
def get_script(
    agent_id: int,
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific outbound script"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    script = db.query(OutboundScript).filter(
        OutboundScript.id == script_id,
        OutboundScript.agent_id == agent_id
    ).first()
    
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    return script


@router.put("/agents/{agent_id}/scripts/{script_id}", response_model=OutboundScriptResponse)
def update_script(
    agent_id: int,
    script_id: int,
    script_data: OutboundScriptUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an outbound script"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "edit")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found or insufficient permissions")
    
    script = db.query(OutboundScript).filter(
        OutboundScript.id == script_id,
        OutboundScript.agent_id == agent_id
    ).first()
    
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # Update fields
    update_data = script_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(script, field, value)
    
    db.commit()
    db.refresh(script)
    
    return script


@router.delete("/agents/{agent_id}/scripts/{script_id}")
def delete_script(
    agent_id: int,
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an outbound script"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "edit")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found or insufficient permissions")
    
    script = db.query(OutboundScript).filter(
        OutboundScript.id == script_id,
        OutboundScript.agent_id == agent_id
    ).first()
    
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    db.delete(script)
    db.commit()
    
    return {"message": "Script deleted successfully"}


@router.post("/agents/{agent_id}/scripts/{script_id}/toggle-favorite")
def toggle_favorite(
    agent_id: int,
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status of a script"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    script = db.query(OutboundScript).filter(
        OutboundScript.id == script_id,
        OutboundScript.agent_id == agent_id
    ).first()
    
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    script.is_favorite = not script.is_favorite
    db.commit()
    
    return {
        "id": script.id,
        "is_favorite": script.is_favorite,
        "message": f"Script {'added to' if script.is_favorite else 'removed from'} favorites"
    }


@router.post("/agents/{agent_id}/scripts/{script_id}/use")
def record_script_use(
    agent_id: int,
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Record that a script was used (increment use count)"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id, "view")
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    script = db.query(OutboundScript).filter(
        OutboundScript.id == script_id,
        OutboundScript.agent_id == agent_id
    ).first()
    
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    script.use_count += 1
    script.last_used_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Script use recorded", "use_count": script.use_count}

