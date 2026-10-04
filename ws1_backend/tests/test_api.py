"""
Unit tests for ws1_backend REST APIs:
- GET /api/sessions
- GET /api/sessions/{session_id}
- POST /api/ai/assist
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx

from contracts.models import CaptionEvent
from ws1_backend.main import app
from ws1_backend.session import session_manager
from ws1_backend.storage import session_storage


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """Ensure clean storage and active rooms before and after each test."""
    session_storage.clear()
    session_manager.reset()
    yield
    session_storage.clear()
    session_manager.reset()


@pytest_asyncio.fixture()
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_sessions_empty(client: httpx.AsyncClient):
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_sessions_with_data(client: httpx.AsyncClient):
    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        start_ts=1000,
        end_ts=3000,
        text="Hello world",
        is_final=True,
    )
    session_storage.save_session("session_alpha", [ev], created_at=1000)

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "session_alpha"
    assert sessions[0]["id"] == "session_alpha"
    assert sessions[0]["timestamp"] == 1000
    assert sessions[0]["duration"] == 2.0


@pytest.mark.asyncio
async def test_get_session_transcript_success(client: httpx.AsyncClient):
    ev1 = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        start_ts=1000,
        end_ts=2000,
        text="Point one",
        is_final=True,
    )
    ev2 = CaptionEvent(
        segment_id="s2",
        speaker_id="p2",
        speaker_name="Bob",
        start_ts=2100,
        end_ts=3500,
        text="Point two",
        is_final=True,
    )
    session_storage.save_session("session_beta", [ev1, ev2], created_at=1000)

    response = await client.get("/api/sessions/session_beta")
    assert response.status_code == 200
    transcript = response.json()
    assert isinstance(transcript, list)
    assert len(transcript) == 2
    assert transcript[0]["speaker_name"] == "Alice"
    assert transcript[0]["text"] == "Point one"
    assert transcript[1]["speaker_name"] == "Bob"
    assert transcript[1]["text"] == "Point two"


@pytest.mark.asyncio
async def test_get_session_transcript_404(client: httpx.AsyncClient):
    response = await client.get("/api/sessions/non_existent_session")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_session_transcript_fallback_to_active_room(client: httpx.AsyncClient):
    room = await session_manager.get_or_create_room("active_memory_room")
    ev = CaptionEvent(
        segment_id="s_live",
        speaker_id="p_live",
        speaker_name="Dana",
        start_ts=500,
        end_ts=1500,
        text="Live in memory",
        is_final=True,
    )
    await room.add_caption(ev, broadcast=False)

    response = await client.get("/api/sessions/active_memory_room")
    assert response.status_code == 200
    transcript = response.json()
    assert len(transcript) == 1
    assert transcript[0]["text"] == "Live in memory"
