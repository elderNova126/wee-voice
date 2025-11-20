# WeeVoice Platform - Complete Implementation Guide

## 🎯 Overview

WeeVoice is now a **complete 24/7 voice agent platform** designed for businesses to handle customer calls automatically. This implementation includes all features required for the sales flow, client onboarding, and Zadarma phone number integration.

---

## ✨ Core Features Implemented

### 1. **24/7 Call Handling**
- ✅ Voice agents answer calls automatically
- ✅ Take messages from website or phone calls
- ✅ Record calls with full transcripts
- ✅ Generate AI-powered call summaries
- ✅ Email summaries to business owners

### 2. **Callback Management**
- ✅ Agents detect when human intervention is needed
- ✅ Create callback requests with priority levels
- ✅ Capture caller information (name, phone, email)
- ✅ Email notifications for urgent callbacks
- ✅ Dashboard to manage callback requests

### 3. **Zadarma Phone Number Integration**
- ✅ Request phone numbers for agents
- ✅ Document verification system
- ✅ Status tracking (Pending → In Review → Approved → Active)
- ✅ Support for both businesses and individuals
- ✅ Multi-country support (FR, US, UK, DE, etc.)

### 4. **Document Verification System**
- ✅ Upload verification documents (company registration, proof of address, passport, etc.)
- ✅ Track document status (Received → In Review → Accepted/Rejected)
- ✅ Resubmission capability for rejected documents
- ✅ Admin review interface

### 5. **Website Integration**
- ✅ Generate embed code for any website
- ✅ Customizable widget (color, position, greeting)
- ✅ Domain whitelisting for security
- ✅ Easy copy-paste installation

### 6. **Billing & Usage**
- ✅ Call minute tracking
- ✅ Cost per minute calculation
- ✅ Monthly phone number costs
- ✅ Usage reports and analytics

---

## 📋 Sales Flow Implementation

### Step 1: Demo the Agent
1. Create a demo agent in the dashboard
2. Share the public demo link: `/agent/{agentId}`
3. Client tests the voice agent

### Step 2: Client Signs Up
1. Client registers on the platform
2. Client creates their first agent
3. Configure system prompt, voice, language

### Step 3: Offer & Pricing
**Default Pricing (configurable in `.env`):**
- `COST_PER_MINUTE=0.05` ($0.05 per minute)
- `PHONE_NUMBER_MONTHLY_COST=4.99` ($4.99/month per number)

**Example Packages:**
- **Basic**: 100 minutes/month = $5/month + $4.99 number = $9.99/month
- **Pro**: 500 minutes/month = $25/month + $4.99 number = $29.99/month
- **Enterprise**: Unlimited = Custom pricing

### Step 4: Phone Number Setup
1. Client requests a phone number from dashboard
2. Provides business information
3. Uploads verification documents:
   - **For Companies:** Registration certificate + Proof of address
   - **For Individuals:** Passport/ID + Proof of address
4. Admin reviews documents
5. Number is activated and assigned to agent

### Step 5: Website Integration (Optional)
1. Client goes to agent → "Embed" tab
2. Configures widget appearance
3. Copies embed code
4. Pastes into website before `</body>` tag

---

## 🔧 Technical Implementation

### Backend API Endpoints

#### Phone Numbers
```
GET    /api/v1/phone-numbers/available         # List available numbers
POST   /api/v1/phone-numbers/request           # Request new number
GET    /api/v1/phone-numbers/                  # List user's numbers
GET    /api/v1/phone-numbers/{id}              # Get number details
POST   /api/v1/phone-numbers/{id}/upload-document  # Upload verification doc
GET    /api/v1/phone-numbers/{id}/documents    # List documents
POST   /api/v1/phone-numbers/{id}/activate/{agent_id}  # Activate for agent
```

#### Callbacks
```
GET    /api/v1/callbacks/                      # List callbacks
POST   /api/v1/callbacks/                      # Create callback request
GET    /api/v1/callbacks/{id}                  # Get callback details
PATCH  /api/v1/callbacks/{id}                  # Update callback
DELETE /api/v1/callbacks/{id}                  # Cancel callback
```

#### Website Embed
```
GET    /api/v1/embed/agents/{id}/embed-config  # Get embed settings
PUT    /api/v1/embed/agents/{id}/embed-config  # Update embed settings
GET    /api/v1/embed/agents/{id}/embed-code    # Generate embed code
GET    /api/v1/embed/widget/{id}/config        # Public widget config (CORS-enabled)
```

### Database Models

