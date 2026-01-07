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
        
    def _get_phone_numbers_with_sip(self, db: Session) -> List[Dict[str, Any]]:
        """Get all phone numbers with complete SIP configuration from database"""
        try:
            result = db.execute(text("""
                SELECT 
                    id, user_id, agent_id, phone_number, country_code, number_type,
                    sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                    status, business_name
                FROM phone_numbers
                WHERE sip_websocket_url IS NOT NULL 
                  AND sip_username IS NOT NULL 
                  AND sip_password IS NOT NULL
                  AND sip_domain IS NOT NULL
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
        Generate PJSIP configuration for all phone numbers.
        
        Creates:
        - Transport definitions (one per unique WebSocket URL)
        - Endpoints for each phone number
        - AORs (Address of Records)
        - Auth configurations
        """
        config_lines = [
            ";==============================================================================",
            "; WeeVoice PJSIP Configuration",
            f"; Generated: {datetime.utcnow().isoformat()}",
            "; DO NOT EDIT - This file is auto-generated by WeeVoice",
            ";==============================================================================",
            ""
        ]
        
        # Group phones by SIP domain/WebSocket URL to create shared transports
        transports = {}
        for phone in phones:
            ws_info = self._parse_sip_websocket_url(phone['sip_websocket_url'])
            transport_key = f"{ws_info['host']}_{ws_info['port']}"
            if transport_key not in transports:
                transports[transport_key] = {
                    'ws_info': ws_info,
                    'phones': []
                }
            transports[transport_key]['phones'].append(phone)
        
        # Generate transport sections
        for transport_key, transport_data in transports.items():
            ws_info = transport_data['ws_info']
            transport_name = f"transport-ws-{transport_key.replace('.', '-').replace('_', '-')}"
            
            config_lines.extend([
                f";--- Transport: {transport_name} ---",
                f"[{transport_name}]",
                "type=transport",
                f"protocol={'wss' if ws_info['scheme'] == 'wss' else 'ws'}",
                f"bind=0.0.0.0:{ws_info['port']}",
                "; WebSocket transport for browser/softphone clients",
                ""
            ])
        
        # Generate endpoint, auth, and AOR for each phone number
        for phone in phones:
            endpoint_name = self._generate_endpoint_name(phone)
            ws_info = self._parse_sip_websocket_url(phone['sip_websocket_url'])
            transport_key = f"{ws_info['host']}_{ws_info['port']}"
            transport_name = f"transport-ws-{transport_key.replace('.', '-').replace('_', '-')}"
            
            # Normalized phone number for matching
            norm_phone = self._normalize_phone_for_extension(phone['phone_number'])
            
            config_lines.extend([
                f";==============================================================================",
                f"; Phone: {phone['phone_number']} (ID: {phone['id']})",
                f"; Agent ID: {phone['agent_id']}",
                f"; Business: {phone['business_name'] or 'N/A'}",
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
                "webrtc=yes",  # Enable WebRTC features
                "dtls_auto_generate_cert=yes",
                "media_encryption=dtls",
                f"auth={endpoint_name}-auth",
                f"aors={endpoint_name}",
                f"callerid=\"WeeVoice\" <{phone['phone_number']}>",
                f"from_user={phone['sip_username']}",
                f"from_domain={phone['sip_domain']}",
                "direct_media=no",
                "rtp_symmetric=yes",
                "force_rport=yes",
                "rewrite_contact=yes",
                "ice_support=yes",  # ICE for NAT traversal
                "",
                f";--- Auth: {endpoint_name}-auth ---",
                f"[{endpoint_name}-auth]",
                "type=auth",
                f"auth_type=userpass",
                f"username={phone['sip_username']}",
                f"password={phone['sip_password']}",
                "",
                f";--- AOR: {endpoint_name} ---",
                f"[{endpoint_name}]",
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
        
        # Add Zadarma trunk configuration (for outbound calls to PSTN)
        config_lines.extend([
            ";==============================================================================",
            "; ZADARMA SIP TRUNK (for outbound PSTN calls)",
            ";==============================================================================",
            "",
            "[zadarma-endpoint]",
            "type=endpoint",
            "transport=transport-udp-zadarma",
            "context=from-zadarma",
            "disallow=all",
            "allow=ulaw",
            "allow=alaw",
            "from_user=weevoice",
            "from_domain=sip.zadarma.com",
            "auth=zadarma-auth",
            "outbound_auth=zadarma-auth",
            "aors=zadarma-aor",
            "direct_media=no",
            "",
            "[zadarma-auth]",
            "type=auth",
            "auth_type=userpass",
            "username=${ZADARMA_SIP_LOGIN}",
            "password=${ZADARMA_SIP_PASSWORD}",
            "",
            "[zadarma-aor]",
            "type=aor",
            "contact=sip:sip.zadarma.com",
            "qualify_frequency=30",
            "",
            "[zadarma-identify]",
            "type=identify",
            "endpoint=zadarma-endpoint",
            "match=sip.zadarma.com",
            "",
            "[transport-udp-zadarma]",
            "type=transport",
            "protocol=udp",
            "bind=0.0.0.0:5060",
            ""
        ])
        
        return '\n'.join(config_lines)
    
    def generate_extensions_config(self, phones: List[Dict[str, Any]]) -> str:
        """
        Generate Asterisk extensions.conf for routing calls to WeeVoice EAGI.
        
        Creates patterns to match all registered phone numbers and route
        them to the appropriate AI agent via the EAGI script.
        """
        config_lines = [
            ";==============================================================================",
            "; WeeVoice Extensions Configuration",
            f"; Generated: {datetime.utcnow().isoformat()}",
            "; DO NOT EDIT - This file is auto-generated by WeeVoice",
            ";==============================================================================",
            "",
            "[globals]",
            "; WeeVoice Global Variables",
            "WEEVOICE_EAGI=/var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py",
            "",
            ";==============================================================================",
            "; WEEVOICE INBOUND CONTEXT",
            "; All incoming calls to WeeVoice phone numbers are routed here",
            ";==============================================================================",
            "",
            "[weevoice-inbound]",
            "; Main entry point for all WeeVoice calls",
            "",
        ]
        
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
                f" same => n,NoOp(Caller: ${{CALLERID(num)}})",
                " same => n,Answer()",
                " same => n,Wait(0.5)",
                " same => n,Set(CHANNEL(language)=en)",
                " same => n,EAGI(${WEEVOICE_EAGI})",
                " same => n,NoOp(EAGI Status: ${AGISTATUS})",
                " same => n,Hangup()",
                "",
            ])
            
            # Also add with + prefix
            config_lines.extend([
                f"exten => +{norm_phone},1,Goto({norm_phone},1)",
                "",
            ])
        
        # Add catch-all pattern for unrecognized numbers
        config_lines.extend([
            "; Catch-all for incoming calls (fallback to first available agent)",
            "exten => _X.,1,NoOp(=== WeeVoice Catch-All: ${EXTEN} ===)",
            " same => n,Set(CALLED_DID=${EXTEN})",
            " same => n,Set(FROM_DID=${EXTEN})",
            " same => n,NoOp(Caller: ${CALLERID(num)})",
            " same => n,Answer()",
            " same => n,Wait(0.5)",
            " same => n,EAGI(${WEEVOICE_EAGI})",
            " same => n,Hangup()",
            "",
            "exten => _+X.,1,Goto(${EXTEN:1},1)",
            "",
            "; Start extension",
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
        ])
        
        # Add from-zadarma context for calls from Zadarma trunk
        config_lines.extend([
            ";==============================================================================",
            "; FROM-ZADARMA CONTEXT",
            "; Calls coming from Zadarma SIP trunk",
            ";==============================================================================",
            "",
            "[from-zadarma]",
            "; Route incoming Zadarma calls to weevoice-inbound",
            "exten => _X.,1,NoOp(=== Zadarma Incoming: ${EXTEN} ===)",
            " same => n,Goto(weevoice-inbound,${EXTEN},1)",
            "",
            "exten => _+X.,1,Goto(weevoice-inbound,${EXTEN:1},1)",
            "",
        ])
        
        # Add outbound calling context
        config_lines.extend([
            ";==============================================================================",
            "; WEEVOICE OUTBOUND CONTEXT",
            "; For making outbound calls via Zadarma",
            ";==============================================================================",
            "",
            "[weevoice-outbound]",
            "; Outbound calls via Zadarma trunk",
            "exten => _+X.,1,NoOp(WeeVoice Outbound: ${EXTEN})",
            " same => n,Set(CALLERID(num)=${CALLERID(num)})",
            " same => n,Dial(PJSIP/${EXTEN}@zadarma-endpoint,60)",
            " same => n,Hangup()",
            "",
            "exten => _X.,1,NoOp(WeeVoice Outbound: ${EXTEN})",
            " same => n,Set(CALLERID(num)=${CALLERID(num)})",
            " same => n,Dial(PJSIP/${EXTEN}@zadarma-endpoint,60)",
            " same => n,Hangup()",
            "",
        ])
        
        # Add test extensions
        config_lines.extend([
            ";==============================================================================",
            "; TEST EXTENSIONS",
            ";==============================================================================",
            "",
            "[weevoice-test]",
            "; AI Agent test",
            "exten => 9999,1,NoOp(=== WeeVoice AI Test ===)",
            " same => n,Answer()",
            " same => n,Wait(0.5)",
            " same => n,EAGI(${WEEVOICE_EAGI})",
            " same => n,Hangup()",
            "",
            "; Echo test",
            "exten => 9998,1,NoOp(=== Echo Test ===)",
            " same => n,Answer()",
            " same => n,Echo()",
            " same => n,Hangup()",
            "",
            "; Playback test",
            "exten => 9997,1,NoOp(=== Playback Test ===)",
            " same => n,Answer()",
            " same => n,Playback(hello-world)",
            " same => n,Hangup()",
            ""
        ])
        
        return '\n'.join(config_lines)
    
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

