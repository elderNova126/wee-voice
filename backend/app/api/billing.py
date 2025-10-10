from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, validator
import stripe
import os

from app.models import get_db, User, Transaction, Invoice, PaymentStatus, InvoiceStatus
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter()

# Initialize Stripe
if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY


# Pydantic models
class TransactionCreate(BaseModel):
    amount: float
    description: Optional[str] = None


class CreditTopUpRequest(BaseModel):
    amount: float
    
    @validator('amount')
    def validate_amount(cls, v):
        if v < 5.0:
            raise ValueError('Minimum top-up amount is $5.00')
        return v


class TransactionResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    description: Optional[str]
    payment_method: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    amount: float
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    paid_at: Optional[datetime]
    due_date: Optional[datetime]
    stripe_invoice_url: Optional[str]
    stripe_pdf_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str


class SubscriptionUpgradeRequest(BaseModel):
    tier: str  # "basic", "pro", "enterprise"
    payment_method_id: str


# Get all transactions for current user
@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all transactions for the current user"""
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    
    return transactions


# Get all invoices for current user
@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all invoices for the current user"""
    invoices = db.query(Invoice).filter(
        Invoice.user_id == current_user.id
    ).order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    
    return invoices


# Create payment intent (Stripe)
@router.post("/create-payment-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    transaction_data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe payment intent"""
    if not settings.STRIPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service not configured"
        )
    
    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={"user_id": current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(transaction_data.amount * 100),  # Convert to cents
            currency="usd",
            customer=current_user.stripe_customer_id,
            description=transaction_data.description,
            metadata={
                "user_id": current_user.id,
                "user_email": current_user.email
            }
        )
        
        # Create transaction record
        transaction = Transaction(
            user_id=current_user.id,
            amount=transaction_data.amount,
            currency="usd",
            status=PaymentStatus.PENDING,
            description=transaction_data.description,
            stripe_payment_intent_id=intent.id
        )
        db.add(transaction)
        db.commit()
        
        return PaymentIntentResponse(
            client_secret=intent.client_secret,
            payment_intent_id=intent.id
        )
    
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment intent: {str(e)}"
        )


# Upgrade subscription
@router.post("/upgrade-subscription")
async def upgrade_subscription(
    upgrade_data: SubscriptionUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upgrade user subscription"""
    if not settings.STRIPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service not configured"
        )
    
    try:
        # Price IDs for different tiers (you should set these in your Stripe dashboard)
        price_map = {
            "basic": os.getenv("STRIPE_BASIC_PRICE_ID", "price_basic"),
            "pro": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro"),
            "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise")
        }
        
        if upgrade_data.tier not in price_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subscription tier"
            )
        
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                payment_method=upgrade_data.payment_method_id,
                invoice_settings={"default_payment_method": upgrade_data.payment_method_id}
            )
            current_user.stripe_customer_id = customer.id
        else:
            # Attach payment method to existing customer
            stripe.PaymentMethod.attach(
                upgrade_data.payment_method_id,
                customer=current_user.stripe_customer_id
            )
            stripe.Customer.modify(
                current_user.stripe_customer_id,
                invoice_settings={"default_payment_method": upgrade_data.payment_method_id}
            )
        
        # Cancel existing subscription if any
        if current_user.stripe_subscription_id:
            stripe.Subscription.delete(current_user.stripe_subscription_id)
        
        # Create new subscription
        subscription = stripe.Subscription.create(
            customer=current_user.stripe_customer_id,
            items=[{"price": price_map[upgrade_data.tier]}],
            metadata={
                "user_id": current_user.id,
                "tier": upgrade_data.tier
            }
        )
        
        # Update user record
        current_user.stripe_subscription_id = subscription.id
        current_user.subscription_tier = upgrade_data.tier
        db.commit()
        
        return {
            "success": True,
            "subscription_id": subscription.id,
            "tier": upgrade_data.tier
        }
    
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error upgrading subscription: {str(e)}"
        )


# Cancel subscription
@router.post("/cancel-subscription")
async def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel user subscription"""
    if not settings.STRIPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service not configured"
        )
    
    if not current_user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )
    
    try:
        # Cancel subscription at period end
        subscription = stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        return {
            "success": True,
            "message": "Subscription will be cancelled at period end",
            "cancel_at": subscription.cancel_at
        }
    
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