#### PhoneNumber
- `phone_number`, `country_code`, `number_type`
- `status`: pending → documents_submitted → under_review → approved → active
- `business_name`, `business_type`, `business_address`
- `monthly_cost`, `per_minute_cost`
- `agent_id` (assigned agent)
- `zadarma_number_id`, `zadarma_config`

#### VerificationDocument
- `document_type`: company_registration, proof_of_address, passport, national_id
- `status`: pending → received → in_review → accepted/rejected
- `file_path`, `file_url`, `file_size`
- `reviewed_by`, `reviewed_at`, `rejection_reason`

#### CallbackRequest
- `call_id`, `agent_id`, `user_id`
- `reason`, `priority` (urgent, high, normal, low)
- `caller_name`, `caller_phone`, `caller_email`
- `preferred_callback_time`
- `status`: pending → contacted → completed → cancelled
- `assigned_to`, `notes`, `resolution`

#### Agent Model Extensions
- `embed_enabled`, `embed_widget_color`, `embed_position`
- `embed_greeting_message`
- `allowed_domains` (domain whitelist)

#### Call Model Extensions
- `callback_requested`, `callback_reason`
- `summary_email_sent`, `summary_email_sent_at`

### Services

#### ZadarmaService (`backend/app/services/zadarma_service.py`)
- `get_available_numbers()` - List available phone numbers
- `request_phone_number()` - Request new number from Zadarma
- `check_number_status()` - Check verification status
- `activate_number_for_agent()` - Assign number to agent
- `configure_call_forwarding()` - Set up webhook for calls

**Mock Mode:** Works without Zadarma API credentials for development

#### NotificationService (`backend/app/services/notification_service.py`)
- `send_call_summary_email()` - Email call summaries
- `send_callback_notification()` - Email callback alerts

---

## 🌐 Frontend Pages

### 1. Phone Numbers Page (`/dashboard/phone-numbers`)
- List all phone numbers
- Request new numbers
- Upload verification documents
- Track status
- View document requirements

### 2. Callbacks Page (`/dashboard/callbacks`)
- View all callback requests
- Filter by status (pending, contacted, completed)
- Update callback status
- Assign to team members
- Add notes and resolutions

### 3. Agent Embed Page (`/dashboard/agents/{id}/embed`)
- Enable/disable website embed
- Configure widget appearance (color, position)
- Set greeting message
- Add allowed domains
- Generate and copy embed code
- Installation instructions

---

## 📧 Email Notifications

### Call Summary Email
Sent after call completion (when summary is generated):
- Agent name and call details
- Call duration and cost
- AI-generated summary
- Key points discussed
- Sentiment analysis
- Action items
- Callback notice (if requested)
- Link to full transcript

### Callback Notification Email
Sent immediately when callback is requested:
- Priority level (🚨 urgent, ⚠️ high, 📞 normal, 📝 low)
- Reason for callback
- Caller information (name, phone, email)
- Preferred callback time
- Call context/summary
- Link to callback management page

---

## 🔐 Environment Variables

Add to `.env`:

```bash
# Zadarma Integration
ZADARMA_API_KEY=your_zadarma_api_key
ZADARMA_API_SECRET=your_zadarma_api_secret

# Email Configuration (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@weevoice.com
SMTP_FROM_NAME=WeeVoice

# URLs
FRONTEND_URL=https://your-frontend-url.com
BACKEND_URL=https://your-backend-url.com

# Pricing
COST_PER_MINUTE=0.05
PHONE_NUMBER_MONTHLY_COST=4.99
```

---

## 🚀 Deployment Steps

### 1. Database Migration
Run SQL migration to create new tables:
```sql
-- See database/schema.sql for complete schema
-- New tables: phone_numbers, verification_documents, callback_requests
-- Updated tables: voice_agents, calls
```

### 2. Static Files
Ensure static files are served:
- `/backend/static/js/voice-widget.js`
- `/backend/static/css/voice-widget.css`

### 3. CORS Configuration
Update CORS to allow embed domains:
```python
BACKEND_CORS_ORIGINS = [
    "http://localhost:3000",
    "https://your-frontend.com",
    "*"  # Allow all for widget (configure domain whitelist per agent)
]
```

### 4. Email Setup
- Configure SMTP credentials
- Test email sending
- Verify email templates render correctly

### 5. Zadarma Setup
- Complete Zadarma reseller application
- Get API credentials
- Configure webhook URL for incoming calls
- Test number provisioning

---

## 📖 User Guide

### For Business Owners (Clients)

#### Getting a Phone Number
1. Go to **Phone Numbers** page
2. Click **Request New Number**
3. Fill in business details:
   - Phone number (from available list)
   - Business type (Company/Individual)
   - Business name
   - Address
