-- ============================================================================
-- Section 1.1 (part a)  Create the single assignment database
-- Run while connected to the default "postgres" database:
--     python run_sql.py sql/01_1a_create_database.sql --db postgres
-- A database cannot be created from inside itself, which is why this one
-- statement lives in its own file.
-- ============================================================================
CREATE DATABASE energy_grid;
