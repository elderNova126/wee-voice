# Database Migrations

This directory contains SQL migration scripts for the VoiceAgent SaaS platform.

## Migration Files

### Avatar Feature
- **add_avatar_columns_to_users.sql** - Adds video avatar support columns to users table
  - `avatar_photo_url` - Stores the photo URL or base64 data
  - `avatar_photo_type` - Indicates if photo is 'upload' or 'sample'
  - `avatar_enabled` - Boolean flag to enable/disable avatar in calls

### Other Migrations
- **add_interaction_mode_to_agents.sql** - Adds interaction mode (voice/text/both) to agents
- **add_manager_contact_to_agents.sql** - Adds manager contact information to agents

## How to Apply Migrations

### Using psql
```bash
psql -U your_username -d voiceagent_db -f database/migrations/add_avatar_columns_to_users.sql
```

### Using Docker
```bash
docker exec -i postgres_container psql -U your_username -d voiceagent_db < database/migrations/add_avatar_columns_to_users.sql
```

### Verify Migration
```sql
-- Check if columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' 
  AND column_name IN ('avatar_photo_url', 'avatar_photo_type', 'avatar_enabled');
```

## Rollback

If you need to rollback the avatar feature:

```sql
ALTER TABLE users DROP COLUMN IF EXISTS avatar_photo_url;
ALTER TABLE users DROP COLUMN IF EXISTS avatar_photo_type;
ALTER TABLE users DROP COLUMN IF EXISTS avatar_enabled;
DROP INDEX IF EXISTS idx_users_avatar_enabled;
```

## Best Practices

1. **Always backup your database before running migrations**
2. Test migrations in a development environment first
3. Run migrations during low-traffic periods
4. Keep migration files in version control
5. Document any manual steps required
