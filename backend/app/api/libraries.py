from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.security import get_current_active_user, get_current_admin_user
from app.models import get_db, User, AgentLibrary, LibraryCategory

router = APIRouter()


class LibraryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: LibraryCategory = LibraryCategory.GENERAL
    tags: List[str] = Field(default_factory=list)
    icon: Optional[str] = None
    language: str = "fr-FR"
    system_prompt: str
    greeting: Optional[str] = None
    voice_id: str = "Charon"
    voice_gender: str = "male"
    agent_config: Optional[dict] = None
    tools_enabled: List[str] = Field(default_factory=list)
    model_name: str = "gemini-2.5-flash-native-audio-preview-09-2025"
    temperature: str = "0.7"
    max_tokens: int = 1000
    rag_enabled: bool = False
    rag_config: Optional[dict] = None
    crm_enabled: bool = False
    crm_config: Optional[dict] = None
    is_public: bool = False


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[LibraryCategory] = None
    tags: Optional[List[str]] = None
    icon: Optional[str] = None
    language: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting: Optional[str] = None
    voice_id: Optional[str] = None
    voice_gender: Optional[str] = None
    agent_config: Optional[dict] = None
    tools_enabled: Optional[List[str]] = None
    model_name: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    rag_enabled: Optional[bool] = None
    rag_config: Optional[dict] = None
    crm_enabled: Optional[bool] = None
    crm_config: Optional[dict] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None
    usage_count: Optional[int] = None  # Allow updating usage count


class LibraryResponse(BaseModel):
    id: int
    user_id: Optional[int]
    is_public: bool
    name: str
    description: Optional[str]
    category: str
    tags: List[str]
    icon: Optional[str]
    language: str
    system_prompt: str
    greeting: Optional[str]
    voice_id: str
    voice_gender: str
    agent_config: Optional[dict]
    tools_enabled: List[str]
    model_name: str
    temperature: str
    max_tokens: int
    rag_enabled: bool
    rag_config: Optional[dict]
    crm_enabled: bool
    crm_config: Optional[dict]
    usage_count: int
    saved_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[int]
    can_edit: bool = False  # Whether current user can edit this library
    can_delete: bool = False  # Whether current user can delete this library
    
    class Config:
        from_attributes = True


@router.get("/public", response_model=List[LibraryResponse])
def list_public_libraries(
    category: Optional[LibraryCategory] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all public libraries (available to all users)"""
    query = db.query(AgentLibrary).filter(
        AgentLibrary.is_public == True,
        AgentLibrary.is_active == True
    )
    
    if category:
        query = query.filter(AgentLibrary.category == category)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AgentLibrary.name.ilike(search_term),
                AgentLibrary.description.ilike(search_term),
                AgentLibrary.system_prompt.ilike(search_term)
            )
        )
    
    libraries = query.order_by(desc(AgentLibrary.usage_count), desc(AgentLibrary.created_at)).all()
    
    result = []
    for lib in libraries:
        lib_dict = LibraryResponse.model_validate(lib)
        # Only admins can edit/delete public libraries
        if current_user:
            lib_dict.can_edit = current_user.is_superuser
            lib_dict.can_delete = current_user.is_superuser
        else:
            lib_dict.can_edit = False
            lib_dict.can_delete = False
        result.append(lib_dict)
    
    return result


@router.get("/my", response_model=List[LibraryResponse])
def list_my_libraries(
    category: Optional[LibraryCategory] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List libraries saved by the current user"""
    query = db.query(AgentLibrary).filter(
        AgentLibrary.user_id == current_user.id
    )
    
    if category:
        query = query.filter(AgentLibrary.category == category)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AgentLibrary.name.ilike(search_term),
                AgentLibrary.description.ilike(search_term),
                AgentLibrary.system_prompt.ilike(search_term)
            )
        )
    
    libraries = query.order_by(desc(AgentLibrary.created_at)).all()
    
    result = []
    for lib in libraries:
        lib_dict = LibraryResponse.model_validate(lib)
        # Users can always edit/delete their own libraries
        lib_dict.can_edit = True
        lib_dict.can_delete = True
        result.append(lib_dict)
    
    return result


