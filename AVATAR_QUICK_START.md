# Video Avatar Feature - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Run Database Migration (1 min)

```bash
# Navigate to project root
cd C:\Users\ABC\Music\wee-voice

# Run migration (Windows PowerShell)
# Replace with your actual database credentials
$env:PGPASSWORD="your_password"
psql -U your_username -d voiceagent_db -f database/migrations/add_avatar_columns_to_users.sql
```

### Step 2: Configure Environment (1 min)

Add these lines to `backend/.env`:

```env
# Avatar Configuration (for testing, use mock)
AVATAR_PROVIDER=mock
AVATAR_API_KEY=not-needed-for-mock

# File Upload Settings
MAX_UPLOAD_SIZE=5242880
ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/gif,image/webp
```

### Step 3: Restart Backend (1 min)

```bash
# Stop current backend (Ctrl+C)
# Then restart
cd backend
python -m uvicorn app.main:app --reload
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 4: Test the Feature (2 min)

1. **Open your browser**: http://localhost:3000 (or your frontend URL)

2. **Navigate to a public agent page**:
   - Go to the demo page or any public agent
   - Example: http://localhost:3000/agent/1

3. **Configure Avatar**:
   - Look for the "🎭 Video Avatar" section
   - Click "Configure" or "Setup"
   - Choose a sample photo or upload your own
   - Click on a photo to select it

4. **Start a Call**:
   - Click "Start Voice Call" or "Connect"
   - Allow microphone access when prompted
   - Your avatar will appear!

5. **See It in Action**:
   - Speak into your microphone
   - Watch the avatar animate with speaking indicators
   - See the sound waves and live status

## ✅ Verification Checklist

- [ ] Database migration completed without errors
- [ ] Backend restarted successfully
- [ ] Frontend is running
- [ ] Can access public agent page
- [ ] Avatar selector is visible
- [ ] Can select/upload photos
- [ ] Avatar displays during call
- [ ] Speaking indicators work

## 🎯 What You Should See

### Avatar Selector
- Upload button for custom photos
- Gallery of 6 sample avatars
- Selected photo preview with checkmark
- File size and format information

### During Call
- Avatar photo displayed in a rounded frame
- "Live" badge when call is active
- Animated sound waves when speaking
- Green border pulse effect
- Mute/unmute button
- AI badge indicator

## 🔧 Troubleshooting

### Avatar Not Showing?

**Check 1**: Database columns exist
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'users' AND column_name LIKE 'avatar%';
```
Should return: `avatar_photo_url`, `avatar_photo_type`, `avatar_enabled`

**Check 2**: Backend logs
```bash
# Look for errors in backend console
# Should see: "✅ Avatar router loaded"
```

**Check 3**: Browser console
```javascript
// Open DevTools (F12) and check for errors
// Look for avatar-related errors
```

### Upload Failing?

**Check file size**: Max 5MB
```bash
# Check file size (Windows PowerShell)
(Get-Item "path\to\photo.jpg").Length / 1MB
# Should be less than 5
```

**Check file type**: JPG, PNG, GIF, WebP only

### Can't Select Sample Photos?

**Check network**: Sample photos load from Unsplash
- Ensure internet connection is active
- Check browser network tab for failed requests

## 🎨 Customization Tips

### Add Your Own Sample Photos

Edit `frontend/src/components/ui/AvatarPhotoSelector.tsx`:

```typescript
const SAMPLE_AVATARS = [
  {
    id: 'custom1',
    url: 'https://your-cdn.com/avatar1.jpg',
    name: 'Custom Avatar 1'
  },
  // Add more...
]
```

### Change Avatar Size

In your page component:

```typescript
<VideoAvatar
  photoUrl={avatarPhotoUrl}
  isActive={isConnected}
  isSpeaking={isSpeaking}
  className="w-full h-96"  // Change h-96 to h-64, h-80, etc.
/>
```

### Modify Speaking Animation

Edit `frontend/src/components/ui/VideoAvatar.tsx`:

```css
/* Change animation speed */
.animate-sound-wave-1 {
  animation: sound-wave-1 0.8s ease-in-out infinite;
  /* Change 0.8s to 0.5s for faster, 1.2s for slower */
}

/* Change border color when speaking */
border: 4px solid #10b981;  /* Green - change to any color */
```

## 📱 Test on Mobile

The avatar feature is mobile-responsive:

1. Open on mobile browser
2. Navigate to agent page
3. Select avatar
4. Start call
5. Avatar scales to fit screen

## 🎓 Next Steps

### Enable Real Avatar Animation

1. **Choose a provider**: D-ID, HeyGen, or Synthesia
2. **Sign up**: Get API key from provider
3. **Update .env**:
   ```env
   AVATAR_PROVIDER=did  # or heygen, synthesia
   AVATAR_API_KEY=your-actual-api-key
   ```
4. **Restart backend**
5. **Test**: Avatar will now animate with lip-sync!

### Popular Providers

**D-ID** (Recommended for beginners)
- Website: https://www.d-id.com/
- Free tier: 20 credits/month
- Easy API integration
- Good quality

**HeyGen**
- Website: https://www.heygen.com/
- Professional quality
- Multiple voice options
- Higher pricing

**Synthesia**
- Website: https://www.synthesia.io/
- Enterprise-grade
- Best quality
- Premium pricing

## 📊 Feature Status

| Component | Status | Location |
|-----------|--------|----------|
| Avatar Selector | ✅ Ready | `AvatarPhotoSelector.tsx` |
| Avatar Display | ✅ Ready | `VideoAvatar.tsx` |
| Backend API | ✅ Ready | `backend/app/api/avatars.py` |
| Animation Service | ✅ Ready | `backend/app/services/avatar_service.py` |
| Database Schema | ✅ Ready | Migration script provided |
| Documentation | ✅ Ready | `docs/VIDEO_AVATAR_FEATURE.md` |

## 🎉 You're All Set!

The video avatar feature is now ready to use. Users can:
- ✅ Upload or select avatar photos
- ✅ See animated avatars during calls
- ✅ Enjoy visual feedback and speaking indicators
- ✅ Toggle avatar on/off
- ✅ Use on desktop and mobile

**Enjoy creating interactive video avatars! 🎭✨**

---

Need help? Check the full documentation in `docs/VIDEO_AVATAR_FEATURE.md`

