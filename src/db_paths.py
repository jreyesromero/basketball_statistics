"""Filesystem locations for the SQLite database and schema."""

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DB_PATH = ROOT_DIR / "data" / "basket.sqlite"
SCHEMA_PATH = ROOT_DIR / "schema.sql"
