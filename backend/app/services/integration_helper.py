"""
Helper utilities for using integrations in voice agents
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import Integration, IntegrationType, VoiceAgent
from app.services.integration_service import get_integration_service

logger = logging.getLogger(__name__)


class IntegrationHelper:
    """Helper class for managing integrations in voice agents"""
    
    def __init__(self, db: Session, agent: VoiceAgent):
        self.db = db
        self.agent = agent
        self.user_id = agent.user_id
    
    def get_user_integrations(
        self,
        integration_type: Optional[IntegrationType] = None,
        is_active: bool = True
    ) -> List[Integration]:
        """Get user integrations, optionally filtered by type"""
        query = self.db.query(Integration).filter(
            Integration.user_id == self.user_id,
            Integration.is_active == is_active
        )
        
        if integration_type:
            query = query.filter(Integration.integration_type == integration_type)
        
        return query.all()
    
    def get_integration_service_by_type(
        self,
        integration_type: IntegrationType,
        provider: Optional[str] = None
    ) -> Optional[Any]:
        """Get integration service by type (returns first matching active integration)"""
        integrations = self.get_user_integrations(integration_type=integration_type)
        
        if provider:
            integrations = [i for i in integrations if i.provider.value == provider]
        
        if integrations:
            return get_integration_service(integrations[0])
        
        return None
    
    def get_calendar_service(self) -> Optional[Any]:
        """Get calendar integration service"""
        return self.get_integration_service_by_type(IntegrationType.CALENDAR)
    
    def get_email_service(self) -> Optional[Any]:
        """Get email integration service"""
        return self.get_integration_service_by_type(IntegrationType.EMAIL)
    
    def get_contact_service(self) -> Optional[Any]:
        """Get contact management integration service"""
        return self.get_integration_service_by_type(IntegrationType.CONTACT_MANAGEMENT)
    
    def get_database_service(self) -> Optional[Any]:
        """Get database integration service"""
        return self.get_integration_service_by_type(IntegrationType.DATABASE)
    
    def get_crm_service(self) -> Optional[Any]:
        """Get CRM integration service"""
        return self.get_integration_service_by_type(IntegrationType.CRM)
    
    def get_accounting_service(self) -> Optional[Any]:
        """Get accounting integration service"""
        return self.get_integration_service_by_type(IntegrationType.ACCOUNTING)
    
    def create_agent_tools(self) -> List[Dict[str, Any]]:
        """Create LangChain/LangGraph tools from active integrations"""
        tools = []
        
        # Calendar tools
        calendar_service = self.get_calendar_service()
        if calendar_service:
            tools.extend(self._create_calendar_tools(calendar_service))
        
        # Email tools
        email_service = self.get_email_service()
        if email_service:
            tools.extend(self._create_email_tools(email_service))
        
        # Contact management tools
        contact_service = self.get_contact_service()
        if contact_service:
            tools.extend(self._create_contact_tools(contact_service))
        
        # CRM tools
        crm_service = self.get_crm_service()
        if crm_service:
            tools.extend(self._create_crm_tools(crm_service))
        
        # Accounting tools
        accounting_service = self.get_accounting_service()
        if accounting_service:
            tools.extend(self._create_accounting_tools(accounting_service))
        
        return tools
    
    def _create_calendar_tools(self, service: Any) -> List[Dict[str, Any]]:
        """Create calendar-related tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_calendar_event",
                    "description": "Create a calendar event/appointment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Event title"},
                            "start_time": {"type": "string", "description": "Start time (ISO format)"},
                            "end_time": {"type": "string", "description": "End time (ISO format)"},
                            "description": {"type": "string", "description": "Event description"},
                            "attendees": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of attendee email addresses"
                            }
                        },
                        "required": ["title", "start_time", "end_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_calendar_events",
                    "description": "List calendar events in a date range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date (ISO format)"},
                            "end_date": {"type": "string", "description": "End date (ISO format)"}
                        },
                        "required": ["start_date", "end_date"]
                    }
                }
            }
        ]
    
    def _create_email_tools(self, service: Any) -> List[Dict[str, Any]]:
        """Create email-related tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "send_email",
                    "description": "Send an email",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body text"},
                            "html_body": {"type": "string", "description": "HTML email body (optional)"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                }
            }
        ]
    
    def _create_contact_tools(self, service: Any) -> List[Dict[str, Any]]:
        """Create contact management tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_contact",
                    "description": "Create a new contact",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Contact name"},
                            "email": {"type": "string", "description": "Contact email"},
                            "phone": {"type": "string", "description": "Contact phone number"}
                        },
                        "required": ["name", "email"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_contacts",
                    "description": "Search for contacts",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "description": "Maximum number of results"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    
    def _create_crm_tools(self, service: Any) -> List[Dict[str, Any]]:
        """Create CRM-related tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_lead",
                    "description": "Create a CRM lead",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Lead name"},
                            "email": {"type": "string", "description": "Lead email"},
                            "phone": {"type": "string", "description": "Lead phone"},
                            "company": {"type": "string", "description": "Company name"}
                        },
                        "required": ["name", "email"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_opportunity",
                    "description": "Create a CRM opportunity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Opportunity name"},
                            "value": {"type": "number", "description": "Opportunity value"},
                            "stage": {"type": "string", "description": "Opportunity stage"}
                        },
                        "required": ["name", "value"]
                    }
                }
            }
        ]
    
    def _create_accounting_tools(self, service: Any) -> List[Dict[str, Any]]:
        """Create accounting-related tools"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_invoice",
                    "description": "Create an invoice",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer": {"type": "string", "description": "Customer name"},
                            "amount": {"type": "number", "description": "Invoice amount"},
                            "description": {"type": "string", "description": "Invoice description"}
                        },
                        "required": ["customer", "amount"]
                    }
                }
            }
        ]
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Any:
        """Execute a tool function by name"""
        # Calendar tools
        if tool_name == "create_calendar_event":
            service = self.get_calendar_service()
            if service:
                from datetime import datetime
                return await service.create_event(
                    title=parameters["title"],
                    start_time=datetime.fromisoformat(parameters["start_time"]),
                    end_time=datetime.fromisoformat(parameters["end_time"]),
                    description=parameters.get("description"),
                    attendees=parameters.get("attendees", [])
                )
        
        elif tool_name == "list_calendar_events":
            service = self.get_calendar_service()
            if service:
                from datetime import datetime
                return await service.list_events(
                    start_date=datetime.fromisoformat(parameters["start_date"]),
                    end_date=datetime.fromisoformat(parameters["end_date"])
                )
        
        # Email tools
        elif tool_name == "send_email":
            service = self.get_email_service()
            if service:
                return await service.send_email(
                    to=parameters["to"],
                    subject=parameters["subject"],
                    body=parameters["body"],
                    html_body=parameters.get("html_body")
                )
        
        # Contact tools
        elif tool_name == "create_contact":
            service = self.get_contact_service()
            if service:
                return await service.create_contact(
                    name=parameters["name"],
                    email=parameters["email"],
                    phone=parameters.get("phone")
                )
        
        # CRM tools
        elif tool_name == "create_lead":
            service = self.get_crm_service()
            if service:
                return await service.create_lead(
                    name=parameters["name"],
                    email=parameters["email"],
                    phone=parameters.get("phone"),
                    additional_fields={"company": parameters.get("company")}
                )
        
        elif tool_name == "create_opportunity":
            service = self.get_crm_service()
            if service:
                return await service.create_opportunity(
                    name=parameters["name"],
                    value=parameters["value"],
                    stage=parameters.get("stage", "new")
                )
        
        # Accounting tools
        elif tool_name == "create_invoice":
            service = self.get_accounting_service()
            if service:
                return await service.create_invoice(
                    customer=parameters["customer"],
                    amount=parameters["amount"],
                    items=[{"description": parameters.get("description", ""), "amount": parameters["amount"]}]
                )
        
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


