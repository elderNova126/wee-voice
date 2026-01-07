"""
Asterisk Configuration Generation Service

Generates dynamic pjsip.conf and extensions.conf based on phone numbers
and their SIP configurations stored in the database.

This allows multiple phone numbers with different SIP providers to be
managed dynamically without manual Asterisk configuration.
"""
import os
import subprocess
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.database import SessionLocal
from app.models import PhoneNumber

logger = logging.getLogger(__name__)

# Asterisk paths (can be configured via environment)
ASTERISK_CONFIG_DIR = os.getenv('ASTERISK_CONFIG_DIR', '/etc/asterisk')
ASTERISK_AGI_DIR = os.getenv('ASTERISK_AGI_DIR', '/var/lib/asterisk/agi-bin')
ASTERISK_SPOOL_DIR = os.getenv('ASTERISK_SPOOL_DIR', '/var/spool/asterisk')

# Generated config file paths
PJSIP_GENERATED_FILE = os.path.join(ASTERISK_CONFIG_DIR, 'pjsip_weevoice.conf')
EXTENSIONS_GENERATED_FILE = os.path.join(ASTERISK_CONFIG_DIR, 'extensions_weevoice.conf')


class AsteriskConfigService:
    """
    Service for generating and managing Asterisk configuration files
    dynamically based on database phone number entries.
    """
    
    def __init__(self):
        self.config_dir = Path(ASTERISK_CONFIG_DIR)
        self.pjsip_file = Path(PJSIP_GENERATED_FILE)
        self.extensions_file = Path(EXTENSIONS_GENERATED_FILE)
        self.zadarma_credentials_file = Path(os.path.join(ASTERISK_CONFIG_DIR, 'pjsip_zadarma_credentials.conf'))
        
    def _get_phone_numbers_with_sip(self, db: Session) -> List[Dict[str, Any]]:
        """Get all phone numbers with complete SIP configuration from database"""
        try:
            # NOTE: sip_websocket_url is NOT required for Zadarma trunk
            # Only sip_username, sip_password, sip_domain are needed
            result = db.execute(text("""
                SELECT 
                    id, user_id, agent_id, phone_number, country_code, number_type,
                    sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                    status, business_name
                FROM phone_numbers
                WHERE sip_username IS NOT NULL 
                  AND sip_password IS NOT NULL
                  AND sip_domain IS NOT NULL
                  AND sip_username != ''
                  AND sip_password != ''
                  AND agent_id IS NOT NULL
                ORDER BY id
            """)).fetchall()
            
            phones = []
            for row in result:
                phones.append({
                    'id': row[0],
                    'user_id': row[1],
                    'agent_id': row[2],
                    'phone_number': row[3],
                    'country_code': row[4],
                    'number_type': row[5],
                    'sip_websocket_url': row[6],
                    'sip_transport': row[7] or 'WSS',
                    'sip_username': row[8],
                    'sip_password': row[9],
                    'sip_domain': row[10],
                    'status': row[11],
                    'business_name': row[12]
                })
            
            return phones
            
        except Exception as e:
            logger.error(f"Error loading phone numbers from database: {e}")
            return []
    
    def _normalize_phone_for_extension(self, phone_number: str) -> str:
        """
        Convert phone number to Asterisk extension format.
        E.g., +32480206645 -> 32480206645
        """
        if not phone_number:
            return ""
        # Remove + and all non-digit characters
        return ''.join(c for c in phone_number if c.isdigit())
    
    def _generate_endpoint_name(self, phone: Dict[str, Any]) -> str:
        """Generate unique endpoint name for a phone number"""
        # Use SIP username as endpoint name (ensure it's safe)
        username = phone['sip_username']
        return f"weevoice-{username}".replace('@', '-').replace('.', '-')
    
    def _parse_sip_websocket_url(self, url: str) -> Dict[str, Any]:
        """
        Parse WebSocket URL to extract components.
        E.g., wss://weevoice.weedoo.com:8089/ws
        """
        result = {
            'scheme': 'wss',
            'host': 'localhost',
            'port': 8089,
            'path': '/ws'
        }
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            result['scheme'] = parsed.scheme or 'wss'
            result['host'] = parsed.hostname or 'localhost'
            result['port'] = parsed.port or (443 if parsed.scheme == 'wss' else 8089)
            result['path'] = parsed.path or '/ws'
        except Exception as e:
            logger.warning(f"Could not parse WebSocket URL {url}: {e}")
        
        return result
    
    def generate_pjsip_config(self, phones: List[Dict[str, Any]]) -> str:
        """
        Generate PJSIP configuration for phone number endpoints ONLY.
        
        NOTE: Does NOT generate transports or Zadarma trunk - those are defined
        in the main pjsip.conf file. This file is #included and should only
        contain phone number-specific endpoint configurations.
        
        Creates:
        - Endpoints for each phone number
        - AORs (Address of Records)
        - Auth configurations
        - Identify sections
        """
        config_lines = [
            ";==============================================================================",
            "; WeeVoice PJSIP Configuration - Phone Number Endpoints",
            f"; Generated: {datetime.utcnow().isoformat()}",
            "; DO NOT EDIT - This file is auto-generated by WeeVoice",
            ";",
            "; This file is included from the main pjsip.conf",
            "; It defines endpoints for each configured phone number",
            ";==============================================================================",
            ""
        ]
        
        if not phones:
            config_lines.extend([
                "; No phone numbers with SIP configuration found",
                "; Add a phone number with SIP settings to generate endpoints",
                ""
            ])
            return '\n'.join(config_lines)
        
        # Generate endpoint, auth, and AOR for each phone number
        for phone in phones:
            endpoint_name = self._generate_endpoint_name(phone)
            
            # Use the existing transports from main pjsip.conf:
            # - transport-wss: For WebSocket/WebRTC connections
            # - transport-udp: For standard SIP
            transport = phone.get('sip_transport', 'WSS').upper()
            if transport == 'WSS' or transport == 'WS':
                transport_name = 'transport-wss'
            else:
                transport_name = 'transport-udp'
            
            # Normalized phone number for matching
            norm_phone = self._normalize_phone_for_extension(phone['phone_number'])
            
            config_lines.extend([
                f";==============================================================================",
                f"; Phone: {phone['phone_number']} (ID: {phone['id']})",
                f"; Agent ID: {phone['agent_id']}",
                f"; Business: {phone['business_name'] or 'N/A'}",
                f"; SIP Domain: {phone['sip_domain']}",
                f";==============================================================================",
                "",
                f";--- Endpoint: {endpoint_name} ---",
                f"[{endpoint_name}]",
                "type=endpoint",
                f"transport={transport_name}",
                "context=weevoice-inbound",  # Context for incoming calls
                "disallow=all",
                "allow=ulaw",
                "allow=alaw",
                "allow=opus",  # For WebRTC
                "webrtc=yes" if transport in ('WSS', 'WS') else "; webrtc=no (UDP transport)",
                "dtls_auto_generate_cert=yes" if transport in ('WSS', 'WS') else "; No DTLS for UDP",
                "media_encryption=dtls" if transport in ('WSS', 'WS') else "; No encryption for UDP",
                f"auth={endpoint_name}-auth",
                f"aors={endpoint_name}-aor",
                f"callerid=\"WeeVoice\" <{phone['phone_number']}>",
                f"from_user={phone['sip_username']}",
                f"from_domain={phone['sip_domain']}",
                "direct_media=no",
                "rtp_symmetric=yes",
                "force_rport=yes",
                "rewrite_contact=yes",
                "ice_support=yes" if transport in ('WSS', 'WS') else "; No ICE for UDP",
                "",
                f";--- Auth: {endpoint_name}-auth ---",
                f"[{endpoint_name}-auth]",
                "type=auth",
                "auth_type=userpass",
                f"username={phone['sip_username']}",
                f"password={phone['sip_password']}",
                "",
                f";--- AOR: {endpoint_name}-aor ---",
                f"[{endpoint_name}-aor]",
                "type=aor",
                "max_contacts=5",
                "qualify_frequency=30",
                "remove_existing=yes",
                "",
                f";--- Identify: {endpoint_name}-identify ---",
                f"[{endpoint_name}-identify]",
                "type=identify",
                f"endpoint={endpoint_name}",
                f"match={phone['sip_domain']}",
                "",
            ])
        
        config_lines.extend([
            ";==============================================================================",
            f"; End of WeeVoice PJSIP Configuration",
            f"; Total endpoints configured: {len(phones)}",
            ";==============================================================================",
            ""
        ])
        
        return '\n'.join(config_lines)
    
    def generate_extensions_config(self, phones: List[Dict[str, Any]]) -> str:
        """
        Generate Asterisk extensions.conf for routing calls to WeeVoice EAGI.
        
        NOTE: This file is #included from the main extensions.conf.
        It defines the [weevoice-inbound] context with patterns for each
        configured phone number.
        """
        config_lines = [
            ";==============================================================================",
            "; WeeVoice Extensions Configuration - Phone Number Routing",
            f"; Generated: {datetime.utcnow().isoformat()}",
            "; DO NOT EDIT - This file is auto-generated by WeeVoice",
            ";",
            "; This file is included from the main extensions.conf",
            "; It overrides the [weevoice-inbound] context with specific phone mappings",
            ";==============================================================================",
            "",
            ";==============================================================================",
            "; WEEVOICE INBOUND CONTEXT",
            "; Routes incoming calls to the correct AI agent based on called DID",
            ";==============================================================================",
            "",
            "[weevoice-inbound]",
            "; Main entry point for all WeeVoice calls",
            "",
        ]
        
        if not phones:
            # No phone numbers configured - add catch-all only
            config_lines.extend([
                "; No phone numbers with SIP configuration found",
                "; Using catch-all pattern to route to first available agent",
                "",
            ])
        else:
            # Generate specific patterns for each phone number
            for phone in phones:
                norm_phone = self._normalize_phone_for_extension(phone['phone_number'])
                phone_display = phone['phone_number']
                agent_id = phone['agent_id']
                business = phone['business_name'] or 'Unknown'
                
                config_lines.extend([
                    f"; Phone: {phone_display} -> Agent: {agent_id} ({business})",
                    f"exten => {norm_phone},1,NoOp(=== WeeVoice Incoming: {phone_display} ===)",
                    f" same => n,Set(CALLED_DID={phone_display})",
                    f" same => n,Set(FROM_DID={phone_display})",
                    f" same => n,Set(AGENT_ID={agent_id})",
                    " same => n,NoOp(Caller: ${CALLERID(num)})",
                    " same => n,Answer()",
                    " same => n,Wait(0.5)",
                    " same => n,Set(CHANNEL(language)=en)",
                    " same => n,EAGI(${WEEVOICE_EAGI})",
                    " same => n,NoOp(EAGI Status: ${AGISTATUS})",
                    " same => n,Hangup()",
                    "",
                ])
                
                # Also add with + prefix for international format
                config_lines.extend([
                    f"exten => +{norm_phone},1,Goto({norm_phone},1)",
                    "",
                ])
        
        # Add catch-all pattern for unrecognized numbers (fallback)
        config_lines.extend([
            "; Catch-all for incoming calls (fallback to first available agent)",
            "exten => _X.,1,NoOp(=== WeeVoice Catch-All: ${EXTEN} ===)",
            " same => n,Set(CALLED_DID=${EXTEN})",
            " same => n,Set(FROM_DID=${EXTEN})",
            " same => n,NoOp(Caller: ${CALLERID(num)})",
            " same => n,Answer()",
            " same => n,Wait(0.5)",
            " same => n,Set(CHANNEL(language)=en)",
            " same => n,EAGI(${WEEVOICE_EAGI})",
            " same => n,NoOp(EAGI Status: ${AGISTATUS})",
            " same => n,Hangup()",
            "",
            "exten => _+X.,1,Goto(${EXTEN:1},1)",
            "",
            "; Start extension (for calls without EXTEN)",
            "exten => s,1,NoOp(=== WeeVoice Call (s) ===)",
            " same => n,Answer()",
            " same => n,Wait(0.5)",
            " same => n,EAGI(${WEEVOICE_EAGI})",
            " same => n,Hangup()",
            "",
            "; Hangup handler",
            "exten => h,1,NoOp(=== WeeVoice Call Ended ===)",
            " same => n,NoOp(Duration: ${CDR(billsec)}s)",
            "",
            ";==============================================================================",
            f"; End of WeeVoice Extensions Configuration",
            f"; Total phone numbers: {len(phones)}",
            ";==============================================================================",
            ""
        ])
        
        return '\n'.join(config_lines)
    
    def _get_any_phone_with_sip_credentials(self, db: Session) -> Optional[Dict[str, Any]]:
        """Get any phone number with SIP credentials (doesn't require agent assignment)"""
        try:
            logger.info("Querying database for any phone with SIP credentials...")
            result = db.execute(text("""
                SELECT 
                    id, phone_number, sip_username, sip_password, sip_domain
                FROM phone_numbers
                WHERE sip_username IS NOT NULL 
                  AND sip_password IS NOT NULL
                  AND sip_domain IS NOT NULL
                  AND sip_username != ''
                  AND sip_password != ''
                ORDER BY id
                LIMIT 1
            """)).first()
            
            if result:
                phone_data = {
                    'id': result[0],
                    'phone_number': result[1],
                    'sip_username': result[2],
                    'sip_password': result[3],
                    'sip_domain': result[4]
                }
                logger.info(f"Found phone with SIP credentials: id={phone_data['id']}, number={phone_data['phone_number']}, user={phone_data['sip_username']}")
                return phone_data
            else:
                logger.warning("No phone numbers with SIP credentials found in database")
                # Debug: count all phones and phones with credentials
                total = db.execute(text("SELECT COUNT(*) FROM phone_numbers")).scalar()
                with_creds = db.execute(text("""
                    SELECT COUNT(*) FROM phone_numbers 
                    WHERE sip_username IS NOT NULL AND sip_username != ''
                """)).scalar()
                logger.info(f"Database has {total} total phones, {with_creds} with sip_username set")
                return None
        except Exception as e:
            logger.error(f"Error fetching phone with SIP credentials: {e}", exc_info=True)
            return None
    
    def generate_zadarma_credentials(self, db: Session = None, phones: List[Dict[str, Any]] = None) -> bool:
        """
        Generate Zadarma credentials file from phone number SIP settings.
        Uses the first phone number with SIP credentials configured (any phone, no agent required).
        Falls back to environment variables if no phone has credentials.
        
        This file is #tryinclude'd from pjsip.conf.
        
        Returns True on success, False if credentials not found.
        """
        logger.info(f"generate_zadarma_credentials called: phones={len(phones) if phones else 0}, db={db is not None}")
        
        sip_login = None
        sip_password = None
        sip_domain = None
        source = None
        
        # First try to get credentials from the phones list (if provided)
        if phones:
            logger.info(f"Checking {len(phones)} phones from list for SIP credentials")
            for phone in phones:
                logger.debug(f"Phone {phone.get('phone_number')}: username={phone.get('sip_username')}, domain={phone.get('sip_domain')}")
                if phone.get('sip_username') and phone.get('sip_password'):
                    sip_login = phone['sip_username']
                    sip_password = phone['sip_password']
                    sip_domain = phone.get('sip_domain', 'sip.zadarma.com')
                    source = f"phone number {phone['phone_number']}"
                    logger.info(f"Found SIP credentials from {source}: user={sip_login}, domain={sip_domain}")
                    break
        
        # If no credentials from phones list, try to get ANY phone with SIP credentials
        if (not sip_login or not sip_password) and db:
            logger.info("No credentials from phones list, checking database for any phone with SIP...")
            phone_with_creds = self._get_any_phone_with_sip_credentials(db)
            if phone_with_creds:
                sip_login = phone_with_creds['sip_username']
                sip_password = phone_with_creds['sip_password']
                sip_domain = phone_with_creds.get('sip_domain', 'sip.zadarma.com')
                source = f"phone number {phone_with_creds['phone_number']} (no agent)"
                logger.info(f"Found SIP credentials from {source}: user={sip_login}, domain={sip_domain}")
            else:
                logger.warning("No phone with SIP credentials found in database")
        
        # Fallback to environment variables
        if not sip_login or not sip_password:
            logger.info("Checking environment variables for SIP credentials...")
            sip_login = os.getenv('ZADARMA_SIP_LOGIN')
            sip_password = os.getenv('ZADARMA_SIP_PASSWORD')
            sip_domain = os.getenv('ZADARMA_SIP_DOMAIN', 'sip.zadarma.com')
            if sip_login and sip_password:
                source = "environment variables"
                logger.info(f"Found SIP credentials from environment: user={sip_login}")
            else:
                logger.warning("No SIP credentials in environment variables")
        
        if not sip_login or not sip_password:
            logger.error("No SIP credentials found anywhere - phone numbers, database, or environment")
            return False
        
        content = f""";==============================================================================
; Zadarma SIP Authentication and Registration
; Generated: {datetime.utcnow().isoformat()}
; Source: {source}
; DO NOT EDIT - This file is auto-generated from phone number SIP settings
;==============================================================================

;--- Authentication ---
[zadarma-auth]
type=auth
auth_type=userpass
username={sip_login}
password={sip_password}

;--- Outbound Registration ---
; This tells Asterisk to register with Zadarma to receive incoming calls
[zadarma-registration]
type=registration
transport=transport-udp
outbound_auth=zadarma-auth
server_uri=sip:{sip_domain}
client_uri=sip:{sip_login}@{sip_domain}
retry_interval=60
max_retries=10
expiration=3600
line=yes
endpoint=zadarma-endpoint
"""
        
        try:
            logger.info(f"Writing Zadarma credentials to {self.zadarma_credentials_file}")
            logger.info(f"File path exists: {self.zadarma_credentials_file.exists()}, parent exists: {self.zadarma_credentials_file.parent.exists()}")
            
            self.zadarma_credentials_file.write_text(content)
            
            # Set restrictive permissions (owner read/write only)
            try:
                os.chmod(self.zadarma_credentials_file, 0o640)
                logger.info(f"Set permissions 640 on {self.zadarma_credentials_file}")
            except Exception as perm_err:
                logger.warning(f"Could not set permissions: {perm_err}")
            
            logger.info(f"Successfully wrote Zadarma credentials to {self.zadarma_credentials_file} (from {source})")
            return True
        except PermissionError as e:
            logger.error(f"Permission denied writing Zadarma credentials to {self.zadarma_credentials_file}: {e}")
            logger.error(f"Check file ownership and permissions. Backend runs as www-data.")
            return False
        except Exception as e:
            logger.error(f"Failed to write Zadarma credentials to {self.zadarma_credentials_file}: {e}", exc_info=True)
            return False
    
    def write_config_files(self, pjsip_content: str, extensions_content: str) -> bool:
        """
        Write generated configuration to files.
        Returns True on success, False on failure.
        """
        try:
            # Create backup of existing files
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            
            if self.pjsip_file.exists():
                backup_path = self.pjsip_file.with_suffix(f'.conf.bak.{timestamp}')
                self.pjsip_file.rename(backup_path)
                logger.info(f"Backed up existing pjsip config to {backup_path}")
            
            if self.extensions_file.exists():
                backup_path = self.extensions_file.with_suffix(f'.conf.bak.{timestamp}')
                self.extensions_file.rename(backup_path)
                logger.info(f"Backed up existing extensions config to {backup_path}")
            
            # Write new config files
            self.pjsip_file.write_text(pjsip_content)
            logger.info(f"Wrote PJSIP config to {self.pjsip_file}")
            
            self.extensions_file.write_text(extensions_content)
            logger.info(f"Wrote extensions config to {self.extensions_file}")
            
            return True
            
        except PermissionError as e:
            logger.error(f"Permission denied writing Asterisk config: {e}")
            return False
        except Exception as e:
            logger.error(f"Error writing Asterisk config files: {e}")
            return False
    
    def reload_asterisk(self) -> Dict[str, Any]:
        """
        Reload Asterisk configuration to apply changes.
        Returns status dict with success/failure and details.
        """
        result = {
            'success': False,
            'pjsip_reload': None,
            'dialplan_reload': None,
            'errors': []
        }
        
        try:
            # Check if Asterisk is running
            check_cmd = subprocess.run(
                ['asterisk', '-rx', 'core show version'],
                capture_output=True, text=True, timeout=10
            )
            
            if check_cmd.returncode != 0:
                result['errors'].append("Asterisk is not running or not accessible")
                return result
            
            # Reload PJSIP
            pjsip_cmd = subprocess.run(
                ['asterisk', '-rx', 'pjsip reload'],
                capture_output=True, text=True, timeout=30
            )
            result['pjsip_reload'] = {
                'returncode': pjsip_cmd.returncode,
                'stdout': pjsip_cmd.stdout,
                'stderr': pjsip_cmd.stderr
            }
            
            if pjsip_cmd.returncode != 0:
                result['errors'].append(f"PJSIP reload failed: {pjsip_cmd.stderr}")
            
            # Reload dialplan
            dialplan_cmd = subprocess.run(
                ['asterisk', '-rx', 'dialplan reload'],
                capture_output=True, text=True, timeout=30
            )
            result['dialplan_reload'] = {
                'returncode': dialplan_cmd.returncode,
                'stdout': dialplan_cmd.stdout,
                'stderr': dialplan_cmd.stderr
            }
            
            if dialplan_cmd.returncode != 0:
                result['errors'].append(f"Dialplan reload failed: {dialplan_cmd.stderr}")
            
            # Check if both reloads succeeded
            result['success'] = (
                pjsip_cmd.returncode == 0 and 
                dialplan_cmd.returncode == 0
            )
            
            if result['success']:
                logger.info("Asterisk configuration reloaded successfully")
            else:
                logger.warning(f"Asterisk reload had issues: {result['errors']}")
            
            return result
            
        except subprocess.TimeoutExpired:
            result['errors'].append("Asterisk reload timed out")
            return result
        except FileNotFoundError:
            result['errors'].append("Asterisk CLI not found - is Asterisk installed?")
            return result
        except Exception as e:
            result['errors'].append(f"Error reloading Asterisk: {str(e)}")
            return result
    
    def regenerate_config(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Main method to regenerate all Asterisk configuration.
        
        1. Loads phone numbers from database
        2. Generates pjsip.conf
        3. Generates extensions.conf
        4. Writes config files
        5. Optionally reloads Asterisk
        
        Returns status dict with details.
        """
        result = {
            'success': False,
            'phone_numbers_count': 0,
            'files_written': False,
            'asterisk_reloaded': False,
            'zadarma_credentials_written': False,
            'errors': [],
            'generated_at': datetime.utcnow().isoformat()
        }
        
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Load phone numbers
            phones = self._get_phone_numbers_with_sip(db)
            result['phone_numbers_count'] = len(phones)
            
            if not phones:
                logger.warning("No phone numbers with SIP config found")
                result['errors'].append("No phone numbers with SIP configuration found")
                # Still generate basic config even with no phones
            
            logger.info(f"Generating Asterisk config for {len(phones)} phone number(s)")
            
            # Generate configurations
            pjsip_content = self.generate_pjsip_config(phones)
            extensions_content = self.generate_extensions_config(phones)
            
            # Write config files
            if self.write_config_files(pjsip_content, extensions_content):
                result['files_written'] = True
            else:
                result['errors'].append("Failed to write config files")
                return result
            
            # Generate Zadarma credentials from phone number SIP settings
            # Pass db session so it can look for ANY phone with SIP credentials (not just those with agents)
            result['zadarma_credentials_written'] = self.generate_zadarma_credentials(db=db, phones=phones)
            if not result['zadarma_credentials_written']:
                result['errors'].append("No SIP credentials found - configure SIP settings in Phone Numbers page")
            
            # Reload Asterisk
            reload_result = self.reload_asterisk()
            result['asterisk_reloaded'] = reload_result['success']
            if reload_result['errors']:
                result['errors'].extend(reload_result['errors'])
            
            # Overall success
            result['success'] = result['files_written']
            
            if result['success']:
                logger.info(f"Asterisk config regenerated: {len(phones)} phones, reload: {result['asterisk_reloaded']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error regenerating Asterisk config: {e}", exc_info=True)
            result['errors'].append(str(e))
            return result
        finally:
            if close_db:
                db.close()
    
    def get_config_status(self) -> Dict[str, Any]:
        """Get current status of Asterisk configuration files"""
        return {
            'pjsip_file': {
                'path': str(self.pjsip_file),
                'exists': self.pjsip_file.exists(),
                'modified': self.pjsip_file.stat().st_mtime if self.pjsip_file.exists() else None,
                'size': self.pjsip_file.stat().st_size if self.pjsip_file.exists() else 0
            },
            'extensions_file': {
                'path': str(self.extensions_file),
                'exists': self.extensions_file.exists(),
                'modified': self.extensions_file.stat().st_mtime if self.extensions_file.exists() else None,
                'size': self.extensions_file.stat().st_size if self.extensions_file.exists() else 0
            },
            'zadarma_credentials_file': {
                'path': str(self.zadarma_credentials_file),
                'exists': self.zadarma_credentials_file.exists(),
                'modified': self.zadarma_credentials_file.stat().st_mtime if self.zadarma_credentials_file.exists() else None,
                'has_env_vars': bool(os.getenv('ZADARMA_SIP_LOGIN') and os.getenv('ZADARMA_SIP_PASSWORD'))
            }
        }


# Global service instance
_asterisk_config_service = None


def get_asterisk_config_service() -> AsteriskConfigService:
    """Get singleton Asterisk config service instance"""
    global _asterisk_config_service
    if _asterisk_config_service is None:
        _asterisk_config_service = AsteriskConfigService()
    return _asterisk_config_service

