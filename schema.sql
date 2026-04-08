-- SQLite schema for basketball_statistics (local dev).
-- Create DB: sqlite3 data/basket.sqlite < schema.sql
-- Run app: ./bin/run.sh  (from repo root)

CREATE TABLE IF NOT EXISTS player (
  player_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  surname       TEXT NOT NULL,
  address       TEXT,
  -- ISO 8601 date string (YYYY-MM-DD); SQLite has no native DATE type.
  date_of_birth TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_surname_name
  ON player (surname, name);

CREATE TABLE IF NOT EXISTS club (
  club_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT NOT NULL,
  -- ISO 8601 date (YYYY-MM-DD): foundation / incorporation date.
  foundation_date  TEXT NOT NULL,
  address          TEXT
);

CREATE INDEX IF NOT EXISTS idx_club_name
  ON club (name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS users (
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash  TEXT NOT NULL,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email COLLATE NOCASE);
