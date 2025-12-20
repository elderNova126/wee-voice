# Database Migrations

## How to Run Migrations

### Option 1: Using psql (Recommended)
```bash
psql -U your_username -d your_database -f database/migrations/add_manager_contact_to_agents.sql
```

### Option 2: Using PostgreSQL client
Connect to your database and run the SQL file contents directly.

### Option 3: From DBeaver or other GUI tools
1. Open the SQL file
2. Execute it against your database

## Available Migrations

### add_manager_contact_to_agents.sql
**Date:** 2025-12-20  
**Purpose:** Adds `manager_contact` field to agents for escalation handling

**What it does:**
- Adds `manager_contact` VARCHAR(255) column to `voice_agents` table
- Column is nullable (agents can work without manager contact)
- Includes safeguard to prevent adding column if it already exists

**To apply:**
```bash
psql -U postgres -d wee_voice -f database/migrations/add_manager_contact_to_agents.sql
```

## Migration Status Tracking

After running a migration, you can verify it worked:

```sql
-- Check if manager_contact column exists
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'voice_agents' 
AND column_name = 'manager_contact';
```

## Rollback (if needed)

If you need to remove the `manager_contact` column:

```sql
ALTER TABLE voice_agents DROP COLUMN manager_contact;
```

⚠️ **Warning:** This will delete all manager contact data!

