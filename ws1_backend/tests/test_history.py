"""Tests for Caption History Buffering and Fan-out in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import pytest
import websockets

from contracts.models import CaptionEvent, JoinAck, JoinRequest
from ws1_backend.session import session_manager


@pytest.mark.asyncio
async def test_late_joiner_receives_caption_history(server_url: str):
    """When a new participant joins an existing room, they receive historical captions in JoinAck."""
    # Pre-populate room with historical captions
    room = await session_manager.get_or_create_room("ROOM_HIST")
    cap1 = CaptionEvent(
        segment_id="seg_1",
        speaker_id="p_initial",
        speaker_name="Host",
        start_ts=1000,
        end_ts=2000,
        text="Welcome to Roundtable.",
        is_final=True,
    )
    cap2 = CaptionEvent(
        segment_id="seg_2",
        speaker_id="p_initial",
        speaker_name="Host",
        start_ts=2100,
        end_ts=3500,
        text="We are testing live captions.",
        is_final=True,
    )
    await room.add_caption(cap1, broadcast=False)
    await room.add_caption(cap2, broadcast=False)

    # Late joiner connects
    async with websockets.connect(server_url) as ws:
        await ws.send(JoinRequest(session_id="ROOM_HIST", participant_name="LateAlice").model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        ack = JoinAck(**json.loads(raw))

        assert len(ack.history) == 2
        assert ack.history[0].segment_id == "seg_1"
        assert ack.history[0].text == "Welcome to Roundtable."
        assert ack.history[0].is_final is True
        assert ack.history[1].segment_id == "seg_2"
        assert ack.history[1].text == "We are testing live captions."


@pytest.mark.asyncio
async def test_live_caption_broadcast_to_all_participants(server_url: str):
    """Active participants in the same room receive live CaptionEvent broadcasts."""
    async with websockets.connect(server_url) as ws1, websockets.connect(server_url) as ws2:
        # Alice joins
        await ws1.send(JoinRequest(session_id="ROOM_BROADCAST", participant_name="Alice").model_dump_json())
        await ws1.recv()

        # Bob joins
        await ws2.send(JoinRequest(session_id="ROOM_BROADCAST", participant_name="Bob").model_dump_json())
        await ws2.recv()

        # Inject a caption event from Alice
        cap = CaptionEvent(
            segment_id="seg_live_1",
            speaker_id="p_alice",
            speaker_name="Alice",
            start_ts=5000,
            end_ts=6000,
            text="Can everyone hear me?",
            is_final=True,
        )
        await ws1.send(cap.model_dump_json())

        # Both Alice and Bob should receive the broadcast
        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0))

        assert msg1["type"] == "CAPTION"
        assert msg1["text"] == "Can everyone hear me?"
        assert msg2["type"] == "CAPTION"
        assert msg2["text"] == "Can everyone hear me?"

        # Verify it was added to history
        room = await session_manager.get_room("ROOM_BROADCAST")
        assert len(room.timeline) == 1
        assert room.timeline[0].segment_id == "seg_live_1"
