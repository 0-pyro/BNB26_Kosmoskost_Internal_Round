"""
Unit tests for ws1_backend REST APIs:
- GET /api/sessions
- GET /api/sessions/{session_id}
- POST /api/ai/assist
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
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


@pytest.fixture()
def mock_groq(monkeypatch):
    """Mock the Groq client and capture chat completion arguments."""
    calls = []
    mock_client = AsyncMock()

    async def fake_create(**kwargs):
        calls.append(kwargs)
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Mocked LLM Response for: " + kwargs.get("model", "")
        mock_completion.choices = [mock_choice]
        return mock_completion

    mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr("ws1_backend.main.get_groq_client", lambda **kwargs: mock_client)
    return calls


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


@pytest.mark.asyncio
async def test_ai_assist_summary(client: httpx.AsyncClient, mock_groq: list):
    ev1 = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        text="Let's finalize the roadmap.",
        is_final=True,
    )
    ev2 = CaptionEvent(
        segment_id="s2",
        speaker_id="p2",
        speaker_name="Bob",
        text="Agreed, we ship v1 next Friday.",
        is_final=True,
    )
    session_storage.save_session("session_meeting", [ev1, ev2])

    payload = {
        "session_id": "session_meeting",
        "query_type": "summary",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Mocked LLM Response for: qwen/qwen3.8-27b" in data["response"]
    assert data["result"] == data["response"]

    # Verify Groq LLM invocation parameters
    assert len(mock_groq) == 1
    assert mock_groq[0]["model"] == "qwen/qwen3.8-27b"
    user_prompt = mock_groq[0]["messages"][1]["content"]
    assert "Alice: Let's finalize the roadmap." in user_prompt
    assert "Bob: Agreed, we ship v1 next Friday." in user_prompt


@pytest.mark.asyncio
async def test_ai_assist_translation(client: httpx.AsyncClient, mock_groq: list):
    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        text="Good morning team.",
        is_final=True,
    )
    session_storage.save_session("session_trans", [ev])

    payload = {
        "session_id": "session_trans",
        "query_type": "translation",
        "target_language": "Japanese",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Mocked LLM Response" in data["response"]

    # Verify prompt contains translation target
    assert len(mock_groq) == 1
    system_prompt = mock_groq[0]["messages"][0]["content"]
    user_prompt = mock_groq[0]["messages"][1]["content"]
    assert "Japanese" in system_prompt
    assert "Japanese" in user_prompt
    assert "Alice: Good morning team." in user_prompt


@pytest.mark.asyncio
async def test_ai_assist_custom_query(client: httpx.AsyncClient, mock_groq: list):
    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        speaker_name="Alice",
        text="The server budget is 500 dollars.",
        is_final=True,
    )
    session_storage.save_session("session_custom", [ev])

    payload = {
        "session_id": "session_custom",
        "query_type": "custom",
        "query": "What is the server budget?",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Mocked LLM Response" in data["response"]

    assert len(mock_groq) == 1
    user_prompt = mock_groq[0]["messages"][1]["content"]
    assert "Question: What is the server budget?" in user_prompt
    assert "Alice: The server budget is 500 dollars." in user_prompt


@pytest.mark.asyncio
async def test_ai_assist_session_not_found(client: httpx.AsyncClient, mock_groq: list):
    payload = {
        "session_id": "ghost_session",
        "query_type": "summary",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 404
    assert len(mock_groq) == 0


@pytest.mark.asyncio
async def test_ai_assist_invalid_query_type(client: httpx.AsyncClient, mock_groq: list):
    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        text="Test",
        is_final=True,
    )
    session_storage.save_session("session_valid", [ev])

    payload = {
        "session_id": "session_valid",
        "query_type": "unknown_action",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 400
    assert "Invalid query_type" in response.json()["detail"]
    assert len(mock_groq) == 0


@pytest.mark.asyncio
async def test_ai_assist_empty_transcript(client: httpx.AsyncClient, mock_groq: list):
    session_storage.save_session("session_empty", [])

    payload = {
        "session_id": "session_empty",
        "query_type": "summary",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "No transcript available" in data["response"]
    assert len(mock_groq) == 0


@pytest.mark.asyncio
async def test_ai_assist_groq_api_error(client: httpx.AsyncClient, monkeypatch):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("Groq service timeout"))
    monkeypatch.setattr("ws1_backend.main.get_groq_client", lambda **kwargs: mock_client)

    ev = CaptionEvent(
        segment_id="s1",
        speaker_id="p1",
        text="Hello",
        is_final=True,
    )
    session_storage.save_session("session_err", [ev])

    payload = {
        "session_id": "session_err",
        "query_type": "summary",
    }
    response = await client.post("/api/ai/assist", json=payload)
    assert response.status_code == 500
    assert "Failed to query Groq" in response.json()["detail"]
