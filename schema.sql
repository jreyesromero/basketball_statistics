-- SQLite schema for basket (local dev).
-- Create DB: sqlite3 data/basket.sqlite < schema.sql
-- App: from repo root, uvicorn src.main:app --reload

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