@router.post("/save/{library_id}")
def save_library_to_my_libraries(
    library_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save a public library to user's personal libraries"""
    # Get the public library
    public_lib = db.query(AgentLibrary).filter(
        AgentLibrary.id == library_id,
        AgentLibrary.is_public == True
    ).first()
    
    if not public_lib:
        raise HTTPException(status_code=404, detail="Public library not found")
    
    # Check if user already has this library saved
    existing = db.query(AgentLibrary).filter(
        AgentLibrary.user_id == current_user.id,
        AgentLibrary.name == public_lib.name,
        AgentLibrary.is_public == False
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Library already saved to your collection")
    
    # Create a copy for the user
    user_lib = AgentLibrary(
        user_id=current_user.id,
        is_public=False,
        name=public_lib.name,
        description=public_lib.description,
        category=public_lib.category,
        tags=public_lib.tags.copy() if public_lib.tags else [],
        icon=public_lib.icon,
        language=public_lib.language,
        system_prompt=public_lib.system_prompt,
        greeting=public_lib.greeting,
        voice_id=public_lib.voice_id,
        voice_gender=public_lib.voice_gender,
        agent_config=public_lib.agent_config.copy() if public_lib.agent_config else None,
        tools_enabled=public_lib.tools_enabled.copy() if public_lib.tools_enabled else [],
        model_name=public_lib.model_name,
        temperature=public_lib.temperature,
        max_tokens=public_lib.max_tokens,
        rag_enabled=public_lib.rag_enabled,
        rag_config=public_lib.rag_config.copy() if public_lib.rag_config else None,
        crm_enabled=public_lib.crm_enabled,
        crm_config=public_lib.crm_config.copy() if public_lib.crm_config else None,
        created_by_user_id=public_lib.created_by_user_id,
    )
    
    db.add(user_lib)
    
    # Increment saved count on public library
    public_lib.saved_count = (public_lib.saved_count or 0) + 1
    
    db.commit()
    db.refresh(user_lib)
    
    return {"message": "Library saved successfully", "library": LibraryResponse.model_validate(user_lib)}


@router.post("/", response_model=LibraryResponse)
def create_library(
    library_data: LibraryCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new library (admin can create public, users create private)"""
    # Only admins can create public libraries
    if library_data.is_public and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can create public libraries")
    
    library = AgentLibrary(
        user_id=None if library_data.is_public else current_user.id,
        is_public=library_data.is_public,
        name=library_data.name,
        description=library_data.description,
        category=library_data.category,
        tags=library_data.tags,
        icon=library_data.icon,
        language=library_data.language,
        system_prompt=library_data.system_prompt,
        greeting=library_data.greeting,
        voice_id=library_data.voice_id,
        voice_gender=library_data.voice_gender,
        agent_config=library_data.agent_config,
        tools_enabled=library_data.tools_enabled,
        model_name=library_data.model_name,
        temperature=library_data.temperature,
        max_tokens=library_data.max_tokens,
        rag_enabled=library_data.rag_enabled,
        rag_config=library_data.rag_config,
        crm_enabled=library_data.crm_enabled,
        crm_config=library_data.crm_config,
        created_by_user_id=current_user.id,
    )
    
    db.add(library)
    db.commit()
    db.refresh(library)
    
    lib_dict = LibraryResponse.model_validate(library)
    lib_dict.can_edit = True
    lib_dict.can_delete = True
    
    return lib_dict


@router.get("/{library_id}", response_model=LibraryResponse)
def get_library(
    library_id: int,
    current_user: Optional[User] = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific library"""
    library = db.query(AgentLibrary).filter(AgentLibrary.id == library_id).first()
    
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    # Check access: public libraries are accessible to all, private only to owner
    if not library.is_public and (not current_user or library.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    lib_dict = LibraryResponse.model_validate(library)
    
    # Set permissions
    if current_user:
        if library.is_public:
            # Only admins can edit/delete public libraries
            lib_dict.can_edit = current_user.is_superuser
            lib_dict.can_delete = current_user.is_superuser
        else:
            # Users can edit/delete their own libraries
            lib_dict.can_edit = library.user_id == current_user.id
            lib_dict.can_delete = library.user_id == current_user.id
    
    return lib_dict


@router.put("/{library_id}", response_model=LibraryResponse)
def update_library(
    library_id: int,
    library_data: LibraryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a library (only owner or admin for public libraries)"""
    library = db.query(AgentLibrary).filter(AgentLibrary.id == library_id).first()
    
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    # Check permissions
    if library.is_public:
        # Only admins can edit public libraries
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Only admins can edit public libraries")
    else:
        # Only owner can edit private libraries
        if library.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Prevent users from making their libraries public (only admins can)
    if library_data.is_public is not None and library_data.is_public and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can make libraries public")
    
    # Update fields
    update_data = library_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(library, field, value)
    
    db.commit()
    db.refresh(library)
    
    lib_dict = LibraryResponse.model_validate(library)
    lib_dict.can_edit = True
    lib_dict.can_delete = True
    
    return lib_dict


@router.delete("/{library_id}")
def delete_library(
    library_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a library (only owner or admin for public libraries)"""
    library = db.query(AgentLibrary).filter(AgentLibrary.id == library_id).first()
    
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    # Check permissions
    if library.is_public:
        # Only admins can delete public libraries
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Only admins can delete public libraries")
    else:
        # Only owner can delete private libraries
        if library.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(library)
    db.commit()
    
    return {"message": "Library deleted successfully"}


@router.get("/categories/list", response_model=List[str])
def list_categories():
    """Get list of all available library categories"""
    return [category.value for category in LibraryCategory]

