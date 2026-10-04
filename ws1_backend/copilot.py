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


def build_context_prompt(recent_captions: List[CaptionEvent]) -> str:
    """Format recent captions into readable speaker lines for LLM context."""
    lines = [
        f"{c.speaker_name or c.speaker_id}: {c.text}"
        for c in recent_captions
        if c.text
    ]
    return "\n".join(lines) if lines else "(No previous transcript)"


async def handle_voice_copilot(
    room: Room,
    query: str,
    client: Optional[Any] = None,
    model: Optional[str] = None,
    trigger_caption: Optional[CaptionEvent] = None,
) -> Optional[CaptionEvent]:
    """
    Handle intercepted wake-word query:
    1. Fetch last 50 lines of room's transcript buffer.
    2. Query Groq asynchronously (qwen/qwen3.8-27b).
    3. Broadcast response as a system CaptionEvent (speaker_id="Roundtable AI").
    """
    # 1. Fetch last 50 lines of room's transcript buffer
    async with room.lock:
        recent_captions = list(room.timeline[-50:])
        if trigger_caption:
            room.timeline.append(trigger_caption)

    context_str = build_context_prompt(recent_captions)
    effective_model = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    system_content = (
        "You are Roundtable AI, an intelligent live voice copilot in a meeting. "
        "Answer the user's question directly and concisely based on the recent meeting context. "
        "Keep your response brief (1-3 sentences) suitable for real-time live captions."
    )
    user_content = (
        f"Meeting Context (up to last 50 captions):\n{context_str}\n\n"
        f"User Query: {query if query else 'Please acknowledge that you are listening and ask how you can help.'}"
    )

    # 2. Query Groq LLM asynchronously
    groq_client = client if client is not None else get_groq_client()
    llm_response = ""

    if groq_client is not None:
        try:
            logger.info(
                "Querying Groq (%s) for room %s with %d context lines: %r",
                effective_model,
                room.session_id,
                len(recent_captions),
                query,
            )
            chat_completion = await groq_client.chat.completions.create(
                model=effective_model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=256,
                temperature=0.3,
            )
            if hasattr(chat_completion, "choices") and chat_completion.choices:
                msg = chat_completion.choices[0].message
                llm_response = (getattr(msg, "content", None) or "").strip()
        except Exception as exc:
            logger.error("Error generating Groq LLM response for room %s: %s", room.session_id, exc)
            llm_response = f"[Roundtable AI]: Unable to process query due to an error."
    else:
        logger.warning("No Groq client available (GROQ_API_KEY not configured)")
        llm_response = f"[Roundtable AI]: Query received: '{query}'. (Groq API key not set)"

    if not llm_response:
        llm_response = "[Roundtable AI]: I'm listening. How can I help?"

    # 3. Broadcast Response: CaptionEvent with speaker_id="Roundtable AI", is_final=True
    now_ms = int(time.time() * 1000)
    ai_caption = CaptionEvent(
        segment_id=f"ai_{uuid.uuid4().hex[:8]}",
        speaker_id=AI_SPEAKER_ID,
        speaker_name=AI_SPEAKER_NAME,
        start_ts=now_ms,
        end_ts=now_ms,
        text=llm_response,
        is_final=True,
        revision=1,
    )

    logger.info("Broadcasting Roundtable AI response in room %s: %s", room.session_id, llm_response)
    await room.add_caption(ai_caption, broadcast=True)
    return ai_caption
