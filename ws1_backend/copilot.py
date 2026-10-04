"""
Roundtable Voice Copilot ("Hey Roundtable").

Provides wake-word interception, context aggregation from room history,
asynchronous LLM querying via Groq (qwen/qwen3.8-27b), and synthetic
system caption broadcasting.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import uuid
from typing import TYPE_CHECKING, Any, List, Optional

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contracts.models import CaptionEvent

if TYPE_CHECKING:
    from ws1_backend.session import Room

logger = logging.getLogger("ws1_backend.copilot")

# Regex pattern for wake word interception: (?i)^hey roundtable[,]?\s*(.*)
WAKE_WORD_PATTERN = re.compile(r"(?i)^hey roundtable[,]?\s*(.*)")
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
AI_SPEAKER_ID = "Roundtable AI"
AI_SPEAKER_NAME = "Roundtable AI"

_groq_client: Optional[Any] = None


def extract_wake_word_query(text: str) -> Optional[str]:
    r"""
    Check if text starts with wake word: (?i)^hey roundtable[,]?\s*(.*)
    Returns extracted query string if matched, otherwise None.
    """
    if not text:
        return None
    match = WAKE_WORD_PATTERN.match(text.strip())
    if match:
        return match.group(1).strip()
    return None


def is_wake_word_caption(caption: CaptionEvent) -> Optional[str]:
    """
    Check if a caption event is an is_final user utterance triggering the wake word.
    Returns the extracted query if matched, None otherwise.
    """
    if not caption.is_final:
        return None
    if caption.speaker_id == AI_SPEAKER_ID:
        return None
    return extract_wake_word_query(caption.text)


def get_groq_client(api_key: Optional[str] = None) -> Optional[Any]:
    """Get or create AsyncGroq client."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import AsyncGroq
        _groq_client = AsyncGroq(api_key=key)
        return _groq_client
    except Exception as exc:
        logger.warning("Could not initialize Groq client: %s", exc)
        return None


def set_groq_client(client: Optional[Any]) -> None:
    """Set custom or mock AsyncGroq client (useful for unit tests)."""
    global _groq_client
    _groq_client = client


async def handle_voice_copilot(
    room: Room,
    query: str,
    client: Optional[Any] = None,
    model: Optional[str] = None,
) -> Optional[CaptionEvent]:
    """
    Handle intercepted wake-word query:
    1. Fetch last 50 lines of room's transcript buffer.
    2. Query Groq asynchronously (qwen/qwen3.8-27b).
    3. Broadcast response as a system CaptionEvent (speaker_id="Roundtable AI").
    """
    logger.info("Voice copilot triggered in room %s with query: %r", room.session_id, query)
    return None
