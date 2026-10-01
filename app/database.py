import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(
	os.getenv(
		"DATABASE_PATH",
		str(Path(__file__).resolve().parent.parent / "data" / "roms.db"),
	)
)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
	DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(DATABASE_PATH)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA journal_mode=WAL")
	try:
		with connection:
			yield connection
	finally:
		connection.close()


def initialize_database() -> None:
	with _connect() as connection:
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS roms (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				source_name TEXT NOT NULL,
				clean_title TEXT NOT NULL,
				system TEXT NOT NULL,
				output_path TEXT NOT NULL UNIQUE,
				file_size INTEGER NOT NULL,
				release_date TEXT,
				overview TEXT,
				cover_url TEXT,
				cover_path TEXT,
				gamesdb_id INTEGER,
				indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			)
			"""
		)
		columns = {
			row["name"] for row in connection.execute("PRAGMA table_info(roms)").fetchall()
		}
		if "cover_path" not in columns:
			connection.execute("ALTER TABLE roms ADD COLUMN cover_path TEXT")


def save_rom(record: dict[str, Any]) -> None:
	with _connect() as connection:
		connection.execute(
			"""
			INSERT INTO roms (
				source_name, clean_title, system, output_path, file_size,
				release_date, overview, cover_url, cover_path, gamesdb_id, indexed_at
			) VALUES (
				:source_name, :clean_title, :system, :output_path, :file_size,
				:release_date, :overview, :cover_url, :cover_path, :gamesdb_id, CURRENT_TIMESTAMP
			)
			ON CONFLICT(output_path) DO UPDATE SET
				source_name = excluded.source_name,
				clean_title = excluded.clean_title,
				system = excluded.system,
				file_size = excluded.file_size,
				release_date = excluded.release_date,
				overview = excluded.overview,
				cover_url = excluded.cover_url,
				cover_path = excluded.cover_path,
				gamesdb_id = excluded.gamesdb_id,
				indexed_at = CURRENT_TIMESTAMP
			""",
			record,
		)


def list_roms(limit: int = 500) -> list[dict[str, Any]]:
	with _connect() as connection:
		rows = connection.execute(
			"SELECT * FROM roms ORDER BY system, clean_title LIMIT ?", (limit,)
		).fetchall()
	return [dict(row) for row in rows]


def rom_count() -> int:
	with _connect() as connection:
		return connection.execute("SELECT COUNT(*) FROM roms").fetchone()[0]
