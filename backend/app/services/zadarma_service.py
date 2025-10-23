"""
Zadarma Integration Service
Handles phone number provisioning and management via Zadarma API
"""
import logging
import hashlib
import hmac
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.zadarma import PhoneNumber, PhoneNumberStatus, VerificationDocument, VerificationStatus

logger = logging.getLogger(__name__)


class ZadarmaService:
    """Service for interacting with Zadarma API"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'ZADARMA_API_KEY', None)
        self.api_secret = getattr(settings, 'ZADARMA_API_SECRET', None)
        self.base_url = "https://api.zadarma.com/v1"
        
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
        params_str = "&".join([f"{k}={v}" for k, v in (params or {}).items()])
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
        elif "request_number" in endpoint:
            return {
                "status": "success",
                "number_id": f"MOCK_{datetime.utcnow().timestamp()}",
                "message": "Number request submitted. Awaiting document verification."
            }
        elif "number_status" in endpoint:
            return {
                "status": "success",
                "number_status": "pending_documents",
                "message": "Waiting for verification documents"
            }
        
        return {"status": "success", "message": "Mock response"}
    
    async def get_available_numbers(self, country_code: str = "FR") -> List[Dict[str, Any]]:
        """Get list of available phone numbers for purchase"""
        try:
            response = self._make_request(
                "/info/available_numbers",
                params={"country": country_code}
            )
            
            if response.get("status") == "success":
                return response.get("numbers", [])
            else:
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
            else:
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


def get_zadarma_service() -> ZadarmaService:
    """Get Zadarma service instance"""
    return ZadarmaService()

