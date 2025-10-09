# Quick Setup with Supabase

## 🚀 5-Minute Setup Guide

### Step 1: Create Supabase Project (2 minutes)

1. Go to [https://supabase.com](https://supabase.com)
2. Click **"New Project"**
3. Fill in:
   - Name: `voiceagent-saas`
   - Database Password: (save this!)
   - Region: Choose closest to you
4. Click **"Create new project"**
5. Wait ~2 minutes for provisioning

### Step 2: Run Database Schema (1 minute)

1. In your Supabase dashboard, click **"SQL Editor"** (left sidebar)
2. Click **"New query"**
3. Open `database/supabase_schema_simple.sql` from your project
4. **Copy ALL contents** (Ctrl+A, Ctrl+C)
5. **Paste** into Supabase SQL Editor
6. Click **"Run"** (or press Ctrl+Enter)
7. You should see: ✅ Success message

### Step 3: Get Connection String (1 minute)

1. In Supabase dashboard, click **"Settings"** (bottom left)
2. Click **"Database"**
3. Scroll down to **"Connection string"**
4. Select **"URI"** tab
5. Copy the connection string (looks like this):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with your actual database password

### Step 4: Configure Backend (1 minute)

1. Open `backend/.env` file (create if it doesn't exist)
2. Add your configuration:

```env
# Supabase Database Connection
DATABASE_URL=postgresql://postgres:your-actual-password@db.xxxxx.supabase.co:5432/postgres

# Google Gemini API Key (get from https://ai.google.dev/)
GOOGLE_API_KEY=your-google-api-key-here

# Application Security (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-generated-secret-key-here

# Development Mode
DEBUG=True
HOST=0.0.0.0
PORT=8000

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Step 5: Start Backend (1 minute)

```bash
# Navigate to backend
cd backend

# Install dependencies (if not done already)
pip install -r requirements.txt

# Start the server
python -m uvicorn app.main:app --reload
```

You should see:
```
INFO:     Starting VoiceAgent SaaS application...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 6: Test It! (30 seconds)

Open your browser:
- **API Docs**: http://127.0.0.1:8000/api/docs
- **Health Check**: http://127.0.0.1:8000/health

You should see the API documentation and "healthy" status!

## ✅ You're Done!

Your backend is now connected to Supabase and ready to use.

## 🎯 Next Steps

### Start the Frontend

```bash
# In a new terminal
cd frontend
npm install
npm run dev
```

Then open: http://localhost:3000

### Test with Demo Account

Login credentials (from the SQL schema):
```
Email: demo@voiceagent.com
Password: password123
```

## 🐛 Troubleshooting

### ❌ "greenlet_spawn" error

This error is expected and harmless! The backend will work fine. It just means we're skipping automatic table creation (which we don't need since we created tables in Supabase).

### ❌ Connection refused

- Check your DATABASE_URL is correct
- Verify your password is correct
- Make sure you replaced `[YOUR-PASSWORD]` with actual password
- Try connecting with: `psql "your-connection-string"`

### ❌ "relation does not exist"

- Make sure you ran the SQL schema in Supabase
- Check the SQL ran without errors
- Verify tables exist in Supabase Table Editor

### ❌ GOOGLE_API_KEY error

- Get your key from: https://ai.google.dev/
- Make sure the API is enabled
- Check for any spaces or quotes in the .env file

## 📊 Verify Setup

### Check Database Tables

1. Go to Supabase **"Table Editor"**
2. You should see these tables:
   - users
   - api_keys
   - voice_agents
   - calls
   - call_messages

### Check Demo Data

1. In Supabase, go to **"Table Editor"** → **"users"**
2. You should see one user: `demo@voiceagent.com`
3. Go to **"voice_agents"**
4. You should see: "Assistant Démo Français"

### Test API Endpoint

```bash
# Test health endpoint
curl http://127.0.0.1:8000/health

# Should return: {"status":"healthy",...}
```

## 🎉 Success!

You now have:
- ✅ Supabase database with all tables
- ✅ Backend connected and running
- ✅ Demo account ready to use
- ✅ API documentation available

Total setup time: ~5 minutes! 🚀

## 📖 More Information

- **Full Documentation**: See `README.md`
- **Database Details**: See `database/README.md`
- **Architecture**: See `ARCHITECTURE.md`
- **Deployment**: See `DEPLOYMENT.md`

## 💡 Pro Tips

1. **Bookmark your Supabase dashboard** - you'll use it often
2. **Save your connection string** - you'll need it later
3. **Use Supabase Table Editor** - great for debugging
4. **Enable realtime** in Supabase for live updates
5. **Set up backups** in Supabase settings

Need help? Check the troubleshooting section or open an issue!