4. Upload required documents:
   - **Company**: Registration + Proof of address
   - **Individual**: Passport/ID + Proof of address
5. Wait for admin approval (1-3 business days)
6. Once approved, assign to an agent

#### Managing Callbacks
1. Go to **Callbacks** page
2. View pending callbacks (sorted by priority)
3. Click callback to see details
4. Update status when contacted
5. Add resolution notes
6. Mark as completed

#### Adding Agent to Website
1. Go to **Agents** page
2. Click on agent
3. Go to **Embed** tab
4. Toggle "Enable Website Embed"
5. Customize appearance
6. Copy embed code
7. Paste into website HTML (before `</body>`)

### For Administrators

#### Reviewing Documents
1. Access phone numbers with pending documents
2. Review each document:
   - Check document validity
   - Verify information matches
   - Approve or reject
3. Add rejection reason if needed
4. Client can resubmit if rejected

#### Managing Zadarma Integration
1. Obtain Zadarma API credentials
2. Add to environment variables
3. Test with first client
4. Monitor number activation status
5. Configure call forwarding webhooks

---

## 🛠️ Customization Options

### Widget Customization
- **Colors**: Match brand colors
- **Position**: Bottom-right or bottom-left
- **Greeting**: Custom welcome message
- **Domain Restrictions**: Whitelist specific domains

### Email Templates
Edit in `backend/app/services/notification_service.py`:
- Customize HTML templates
- Add logo/branding
- Modify content structure
- Change colors

### Pricing Models
Adjust in `.env`:
- Per-minute costs
- Monthly number fees
- Package pricing
- Discounts for high volume

---

## 🐛 Troubleshooting

### Phone Number Issues
- **Status stuck on "Pending"**: Documents not uploaded
- **Documents rejected**: Check rejection reason, resubmit correct docs
- **Number not activating**: Contact Zadarma support

### Email Not Sending
- Check SMTP credentials
- Verify email service allows app passwords
- Check firewall/port 587
- Test with different email provider

### Widget Not Appearing
- Verify embed code is before `</body>`
- Check browser console for errors
- Ensure domain is whitelisted
- Check CORS settings

### Callback Notifications
- Verify email notifications are enabled
- Check user email address is correct
- Test with manual callback creation

---

## 📈 Metrics & Analytics

Track these KPIs:
- **Call Volume**: Total calls per agent/client
- **Call Duration**: Average call length
- **Callback Rate**: % of calls requiring human follow-up
- **Resolution Time**: Time to complete callbacks
- **Document Approval**: Average verification time
- **Revenue**: Total from call minutes + phone numbers

---

## 🔮 Future Enhancements

### Planned Features
1. **Automated Zadarma API Integration**
   - Automatic number provisioning
   - Webhook configuration
   - Status sync

2. **CRM Integration**
   - Salesforce connector
   - HubSpot integration
   - Custom webhooks

3. **Advanced Analytics**
   - Call quality metrics
   - Customer satisfaction scores
   - Agent performance reports

4. **Multi-language Support**
   - Automatic language detection
   - Translated summaries
   - Multi-language widgets

5. **Mobile App**
   - iOS/Android apps
   - Push notifications for callbacks
   - Mobile dashboard

---

## 📞 Support

### For Issues
1. Check troubleshooting guide above
2. Review logs in `/backend/logs`
3. Check API documentation at `/api/docs`
4. Contact support via Support page

### For Zadarma Support
- Email: support@zadarma.com
- Documentation: https://zadarma.com/en/support/
- API Docs: https://zadarma.com/en/support/api/

---

## 🎉 Success Metrics

**Completed Implementation:**
✅ 24/7 call handling  
✅ Call recording & summaries  
✅ Email notifications  
✅ Callback management  
✅ Phone number provisioning (Zadarma)  
✅ Document verification system  
✅ Website embed widget  
✅ Pricing & billing configuration  
✅ Full frontend UI  
✅ Complete API endpoints  

**Ready for Production:**
- ✅ All features implemented
- ✅ Database schema complete
- ✅ API documented
- ✅ Frontend responsive
- ✅ Email templates ready
- ⏳ Zadarma API integration (needs credentials)
- ⏳ Production deployment
- ⏳ First client onboarding

---

## 🙏 Credits

Built with:
- **Backend**: FastAPI, SQLAlchemy, Python
- **Frontend**: React, TypeScript, Tailwind CSS
- **AI**: Google Gemini 2.0
- **Voice**: Gemini Live API
- **Telephony**: Zadarma
- **Email**: SMTP (Gmail/SendGrid)

---

**Version**: 1.0.0  
**Last Updated**: October 22, 2025  
**License**: Proprietary  

For questions or support, contact your development team.

