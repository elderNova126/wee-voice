# Public Agents on Landing Page - Feature Documentation

## Overview

Public agents are now displayed on the landing page (homepage), allowing visitors to interact with agents without signing up. This feature enables admins and users to showcase their agents to the public.

## Default Public Agents

Run the helper script below to create or refresh the bundled demo agents:

```
python backend/scripts/seed_public_agents.py
```

The script ensures the following public agents are available:
- **Assistant Démo Français** – French concierge that explains the WeeVoice platform.
- **Dubai Real Estate Discovery** – Agent francophone qui réalise des appels de découverte immobilière à Dubaï, gère les objections initiales et collecte les informations de qualification sans proposer d’offres.

## What Was Implemented

### 1. Backend API Endpoint
**File:** `backend/app/api/agents.py`

**New Endpoint:**
```python
@router.get("/public/list", response_model=List[AgentResponse])
def list_public_agents(db: Session = Depends(get_db)):
    """Get all public agents (no authentication required)"""
    agents = db.query(VoiceAgent).filter(
        VoiceAgent.is_public == True,
        VoiceAgent.is_active == True
    ).order_by(VoiceAgent.created_at.desc()).all()
    
    return agents
```

**Features:**
- ✅ No authentication required
- ✅ Returns only agents marked as public and active
- ✅ Ordered by creation date (newest first)

### 2. Frontend Landing Page Updates
**File:** `frontend/src/pages/LandingPage.tsx`

**New Section Added:**
- "Agents Publics Disponibles" (Public Agents Available)
- Displays cards for each public agent
- Shows agent name, description, language, and RAG status
- "Essayer Maintenant" button links to demo with specific agent

**Features:**
- ✅ Auto-loads public agents on page load
- ✅ Beautiful card design with hover effects
- ✅ Shows language badge (Français/English)
- ✅ Shows "Knowledge Base" badge if RAG is enabled
- ✅ Loading spinner while fetching agents
- ✅ Graceful handling when no agents are available

### 3. Dedicated Public Agent Page (NEW!)
**File:** `frontend/src/pages/PublicAgentPage.tsx`

**URL Pattern:**
```
/agent/:agentId
```

**Features:**
- ✅ Clean, dedicated page for each public agent
- ✅ Shows agent name, description, and features
- ✅ Language and RAG status badges
- ✅ Direct "Start Conversation" button
- ✅ No agent selector (focused experience)
- ✅ Validates agent is public and active
- ✅ Redirects to homepage if agent not found
- ✅ Real-time voice conversation interface
- ✅ "Back to Home" button for easy navigation
- ✅ Tips section for best experience
- ✅ Responsive design

### 4. Demo Page Integration
**File:** `frontend/src/pages/DemoPage.tsx`

**URL Parameter Support (Still Available):**
```typescript
// URL: /demo?agent=2
const [searchParams] = useSearchParams()
const urlAgentId = searchParams.get('agent')
```

**Features:**
- ✅ Accepts `?agent=X` parameter in URL
- ✅ Auto-selects specified agent
- ✅ Falls back to default if agent not found
- ✅ Works seamlessly with existing demo functionality
- ✅ Shows agent selector for browsing all demo agents

## How to Use

### For Admins/Users: Making an Agent Public

1. Go to your **Agents** page
2. Edit an agent
3. Toggle **"Is Public"** to ON
4. Save the agent
5. The agent will now appear on the landing page

### For Visitors: Trying a Public Agent

1. Visit the homepage (landing page)
2. Scroll to the **"Agents Publics Disponibles"** section
3. Browse available public agents
4. Click **"Essayer Maintenant"** on any agent
5. You'll be redirected to `/agent/X` where X is the agent ID
6. See dedicated agent page with clean interface
7. Click "Start Conversation" to begin
8. Start talking with the agent (no login required)

## User Flow

```
Visitor → Landing Page → See Public Agents → Click "Try Now" 
   → Dedicated Agent Page (/agent/X) → Voice Conversation
```

**Benefits of Dedicated Page:**
- ✅ Clean, focused interface for single agent
- ✅ No agent selector dropdown (reduces confusion)
- ✅ Shows agent details prominently
- ✅ Direct "Start Conversation" button
- ✅ Better branding (not labeled as "demo")
- ✅ Shareable direct link to specific agent

## Configuration

### Making an Agent Public

**Database Field:**
```python
class VoiceAgent:
    is_public = Column(Boolean, default=False)  # Set to True
    is_active = Column(Boolean, default=True)   # Must be True
```

**Requirements for Public Agent:**
- ✅ `is_public = True`
- ✅ `is_active = True`
- ✅ Agent must be properly configured with system prompt
- ✅ Optional: RAG enabled with documents for better responses

## API Usage

### Get Public Agents

```bash
curl -X GET http://localhost:8000/agents/public/list
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "French Customer Service",
    "description": "Helpful customer service agent in French",
    "language": "fr-FR",
    "rag_enabled": true,
    "is_public": true,
    "is_active": true,
    ...
  }
]
```

### Try Agent via Direct URL

```bash
# Direct link to specific public agent page
https://yoursite.com/agent/1

# Alternative: Demo page with agent parameter
https://yoursite.com/demo?agent=1
```

## UI/UX Features

