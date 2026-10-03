"""Tests for Disconnect and Reconnect handling in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import pytest
import websockets

from contracts.models import ConnectionState, JoinAck, JoinRequest
from ws1_backend.session import session_manager


@pytest.mark.asyncio
async def test_disconnect_marks_participant_inactive(server_url: str):
    """When a client disconnects, mark them DISCONNECTED but keep them in the room."""
    async with websockets.connect(server_url) as ws:
        await ws.send(JoinRequest(session_id="ROOM_DISC", participant_name="Alice").model_dump_json())
        ack = JoinAck(**json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0)))
        pid = ack.participant_id

        room = await session_manager.get_room("ROOM_DISC")
        assert room is not None
        assert room.participants[pid].connection_state == ConnectionState.ACTIVE

    # WebSocket is now closed; give event loop a moment to trigger disconnect
    await asyncio.sleep(0.1)

    assert pid in room.participants
    assert room.participants[pid].connection_state == ConnectionState.DISCONNECTED


@pytest.mark.asyncio
async def test_reconnect_within_grace_period(server_url: str):
    """A client that reconnects within the grace period retains their participant_id."""
    # First connection
    async with websockets.connect(server_url) as ws1:
        await ws1.send(JoinRequest(session_id="ROOM_RECON", participant_name="Bob").model_dump_json())
        ack1 = JoinAck(**json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0)))
        pid1 = ack1.participant_id

    # Disconnected
    await asyncio.sleep(0.1)
    room = await session_manager.get_room("ROOM_RECON")
    assert room.participants[pid1].connection_state == ConnectionState.DISCONNECTED

    # Reconnection with same name
    async with websockets.connect(server_url) as ws2:
        await ws2.send(JoinRequest(session_id="ROOM_RECON", participant_name="Bob").model_dump_json())
        ack2 = JoinAck(**json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0)))
        pid2 = ack2.participant_id

        assert pid1 == pid2
        assert room.participants[pid1].connection_state == ConnectionState.ACTIVE


@pytest.mark.asyncio
async def test_reconnect_with_explicit_participant_id(server_url: str):
    """A client reconnecting with explicit participant_id in payload is restored."""
    async with websockets.connect(server_url) as ws1:
        await ws1.send(JoinRequest(session_id="ROOM_RECON_ID", participant_name="Charlie").model_dump_json())
        ack1 = JoinAck(**json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0)))
        pid1 = ack1.participant_id

    await asyncio.sleep(0.1)

    # Reconnect with raw payload containing participant_id
    async with websockets.connect(server_url) as ws2:
        await ws2.send(json.dumps({
            "type": "JOIN",
            "session_id": "ROOM_RECON_ID",
            "participant_name": "Charlie",
            "participant_id": pid1,
        }))
        ack2 = JoinAck(**json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0)))
        assert ack2.participant_id == pid1

        room = await session_manager.get_room("ROOM_RECON_ID")
        assert room.participants[pid1].connection_state == ConnectionState.ACTIVE


@pytest.mark.asyncio
async def test_grace_period_expiry_removes_participant(server_url: str):
    """When the grace period expires, inactive participant is removed from room."""
    # Pre-configure room with short timeout for fast testing
    room = await session_manager.get_or_create_room("ROOM_EXPIRY", disconnect_timeout=0.2)

    async with websockets.connect(server_url) as ws:
        await ws.send(JoinRequest(session_id="ROOM_EXPIRY", participant_name="Dave").model_dump_json())
        ack = JoinAck(**json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0)))
        pid = ack.participant_id

    # Immediately after disconnect, participant is DISCONNECTED but still in room
    await asyncio.sleep(0.05)
    assert pid in room.participants
    assert room.participants[pid].connection_state == ConnectionState.DISCONNECTED

    # Wait for grace period (0.2s) to expire
    await asyncio.sleep(0.3)
    assert pid not in room.participants
    # Room should also be removed if empty
    assert await session_manager.get_room("ROOM_EXPIRY") is None
