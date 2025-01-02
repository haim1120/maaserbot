-- Change telegram_id column type to BIGINT in users table
ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT;

-- Change telegram_id column type to BIGINT in access_requests table
ALTER TABLE access_requests ALTER COLUMN telegram_id TYPE BIGINT; 