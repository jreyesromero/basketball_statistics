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
  is_admin       INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS password_reset (
  reset_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES users (user_id),
  token_hash  TEXT NOT NULL UNIQUE,
  expires_at  TEXT NOT NULL,
  used_at     TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset (user_id);

CREATE TABLE IF NOT EXISTS season (
  season_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  start_year  TEXT NOT NULL,
  end_year    TEXT NOT NULL,
  UNIQUE (start_year, end_year)
);

CREATE TABLE IF NOT EXISTS season_team (
  season_team_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id       INTEGER NOT NULL REFERENCES season (season_id),
  club_id         INTEGER NOT NULL REFERENCES club (club_id),
  UNIQUE (season_id, club_id)
);

CREATE INDEX IF NOT EXISTS idx_season_team_season ON season_team (season_id);

CREATE TABLE IF NOT EXISTS season_team_player (
  season_team_player_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  season_team_id         INTEGER NOT NULL REFERENCES season_team (season_team_id) ON DELETE CASCADE,
  season_id              INTEGER NOT NULL REFERENCES season (season_id),
  player_id              INTEGER NOT NULL REFERENCES player (player_id),
  jersey_number          TEXT,
  UNIQUE (season_team_id, player_id),
  UNIQUE (player_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_season_team_player_team ON season_team_player (season_team_id);
CREATE INDEX IF NOT EXISTS idx_season_team_player_season ON season_team_player (season_id);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id             INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type          TEXT NOT NULL,
  entity_id            INTEGER NOT NULL,
  action               TEXT NOT NULL,
  changed_at           TEXT NOT NULL DEFAULT (datetime('now')),
  changed_by_user_id   INTEGER REFERENCES users (user_id),
  details              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log (changed_at);
