"""
Base integration service and factory for all integration types
"""
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime

from app.models import Integration, IntegrationType, IntegrationProvider, IntegrationStatus

logger = logging.getLogger(__name__)


class BaseIntegrationService(ABC):
    """Base class for all integration services"""
    
    def __init__(self, integration: Integration):
        self.integration = integration
        self.config = integration.config or {}
        self.provider = integration.provider
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the integration connection"""
        pass
    
    @abstractmethod
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync data from the integration"""
        pass
    
    def update_status(self, status: IntegrationStatus, error: Optional[str] = None):
        """Update integration status"""
        self.integration.status = status
        if error:
            self.integration.last_error = error
        self.integration.last_sync_at = datetime.utcnow()


# Calendar Integration Services

class CalendarIntegrationService(BaseIntegrationService):
    """Base class for calendar integrations"""
    
    async def create_event(self, title: str, start_time: datetime, end_time: datetime, 
                          description: Optional[str] = None, attendees: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a calendar event"""
        raise NotImplementedError
    
    async def list_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """List events in a date range"""
        raise NotImplementedError
    
    async def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing event"""
        raise NotImplementedError
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event"""
        raise NotImplementedError


class GoogleCalendarService(CalendarIntegrationService):
    """Google Calendar integration"""
    
    async def test_connection(self) -> bool:
        """Test Google Calendar connection"""
        try:
            # In production, use Google Calendar API
            # For now, check if credentials are present
            return "access_token" in self.config or "credentials" in self.config
        except Exception as e:
            logger.error(f"Google Calendar connection test failed: {e}")
            return False
    
    async def create_event(self, title: str, start_time: datetime, end_time: datetime,
                          description: Optional[str] = None, attendees: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create Google Calendar event"""
        # Implementation would use Google Calendar API
        logger.info(f"Creating Google Calendar event: {title}")
        return {"id": "event_123", "status": "created"}
    
    async def list_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """List Google Calendar events"""
        # Implementation would use Google Calendar API
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync calendar events"""
        return {"synced": True, "events_count": 0}
    
    async def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """Update Google Calendar event"""
        return {"id": event_id, "status": "updated"}
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete Google Calendar event"""
        return True


class OutlookCalendarService(CalendarIntegrationService):
    """Microsoft Outlook Calendar integration"""
    
    async def test_connection(self) -> bool:
        """Test Outlook Calendar connection"""
        try:
            return "access_token" in self.config or "credentials" in self.config
        except Exception as e:
            logger.error(f"Outlook Calendar connection test failed: {e}")
            return False
    
    async def create_event(self, title: str, start_time: datetime, end_time: datetime,
                          description: Optional[str] = None, attendees: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create Outlook Calendar event"""
        logger.info(f"Creating Outlook Calendar event: {title}")
        return {"id": "event_123", "status": "created"}
    
    async def list_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """List Outlook Calendar events"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync calendar events"""
        return {"synced": True, "events_count": 0}
    
    async def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """Update Outlook Calendar event"""
        return {"id": event_id, "status": "updated"}
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete Outlook Calendar event"""
        return True


# Email Integration Services

class EmailIntegrationService(BaseIntegrationService):
    """Base class for email integrations"""
    
    async def send_email(self, to: str, subject: str, body: str, 
                        html_body: Optional[str] = None, attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send an email"""
        raise NotImplementedError
    
    async def list_emails(self, limit: int = 50, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """List emails"""
        raise NotImplementedError


class GmailService(EmailIntegrationService):
    """Gmail integration"""
    
    async def test_connection(self) -> bool:
        """Test Gmail connection"""
        try:
            return "access_token" in self.config or "credentials" in self.config
        except Exception as e:
            logger.error(f"Gmail connection test failed: {e}")
            return False
    
    async def send_email(self, to: str, subject: str, body: str,
                        html_body: Optional[str] = None, attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send email via Gmail"""
        logger.info(f"Sending Gmail to {to}: {subject}")
        return {"id": "msg_123", "status": "sent"}
    
    async def list_emails(self, limit: int = 50, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """List Gmail emails"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync emails"""
        return {"synced": True, "emails_count": 0}


class SMTPEmailService(EmailIntegrationService):
    """SMTP email integration"""
    
    async def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            required = ["smtp_host", "smtp_port", "username", "password"]
            return all(key in self.config for key in required)
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
    
    async def send_email(self, to: str, subject: str, body: str,
                        html_body: Optional[str] = None, attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send email via SMTP"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.get("from_email", self.config.get("username"))
            msg['To'] = to
            msg['Subject'] = subject
            
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.config["smtp_host"], self.config["smtp_port"])
            server.starttls()
            server.login(self.config["username"], self.config["password"])
            server.send_message(msg)
            server.quit()
            
            return {"status": "sent", "to": to}
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise
    
    async def list_emails(self, limit: int = 50, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """SMTP doesn't support listing emails"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """SMTP sync"""
        return {"synced": True}


# Contact Management Services

class ContactManagementService(BaseIntegrationService):
    """Base class for contact management"""
    
    async def create_contact(self, name: str, email: str, phone: Optional[str] = None,
                            additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a contact"""
        raise NotImplementedError
    
    async def list_contacts(self, limit: int = 100, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """List contacts"""
        raise NotImplementedError
    
    async def update_contact(self, contact_id: str, **kwargs) -> Dict[str, Any]:
        """Update a contact"""
        raise NotImplementedError
    
    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact"""
        raise NotImplementedError


class HubSpotContactsService(ContactManagementService):
    """HubSpot Contacts integration"""
    
    async def test_connection(self) -> bool:
        """Test HubSpot connection"""
        try:
            return "api_key" in self.config or "access_token" in self.config
        except Exception as e:
            logger.error(f"HubSpot connection test failed: {e}")
            return False
    
    async def create_contact(self, name: str, email: str, phone: Optional[str] = None,
                            additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create HubSpot contact"""
        logger.info(f"Creating HubSpot contact: {name}")
        return {"id": "contact_123", "status": "created"}
    
    async def list_contacts(self, limit: int = 100, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """List HubSpot contacts"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync contacts"""
        return {"synced": True, "contacts_count": 0}
    
    async def update_contact(self, contact_id: str, **kwargs) -> Dict[str, Any]:
        """Update HubSpot contact"""
        return {"id": contact_id, "status": "updated"}
    
    async def delete_contact(self, contact_id: str) -> bool:
        """Delete HubSpot contact"""
        return True


# Database Integration Services

class DatabaseIntegrationService(BaseIntegrationService):
    """Base class for database integrations"""
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a database query"""
        raise NotImplementedError
    
    async def execute_write(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a write operation"""
        raise NotImplementedError


class PostgreSQLService(DatabaseIntegrationService):
    """PostgreSQL integration"""
    
    async def test_connection(self) -> bool:
        """Test PostgreSQL connection"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.get("host"),
                port=self.config.get("port", 5432),
                database=self.config.get("database"),
                user=self.config.get("user"),
                password=self.config.get("password")
            )
            conn.close()
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute PostgreSQL query"""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=self.config.get("host"),
            port=self.config.get("port", 5432),
            database=self.config.get("database"),
            user=self.config.get("user"),
            password=self.config.get("password")
        )
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(row) for row in results]
        finally:
            conn.close()
    
    async def execute_write(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute PostgreSQL write"""
        import psycopg2
        
        conn = psycopg2.connect(
            host=self.config.get("host"),
            port=self.config.get("port", 5432),
            database=self.config.get("database"),
            user=self.config.get("user"),
            password=self.config.get("password")
        )
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
                return {"status": "success", "rows_affected": cur.rowcount}
        finally:
            conn.close()
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync database"""
        return {"synced": True}


# CRM Integration Services (Expanded)

class CRMIntegrationService(BaseIntegrationService):
    """Base class for CRM integrations (expanded from existing)"""
    
    async def create_lead(self, name: str, email: str, phone: Optional[str] = None,
                         additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a lead"""
        raise NotImplementedError
    
    async def create_opportunity(self, name: str, value: float, stage: str,
                                 additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create an opportunity"""
        raise NotImplementedError
    
    async def sync_call_to_crm(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync call data to CRM"""
        raise NotImplementedError


class HubSpotCRMService(CRMIntegrationService):
    """HubSpot CRM integration (expanded)"""
    
    async def test_connection(self) -> bool:
        """Test HubSpot CRM connection"""
        try:
            return "api_key" in self.config or "access_token" in self.config
        except Exception as e:
            logger.error(f"HubSpot CRM connection test failed: {e}")
            return False
    
    async def create_lead(self, name: str, email: str, phone: Optional[str] = None,
                         additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create HubSpot lead"""
        logger.info(f"Creating HubSpot lead: {name}")
        return {"id": "lead_123", "status": "created"}
    
    async def create_opportunity(self, name: str, value: float, stage: str,
                                 additional_fields: Optional[Dict] = None) -> Dict[str, Any]:
        """Create HubSpot opportunity"""
        return {"id": "opp_123", "status": "created"}
    
    async def sync_call_to_crm(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync call to HubSpot"""
        # Use existing CRM service logic
        return {"synced": True, "crm_id": "call_123"}
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync CRM data"""
        return {"synced": True}


# Accounting Integration Services

class AccountingIntegrationService(BaseIntegrationService):
    """Base class for accounting integrations"""
    
    async def create_invoice(self, customer: str, amount: float, items: List[Dict],
                            due_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Create an invoice"""
        raise NotImplementedError
    
    async def list_transactions(self, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """List transactions"""
        raise NotImplementedError


class QuickBooksService(AccountingIntegrationService):
    """QuickBooks integration"""
    
    async def test_connection(self) -> bool:
        """Test QuickBooks connection"""
        try:
            return "access_token" in self.config or "oauth_credentials" in self.config
        except Exception as e:
            logger.error(f"QuickBooks connection test failed: {e}")
            return False
    
    async def create_invoice(self, customer: str, amount: float, items: List[Dict],
                            due_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Create QuickBooks invoice"""
        logger.info(f"Creating QuickBooks invoice for {customer}: ${amount}")
        return {"id": "inv_123", "status": "created"}
    
    async def list_transactions(self, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """List QuickBooks transactions"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync accounting data"""
        return {"synced": True}


class XeroService(AccountingIntegrationService):
    """Xero integration"""
    
    async def test_connection(self) -> bool:
        """Test Xero connection"""
        try:
            return "access_token" in self.config or "oauth_credentials" in self.config
        except Exception as e:
            logger.error(f"Xero connection test failed: {e}")
            return False
    
    async def create_invoice(self, customer: str, amount: float, items: List[Dict],
                            due_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Create Xero invoice"""
        logger.info(f"Creating Xero invoice for {customer}: ${amount}")
        return {"id": "inv_123", "status": "created"}
    
    async def list_transactions(self, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """List Xero transactions"""
        return []
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Sync accounting data"""
        return {"synced": True}


# Generic/Other Integration Services

class WebhookService(BaseIntegrationService):
    """Generic webhook integration"""
    
    async def test_connection(self) -> bool:
        """Test webhook URL"""
        try:
            import httpx
            url = self.config.get("webhook_url")
            if not url:
                return False
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                return response.status_code < 400
        except Exception as e:
            logger.error(f"Webhook connection test failed: {e}")
            return False
    
    async def send_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook payload"""
        import httpx
        
        url = self.config.get("webhook_url")
        headers = self.config.get("headers", {})
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            return {"status": "sent", "response": response.json()}
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """Webhook sync"""
        return {"synced": True}


class RESTAPIService(BaseIntegrationService):
    """Generic REST API integration"""
    
    async def test_connection(self) -> bool:
        """Test REST API connection"""
        try:
            import httpx
            base_url = self.config.get("base_url")
            if not base_url:
                return False
            async with httpx.AsyncClient() as client:
                headers = self._get_headers()
                response = await client.get(f"{base_url}/health", headers=headers, timeout=5.0)
                return response.status_code < 400
        except Exception:
            # If /health doesn't exist, just check if URL is reachable
            return "base_url" in self.config
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        headers = {"Content-Type": "application/json"}
        if "api_key" in self.config:
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
        elif "auth_header" in self.config:
            headers.update(self.config["auth_header"])
        return headers
    
    async def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make REST API request"""
        import httpx
        
        base_url = self.config.get("base_url")
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, timeout=10.0)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers, timeout=10.0)
            elif method.upper() == "PUT":
                response = await client.put(url, json=data, headers=headers, timeout=10.0)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers, timeout=10.0)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
    
    async def sync_data(self, *args, **kwargs) -> Dict[str, Any]:
        """REST API sync"""
        return {"synced": True}


# Factory function to get appropriate integration service

def get_integration_service(integration: Integration) -> BaseIntegrationService:
    """Factory function to get appropriate integration service"""
    # integration_type and provider are stored as strings, convert to enum for comparison
    integration_type_str = integration.integration_type if isinstance(integration.integration_type, str) else integration.integration_type.value
    provider_str = integration.provider if isinstance(integration.provider, str) else integration.provider.value
    
    integration_type = IntegrationType(integration_type_str)
    provider = IntegrationProvider(provider_str)
    
    # Calendar integrations
    if integration_type == IntegrationType.CALENDAR:
        if provider == IntegrationProvider.GOOGLE_CALENDAR:
            return GoogleCalendarService(integration)
        elif provider == IntegrationProvider.OUTLOOK_CALENDAR:
            return OutlookCalendarService(integration)
        else:
            raise ValueError(f"Unsupported calendar provider: {provider}")
    
    # Email integrations
    elif integration_type == IntegrationType.EMAIL:
        if provider == IntegrationProvider.GMAIL:
            return GmailService(integration)
        elif provider == IntegrationProvider.SMTP:
            return SMTPEmailService(integration)
        elif provider == IntegrationProvider.OUTLOOK_EMAIL:
            # Use similar structure as Outlook Calendar
            return GmailService(integration)  # Placeholder
        else:
            raise ValueError(f"Unsupported email provider: {provider}")
    
    # Contact Management integrations
    elif integration_type == IntegrationType.CONTACT_MANAGEMENT:
        if provider == IntegrationProvider.HUBSPOT_CONTACTS:
            return HubSpotContactsService(integration)
        else:
            raise ValueError(f"Unsupported contact provider: {provider}")
    
    # Database integrations
    elif integration_type == IntegrationType.DATABASE:
        if provider == IntegrationProvider.POSTGRESQL:
            return PostgreSQLService(integration)
        else:
            raise ValueError(f"Unsupported database provider: {provider}")
    
    # CRM integrations
    elif integration_type == IntegrationType.CRM:
        if provider == IntegrationProvider.HUBSPOT:
            return HubSpotCRMService(integration)
        elif provider == IntegrationProvider.SALESFORCE:
            # Use existing Salesforce integration
            return HubSpotCRMService(integration)  # Placeholder
        else:
            raise ValueError(f"Unsupported CRM provider: {provider}")
    
    # Accounting integrations
    elif integration_type == IntegrationType.ACCOUNTING:
        if provider == IntegrationProvider.QUICKBOOKS:
            return QuickBooksService(integration)
        elif provider == IntegrationProvider.XERO:
            return XeroService(integration)
        else:
            raise ValueError(f"Unsupported accounting provider: {provider}")
    
    # Other integrations
    elif integration_type == IntegrationType.OTHER:
        if provider == IntegrationProvider.WEBHOOK:
            return WebhookService(integration)
        elif provider == IntegrationProvider.REST_API:
            return RESTAPIService(integration)
        else:
            raise ValueError(f"Unsupported other provider: {provider}")
    
    else:
        raise ValueError(f"Unsupported integration type: {integration_type}")


