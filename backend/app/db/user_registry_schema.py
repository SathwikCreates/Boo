# User Registry Database Schema
# This file defines the schema for the shared user_registry.db database

USER_REGISTRY_SCHEMA = """
-- user_registry.db - Shared authentication database
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,           -- Unique identifier (derived from name)
    display_name TEXT NOT NULL,              -- User's display name
    password_hash TEXT NOT NULL,             -- bcrypt hash of password
    secret_phrase_hash TEXT,                 -- bcrypt hash of recovery phrase
    recovery_key TEXT,                       -- UUID for emergency unlock
    database_path TEXT NOT NULL,             -- Path to user's boo.db
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until DATETIME,
    is_active BOOLEAN DEFAULT TRUE
);

-- Index for fast username lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);
"""

USER_REGISTRY_MIGRATIONS = [
    {
        "version": 1,
        "description": "Initial user registry schema",
        "sql": USER_REGISTRY_SCHEMA
    }
]