"""
Unit tests for ws1_backend storage layer and Room persistence.
"""

from __future__ import annotations

import os
import tempfile
import pytest

from contracts.models import CaptionEvent
from ws1_backend.session import Room, SessionManager
from ws1_backend.storage import SessionStorage


@pytest.fixture()
def temp_storage():
    """Create a temporary SQLite storage instance for isolated testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    storage = SessionStorage(db_path=db_path)
    yield storage
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


def test_save_and_get_session(temp_storage: SessionStorage):
    events = [
        CaptionEvent(
            segment_id="seg_1",
            speaker_id="p1",
            speaker_name="Alice",
            start_ts=1000,
            end_ts=3000,
            text="Hello everyone",
            is_final=True,
            revision=1,
        ),
        CaptionEvent(
            segment_id="seg_2",
            speaker_id="p2",
            speaker_name="Bob",
            start_ts=3500,
            end_ts=5500,
            text="Hi Alice",
            is_final=True,
            revision=1,
        ),
    ]

    res = temp_storage.save_session(
        session_id="room_123",
        transcript=events,
        created_at=1000,
    )
    assert res["id"] == "room_123"
    assert res["transcript_count"] == 2
    assert res["duration"] == 4.5  # (5500 - 1000) / 1000 = 4.5s

    session = temp_storage.get_session("room_123")
    assert session is not None
    assert session["id"] == "room_123"
    assert session["session_id"] == "room_123"
    assert session["timestamp"] == 1000
    assert len(session["transcript"]) == 2
    assert session["transcript"][0].text == "Hello everyone"
    assert session["transcript"][1].speaker_name == "Bob"

    transcript = temp_storage.get_session_transcript("room_123")
    assert transcript is not None
    assert len(transcript) == 2
    assert transcript[0].segment_id == "seg_1"


def test_get_nonexistent_session(temp_storage: SessionStorage):
    assert temp_storage.get_session("unknown_room") is None
    assert temp_storage.get_session_transcript("unknown_room") is None


def test_list_sessions(temp_storage: SessionStorage):
    assert temp_storage.list_sessions() == []

    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        start_ts=100,
        end_ts=200,
        text="Testing",
        is_final=True,
    )

    temp_storage.save_session("room_a", [ev], created_at=1000)
    temp_storage.save_session("room_b", [ev], created_at=2000)

    sessions = temp_storage.list_sessions()
    assert len(sessions) == 2
    # Ordered newest first
    assert sessions[0]["session_id"] == "room_b"
    assert sessions[1]["session_id"] == "room_a"
    assert "timestamp" in sessions[0]
    assert "duration" in sessions[0]


def test_session_update_on_conflict(temp_storage: SessionStorage):
    ev1 = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        start_ts=1000,
        end_ts=2000,
        text="First sentence",
        is_final=True,
    )
    temp_storage.save_session("room_update", [ev1], created_at=1000)

    ev2 = CaptionEvent(
        segment_id="s2",
        speaker_id="p1",
        speaker_name="Alice",
        start_ts=2500,
        end_ts=4000,
        text="Second sentence",
        is_final=True,
    )
    temp_storage.save_session("room_update", [ev1, ev2], created_at=1000)

    transcript = temp_storage.get_session_transcript("room_update")
    assert transcript is not None
    assert len(transcript) == 2
    assert transcript[1].text == "Second sentence"


def test_delete_and_clear_session(temp_storage: SessionStorage):
    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        start_ts=100,
        end_ts=200,
        text="Sample",
        is_final=True,
    )
    temp_storage.save_session("room_del", [ev])
    assert temp_storage.get_session("room_del") is not None

    deleted = temp_storage.delete_session("room_del")
    assert deleted is True
    assert temp_storage.get_session("room_del") is None

    temp_storage.save_session("room_x", [ev])
    temp_storage.save_session("room_y", [ev])
    assert len(temp_storage.list_sessions()) == 2
    temp_storage.clear()
    assert len(temp_storage.list_sessions()) == 0


@pytest.mark.asyncio
async def test_room_close_and_clear_persists():
    from ws1_backend.storage import session_storage

    room = Room("room_auto_persist_close")
    ev = CaptionEvent(
        segment_id="seg_close",
        speaker_id="p1",
        speaker_name="Charlie",
        start_ts=100,
        end_ts=500,
        text="Closing soon",
        is_final=True,
    )
    await room.add_caption(ev, broadcast=False)
    await room.close()

    stored = session_storage.get_session("room_auto_persist_close")
    assert stored is not None
    assert len(stored["transcript"]) == 1
    assert stored["transcript"][0].text == "Closing soon"

    # Test clear()
    room2 = Room("room_auto_persist_clear")
    ev2 = CaptionEvent(
        segment_id="seg_clear",
        speaker_id="p2",
        speaker_name="Dana",
        start_ts=200,
        end_ts=600,
        text="Clearing now",
        is_final=True,
    )
    await room2.add_caption(ev2, broadcast=False)
    assert len(room2.timeline) == 1

    await room2.clear()
    assert len(room2.timeline) == 0

    stored2 = session_storage.get_session("room_auto_persist_clear")
    assert stored2 is not None
    assert len(stored2["transcript"]) == 1
    assert stored2["transcript"][0].text == "Clearing now"


@pytest.mark.asyncio
async def test_session_manager_remove_persists():
    from ws1_backend.storage import session_storage

    sm = SessionManager({})
    room = await sm.get_or_create_room("room_sm_persist")
    ev = CaptionEvent(
        segment_id="seg_sm",
        speaker_id="p3",
        speaker_name="Eve",
        start_ts=300,
        end_ts=700,
        text="Manager remove test",
        is_final=True,
    )
    await room.add_caption(ev, broadcast=False)

    await sm.remove_room("room_sm_persist")

    stored = session_storage.get_session("room_sm_persist")
    assert stored is not None
    assert stored["transcript"][0].text == "Manager remove test"
