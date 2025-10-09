# Database Setup Guide

## Using with Supabase

### 1. Create a New Supabase Project

1. Go to [Supabase](https://supabase.com)
2. Create a new project
3. Wait for the database to be provisioned

### 2. Choose Your Schema

**Option A: Simple Schema (Recommended for Testing)**
- File: `supabase_schema_simple.sql`
- No Row Level Security
- Quick setup
- Good for development/testing

**Option B: Full Schema (Recommended for Production)**
- File: `supabase_schema.sql`
- Includes Row Level Security (RLS)
- Complete feature set
- Production-ready

### 3. Run the Schema

1. Go to your Supabase project dashboard
2. Click on **SQL Editor** in the left sidebar
3. Create a new query
4. Copy and paste the contents of your chosen SQL file
5. Click **Run** to execute

**Note:** The scripts are idempotent - you can run them multiple times safely. They will drop and recreate all objects.

### 4. Get Your Database Connection String

1. Go to **Settings** → **Database**
2. Copy the **Connection string** (URI format)
3. Update your `backend/.env` file:

```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

### 5. Configure Backend to Use Supabase

Update `backend/.env`:

```env
# Supabase Database
DATABASE_URL=postgresql://postgres:your-password@db.xxxxx.supabase.co:5432/postgres

# Google Gemini API
GOOGLE_API_KEY=your-google-api-key

# Application
SECRET_KEY=your-secret-key
DEBUG=True
```

### 6. Test the Connection

```bash
cd backend
python -m uvicorn app.main:app --reload
```

You should see:
```
INFO:     Database tables created successfully
INFO:     Application startup complete.
```

## Schema Overview

### Tables

1. **users** - User accounts with authentication and subscription
2. **api_keys** - API keys for programmatic access
3. **voice_agents** - Voice agent configurations
4. **calls** - Call history with transcripts and analytics
5. **call_messages** - Individual messages within calls

### Features

✅ **Row Level Security (RLS)** - Users can only access their own data
✅ **Automatic Timestamps** - `created_at` and `updated_at` are managed automatically
✅ **Duration Calculation** - Call duration and cost calculated automatically
✅ **Indexes** - Optimized for common query patterns
✅ **Full-Text Search** - Search transcripts in French
✅ **Views** - Pre-built statistics views

### Sample Data

The schema includes a demo user and agent:
- **Email**: `demo@voiceagent.com`
- **Password**: `password123`
- **Agent**: Public French demo agent

### Maintenance Functions

```sql
-- Clean up old calls (older than 90 days)
SELECT cleanup_old_calls(90);
```

## Using with PostgreSQL (Local)

If you prefer local PostgreSQL:

```bash
# Create database
createdb voiceagent_db

# Run schema
psql -d voiceagent_db -f database/supabase_schema.sql

# Update .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/voiceagent_db
```

## Troubleshooting

### Connection Issues

1. Check your connection string format
2. Verify your password
3. Ensure your IP is allowed in Supabase firewall
4. Test with: `psql "your-connection-string"`

### Schema Errors

1. Make sure you're using PostgreSQL 14+
2. Run migrations in order
3. Check Supabase logs for detailed errors

### RLS Issues

If you can't access data:
1. Ensure Supabase Auth is configured
2. Check RLS policies in Supabase dashboard
3. Use service role key for backend (not anon key)

## Advanced Configuration

### Backups

Supabase automatically backs up your database daily. To create manual backups:

```sql
-- Export schema
pg_dump -s voiceagent_db > schema_backup.sql

-- Export data
pg_dump -a voiceagent_db > data_backup.sql
```

### Monitoring

Use Supabase dashboard to monitor:
- Query performance
- Database size
- Active connections
- Slow queries

### Scaling

For production:
1. Upgrade to Supabase Pro for better performance
2. Add read replicas for read-heavy workloads
3. Use connection pooling (Supabase includes this)
4. Monitor and optimize slow queries

## Security Best Practices

1. ✅ Never commit database passwords
2. ✅ Use environment variables
3. ✅ Enable RLS on all tables
4. ✅ Rotate API keys regularly
5. ✅ Use service role key only in backend
6. ✅ Enable 2FA on Supabase account
7. ✅ Regularly update passwords
8. ✅ Monitor access logs

## Support

- [Supabase Documentation](https://supabase.com/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- Project Issues: GitHub repository

