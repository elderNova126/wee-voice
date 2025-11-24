"""
Async Email Service
Non-blocking email sending using asyncio and thread pool executor
"""
import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import functools

from app.core.config import settings
from app.core.performance import smtp_pool

logger = logging.getLogger(__name__)

# Thread pool for blocking SMTP operations
_email_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="email_worker")


def _send_email_sync(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> bool:
    """
    Synchronous email sending (runs in thread pool)
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
            logger.warning("SMTP not configured - email not sent")
            return False
        
        # Send email
        smtp_port = getattr(settings, 'SMTP_PORT', 587)
        smtp_user = getattr(settings, 'SMTP_USER', None)
        smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        use_tls = getattr(settings, 'SMTP_USE_TLS', True)
        
        if not smtp_user or not smtp_password:
            logger.warning("SMTP credentials not configured - email not sent")
            return False
        
        logger.debug(f"Sending email to {to_email}: {subject}")
        
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if use_tls:
                server.starttls()
            
            server.login(smtp_user, smtp_password)
            failed_recipients = server.send_message(msg)
            
            if failed_recipients:
                logger.error(f"Email sending failed for recipients: {failed_recipients}")
                return False
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False


async def send_email_async(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> bool:
    """
    Async email sending - doesn't block the event loop
    
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
    # Use connection pool to limit concurrent SMTP connections
    async with smtp_pool:
        # Run blocking SMTP operation in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _email_executor,
            functools.partial(
                _send_email_sync,
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_email=from_email,
                from_name=from_name
            )
        )


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Convenience function for sending emails (async)
    
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
    
    return await send_email_async(
        to_email=to_email,
        subject=subject,
        body_text=text_content,
        body_html=html_content
    )


def send_email_background(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
):
    """
    Fire-and-forget email sending
    Triggers email send as a background task without waiting
    """
    asyncio.create_task(send_email(to_email, subject, html_content, text_content))
    logger.debug(f"Email queued for background sending to {to_email}")

