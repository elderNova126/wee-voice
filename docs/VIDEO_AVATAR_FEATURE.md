# Video Avatar Feature - Interactive AI Avatars from Photos

## Overview

The Video Avatar feature allows users to create interactive, AI-powered video avatars from a single photo. These avatars can be animated during voice calls, providing a more engaging and personalized experience.

## Features

### ✨ Key Capabilities

1. **Photo Selection**
   - Upload custom photos (JPG, PNG, GIF, max 5MB)
   - Choose from sample avatar gallery
   - Real-time preview

2. **Avatar Animation**
   - Lip-sync with voice during calls
   - Natural facial expressions
   - Speaking indicators and visual feedback

3. **Multiple Provider Support**
   - D-ID (https://www.d-id.com/)
   - HeyGen (https://www.heygen.com/)
   - Synthesia (https://www.synthesia.io/)
   - Mock mode for testing

4. **Call Integration**
   - Seamless integration with voice calls
   - Real-time animation during conversation
   - Mute/unmute controls
   - Live status indicators

## Architecture

### Frontend Components

#### `AvatarPhotoSelector.tsx`
Component for selecting and uploading avatar photos.

**Props:**
- `onPhotoSelected: (photoUrl: string, photoType: 'upload' | 'sample') => void`
- `currentPhoto?: string | null`
- `className?: string`

**Features:**
- File upload with validation
- Sample photo gallery
- Preview selected photo
- Clear selection option

#### `VideoAvatar.tsx`
Component for displaying and animating the avatar during calls.

**Props:**
- `photoUrl: string | null`
- `isActive: boolean`
- `isSpeaking?: boolean`
- `className?: string`

**Features:**
- Animated speaking indicators
- Live/offline status
- Mute controls
- Loading states

### Backend Services

#### Avatar API (`/api/v1/avatars`)

**Endpoints:**

1. **POST /upload**
   - Upload custom avatar photo
   - Validates file type and size
   - Returns photo URL

2. **POST /select**
   - Select avatar photo (sample or uploaded)
   - Body: `{ photo_url: string, photo_type: 'upload' | 'sample' }`

3. **GET /current**
   - Get current user's avatar settings
   - Returns: `{ photo_url, photo_type, enabled }`

4. **DELETE /remove**
   - Remove current avatar photo

5. **PUT /toggle**
   - Enable/disable avatar for calls
   - Body: `enabled: boolean`

#### Avatar Animation Service

**File:** `backend/app/services/avatar_service.py`

**Methods:**

```python
async def create_talking_avatar(
    photo_url: str,
    audio_url: Optional[str] = None,
    text: Optional[str] = None,
    voice_id: Optional[str] = None
) -> Dict[str, Any]
```

Creates an animated talking avatar from a photo.

```python
async def get_avatar_status(video_id: str) -> Dict[str, Any]
```

Checks the status of avatar video generation.

### Database Schema

**New columns in `users` table:**

```sql
-- Avatar photo URL (base64 or URL)
avatar_photo_url TEXT

-- Avatar photo type ('upload' or 'sample')
avatar_photo_type VARCHAR(20)

-- Enable/disable avatar in calls
avatar_enabled BOOLEAN DEFAULT FALSE
```

## Setup Instructions

### 1. Database Migration

Run the migration script to add avatar columns:

```bash
psql -U your_username -d voiceagent_db -f database/migrations/add_avatar_columns_to_users.sql
```

### 2. Environment Configuration

Add to your `.env` file:

```env
# Avatar Animation Service
AVATAR_PROVIDER=mock  # Options: mock, did, heygen, synthesia
AVATAR_API_KEY=your-api-key-here

# File Upload Limits
MAX_UPLOAD_SIZE=5242880  # 5MB
ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/gif,image/webp
```

### 3. Provider Setup

#### Using D-ID

1. Sign up at https://www.d-id.com/
2. Get your API key from the dashboard
3. Set environment variables:
   ```env
   AVATAR_PROVIDER=did
   AVATAR_API_KEY=your-did-api-key
   ```

#### Using HeyGen

1. Sign up at https://www.heygen.com/
2. Get your API key
3. Set environment variables:
   ```env
   AVATAR_PROVIDER=heygen
   AVATAR_API_KEY=your-heygen-api-key
   ```

#### Using Synthesia

1. Sign up at https://www.synthesia.io/
2. Get your API key
3. Set environment variables:
   ```env
   AVATAR_PROVIDER=synthesia
   AVATAR_API_KEY=your-synthesia-api-key
   ```

#### Testing with Mock Provider

For development and testing:

```env
AVATAR_PROVIDER=mock
```

This uses static images without actual animation.

## Usage Guide

### For End Users

1. **Navigate to Public Agent Page**
   - Go to `/agent/:agentId`

2. **Select Avatar Photo**
   - Click "Configure" in the Video Avatar section
   - Either upload your photo or choose from samples
   - Photo will be automatically selected

3. **Start Voice Call**
   - Click "Start Voice Call"
   - Your avatar will appear and animate when speaking
   - Avatar shows live status and speaking indicators

4. **During Call**
   - Avatar animates in sync with voice
   - Visual feedback when agent is speaking
   - Mute/unmute controls available

### For Developers

#### Frontend Integration

```typescript
import { AvatarPhotoSelector, VideoAvatar } from '@/components/ui'

// In your component
const [avatarPhotoUrl, setAvatarPhotoUrl] = useState<string | null>(null)
const [isSpeaking, setIsSpeaking] = useState(false)

// Photo selection
<AvatarPhotoSelector
  onPhotoSelected={(url, type) => setAvatarPhotoUrl(url)}
  currentPhoto={avatarPhotoUrl}
/>

// Avatar display
<VideoAvatar
  photoUrl={avatarPhotoUrl}
  isActive={isCallActive}
  isSpeaking={isSpeaking}
  className="w-full h-96"
/>
```

#### Backend Integration

```python
from app.services.avatar_service import avatar_service

# Create animated avatar
result = await avatar_service.create_talking_avatar(
    photo_url="https://example.com/photo.jpg",
    text="Hello, I'm your AI assistant!",
    voice_id="en-US-Neural2-A"
)

# Check status
status = await avatar_service.get_avatar_status(result['video_id'])
```

## API Examples

### Upload Avatar Photo

```bash
curl -X POST http://localhost:8000/api/v1/avatars/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/photo.jpg"
```

### Select Sample Photo

```bash
curl -X POST http://localhost:8000/api/v1/avatars/select \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "photo_url": "https://example.com/sample.jpg",
    "photo_type": "sample"
  }'
```

### Get Current Avatar

```bash
curl -X GET http://localhost:8000/api/v1/avatars/current \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Toggle Avatar

```bash
curl -X PUT http://localhost:8000/api/v1/avatars/toggle \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "enabled=true"
```

## Customization

### Sample Avatar Gallery

Edit `frontend/src/components/ui/AvatarPhotoSelector.tsx`:

```typescript
const SAMPLE_AVATARS = [
  {
    id: 'avatar1',
    url: 'https://your-cdn.com/avatar1.jpg',
    name: 'Professional Woman'
  },
  // Add more samples...
]
```

### Animation Styles

Modify `frontend/src/components/ui/VideoAvatar.tsx` to customize:
- Speaking animation effects
- Border styles and colors
- Sound wave visualizations
- Status indicators

### Provider Configuration

Add custom providers in `backend/app/services/avatar_service.py`:

```python
async def _custom_create_avatar(self, photo_url, audio_url, text, voice_id):
    # Your custom implementation
    pass
```

## Performance Considerations

### File Size Limits
- Maximum upload size: 5MB
- Recommended: 1-2MB for optimal performance
- Supported formats: JPG, PNG, GIF, WebP

### Caching
- Avatar photos are cached in browser
- Base64 encoding for uploaded photos
- CDN recommended for sample photos

### API Rate Limits
- D-ID: Check their pricing page
- HeyGen: Check their pricing page
- Synthesia: Check their pricing page

## Troubleshooting

### Avatar Not Displaying

1. Check browser console for errors
2. Verify photo URL is accessible
3. Check avatar_enabled flag in database
4. Ensure proper CORS configuration

### Upload Failing

1. Check file size (max 5MB)
2. Verify file type is supported
3. Check backend logs for errors
4. Ensure proper authentication

### Animation Not Working

1. Verify provider is configured
2. Check API key validity
3. Review provider API status
4. Check network connectivity

### Database Issues

```sql
-- Check if columns exist
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'users' 
  AND column_name LIKE 'avatar%';

-- Reset avatar for user
UPDATE users SET 
  avatar_photo_url = NULL,
  avatar_photo_type = NULL,
  avatar_enabled = FALSE
WHERE id = YOUR_USER_ID;
```

## Security Considerations

1. **File Validation**
   - Always validate file types
   - Check file size limits
   - Scan for malicious content

2. **Data Privacy**
   - Store photos securely
   - Respect user privacy
   - Comply with GDPR/CCPA

3. **API Keys**
   - Never expose in frontend
   - Use environment variables
   - Rotate regularly

4. **Rate Limiting**
   - Implement upload limits
   - Prevent API abuse
   - Monitor usage

## Future Enhancements

- [ ] Real-time avatar animation streaming
- [ ] Custom voice cloning
- [ ] Multiple avatar profiles per user
- [ ] Avatar emotion detection
- [ ] Background customization
- [ ] 3D avatar support
- [ ] Avatar marketplace
- [ ] Video recording and export

## Support

For issues or questions:
- GitHub Issues: [Your Repo]
- Documentation: [Your Docs]
- Email: support@voiceagent.com

## License

This feature is part of VoiceAgent SaaS platform.
See LICENSE file for details.

