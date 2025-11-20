from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from datetime import datetime

from app.core.security import get_current_active_user
from app.models import (
    get_db, User, Integration, IntegrationType, 
    IntegrationProvider, IntegrationStatus
)
from app.services.integration_service import get_integration_service

router = APIRouter()


# Pydantic Models

class IntegrationConfig(BaseModel):
    """Flexible config model for integration credentials"""
    pass


class IntegrationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    integration_type: str
    provider: str
    config: Dict[str, Any]
    
    @field_validator('integration_type')
    @classmethod
    def validate_integration_type(cls, v):
        # Normalize to lowercase to match enum values
        v_lower = v.lower() if isinstance(v, str) else v
        try:
            IntegrationType(v_lower)
        except ValueError:
            raise ValueError(f"Invalid integration type. Must be one of: {[t.value for t in IntegrationType]}")
        return v_lower  # Return normalized value
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        # Normalize to lowercase to match enum values
        v_lower = v.lower() if isinstance(v, str) else v
        try:
            IntegrationProvider(v_lower)
        except ValueError:
            raise ValueError(f"Invalid provider. Must be one of: {[p.value for p in IntegrationProvider]}")
        return v_lower  # Return normalized value


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class IntegrationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    integration_type: str
    provider: str
    status: str
    is_active: bool
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IntegrationTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class IntegrationSyncResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class IntegrationTypesResponse(BaseModel):
    """Response model for integration types list"""
    types: List[str]
    providers: List[str]
    type_provider_mapping: Dict[str, List[str]]


# API Endpoints

