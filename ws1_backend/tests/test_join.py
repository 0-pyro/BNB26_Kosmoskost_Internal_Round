"""Tests for Join Flow in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import pytest
import websockets

from contracts.models import JoinAck, JoinRequest
from ws1_backend.session import session_manager


@pytest.mark.asyncio
async def test_join_single_participant(server_url: str):
    """Client connects, sends JoinRequest, receives valid JoinAck with history."""
    async with websockets.connect(server_url) as ws:
        req = JoinRequest(session_id="ROOM1", participant_name="Alice")
        await ws.send(req.model_dump_json())

        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)

        assert data["type"] == "JOIN_ACK"
        ack = JoinAck(**data)
        assert ack.participant_id.startswith("p_")
        assert ack.history == []

        # Verify backend room state
        room = await session_manager.get_room("ROOM1")
        assert room is not None
        assert ack.participant_id in room.participants
        assert room.participants[ack.participant_id].name == "Alice"


@pytest.mark.asyncio
async def test_join_multiple_participants_same_room(server_url: str):
    """Multiple participants can join the same room and get unique IDs."""
    async with websockets.connect(server_url) as ws1, websockets.connect(server_url) as ws2:
        req1 = JoinRequest(session_id="ROOM_A", participant_name="Alice")
        await ws1.send(req1.model_dump_json())
        ack1 = JoinAck(**json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0)))

        req2 = JoinRequest(session_id="ROOM_A", participant_name="Bob")
        await ws2.send(req2.model_dump_json())
        ack2 = JoinAck(**json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0)))

        assert ack1.participant_id != ack2.participant_id
        room = await session_manager.get_room("ROOM_A")
        assert len(room.participants) == 2
        assert ack1.participant_id in room.participants
        assert ack2.participant_id in room.participants


@pytest.mark.asyncio
async def test_join_different_rooms_isolated(server_url: str):
    """Participants in different rooms are isolated."""
    async with websockets.connect(server_url) as ws1, websockets.connect(server_url) as ws2:
        await ws1.send(JoinRequest(session_id="ROOM_1", participant_name="Alice").model_dump_json())
        ack1 = JoinAck(**json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0)))

        await ws2.send(JoinRequest(session_id="ROOM_2", participant_name="Bob").model_dump_json())
        ack2 = JoinAck(**json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0)))

        room1 = await session_manager.get_room("ROOM_1")
        room2 = await session_manager.get_room("ROOM_2")
        assert room1 is not None and room2 is not None
        assert ack1.participant_id in room1.participants
        assert ack2.participant_id not in room1.participants
        assert ack2.participant_id in room2.participants


@pytest.mark.asyncio
async def test_join_same_name_disambiguation(server_url: str):
    """Two concurrent clients with the same name get disambiguated names."""
    async with websockets.connect(server_url) as ws1, websockets.connect(server_url) as ws2:
        await ws1.send(JoinRequest(session_id="ROOM_DUPE", participant_name="Alice").model_dump_json())
        ack1 = JoinAck(**json.loads(await asyncio.wait_for(ws1.recv(), timeout=5.0)))

        await ws2.send(JoinRequest(session_id="ROOM_DUPE", participant_name="Alice").model_dump_json())
        ack2 = JoinAck(**json.loads(await asyncio.wait_for(ws2.recv(), timeout=5.0)))

        room = await session_manager.get_room("ROOM_DUPE")
        p1 = room.participants[ack1.participant_id]
        p2 = room.participants[ack2.participant_id]
        assert p1.name == "Alice"
        assert p2.name == "Alice (1)"
