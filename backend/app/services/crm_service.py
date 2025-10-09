import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from app.models import Call, VoiceAgent

logger = logging.getLogger(__name__)


class CRMIntegrationService:
    """Service for integrating with external CRM systems"""
    
    def __init__(self, agent: VoiceAgent):
        self.agent = agent
        self.webhook_url = agent.crm_webhook_url
        self.config = agent.crm_config or {}
    
    async def sync_call(self, call: Call) -> bool:
        """Sync call data to CRM"""
        if not self.webhook_url:
            return False
        
        try:
            payload = self._prepare_payload(call)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                    headers=self._get_headers()
                )
                
                response.raise_for_status()
                
                # Store response
                call.crm_synced = True
                call.crm_response = response.json()
                
                # Extract CRM record ID if available
                if "id" in call.crm_response:
                    call.crm_record_id = call.crm_response["id"]
                elif "record_id" in call.crm_response:
                    call.crm_record_id = call.crm_response["record_id"]
                
                logger.info(f"Successfully synced call {call.id} to CRM")
                return True
        
        except Exception as e:
            logger.error(f"Failed to sync call {call.id} to CRM: {e}")
            call.crm_response = {"error": str(e)}
            return False
    
    def _prepare_payload(self, call: Call) -> Dict[str, Any]:
        """Prepare call data for CRM webhook"""
        payload = {
            "call_id": call.session_id,
            "agent_name": self.agent.name,
            "duration_seconds": call.duration_seconds,
            "duration_minutes": call.duration_minutes,
            "status": call.status.value,
            "started_at": call.started_at.isoformat(),
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "transcript": call.transcript,
            "summary": call.summary,
            "sentiment": call.sentiment,
            "key_points": call.key_points,
        }
        
        # Add caller information if available
        if call.caller_phone:
            payload["caller"] = {
                "phone": call.caller_phone,
                "name": call.caller_name,
                "metadata": call.caller_metadata
            }
        
        # Add custom fields from config
        if "custom_fields" in self.config:
            payload.update(self.config["custom_fields"])
        
        return payload
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for CRM webhook request"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VoiceAgent-SaaS/1.0"
        }
        
        # Add authentication if configured
        if "api_key" in self.config:
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
        elif "auth_header" in self.config:
            headers.update(self.config["auth_header"])
        
        return headers


class HubSpotIntegration(CRMIntegrationService):
    """Specialized integration for HubSpot"""
    
    def _prepare_payload(self, call: Call) -> Dict[str, Any]:
        """Prepare HubSpot-specific payload"""
        return {
            "properties": {
                "hs_timestamp": call.started_at.isoformat(),
                "hs_call_title": f"Call with {self.agent.name}",
                "hs_call_duration": int(call.duration_seconds * 1000),  # milliseconds
                "hs_call_status": "COMPLETED",
                "hs_call_body": call.transcript or "",
                "hs_call_recording_url": call.recording_url,
            }
        }


class SalesforceIntegration(CRMIntegrationService):
    """Specialized integration for Salesforce"""
    
    def _prepare_payload(self, call: Call) -> Dict[str, Any]:
        """Prepare Salesforce-specific payload"""
        return {
            "Subject": f"Call - {call.session_id}",
            "ActivityDate": call.started_at.date().isoformat(),
            "DurationInSeconds": int(call.duration_seconds),
            "Status": "Completed",
            "Description": call.transcript or "",
            "CallType": "Inbound",
        }


def get_crm_integration(agent: VoiceAgent) -> CRMIntegrationService:
    """Factory function to get appropriate CRM integration"""
    crm_type = agent.crm_config.get("type", "generic") if agent.crm_config else "generic"
    
    if crm_type == "hubspot":
        return HubSpotIntegration(agent)
    elif crm_type == "salesforce":
        return SalesforceIntegration(agent)
    else:
        return CRMIntegrationService(agent)

