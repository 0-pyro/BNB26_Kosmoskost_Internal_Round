"""Unit tests for Voice Copilot wake-word interception and Groq LLM integration."""

from __future__ import annotations

import asyncio
import json
import pytest
import websockets

from contracts.models import CaptionEvent, JoinRequest
from ws1_backend.copilot import (
    AI_SPEAKER_ID,
    WAKE_WORD_PATTERN,
    extract_wake_word_query,
    is_wake_word_caption,
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

    # The user's wake word command was NOT broadcast
    user_broadcasts = [
        json.loads(msg) for msg in mock_ws.sent_texts
        if json.loads(msg).get("speaker_id") != AI_SPEAKER_ID
    ]
    assert len(user_broadcasts) == 0
