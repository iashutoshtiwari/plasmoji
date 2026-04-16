"""
Database module for Plasmoji.

Handles local state using SQLite3. Uses FTS5 for lightning-fast fuzzy searching
of the static asset dataset and maintains a Most Recently Used (MRU) cache.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Asset:
    """Represents a selectable asset (emoji, kaomoji, ascii)."""
    id: int
    asset_type: str
    asset_string: str
    keywords: str
    skin_tone_support: bool
    usage_count: int = 0
    last_used: float = 0.0


class DataStore:
    """
    SQLite DataStore for indexing assets and managing MRU cache.
    The database is stored in ~/.local/share/plasmoji/plasmoji.db.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            # Default to XDG data home as per constraints
            xdg_data_home = Path.home() / ".local" / "share"
            self.db_dir = xdg_data_home / "plasmoji"
            self.db_path = self.db_dir / "plasmoji.db"
        else:
            self.db_path = Path(db_path)
            self.db_dir = self.db_path.parent

        # Ensure directory exists
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Establish the database connection and initialize schema."""
        if self._conn is None:
            # Use check_same_thread=False since Qt might access this across threads,
            # but we must still manage concurrency carefully if writing concurrently.
            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
            self.initialize_schema()

    def disconnect(self) -> None:
        """Close the database connection safely."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        # Assert is safe because connect() instantiates _conn or throws.
        assert self._conn is not None
        return self._conn

    def initialize_schema(self) -> None:
        """
        Creates the required tables incorporating FTS5 for keywords.
        """
        conn = self._get_connection()
        try:
            with conn:
                # Primary assets table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type TEXT NOT NULL,
                        asset_string TEXT NOT NULL,
                        keywords TEXT NOT NULL,
                        skin_tone_support BOOLEAN NOT NULL DEFAULT 0
                    )
                """)

                # FTS5 virtual table for fuzzy searching on keywords
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
                        keywords,
                        content='assets',
                        content_rowid='id'
                    )
                """)

                # Triggers to keep FTS index synced with assets table inserts, updates, deletes
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
                        INSERT INTO assets_fts(rowid, keywords) VALUES (new.id, new.keywords);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
                        INSERT INTO assets_fts(assets_fts, rowid, keywords) VALUES ('delete', old.id, old.keywords);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE ON assets BEGIN
                        INSERT INTO assets_fts(assets_fts, rowid, keywords) VALUES ('delete', old.id, old.keywords);
                        INSERT INTO assets_fts(rowid, keywords) VALUES (new.id, new.keywords);
                    END;
                """)

                # MRU table for usage tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mru (
                        asset_id INTEGER PRIMARY KEY,
                        usage_count INTEGER NOT NULL DEFAULT 0,
                        last_used_timestamp REAL NOT NULL,
                        FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
                    )
                """)
            logger.info("Database schema initialized successfully at %s", self.db_path)
        except sqlite3.Error as e:
            logger.critical("Failed to initialize database schema: %s", e)
            raise

    def record_usage(self, asset_id: int) -> None:
        """
        Upsert operation into the MRU table to increment usage count 
        and update the last used timestamp.
        """
        conn = self._get_connection()
        current_time = time.time()
        
        try:
            with conn:
                # Upsert query: if the asset_id exists, increment the usage_count and update time.
                conn.execute("""
                    INSERT INTO mru (asset_id, usage_count, last_used_timestamp)
                    VALUES (?, 1, ?)
                    ON CONFLICT(asset_id) DO UPDATE SET
                        usage_count = usage_count + 1,
                        last_used_timestamp = excluded.last_used_timestamp
                """, (asset_id, current_time))
            logger.debug("Recorded usage for asset_id %d", asset_id)
        except sqlite3.Error as e:
            logger.error("Failed to record usage for asset_id %d: %s", asset_id, e)

    def search(self, query: str = "", limit: int = 50) -> list[Asset]:
        """
        Fuzzy search assets, heavily favoring recently and frequently used items.
        
        If query is empty, returns the global MRU list.
        If query is provided, joins FTS5 results with MRU to rank results.
        """
        conn = self._get_connection()
        
        try:
            if not query.strip():
                # Global MRU lookup when no search term is entered
                cursor = conn.execute("""
                    SELECT a.id, a.type, a.asset_string, a.keywords, a.skin_tone_support,
                           COALESCE(m.usage_count, 0) as usage_count,
                           COALESCE(m.last_used_timestamp, 0.0) as last_used
                    FROM assets a
                    JOIN mru m ON a.id = m.asset_id
                    ORDER BY m.last_used_timestamp DESC, m.usage_count DESC
                    LIMIT ?
                """, (limit,))
            else:
                # To prevent SQLite FTS syntax errors with bad inputs, we sanitize/append wildcard.
                # Example: "cat" -> "cat*"
                safe_query = query.replace("'", "").replace('"', "")
                fts_query = f"{safe_query}*"
                
                cursor = conn.execute("""
                    SELECT a.id, a.type, a.asset_string, a.keywords, a.skin_tone_support,
                           COALESCE(m.usage_count, 0) as usage_count,
                           COALESCE(m.last_used_timestamp, 0.0) as last_used,
                           fts.rank
                    FROM assets_fts fts
                    JOIN assets a ON fts.rowid = a.id
                    LEFT JOIN mru m ON a.id = m.asset_id
                    WHERE assets_fts MATCH ?
                    ORDER BY 
                        -- Priority 1: High usage instances first
                        COALESCE(m.usage_count, 0) DESC, 
                        -- Priority 2: FTS relevancy (lower rank score = better in FTS5)
                        fts.rank ASC,
                        -- Priority 3: Fallback recency
                        COALESCE(m.last_used_timestamp, 0.0) DESC
                    LIMIT ?
                """, (fts_query, limit))

            results = []
            for row in cursor:
                results.append(
                    Asset(
                        id=row["id"],
                        asset_type=row["type"],
                        asset_string=row["asset_string"],
                        keywords=row["keywords"],
                        skin_tone_support=bool(row["skin_tone_support"]),
                        usage_count=row["usage_count"],
                        last_used=row["last_used"]
                    )
                )
            return results

        except sqlite3.Error as e:
            logger.error("Database search failed for query '%s': %s", query, e)
            return []