@router.post("/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
def create_integration(
    integration_data: IntegrationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new integration"""
    # Validate integration type and provider combination
    # Normalize to lowercase to match enum values
    integration_type_str = integration_data.integration_type.lower()
    provider_str = integration_data.provider.lower()
    
    try:
        integration_type = IntegrationType(integration_type_str)
        provider = IntegrationProvider(provider_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integration type or provider: {str(e)}"
        )
    
    # Check if user already has this integration
    existing = db.query(Integration).filter(
        Integration.user_id == current_user.id,
        Integration.integration_type == integration_type,
        Integration.provider == provider,
        Integration.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active integration of this type and provider already exists"
        )
    
    integration = Integration(
        user_id=current_user.id,
        name=integration_data.name,
        description=integration_data.description,
        integration_type=integration_type.value,  # Store enum value as string
        provider=provider.value,  # Store enum value as string
        config=integration_data.config,
        status=IntegrationStatus.INACTIVE.value  # Store enum value as string
    )
    
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    return integration


@router.get("/", response_model=List[IntegrationResponse])
def list_integrations(
    integration_type: Optional[str] = None,
    provider: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all integrations for current user"""
    query = db.query(Integration).filter(Integration.user_id == current_user.id)
    
    if integration_type:
        try:
            # Normalize to lowercase to match enum values
            integration_type_lower = integration_type.lower()
            # Validate the enum value
            enum_type = IntegrationType(integration_type_lower)
            # Compare directly with string value since database uses VARCHAR
            query = query.filter(Integration.integration_type == enum_type.value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid integration type: {integration_type}")
    
    if provider:
        try:
            # Normalize to lowercase to match enum values
            provider_lower = provider.lower()
            # Validate the enum value
            enum_provider = IntegrationProvider(provider_lower)
            # Compare directly with string value since database uses VARCHAR
            query = query.filter(Integration.provider == enum_provider.value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    if is_active is not None:
        query = query.filter(Integration.is_active == is_active)
    
    integrations = query.order_by(Integration.created_at.desc()).all()
    return integrations


@router.get("/{integration_id}", response_model=IntegrationResponse)
def get_integration(
    integration_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific integration"""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    return integration


@router.put("/{integration_id}", response_model=IntegrationResponse)
def update_integration(
    integration_id: int,
    integration_data: IntegrationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an integration"""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Update fields
    update_data = integration_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(integration, field, value)
    
    db.commit()
    db.refresh(integration)
    
    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(
    integration_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an integration"""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    db.delete(integration)
    db.commit()
    
    return None


@router.post("/{integration_id}/test", response_model=IntegrationTestResponse)
async def test_integration(
    integration_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Test an integration connection"""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    try:
        service = get_integration_service(integration)
        success = await service.test_connection()
        
        if success:
            integration.status = IntegrationStatus.ACTIVE.value
            integration.last_error = None
            message = "Connection test successful"
        else:
            integration.status = IntegrationStatus.ERROR.value
            integration.last_error = "Connection test failed"
            message = "Connection test failed"
        
        db.commit()
        
        return IntegrationTestResponse(
            success=success,
            message=message
        )
    except Exception as e:
        integration.status = IntegrationStatus.ERROR.value
        integration.last_error = str(e)
        db.commit()
        
        return IntegrationTestResponse(
            success=False,
            message=f"Connection test error: {str(e)}"
        )


@router.post("/{integration_id}/sync", response_model=IntegrationSyncResponse)
async def sync_integration(
    integration_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Sync data from an integration"""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    if not integration.is_active:
        raise HTTPException(status_code=400, detail="Integration is not active")
    
    try:
        service = get_integration_service(integration)
        result = await service.sync_data()
        
        integration.last_sync_at = datetime.utcnow()
        integration.status = IntegrationStatus.ACTIVE
        integration.last_error = None
        db.commit()
        
        return IntegrationSyncResponse(
            success=True,
            message="Sync completed successfully",
            data=result
        )
    except Exception as e:
        integration.status = IntegrationStatus.ERROR
        integration.last_error = str(e)
        db.commit()
        
        return IntegrationSyncResponse(
            success=False,
            message=f"Sync failed: {str(e)}"
        )


@router.get("/types/list", response_model=IntegrationTypesResponse)
def list_integration_types():
    """List all available integration types and providers"""
    return {
        "types": [t.value for t in IntegrationType],
        "providers": [p.value for p in IntegrationProvider],
        "type_provider_mapping": {
            IntegrationType.CALENDAR.value: [
                IntegrationProvider.GOOGLE_CALENDAR.value,
                IntegrationProvider.OUTLOOK_CALENDAR.value,
                IntegrationProvider.CALENDLY.value,
            ],
            IntegrationType.EMAIL.value: [
                IntegrationProvider.GMAIL.value,
                IntegrationProvider.OUTLOOK_EMAIL.value,
                IntegrationProvider.SMTP.value,
                IntegrationProvider.SENDGRID.value,
            ],
            IntegrationType.CONTACT_MANAGEMENT.value: [
                IntegrationProvider.HUBSPOT_CONTACTS.value,
                IntegrationProvider.SALESFORCE_CONTACTS.value,
                IntegrationProvider.ZAPIER.value,
            ],
            IntegrationType.DATABASE.value: [
                IntegrationProvider.POSTGRESQL.value,
                IntegrationProvider.MYSQL.value,
                IntegrationProvider.MONGODB.value,
                IntegrationProvider.REDIS.value,
            ],
            IntegrationType.CRM.value: [
                IntegrationProvider.HUBSPOT.value,
                IntegrationProvider.SALESFORCE.value,
                IntegrationProvider.PIPEDRIVE.value,
                IntegrationProvider.ZOHO_CRM.value,
            ],
            IntegrationType.ACCOUNTING.value: [
                IntegrationProvider.QUICKBOOKS.value,
                IntegrationProvider.XERO.value,
                IntegrationProvider.SAGE.value,
                IntegrationProvider.WAVE.value,
            ],
            IntegrationType.OTHER.value: [
                IntegrationProvider.WEBHOOK.value,
                IntegrationProvider.REST_API.value,
                IntegrationProvider.CUSTOM.value,
            ],
        }
    }