# Webhook for Stripe events
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    if not settings.STRIPE_API_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook not configured"
        )
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    
    # Handle the event
    if event.type == "payment_intent.succeeded":
        payment_intent = event.data.object
        
        # Update transaction status
        transaction = db.query(Transaction).filter(
            Transaction.stripe_payment_intent_id == payment_intent.id
        ).first()
        
        if transaction:
            transaction.status = PaymentStatus.SUCCEEDED
            transaction.stripe_charge_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
            transaction.payment_method = payment_intent.payment_method
            
            # If this is a credit top-up, add credits to user balance
            if payment_intent.metadata.get("type") == "credit_topup":
                user = db.query(User).filter(User.id == transaction.user_id).first()
                if user:
                    credit_amount = float(payment_intent.metadata.get("amount", 0))
                    user.credit_balance += credit_amount
            
            db.commit()
    
    elif event.type == "payment_intent.payment_failed":
        payment_intent = event.data.object
        
        # Update transaction status
        transaction = db.query(Transaction).filter(
            Transaction.stripe_payment_intent_id == payment_intent.id
        ).first()
        
        if transaction:
            transaction.status = PaymentStatus.FAILED
            db.commit()
    
    elif event.type == "invoice.paid":
        invoice = event.data.object
        
        # Create invoice record
        user = db.query(User).filter(
            User.stripe_customer_id == invoice.customer
        ).first()
        
        if user:
            invoice_record = Invoice(
                user_id=user.id,
                invoice_number=invoice.number,
                amount=invoice.amount_paid / 100,
                currency=invoice.currency,
                status=InvoiceStatus.PAID,
                period_start=datetime.fromtimestamp(invoice.period_start),
                period_end=datetime.fromtimestamp(invoice.period_end),
                stripe_invoice_id=invoice.id,
                stripe_invoice_url=invoice.hosted_invoice_url,
                stripe_pdf_url=invoice.invoice_pdf,
                paid_at=datetime.fromtimestamp(invoice.status_transitions.paid_at)
            )
            db.add(invoice_record)
            db.commit()
    
    return {"status": "success"}


# Get subscription info
@router.get("/subscription")
async def get_subscription_info(
    current_user: User = Depends(get_current_user)
):
    """Get current subscription information"""
    if not current_user.stripe_subscription_id:
        return {
            "tier": current_user.subscription_tier,
            "active": False
        }
    
    try:
        if settings.STRIPE_API_KEY:
            subscription = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
            
            return {
                "tier": current_user.subscription_tier,
                "active": subscription.status == "active",
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        else:
            return {
                "tier": current_user.subscription_tier,
                "active": True
            }
    except stripe.error.StripeError:
        return {
            "tier": current_user.subscription_tier,
            "active": False
        }


# Get credit balance
@router.get("/credit-balance")
async def get_credit_balance(
    current_user: User = Depends(get_current_user)
):
    """Get user's credit balance"""
    return {
        "balance": current_user.credit_balance,
        "currency": "USD"
    }


# Top up credits
@router.post("/top-up-credits")
async def top_up_credits(
    top_up_data: CreditTopUpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Top up user credits"""
    if not settings.STRIPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service not configured"
        )
    
    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={"user_id": current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Create payment intent for credit top-up
        intent = stripe.PaymentIntent.create(
            amount=int(top_up_data.amount * 100),  # Convert to cents
            currency="usd",
            customer=current_user.stripe_customer_id,
            description=f"Credit top-up: ${top_up_data.amount:.2f}",
            metadata={
                "user_id": current_user.id,
                "type": "credit_topup",
                "amount": top_up_data.amount
            }
        )
        
        # Create transaction record
        transaction = Transaction(
            user_id=current_user.id,
            amount=top_up_data.amount,
            currency="usd",
            status=PaymentStatus.PENDING,
            description=f"Credit top-up: ${top_up_data.amount:.2f}",
            stripe_payment_intent_id=intent.id
        )
        db.add(transaction)
        db.commit()
        
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": top_up_data.amount
        }
    
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing top-up: {str(e)}"
        )

