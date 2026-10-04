"""Unit tests for Voice Copilot wake-word interception and Groq LLM integration."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import websockets

from contracts.models import CaptionEvent, JoinRequest
from ws1_backend.copilot import (
    AI_SPEAKER_ID,
    AI_SPEAKER_NAME,
    DEFAULT_MODEL,
    WAKE_WORD_PATTERN,
    extract_wake_word_query,
    handle_voice_copilot,
    is_wake_word_caption,
    set_groq_client,
)
from ws1_backend.session import Room, session_manager


class MockWebSocket:
    """Mock Starlette/FastAPI WebSocket for direct unit testing."""

    def __init__(self):
        self.sent_texts: list[str] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


@pytest.fixture(autouse=True)
def reset_copilot_client():
    """Reset global copilot client after each test."""
    yield
    set_groq_client(None)


@pytest.mark.parametrize(
    "input_text,expected_query",
    [
        ("Hey Roundtable, what are the action items?", "what are the action items?"),
        ("hey roundtable what are the action items?", "what are the action items?"),
        ("HEY ROUNDTABLE, summarize the meeting", "summarize the meeting"),
        ("Hey Roundtable,   can you help?  ", "can you help?"),
        ("Hey Roundtable", ""),
        ("Hey Roundtable,", ""),
        ("hey roundtable   ", ""),
        ("Hey Roundtable, who just spoke?", "who just spoke?"),
    ],
)
def test_wake_word_regex_matches(input_text: str, expected_query: str):
    """Verify regex correctly matches case-insensitively and extracts the query."""
    query = extract_wake_word_query(input_text)
    assert query is not None
    assert query == expected_query


@pytest.mark.parametrize(
    "input_text",
    [
        "Hello everyone, welcome to the meeting.",
        "We are sitting at the roundtable today.",
        "I think hey roundtable is a neat wake word.",
        "Can someone say hey roundtable please?",
        "",
        "   ",
        "Just a normal caption segment.",
    ],
)
def test_wake_word_regex_non_matches(input_text: str):
    """Verify non-wake-word sentences do not trigger the interceptor."""
    query = extract_wake_word_query(input_text)
    assert query is None


def test_is_wake_word_caption():
    """Verify caption metadata checks (is_final, speaker_id)."""
    # Final user caption with wake word -> match
    cap_final = CaptionEvent(
        segment_id="seg_1",
        speaker_id="user_1",
        text="Hey Roundtable, repeat that",
        is_final=True,
    )
    assert is_wake_word_caption(cap_final) == "repeat that"

    # Non-final caption with wake word -> do NOT intercept
    cap_partial = CaptionEvent(
        segment_id="seg_2",
        speaker_id="user_1",
        text="Hey Roundtable, repeat that",
        is_final=False,
    )
    assert is_wake_word_caption(cap_partial) is None

    # AI caption with wake word -> do NOT intercept (prevent feedback loop)
    cap_ai = CaptionEvent(
        segment_id="seg_3",
        speaker_id=AI_SPEAKER_ID,
        text="Hey Roundtable, I am already answering",
        is_final=True,
    )
    assert is_wake_word_caption(cap_ai) is None


@pytest.mark.asyncio
async def test_wake_word_interception_not_broadcast_as_user_caption():
    """Verify intercepted wake-word segment is not broadcast as a normal user caption."""
    from ws1_backend.session import Connection

    room = Room("ROOM_INTERCEPT_TEST")
    mock_ws = MockWebSocket()
    conn = Connection(mock_ws)
    await room.join("Alice", conn)

    # 1. Normal caption is broadcast
    normal_cap = CaptionEvent(
        segment_id="seg_normal",
        speaker_id="p_alice",
        speaker_name="Alice",
        text="Normal meeting discussion point.",
        is_final=True,
    )
    await room.add_caption(normal_cap, broadcast=True)
    assert len(mock_ws.sent_texts) == 1
    sent_json = json.loads(mock_ws.sent_texts[0])
    assert sent_json["text"] == "Normal meeting discussion point."

    # Clear sent messages
    mock_ws.sent_texts.clear()

    # 2. Wake-word caption is intercepted and NOT broadcast as user caption
    wake_cap = CaptionEvent(
        segment_id="seg_wake",
        speaker_id="p_alice",
        speaker_name="Alice",
        text="Hey Roundtable, what did we just discuss?",
        is_final=True,
    )
    await room.add_caption(wake_cap, broadcast=True)

    # Allow async task to be scheduled
    await asyncio.sleep(0.05)

    # The user's wake word command was NOT broadcast as a user caption
    user_broadcasts = [
        json.loads(msg) for msg in mock_ws.sent_texts
        if json.loads(msg).get("speaker_id") != AI_SPEAKER_ID
    ]
    assert len(user_broadcasts) == 0


@pytest.mark.asyncio
async def test_mock_groq_llm_call_and_broadcast():
    """Verify Groq client is called with context and query, and AI response is broadcast."""
    from ws1_backend.session import Connection

    room = Room("ROOM_LLM_BROADCAST")
    mock_ws = MockWebSocket()
    conn = Connection(mock_ws)
    await room.join("Bob", conn)

    # Pre-populate some room discussion
    prior_cap = CaptionEvent(
        segment_id="seg_prior",
        speaker_id="p_carol",
        speaker_name="Carol",
        text="We agreed to launch the beta next Tuesday.",
        is_final=True,
    )
    await room.add_caption(prior_cap, broadcast=False)

    # Mock the Groq AsyncClient
    mock_groq = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message = MagicMock(content="The launch is scheduled for next Tuesday.")
    mock_completion = MagicMock(choices=[mock_choice])
    mock_groq.chat.completions.create = AsyncMock(return_value=mock_completion)

    set_groq_client(mock_groq)

    # Clear WS messages
    mock_ws.sent_texts.clear()

    # Send wake-word caption
    wake_cap = CaptionEvent(
        segment_id="seg_wake_1",
        speaker_id="p_bob",
        speaker_name="Bob",
        text="Hey Roundtable, when is the beta launch?",
        is_final=True,
    )
    await room.add_caption(wake_cap, broadcast=True)

    # Wait for non-blocking task to complete
    for _ in range(20):
        if any(AI_SPEAKER_ID in msg for msg in mock_ws.sent_texts):
            break
        await asyncio.sleep(0.05)

    # 1. Verify Groq call arguments
    mock_groq.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_groq.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "qwen/qwen3.8-27b"
    messages = call_kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Roundtable AI" in messages[0]["content"]

    user_prompt = messages[1]["content"]
    assert "We agreed to launch the beta next Tuesday." in user_prompt
    assert "when is the beta launch?" in user_prompt

    # 2. Verify AI CaptionEvent was broadcast to client
    assert len(mock_ws.sent_texts) == 1
    ai_event_data = json.loads(mock_ws.sent_texts[0])
    assert ai_event_data["type"] == "CAPTION"
    assert ai_event_data["speaker_id"] == AI_SPEAKER_ID
    assert ai_event_data["speaker_name"] == AI_SPEAKER_NAME
    assert ai_event_data["is_final"] is True
    assert ai_event_data["text"] == "The launch is scheduled for next Tuesday."


@pytest.mark.asyncio
async def test_context_buffer_last_50_lines():
    """Verify that only the last 50 lines of room history are passed to Groq context."""
    room = Room("ROOM_50_LINES")

    # Add 65 captions (0 to 64)
    for i in range(65):
        cap = CaptionEvent(
            segment_id=f"seg_{i}",
            speaker_id=f"speaker_{i % 3}",
            speaker_name=f"User_{i % 3}",
            text=f"Discussion line number {i}",
            is_final=True,
        )
        await room.add_caption(cap, broadcast=False)

    assert len(room.timeline) == 65

    # Mock Groq client
    mock_groq = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message = MagicMock(content="Summary of recent lines.")
    mock_groq.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice]))

    # Query voice copilot directly
    await handle_voice_copilot(
        room=room,
        query="what was discussed?",
        client=mock_groq,
    )

    mock_groq.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_groq.chat.completions.create.call_args.kwargs
    user_prompt = call_kwargs["messages"][1]["content"]

    # Lines 0 to 14 should NOT be in context (only last 50: lines 15 to 64)
    assert "Discussion line number 0" not in user_prompt
    assert "Discussion line number 14" not in user_prompt
    assert "Discussion line number 15" in user_prompt
    assert "Discussion line number 64" in user_prompt


@pytest.mark.asyncio
async def test_non_blocking_ingestion_during_llm_call():
    """Verify that a slow Groq call does not block room ingestion of subsequent captions."""
    from ws1_backend.session import Connection

    room = Room("ROOM_NON_BLOCKING")
    mock_ws = MockWebSocket()
    conn = Connection(mock_ws)
    await room.join("Alice", conn)

    # Slow Groq mock (sleeps 0.2s)
    async def delayed_completion(*args, **kwargs):
        await asyncio.sleep(0.2)
        choice = MagicMock()
        choice.message = MagicMock(content="Delayed AI reply")
        return MagicMock(choices=[choice])

    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=delayed_completion)
    set_groq_client(mock_groq)

    # Send wake word
    wake_cap = CaptionEvent(
        segment_id="seg_slow_wake",
        speaker_id="p_alice",
        speaker_name="Alice",
        text="Hey Roundtable, calculate this slowly",
        is_final=True,
    )
    # add_caption must return immediately without waiting 0.2s!
    t0 = asyncio.get_event_loop().time()
    await room.add_caption(wake_cap, broadcast=True)
    t1 = asyncio.get_event_loop().time()
    assert (t1 - t0) < 0.05, "add_caption blocked on LLM call!"

    # While LLM is still running in background, send a regular user caption
    urgent_cap = CaptionEvent(
        segment_id="seg_urgent",
        speaker_id="p_alice",
        speaker_name="Alice",
        text="Urgent point during meeting!",
        is_final=True,
    )
    await room.add_caption(urgent_cap, broadcast=True)

    # The urgent point was immediately broadcast before AI reply finishes
    assert len(mock_ws.sent_texts) == 1
    assert "Urgent point during meeting!" in mock_ws.sent_texts[0]

    # Now wait for the background AI task to finish
    await asyncio.sleep(0.3)
    assert len(mock_ws.sent_texts) == 2
    assert "Delayed AI reply" in mock_ws.sent_texts[1]


@pytest.mark.asyncio
async def test_groq_error_handled_gracefully():
    """Verify backend remains healthy and emits fallback if Groq API throws an error."""
    room = Room("ROOM_ERROR_TEST")
    mock_ws = MockWebSocket()
    from ws1_backend.session import Connection
    await room.join("Alice", connection=Connection(mock_ws))

    # Mock Groq failure
    mock_groq = AsyncMock()
    mock_groq.chat.completions.create = AsyncMock(side_effect=RuntimeError("Groq rate limit 429"))
    set_groq_client(mock_groq)

    wake_cap = CaptionEvent(
        segment_id="seg_fail",
        speaker_id="p_alice",
        speaker_name="Alice",
        text="Hey Roundtable, help me out",
        is_final=True,
    )
    await room.add_caption(wake_cap, broadcast=True)

    # Allow async task to complete
    for _ in range(10):
        if mock_ws.sent_texts:
            break
        await asyncio.sleep(0.05)

    assert len(mock_ws.sent_texts) == 1
    data = json.loads(mock_ws.sent_texts[0])
    assert data["speaker_id"] == AI_SPEAKER_ID
    assert "error" in data["text"].lower()


@pytest.mark.asyncio
async def test_full_websocket_wake_word_flow(server_url: str):
    """End-to-end WebSocket test: Client connects, sends wake word, receives AI CaptionEvent broadcast."""
    mock_groq = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message = MagicMock(content="Here is your live answer from Roundtable AI.")
    mock_groq.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice]))
    set_groq_client(mock_groq)

    async with websockets.connect(server_url) as ws1, websockets.connect(server_url) as ws2:
        # Alice & Bob join
        await ws1.send(JoinRequest(session_id="ROOM_WS_COPILOT", participant_name="Alice").model_dump_json())
        await ws1.recv()
        await ws2.send(JoinRequest(session_id="ROOM_WS_COPILOT", participant_name="Bob").model_dump_json())
        await ws2.recv()

        # Alice sends regular caption
        normal_cap = CaptionEvent(
            segment_id="seg_c1",
            speaker_id="p_alice",
            speaker_name="Alice",
            text="Let us discuss the Q3 roadmap.",
            is_final=True,
        )
        await ws1.send(normal_cap.model_dump_json())

        # Both receive the normal caption
        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0))
        assert msg1["text"] == "Let us discuss the Q3 roadmap."
        assert msg2["text"] == "Let us discuss the Q3 roadmap."

        # Bob sends wake-word query
        wake_cap = CaptionEvent(
            segment_id="seg_c2",
            speaker_id="p_bob",
            speaker_name="Bob",
            text="Hey Roundtable, what are we discussing?",
            is_final=True,
        )
        await ws2.send(wake_cap.model_dump_json())

        # Neither Alice nor Bob should receive Bob's caption as normal user text
        # Instead, both receive the Roundtable AI broadcast!
        ai_msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0))
        ai_msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0))

        assert ai_msg1["speaker_id"] == AI_SPEAKER_ID
        assert ai_msg1["speaker_name"] == AI_SPEAKER_NAME
        assert ai_msg1["is_final"] is True
        assert ai_msg1["text"] == "Here is your live answer from Roundtable AI."

        assert ai_msg2["speaker_id"] == AI_SPEAKER_ID
        assert ai_msg2["text"] == "Here is your live answer from Roundtable AI."
