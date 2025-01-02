-- Drop foreign key constraints first
ALTER TABLE incomes DROP CONSTRAINT IF EXISTS incomes_user_id_fkey;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_user_id_fkey;

-- Convert enum columns to varchar
ALTER TABLE users ALTER COLUMN default_calc_type TYPE varchar USING default_calc_type::varchar;
ALTER TABLE users ALTER COLUMN currency TYPE varchar USING currency::varchar;
ALTER TABLE incomes ALTER COLUMN calc_type TYPE varchar USING calc_type::varchar;

-- Drop the custom enum types
DROP TYPE IF EXISTS calculationtype;
DROP TYPE IF EXISTS currency;

-- Restore foreign key constraints
ALTER TABLE incomes ADD CONSTRAINT incomes_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE payments ADD CONSTRAINT payments_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id); 