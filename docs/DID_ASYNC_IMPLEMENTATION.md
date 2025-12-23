# D-ID Async Implementation Guide
## Running D-ID in Background Without Blocking Gemini

## 🎯 Problem & Solution

### The Challenge
```python
# ❌ WRONG: This blocks Gemini!
user_speaks()
gemini_response = await gemini.process()  # 300ms
avatar_video = await did.create()         # 60,000ms! 🐢
send_to_user(gemini_response, avatar_video)
# User waits 60 seconds! Not acceptable!
```

### The Solution
```python
# ✅ CORRECT: Background processing
user_speaks()
gemini_response = await gemini.process()  # 300ms
send_to_user(gemini_response)             # User gets answer fast!

# Meanwhile, in background:
asyncio.create_task(did.create())         # Runs separately
# Avatar updates later when ready
```

## 🚀 **Approach 1: Pre-Generation (RECOMMENDED)**

Generate avatar videos **BEFORE** the call starts.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: Setup (One-time, before any calls)           │
├─────────────────────────────────────────────────────────┤
│  User uploads photo                                     │
│     ↓                                                   │
│  Background task starts (async)                         │
│     ↓                                                   │
│  D-ID generates base avatar model (60s)                │
│     ↓                                                   │
│  Store avatar template in DB                            │
│     ✅ Ready for instant use in calls!                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  PHASE 2: Real-Time Call (No D-ID delays!)             │
├─────────────────────────────────────────────────────────┤
│  User speaks (0ms)                                      │
│     ↓                                                   │
│  Gemini processes (300ms) ⚡                            │
│     ↓                                                   │
│  Response sent immediately                              │
│     ↓                                                   │
│  Pre-generated avatar plays (instant!)                  │
│     ✅ Total: 500ms (FAST!)                            │
└─────────────────────────────────────────────────────────┘
```

### Backend Implementation

```python
# backend/app/api/avatars.py

