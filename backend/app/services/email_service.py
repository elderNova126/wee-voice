import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text email body
            body_html: HTML email body (optional)
            from_email: Sender email (defaults to settings.SMTP_FROM_EMAIL)
            from_name: Sender name (defaults to settings.SMTP_FROM_NAME)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Validate email addresses
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, to_email):
                logger.error(f"Invalid recipient email address: {to_email}")
                return False
            
            # Use defaults from settings if not provided
            from_email = from_email or getattr(settings, 'SMTP_FROM_EMAIL', 'noreply@voiceagent.ai')
            from_name = from_name or getattr(settings, 'SMTP_FROM_NAME', 'VoiceAgent Support')
            
            if not re.match(email_pattern, from_email):
                logger.error(f"Invalid sender email address: {from_email}")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{from_email}>"
            msg['To'] = to_email
            # Add Date header
            from email.utils import formatdate
            msg['Date'] = formatdate(localtime=True)
            
            # Add text part
            text_part = MIMEText(body_text, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if body_html:
                html_part = MIMEText(body_html, 'html')
                msg.attach(html_part)
            
            # Check if SMTP is configured
            smtp_host = getattr(settings, 'SMTP_HOST', None)
            if not smtp_host or smtp_host.strip() == '':
                error_msg = "SMTP is not configured. Please set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD environment variables."
                logger.error(error_msg)
                logger.error("Email not sent to: %s", to_email)
                logger.error("Subject: %s", subject)
                return False
            
            # Send email
            smtp_port = getattr(settings, 'SMTP_PORT', 587)
            smtp_user = getattr(settings, 'SMTP_USER', None)
            smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
            use_tls = getattr(settings, 'SMTP_USE_TLS', False)
            use_ssl = getattr(settings, 'SMTP_USE_SSL', True)  # SSL for port 465
            
            # Check if credentials are provided
            if not smtp_user or not smtp_password:
                error_msg = "SMTP credentials not configured. Please set SMTP_USER and SMTP_PASSWORD environment variables."
                logger.error(error_msg)
                logger.error("Email not sent to: %s", to_email)
                return False
            
            try:
                logger.info(f"Attempting to send email via SMTP: {smtp_host}:{smtp_port}")
                logger.info(f"From: {from_email}, To: {to_email}, Subject: {subject}")
                logger.info(f"SMTP User: {smtp_user}, Use TLS: {use_tls}, Use SSL: {use_ssl}")
                
                # Use SMTP_SSL for port 465, regular SMTP for 587/25
                if use_ssl:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                
                try:
                    # Enable debug output to see SMTP conversation (set to 1 for verbose, 0 for none)
                    debug_level = getattr(settings, 'SMTP_DEBUG_LEVEL', 0)
                    server.set_debuglevel(debug_level)
                    if debug_level > 0:
                        logger.info(f"SMTP debug level set to {debug_level}")
                    logger.debug(f"Connected to SMTP server {smtp_host}:{smtp_port}")
                    
                    if not use_ssl and use_tls:
                        logger.debug("Starting TLS...")
                        server.starttls()
                        logger.debug("TLS started successfully")
                    
                    logger.debug(f"Logging in as {smtp_user}...")
                    server.login(smtp_user, smtp_password)
                    logger.debug("SMTP login successful")
                    
                    logger.debug(f"Sending email message to {to_email}...")
                    # send_message returns a dict of failed recipients, check it
                    failed_recipients = server.send_message(msg)
                    
                    server.quit()
                    logger.debug("SMTP connection closed")
                    
                    if failed_recipients:
                        logger.error(f"Email sending failed for recipients: {failed_recipients}")
                        logger.error(f"Failed to send email to: {to_email}")
                        return False
                    
                    logger.info(f"Email sent successfully to {to_email}")
                    logger.info(f"SMTP server accepted the message for delivery")
                    return True
                finally:
                    try:
                        server.quit()
                    except:
                        pass
            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"SMTP authentication failed: {str(e)}"
                logger.error(error_msg)
                logger.error("Email not sent to: %s", to_email)
                return False
            except smtplib.SMTPException as e:
                error_msg = f"SMTP error occurred: {str(e)}"
                logger.error(error_msg)
                logger.error("Email not sent to: %s", to_email)
                return False
            except Exception as e:
                error_msg = f"Unexpected error sending email: {str(e)}"
                logger.error(error_msg)
                logger.error("Email not sent to: %s", to_email)
                return False
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_support_ticket_confirmation(
        to_email: str,
        name: str,
        ticket_number: str,
        subject: str,
        message: str
    ) -> bool:
        """Send confirmation email when support ticket is created"""
        
        body_text = f"""
Bonjour {name},

Nous avons bien reçu votre demande de support.

Numéro de ticket: {ticket_number}
Sujet: {subject}

Votre message:
{message}

Notre équipe examinera votre demande et vous répondra dans les plus brefs délais.

Cordialement,
L'équipe VoiceAgent
        """
        
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .ticket-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Confirmation de Ticket de Support</h1>
        </div>
        <div class="content">
            <p>Bonjour <strong>{name}</strong>,</p>
            <p>Nous avons bien reçu votre demande de support.</p>
            
            <div class="ticket-info">
                <p><strong>Numéro de ticket:</strong> {ticket_number}</p>
                <p><strong>Sujet:</strong> {subject}</p>
                <p><strong>Votre message:</strong></p>
                <p style="white-space: pre-wrap;">{message}</p>
            </div>
            
            <p>Notre équipe examinera votre demande et vous répondra dans les plus brefs délais.</p>
            
            <div class="footer">
                <p>Cordialement,<br><strong>L'équipe VoiceAgent</strong></p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        return EmailService.send_email(
            to_email=to_email,
            subject=f"Confirmation de votre demande de support - {ticket_number}",
            body_text=body_text,
            body_html=body_html
        )
    
    @staticmethod
    def send_support_ticket_notification(
        ticket_number: str,
        name: str,
        email: str,
        subject: str,
        message: str,
        category: str,
        priority: str
    ) -> bool:
        """Send notification to support team when new ticket is created"""
        
        support_email = getattr(settings, 'SUPPORT_EMAIL', 'support@voiceagent.ai')
        
        body_text = f"""
Nouveau ticket de support reçu:

Numéro: {ticket_number}
De: {name} ({email})
Sujet: {subject}
Catégorie: {category}
Priorité: {priority}

Message:
{message}

---
VoiceAgent Support System
        """
        
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc2626; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; }}
        .ticket-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .label {{ font-weight: bold; color: #666; }}
        .priority-{priority.lower()} {{ background: {('red' if priority == 'urgent' else 'orange' if priority == 'high' else 'yellow' if priority == 'medium' else 'green')}; color: white; padding: 4px 8px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🎫 Nouveau Ticket de Support</h2>
        </div>
        <div class="content">
            <div class="ticket-info">
                <p><span class="label">Numéro:</span> {ticket_number}</p>
                <p><span class="label">De:</span> {name} ({email})</p>
                <p><span class="label">Sujet:</span> {subject}</p>
                <p><span class="label">Catégorie:</span> {category}</p>
                <p><span class="label">Priorité:</span> <span class="priority-{priority.lower()}">{priority}</span></p>
            </div>
            
            <p><span class="label">Message:</span></p>
            <div style="background: white; padding: 15px; border-radius: 8px; white-space: pre-wrap;">
{message}
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        return EmailService.send_email(
            to_email=support_email,
            subject=f"[{priority.upper()}] Nouveau ticket: {subject}",
            body_text=body_text,
            body_html=body_html
        )


# Convenience function for easy importing
async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Async wrapper for sending emails
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text email body (optional, will be auto-generated if not provided)
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # If no text content provided, create a simple text version
    if not text_content:
        # Strip HTML tags for basic text version
        import re
        text_content = re.sub('<[^<]+?>', '', html_content)
    
    return EmailService.send_email(
        to_email=to_email,
        subject=subject,
        body_text=text_content,
        body_html=html_content
    )
