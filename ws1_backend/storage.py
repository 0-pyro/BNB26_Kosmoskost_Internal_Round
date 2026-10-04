"""
Roundtable Session Storage Layer.

Persists session transcripts and metadata to disk using SQLite.
Supports retrieving saved sessions, session transcripts, and clearing data.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Ensure project root is on sys.path for contracts import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contracts.models import CaptionEvent

logger = logging.getLogger("ws1_backend.storage")

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DATA_DIR, "sessions.db")


class SessionStorage:
    """Manages SQLite-based persistence for Roundtable session transcripts."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.environ.get("SESSIONS_DB_PATH", DEFAULT_DB_PATH)
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create sessions table if it doesn't already exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    duration REAL NOT NULL,
                    transcript TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """
            )
            conn.commit()

    def save_session(
        self,
        session_id: str,
        transcript: List[Union[CaptionEvent, dict]],
        created_at: Optional[int] = None,
        duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Persist a session's transcript (list of CaptionEvents) to SQLite.
        If the session already exists, its transcript and duration are updated.
        """
        now_ms = int(time.time() * 1000)

        # Normalize transcript items to dictionaries
        events_data: List[dict] = []
        for item in transcript:
            if isinstance(item, CaptionEvent):
                events_data.append(item.model_dump())
            elif isinstance(item, dict):
                events_data.append(item)
            elif hasattr(item, "dict"):
                events_data.append(item.dict())
            else:
                events_data.append(dict(item))

        # Infer created_at if not provided
        if created_at is None or created_at <= 0:
            if events_data and events_data[0].get("start_ts", 0) > 0:
                created_at = int(events_data[0]["start_ts"])
            else:
                created_at = now_ms

        # Calculate duration if not provided
        if duration is None:
            if events_data:
                first_ts = events_data[0].get("start_ts", 0)
                last_ts = events_data[-1].get("end_ts", 0) or events_data[-1].get("start_ts", 0)
                if last_ts > first_ts > 0:
                    duration = round((last_ts - first_ts) / 1000.0, 2)
                else:
                    duration = round(max(0.0, (now_ms - created_at) / 1000.0), 2)
            else:
                duration = 0.0

        transcript_json = json.dumps(events_data)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, created_at, duration, transcript, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    duration = excluded.duration,
                    transcript = excluded.transcript,
                    updated_at = excluded.updated_at;
                """,
                (session_id, created_at, duration, transcript_json, now_ms),
            )
            conn.commit()

        logger.info(
            "Saved session %s (%d captions, duration=%.1fs) to %s",
            session_id,
            len(events_data),
            duration,
            self.db_path,
        )

        return {
            "id": session_id,
            "session_id": session_id,
            "timestamp": created_at,
            "created_at": created_at,
            "duration": duration,
            "transcript_count": len(events_data),
            "updated_at": now_ms,
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full session record including parsed CaptionEvent models."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT session_id, created_at, duration, transcript, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                raw_events = json.loads(row["transcript"])
                timeline = [CaptionEvent(**ev) for ev in raw_events]
            except Exception as exc:
                logger.warning("Error parsing transcript for session %s: %s", session_id, exc)
                timeline = []

            return {
                "id": row["session_id"],
                "session_id": row["session_id"],
                "timestamp": row["created_at"],
                "created_at": row["created_at"],
                "duration": row["duration"],
                "transcript": timeline,
                "updated_at": row["updated_at"],
            }

    def get_session_transcript(self, session_id: str) -> Optional[List[CaptionEvent]]:
        """Retrieve just the list of CaptionEvents for a session, or None if not found."""
        session = self.get_session(session_id)
        if session is None:
            return None
        return session["transcript"]

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return summary of all saved sessions ordered newest first."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT session_id, created_at, duration, updated_at FROM sessions ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row["session_id"],
                    "session_id": row["session_id"],
                    "timestamp": row["created_at"],
                    "created_at": row["created_at"],
                    "duration": row["duration"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session from storage."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> None:
        """Clear all saved sessions (useful for tests)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions")
            conn.commit()


# Default singleton instance
session_storage = SessionStorage()


# Module-level convenience functions
def save_session(
    session_id: str,
    transcript: List[Union[CaptionEvent, dict]],
    created_at: Optional[int] = None,
    duration: Optional[float] = None,
) -> Dict[str, Any]:
    return session_storage.save_session(session_id, transcript, created_at, duration)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return session_storage.get_session(session_id)


def get_session_transcript(session_id: str) -> Optional[List[CaptionEvent]]:
    return session_storage.get_session_transcript(session_id)


def list_sessions() -> List[Dict[str, Any]]:
    return session_storage.list_sessions()


def delete_session(session_id: str) -> bool:
    return session_storage.delete_session(session_id)
