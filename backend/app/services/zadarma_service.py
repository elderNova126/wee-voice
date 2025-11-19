"""
Zadarma Integration Service
Handles phone number provisioning and management via Zadarma API
"""
import json
import logging
import hashlib
import hmac
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, Sequence

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import VoiceAgent
from app.models.zadarma import (
    PhoneNumber,
    PhoneNumberStatus,
    VerificationDocument,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class ZadarmaService:
    """Service for interacting with Zadarma API"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'ZADARMA_API_KEY', None)
        self.api_secret = getattr(settings, 'ZADARMA_API_SECRET', None)
        self.base_url = "https://api.zadarma.com/v1"
        
        # PBX credentials (optional, for PBX extension management)
        self.pbx_server = getattr(settings, 'ZADARMA_PBX_SERVER', None)
        self.pbx_login = getattr(settings, 'ZADARMA_PBX_LOGIN', None)
        self.pbx_password = getattr(settings, 'ZADARMA_PBX_PASSWORD', None)
        self.pbx_id = getattr(settings, 'ZADARMA_PBX_ID', None)
    
    # -------------------------------------------------------------------------
    # Low-level helpers
    # -------------------------------------------------------------------------
    def _generate_signature(self, method: str, params: str) -> str:
        """Generate HMAC signature for Zadarma API request"""
        if not self.api_secret:
            raise ValueError("ZADARMA_API_SECRET not configured")
        
        message = method + params + hashlib.md5(params.encode()).hexdigest()
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha1
        ).hexdigest()
        
        return signature
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict[str, Any]:
        """Make authenticated request to Zadarma API"""
        if not self.api_key or not self.api_secret:
            logger.warning("Zadarma API credentials not configured. Using mock mode.")
            return self._mock_response(endpoint, method, params)
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params_str = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = self._generate_signature(endpoint, params_str)
        
        headers = {
            "Authorization": f"{self.api_key}:{signature}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=headers)
            else:
                response = requests.post(url, data=params, headers=headers)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Zadarma API request failed: {e}")
            raise
    
    def _mock_response(self, endpoint: str, method: str, params: Dict) -> Dict[str, Any]:
        """Mock responses for development without Zadarma credentials"""
        params = params or {}
        if "available_numbers" in endpoint:
            return {
                "status": "success",
                "numbers": [
                    {
                        "number": "+33123456789",
                        "country": "FR",
                        "type": "local",
                        "monthly_cost": "4.99",
                        "setup_cost": "0.00"
                    },
                    {
                        "number": "+33987654321",
                        "country": "FR",
                        "type": "local",
                        "monthly_cost": "4.99",
                        "setup_cost": "0.00"
                    }
                ]
            }
        if "request/number" in endpoint:
            return {
                "status": "success",
                "number_id": f"MOCK_{datetime.utcnow().timestamp()}",
                "message": "Number request submitted. Awaiting document verification."
            }
        if "info/number_status" in endpoint:
            return {
                "status": "success",
                "number_status": "pending_documents",
                "message": "Waiting for verification documents"
            }
        if "pbx/internal" in endpoint:
            return {
                "status": "success",
                "extension": params.get("extension", "2001")
            }
        if "pbx/set_scenario" in endpoint:
            return {
                "status": "success",
                "scenario_id": f"SCN-MOCK-{datetime.utcnow().timestamp()}",
                "message": "PBX scenario configured (mock)"
            }
        if "settings/pbx" in endpoint:
            return {
                "status": "success",
                "message": "PBX settings updated (mock)"
            }
        
        return {"status": "success", "message": "Mock response"}
    
    # -------------------------------------------------------------------------
    # Extension helpers
    # -------------------------------------------------------------------------
    def _generate_extension_number(self, db: Session) -> str:
        """Generate a unique PBX extension number"""
        existing_exts = {
            pn.pbx_extension
            for pn in db.query(PhoneNumber)
            .filter(PhoneNumber.pbx_extension.isnot(None))
            .all()
        }
        
        # Use the range 2000-2999 for virtual agents
        for _ in range(1000):
            candidate = str(random.randint(2000, 2999))
            if candidate not in existing_exts:
                return candidate
        
        raise RuntimeError("Failed to generate unique PBX extension number")
    
    async def ensure_agent_extension(
        self,
        db: Session,
        phone_record: PhoneNumber,
        agent: VoiceAgent
    ) -> str:
        """
        Ensure call routing is configured for the agent.
        Prefers SIP if available, falls back to PBX extension.
        """
        # Prefer SIP if available
        sip_id = getattr(settings, 'ZADARMA_SIP_LOGIN', None)
        if sip_id:
            logger.info(f"Using SIP {sip_id} for call routing")
            sip_result = await self.ensure_sip_configured(db, phone_record, agent)
            if sip_result:
                # Return SIP ID as the "extension" identifier for compatibility
                return sip_result
        
        # Fallback to PBX extension if no SIP
        if phone_record.pbx_extension:
            return phone_record.pbx_extension
        
        extension = self._generate_extension_number(db)
        extension_label = agent.name or f"Agent {agent.id}"
        
        params = {
            "extension": extension,
            "display_name": extension_label,
            "forwarding": "webhook",
            "webhook_url": f"{settings.BACKEND_URL}{settings.API_V1_STR}/zadarma/webhook",
            "caller_id": phone_record.phone_number,
        }
        
        # Add PBX credentials if provided (required for PBX extension management)
        if self.pbx_id:
            params["pbx_id"] = self.pbx_id
        if self.pbx_login:
            params["pbx_login"] = self.pbx_login
        if self.pbx_password:
            params["pbx_password"] = self.pbx_password
        
        try:
            response = self._make_request(
                "/pbx/internal/set",
                method="POST",
                params=params
            )
            if response.get("status") != "success":
                logger.warning(
                    "Failed to provision PBX extension in Zadarma",
                    extra={"extension": extension, "response": response}
                )
        except Exception as exc:
            logger.error(
                "Error provisioning PBX extension with Zadarma",
                exc_info=True,
                extra={"extension": extension}
            )
            # In case of failure we still store extension locally so the rest of the
            # configuration can proceed. Operators can reconcile later in Zadarma UI.
        
        phone_record.pbx_extension = extension
        db.commit()
        db.refresh(phone_record)
        
        logger.info(
            "Assigned PBX extension %s to agent %s for number %s",
            extension,
            agent.id,
            phone_record.phone_number,
        )
        return extension
    
    # -------------------------------------------------------------------------
    # SIP helpers
    # -------------------------------------------------------------------------
    def get_sip_list(self) -> List[Dict[str, Any]]:
        """Get list of user's SIP numbers"""
        try:
            response = self._make_request("/sip/", method="GET")
            if response.get("status") == "success":
                return response.get("sips", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get SIP list: {e}")
            return []
    
    def get_sip_status(self, sip_id: str) -> Dict[str, Any]:
        """Get SIP number online status"""
        try:
            response = self._make_request(f"/sip/{sip_id}/status/", method="GET")
            return response
        except Exception as e:
            logger.error(f"Failed to get SIP status for {sip_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_sip_redirection(self, sip_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get SIP redirection settings"""
        try:
            params = {}
            if sip_id:
                params["id"] = sip_id
            response = self._make_request("/sip/redirection/", method="GET", params=params)
            if response.get("status") == "success":
                return response.get("info", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get SIP redirection: {e}")
            return []
    
    def set_sip_redirection_status(self, sip_id: str, status: str = "on") -> Dict[str, Any]:
        """Enable or disable SIP redirection"""
        try:
            params = {
                "id": sip_id,
                "status": status
            }
            response = self._make_request("/sip/redirection/", method="PUT", params=params)
            return response
        except Exception as e:
            logger.error(f"Failed to set SIP redirection status for {sip_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def ensure_sip_configured(
        self,
        db: Session,
        phone_record: PhoneNumber,
        agent: VoiceAgent
    ) -> Optional[str]:
        """
        Ensure SIP is configured for call forwarding.
        Uses SIP ID from settings or finds existing SIP.
        
        Note: SIP redirection API forwards to phone numbers, not webhooks directly.
        Webhook forwarding must be configured in Zadarma Event Notifications.
        
        Returns:
            SIP ID if configured, None otherwise
        """
        # Get SIP ID from settings or phone record
        sip_id = getattr(settings, 'ZADARMA_SIP_LOGIN', None) or phone_record.sip_id
        
        if not sip_id:
            # Try to find an existing SIP
            sips = self.get_sip_list()
            if sips:
                sip_id = sips[0].get("id")
                logger.info(f"Using existing SIP: {sip_id}")
            else:
                logger.warning("No SIP ID found and no existing SIPs available")
                return None
        
        # Store SIP ID in phone record
        phone_record.sip_id = sip_id
        db.commit()
        
        # Enable SIP redirection (webhook is configured in Event Notifications, not here)
        result = self.set_sip_redirection_status(sip_id, status="on")
        if result.get("status") == "success":
            logger.info(f"SIP {sip_id} redirection enabled for phone number {phone_record.phone_number}")
        else:
            logger.warning(f"Failed to enable SIP redirection: {result}")
        
        logger.info(
            f"SIP {sip_id} configured for phone number {phone_record.phone_number}. "
            f"Ensure webhook URL is set in Zadarma Event Notifications."
        )
        
        return sip_id
    
    # -------------------------------------------------------------------------
    # PBX scenario builders
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_business_hours(config: Dict[str, Any]) -> Dict[str, Any]:
        if not config:
            return {
                "timezone": "Europe/Paris",
                "open_time": "09:00",
                "close_time": "18:00",
                "days": ["mon", "tue", "wed", "thu", "fri"],
            }
        
        days = config.get("days") or ["mon", "tue", "wed", "thu", "fri"]
        open_time = config.get("open_time", "09:00")
        close_time = config.get("close_time", "18:00")
        timezone = config.get("timezone", "Europe/Paris")
        
        return {
            "timezone": timezone,
            "open_time": open_time,
            "close_time": close_time,
            "days": days,
        }
    
    @staticmethod
    def _normalize_menu_options(
        menu_options: Sequence[Dict[str, Any]],
        agent_extension: str
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen_keys = set()
        
        for option in menu_options or []:
            key = str(option.get("key", "")).strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            
            destination_type = option.get("destination_type", "agent")
            entry: Dict[str, Any] = {
                "key": key,
                "label": option.get("label") or f"Option {key}",
                "destination_type": destination_type,
            }
            
            if destination_type == "agent":
                entry["destination"] = {
                    "type": "extension",
                    "value": agent_extension,
                }
            elif destination_type == "forward":
                entry["destination"] = {
                    "type": "external",
                    "value": option.get("destination_value"),
                }
            elif destination_type == "voicemail":
                entry["destination"] = {
                    "type": "voicemail",
                    "value": option.get("destination_value", "default"),
                }
            else:
                entry["destination"] = {
                    "type": option.get("destination_type"),
                    "value": option.get("destination_value"),
                }
            
            normalized.append(entry)
        
        if not normalized:
            normalized.append(
                {
                    "key": "1",
                    "label": "Speak with our AI agent",
                    "destination_type": "agent",
                    "destination": {
                        "type": "extension",
                        "value": agent_extension,
                    },
                }
            )
        
        return normalized
    
    @staticmethod
    def _normalize_after_hours(
        config: Dict[str, Any],
        agent_extension: str
    ) -> Dict[str, Any]:
        config = config or {}
        destination_type = config.get("destination_type", "agent")
        
        if destination_type == "agent":
            return {
                "destination_type": "agent",
                "destination": {
                    "type": "extension",
                    "value": agent_extension,
                },
                "message": config.get(
                    "message",
                    "Our offices are closed. Connecting you to our virtual agent.",
                ),
            }
        
        return {
            "destination_type": destination_type,
            "destination": {
                "type": config.get("destination_type"),
                "value": config.get("destination_value"),
            },
            "message": config.get("message"),
        }
    
    def _build_pbx_scenario_payload(
        self,
        phone_number: PhoneNumber,
        business_hours: Dict[str, Any],
        menu_options: List[Dict[str, Any]],
        after_hours: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compose Zadarma PBX scenario payload"""
        return {
            "name": f"WeeVoice-{phone_number.phone_number}",
            "number": phone_number.phone_number,
            "business_hours": business_hours,
            "day_menu": menu_options,
            "after_hours": after_hours,
        }
    
    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    async def get_available_numbers(self, country_code: str = "FR") -> List[Dict[str, Any]]:
        """Get list of available phone numbers for purchase"""
        try:
            response = self._make_request(
                "/info/available_numbers",
                params={"country": country_code}
            )
            
            if response.get("status") == "success":
                return response.get("numbers", [])
            logger.error(f"Failed to get available numbers: {response}")
            return []
        except Exception as e:
            logger.error(f"Error getting available numbers: {e}")
            return []
    
    async def request_phone_number(
        self, 
        db: Session,
        user_id: int,
        phone_number: str,
        country_code: str,
        business_name: str,
        business_type: str,
        business_address: str
    ) -> Optional[PhoneNumber]:
        """Request a new phone number from Zadarma"""
        try:
            # Make API request to Zadarma
            response = self._make_request(
                "/request/number",
                method="POST",
                params={
                    "number": phone_number,
                    "business_name": business_name,
                    "business_type": business_type,
                    "address": business_address
                }
            )
            
            if response.get("status") == "success":
                # Create phone number record in database
                phone_record = PhoneNumber(
                    user_id=user_id,
                    phone_number=phone_number,
                    country_code=country_code,
                    number_type="local",
                    zadarma_number_id=response.get("number_id"),
                    status=PhoneNumberStatus.DOCUMENTS_SUBMITTED,
                    business_name=business_name,
                    business_type=business_type,
                    business_address=business_address,
                    monthly_cost="4.99",
                    per_minute_cost="0.02"
                )
                
                db.add(phone_record)
                db.commit()
                db.refresh(phone_record)
                
                logger.info(f"Phone number {phone_number} requested successfully for user {user_id}")
                return phone_record
            
            logger.error(f"Failed to request phone number: {response}")
            return None
                
        except Exception as e:
            logger.error(f"Error requesting phone number: {e}")
            db.rollback()
            return None
    
    async def check_number_status(self, db: Session, phone_number_id: int) -> bool:
        """Check the status of a phone number request with Zadarma"""
        try:
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
            if not phone_record:
                return False
            
            # Query Zadarma API for status
            response = self._make_request(
                "/info/number_status",
                params={"number_id": phone_record.zadarma_number_id}
            )
            
            if response.get("status") == "success":
                zadarma_status = response.get("number_status")
                
                # Update local status based on Zadarma response
                if zadarma_status == "active":
                    phone_record.status = PhoneNumberStatus.ACTIVE
                    phone_record.activated_at = datetime.utcnow()
                elif zadarma_status == "rejected":
                    phone_record.status = PhoneNumberStatus.REJECTED
                    phone_record.status_message = response.get("message", "Documents rejected")
                elif zadarma_status == "under_review":
                    phone_record.status = PhoneNumberStatus.UNDER_REVIEW
                
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking number status: {e}")
            return False
    
    async def activate_number_for_agent(self, db: Session, phone_number_id: int, agent_id: int) -> bool:
        """Activate a phone number and assign it to an agent"""
        try:
            phone_record = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
            if not phone_record:
                logger.error(f"Phone number {phone_number_id} not found")
                return False
            
            # Allow APPROVED or ACTIVE status (ACTIVE for existing numbers already owned)
            if phone_record.status not in [PhoneNumberStatus.APPROVED, PhoneNumberStatus.ACTIVE]:
                logger.error(f"Phone number {phone_number_id} status is {phone_record.status}, must be APPROVED or ACTIVE")
                return False
            
            # Assign to agent
            phone_record.agent_id = agent_id
            phone_record.status = PhoneNumberStatus.ACTIVE
            if not phone_record.activated_at:
                phone_record.activated_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Phone number {phone_record.phone_number} assigned to agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating phone number: {e}")
            db.rollback()
            return False
    
    async def configure_call_forwarding(
        self, 
        phone_number: str, 
        webhook_url: str
    ) -> bool:
        """Configure call forwarding to webhook for voice agent"""
        try:
            response = self._make_request(
                "/settings/pbx",
                method="POST",
                params={
                    "number": phone_number,
                    "action": "forward",
                    "destination": webhook_url
                }
            )
            
            return response.get("status") == "success"
            
        except Exception as e:
            logger.error(f"Error configuring call forwarding: {e}")
            return False
    
    async def configure_pbx_for_number(
        self,
        db: Session,
        phone_number: PhoneNumber,
        pbx_config: Dict[str, Any]
    ) -> bool:
        """
        Configure PBX schedule and IVR for the provided phone number.
        Ensures the voice agent is reachable via PBX extension during the day
        while after-hours callers are connected directly to the agent.
        """
        if not phone_number.agent:
            logger.error(
                "Cannot configure PBX routing because phone number has no agent assigned",
                extra={"phone_number_id": phone_number.id},
            )
            return False
        
        agent = phone_number.agent
        extension = await self.ensure_agent_extension(db, phone_number, agent)
        
        business_hours = self._normalize_business_hours(
            pbx_config.get("business_hours") if pbx_config else None
        )
        menu_options = self._normalize_menu_options(
            pbx_config.get("menu_options") if pbx_config else [],
            extension,
        )
        after_hours = self._normalize_after_hours(
            pbx_config.get("after_hours_routing") if pbx_config else {},
            extension,
        )
        
        payload = self._build_pbx_scenario_payload(
            phone_number,
            business_hours,
            menu_options,
            after_hours,
        )
        
        params = {
            "number": phone_number.phone_number,
            "scenario": json.dumps(payload),
        }
        
        try:
            response = self._make_request(
                "/pbx/set_scenario",
                method="POST",
                params=params
            )
        except Exception as exc:
            logger.error(
                "Failed to configure PBX scenario via Zadarma",
                exc_info=True,
                extra={"phone_number": phone_number.phone_number, "payload": payload},
            )
            return False
        
        if response.get("status") != "success":
            logger.error(
                "Zadarma PBX configuration was not accepted",
                extra={"response": response, "phone_number": phone_number.phone_number},
            )
            return False
        
        scenario_id = response.get("scenario_id")
        phone_number.pbx_enabled = True
        phone_number.pbx_scenario_id = scenario_id
        phone_number.pbx_extension = extension
        phone_number.business_hours = business_hours
        phone_number.menu_options = menu_options
        phone_number.after_hours_routing = after_hours
        phone_number.zadarma_config = payload
        db.commit()
        db.refresh(phone_number)
        
        logger.info(
            "Configured Zadarma PBX scenario for number %s. Scenario ID: %s",
            phone_number.phone_number,
            scenario_id,
        )
        return True


def get_zadarma_service() -> ZadarmaService:
    """Get Zadarma service instance"""
    return ZadarmaService()