### Agent Card Design
- **Icon**: Purple gradient with microphone icon
- **Name**: Bold, prominent display
- **Description**: 2-line truncated preview
- **Badges**:
  - Language (blue): Shows `Français` or `English`
  - Knowledge Base (purple): Shows if RAG is enabled
- **Button**: Gradient "Try Now" button with phone icon

### Visual Elements
- ✅ Sparkles icon badge: "Essayez Maintenant"
- ✅ Section title: "Agents Publics Disponibles"
- ✅ Subtitle: "Testez nos agents vocaux intelligents - aucune inscription requise"
- ✅ Hover effects on cards (border color change, shadow increase)
- ✅ Gradient overlays on hover
- ✅ Responsive grid (1 column mobile, 2 tablet, 3 desktop)

### Empty State
If no public agents are available:
- Shows microphone icon
- Message: "Aucun agent public disponible pour le moment"
- Call-to-action button to create first agent (if not authenticated)

## Security Considerations

### What's Safe ✅
- Public agents can be accessed without authentication
- Websocket allows connection to public agents (already implemented)
- No sensitive data exposed in agent list

### What's Protected 🔒
- Private agents (is_public=False) are NOT returned
- User information is not exposed
- Only active agents are shown
- System prompts and internal configs are not exposed to public

## Testing

### Test the Feature

1. **Create a Public Agent:**
   ```python
   # In Python/Database
   from app.models.database import SessionLocal
   from app.models.agent import VoiceAgent
   
   db = SessionLocal()
   agent = db.query(VoiceAgent).filter(VoiceAgent.id == 1).first()
   agent.is_public = True
   agent.is_active = True
   db.commit()
   ```

2. **Verify API Endpoint:**
   ```bash
   curl http://localhost:8000/agents/public/list
   ```

3. **Check Landing Page:**
   - Visit `http://localhost:5173/` (or your frontend URL)
   - Scroll down to see "Agents Publics Disponibles"
   - Should see your public agent(s)

4. **Test Agent Selection:**
   - Click "Essayer Maintenant" on an agent
   - Should redirect to `/demo?agent=X`
   - Agent should be pre-selected in demo page

5. **Test Voice Conversation:**
   - Click "Start Conversation" in demo
   - Should connect without requiring login
   - Should work exactly like authenticated demo

## Troubleshooting

### Public Agents Not Showing

**Problem:** Landing page doesn't show any agents

**Solutions:**
1. Check if agents are marked as public:
   ```python
   db.query(VoiceAgent).filter(VoiceAgent.is_public == True).all()
   ```

2. Verify backend endpoint works:
   ```bash
   curl http://localhost:8000/agents/public/list
   ```

3. Check browser console for API errors

4. Ensure backend server is running

### Redirected to Homepage Instead of Agent Page

**Problem:** Clicking "Try Now" goes to homepage

**Solutions:**
1. Verify agent is marked as `is_public = True`
2. Verify agent is marked as `is_active = True`
3. Check `/agents/public/list` endpoint returns the agent
4. Check browser console for errors
5. Verify route `/agent/:agentId` exists in App.tsx

### Connection Fails for Public Agent

**Problem:** Can't connect to agent voice

**Solutions:**
1. Verify agent is both public AND active
2. Check websocket allows public agents (should already be configured)
3. Check browser microphone permissions
4. Review backend logs for errors

## Future Enhancements

### Potential Improvements
- 🔮 Agent categories/tags for filtering
- 🔮 Search functionality for agents
- 🔮 Agent ratings and reviews
- 🔮 Usage statistics for public agents
- 🔮 Featured/promoted agents section
- 🔮 Agent preview (sample conversation)
- 🔮 Custom agent thumbnails/avatars

## Files Modified

1. **Backend:**
   - `backend/app/api/agents.py` - Added `/public/list` endpoint

2. **Frontend:**
   - `frontend/src/pages/PublicAgentPage.tsx` - **NEW** dedicated public agent page
   - `frontend/src/pages/LandingPage.tsx` - Added public agents section, links to `/agent/X`
   - `frontend/src/pages/DemoPage.tsx` - Added URL parameter support
   - `frontend/src/App.tsx` - Added route for `/agent/:agentId`

## Summary

✅ **Public agents displayed on landing page**
✅ **Dedicated page for each public agent** (`/agent/X`)
✅ **Clean, focused interface** (no agent selector)  
✅ **Visitors can try agents without signing up**  
✅ **Beautiful UI with agent cards**  
✅ **Shows language and RAG status**  
✅ **No authentication required**  
✅ **Shareable direct links**  
✅ **Mobile responsive**

### Key Improvements Over Demo Page

| Feature | Demo Page | Public Agent Page |
|---------|-----------|-------------------|
| URL | `/demo?agent=X` | `/agent/X` |
| Agent Selector | ✓ Shown | ✗ Hidden |
| Branding | "Demo" | Agent-specific |
| Focus | All agents | Single agent |
| Shareability | Good | Excellent |
| User Experience | Multi-agent | Dedicated |

This feature makes your voice agent platform more accessible and provides a professional, focused experience for visitors trying specific agents!

---

**Ready to use!** Just mark any agent as public (`is_public=True`) and visitors can access it at `/agent/X`. 🎉