import asyncio
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_avatar_photo(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload photo and trigger background avatar generation"""
    
    # Step 1: Save photo immediately (fast)
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode('utf-8')
    photo_url = f"data:{file.content_type};base64,{base64_image}"
    
    current_user.avatar_photo_url = photo_url
    current_user.avatar_photo_type = 'upload'
    current_user.avatar_enabled = True
    db.commit()
    
    # Step 2: Generate avatar in background (slow, doesn't block)
    background_tasks.add_task(
        generate_avatar_async,
        user_id=current_user.id,
        photo_url=photo_url
    )
    
    # Step 3: Return immediately (user doesn't wait!)
    return {
        "message": "Photo uploaded! Avatar is being generated...",
        "photo_url": photo_url,
        "status": "processing"  # Will become "ready" later
    }


async def generate_avatar_async(user_id: int, photo_url: str):
    """
    Background task: Generate D-ID avatar without blocking
    This runs in a separate thread and doesn't affect Gemini speed!
    """
    from app.models.database import SessionLocal
    from app.services.avatar_service import avatar_service
    
    db = SessionLocal()
    try:
        logger.info(f"🎬 Starting background avatar generation for user {user_id}")
        
        # This takes 60s but doesn't block anything!
        result = await avatar_service.create_talking_avatar(
            photo_url=photo_url,
            text="Hello! I'm ready to help you.",  # Test phrase
        )
        
        if result.get("success"):
            # Save the generated avatar
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.avatar_video_id = result.get("video_id")
                user.avatar_video_url = result.get("video_url")
                user.avatar_status = "ready"
                db.commit()
                
                logger.info(f"✅ Avatar ready for user {user_id}")
                
                # Optional: Notify user via WebSocket
                await notify_avatar_ready(user_id)
        else:
            logger.error(f"❌ Avatar generation failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error in background avatar generation: {e}")
    finally:
        db.close()


async def notify_avatar_ready(user_id: int):
    """Notify user that avatar is ready (via WebSocket)"""
    # This would connect to your existing WebSocket system
    pass
```

### Database Schema Update

```python
# backend/app/models/user.py

class User(Base):
    __tablename__ = "users"
    
    # ... existing fields ...
    
    # Avatar fields (already added)
    avatar_photo_url = Column(String, nullable=True)
    avatar_photo_type = Column(String, nullable=True)
    avatar_enabled = Column(Boolean, default=False)
    
    # NEW: D-ID specific fields
    avatar_video_id = Column(String, nullable=True)      # D-ID video ID
    avatar_video_url = Column(String, nullable=True)     # Generated video URL
    avatar_status = Column(String, default="none")       # none, processing, ready, error
    avatar_created_at = Column(DateTime, nullable=True)
```

### Migration Script

```sql
-- database/migrations/add_did_avatar_fields.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_video_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_video_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_status VARCHAR(50) DEFAULT 'none';
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_created_at TIMESTAMP;

COMMENT ON COLUMN users.avatar_video_id IS 'D-ID video ID for generated avatar';
COMMENT ON COLUMN users.avatar_video_url IS 'URL to generated D-ID avatar video';
COMMENT ON COLUMN users.avatar_status IS 'Status: none, processing, ready, error';
```

### Frontend Implementation

```typescript
// frontend/src/components/ui/AvatarPhotoSelector.tsx

const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
  const file = event.target.files?.[0]
  if (!file) return
  
  setIsUploading(true)
  
  try {
    // Upload photo
    const response = await avatarAPI.uploadPhoto(file)
    
    // Photo is saved immediately
    setUploadedPhoto(response.data.photo_url)
    setSelectedPhoto(response.data.photo_url)
    
    // Show status
    toast.success(isFrench 
      ? 'Photo téléchargée ! Avatar en cours de génération...' 
      : 'Photo uploaded! Avatar generating...')
    
    // Check status periodically (optional)
    pollAvatarStatus()
    
  } catch (error) {
    toast.error('Upload failed')
  } finally {
    setIsUploading(false)
  }
}

const pollAvatarStatus = async () => {
  const interval = setInterval(async () => {
    const response = await avatarAPI.getCurrentAvatar()
    
    if (response.data.avatar_status === 'ready') {
      toast.success('✅ Avatar ready!')
      clearInterval(interval)
    } else if (response.data.avatar_status === 'error') {
      toast.error('Avatar generation failed')
      clearInterval(interval)
    }
  }, 5000) // Check every 5 seconds
}
```

## 🚀 **Approach 2: Real-Time Background Generation**

Generate avatar during the call but don't block responses.

### Architecture

```
User speaks
    ↓
┌─────────────────────┬─────────────────────────┐
│ MAIN THREAD         │ BACKGROUND THREAD       │
├─────────────────────┼─────────────────────────┤
│ Gemini AI (300ms)   │ (idle)                  │
│ Send response ✅    │                         │
│                     │                         │
│ User speaks again   │ Start D-ID (async)      │
│ Gemini AI (300ms)   │   ↓ (doesn't block)    │
│ Send response ✅    │ Processing...           │
│                     │   ↓                     │
│ User speaks again   │ Still processing...     │
│ Gemini AI (300ms)   │   ↓                     │
│ Send response ✅    │ Avatar ready (60s)      │
│                     │ Update UI ✅            │
└─────────────────────┴─────────────────────────┘
```

### Implementation

```python
# backend/app/api/websocket.py

@router.websocket("/voice/{agent_id}")
async def voice_websocket(
    websocket: WebSocket,
    agent_id: int,
    # ... other params ...
):
    """WebSocket with non-blocking D-ID generation"""
    
    # ... existing connection setup ...
    
    # Background task for avatar generation
    avatar_generation_task = None
    
    async def handle_user_audio(audio_data: bytes):
        """Process user audio - MUST BE FAST!"""
        
        # Step 1: Get Gemini response (300ms - FAST!)
        response = await agent_service.process_audio(audio_data)
        
        # Step 2: Send response immediately (DON'T WAIT for avatar!)
        await websocket.send_json({
            "type": "response",
            "audio": response.audio,
            "text": response.text
        })
        
        # Step 3: Generate avatar in background (NON-BLOCKING)
        if user.avatar_enabled and not avatar_generation_task:
            avatar_generation_task = asyncio.create_task(
                generate_avatar_for_response(
                    photo_url=user.avatar_photo_url,
                    audio_data=response.audio,
                    text=response.text
                )
            )
    
    async def generate_avatar_for_response(
        photo_url: str,
        audio_data: bytes,
        text: str
    ):
        """Generate avatar video in background"""
        try:
            # This takes 60s but runs separately!
            result = await avatar_service.create_talking_avatar(
                photo_url=photo_url,
                audio_url=None,  # Use the audio we already have
                text=text
            )
            
            if result.get("success"):
                # Send avatar video when ready
                await websocket.send_json({
                    "type": "avatar_ready",
                    "video_url": result.get("video_url")
                })
        except Exception as e:
            logger.error(f"Avatar generation failed: {e}")
    
    # ... rest of websocket handling ...
```

## 📊 Performance Comparison

### ❌ Without Background Processing (SLOW)

```
User: "Hello"
  ├─ Gemini: 300ms
  ├─ D-ID: 60,000ms 🐢
  └─ Total: 60,300ms (UNACCEPTABLE!)

User: "How are you?"
  ├─ Gemini: 300ms
  ├─ D-ID: 60,000ms 🐢
  └─ Total: 60,300ms (STILL TERRIBLE!)
```

### ✅ With Background Processing (FAST!)

```
User: "Hello"
  ├─ Gemini: 300ms ⚡
  ├─ Response sent: 500ms
  ├─ [Background: D-ID starts]
  └─ Total perceived: 500ms ✅ EXCELLENT!

User: "How are you?"
  ├─ Gemini: 300ms ⚡
  ├─ Response sent: 500ms
  ├─ [Background: D-ID still processing]
  └─ Total perceived: 500ms ✅ STILL FAST!

[60s later]
  └─ Avatar video ready, UI updates smoothly
```

## 🎯 Recommended Architecture

### Best Practice: Hybrid Approach

```python
# Combine pre-generation + real-time generation

class AvatarManager:
    def __init__(self):
        self.pregenerated_cache = {}
        self.generation_queue = asyncio.Queue()
    
    async def handle_call(self, user_id: int, text: str):
        """Handle avatar during call"""
        
        # Option 1: Use pre-generated if available (INSTANT!)
        if text in self.pregenerated_cache.get(user_id, {}):
            return self.pregenerated_cache[user_id][text]
        
        # Option 2: Generate in background (DOESN'T BLOCK!)
        task = asyncio.create_task(
            self.generate_avatar(user_id, text)
        )
        
        # Don't wait! Return immediately with placeholder
        return {
            "status": "generating",
            "task_id": id(task)
        }
    
    async def generate_avatar(self, user_id: int, text: str):
        """Background generation"""
        result = await avatar_service.create_talking_avatar(
            photo_url=get_user_photo(user_id),
            text=text
        )
        
        # Cache for future use
        if user_id not in self.pregenerated_cache:
            self.pregenerated_cache[user_id] = {}
        self.pregenerated_cache[user_id][text] = result
        
        return result
```

## 🔧 Complete Code Example

### Updated Avatar API

```python
# backend/app/api/avatars.py - COMPLETE VERSION

from fastapi import BackgroundTasks
import asyncio
from typing import Optional

@router.post("/upload")
async def upload_avatar_photo(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process avatar without blocking"""
    
    # Save photo immediately
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode('utf-8')
    photo_url = f"data:{file.content_type};base64,{base64_image}"
    
    current_user.avatar_photo_url = photo_url
    current_user.avatar_status = "processing"
    db.commit()
    
    # Generate in background
    background_tasks.add_task(
        generate_did_avatar,
        user_id=current_user.id,
        photo_url=photo_url
    )
    
    return {
        "message": "Photo uploaded! Generating avatar...",
        "status": "processing",
        "photo_url": photo_url
    }


@router.get("/status")
async def get_avatar_status(
    current_user: User = Depends(get_current_user)
):
    """Check avatar generation status"""
    return {
        "status": current_user.avatar_status,
        "video_url": current_user.avatar_video_url,
        "photo_url": current_user.avatar_photo_url
    }


async def generate_did_avatar(user_id: int, photo_url: str):
    """Background task - doesn't block anything!"""
    from app.services.avatar_service import avatar_service
    from app.models.database import SessionLocal
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # This takes 60s but runs in background!
        result = await avatar_service.create_talking_avatar(
            photo_url=photo_url,
            text="Hello! I'm your AI assistant."
        )
        
        # Update status
        user.avatar_status = "ready" if result.get("success") else "error"
        user.avatar_video_id = result.get("video_id")
        user.avatar_video_url = result.get("video_url")
        user.avatar_created_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ Avatar ready for user {user_id}")
        
    except Exception as e:
        logger.error(f"Avatar generation failed: {e}")
        user.avatar_status = "error"
        db.commit()
    finally:
        db.close()
```

## 🎉 Summary

### YES, You MUST Use Background Processing!

✅ **Correct Architecture:**
```
Gemini Voice (Main Thread)    D-ID Generation (Background)
        ⚡ 300ms                      🎬 60s
         FAST!                    NO IMPACT!
```

✅ **Benefits:**
- ⚡ Gemini stays ultra-fast (300ms)
- 🎭 Avatar generates separately
- 👤 User gets immediate responses
- ✨ Avatar updates when ready

✅ **Implementation:**
1. Use `asyncio.create_task()` in Python
2. Use `BackgroundTasks` in FastAPI
3. Or pre-generate before calls (BEST!)

✅ **Result:**
- Voice: 300ms response time ⚡
- Avatar: Updates later (no blocking)
- User experience: EXCELLENT! 🎉

Your instinct is **100% correct** - always run D-ID in a separate thread! 🚀

