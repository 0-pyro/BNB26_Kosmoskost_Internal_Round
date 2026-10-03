"""
Tests for the Mock ASR Server.

These tests start the mock server in-process on a random port, exercise
JSON and binary message handling, and verify the server does not crash
on malformed input.

Run with:
    python -m pytest ws4_eval/tests/ -v
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import time

import pytest
import pytest_asyncio
import websockets

# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from contracts.models import (
    AUDIO_MAGIC,
    AudioFrameHeader,
    CaptionEvent,
    JoinAck,
    JoinRequest,
    TimeSyncRequest,
    TimeSyncResponse,
)

# Import the server handler so we can serve it on a random port
from ws4_eval.mock_server import handle_connection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def server_url():
    """Start the mock server on a random free port and yield the URL."""
    # Port 0 lets the OS pick a free port
    server = await websockets.serve(handle_connection, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}"
    yield url
    server.close()
    await server.wait_closed()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_join_request_gets_ack(server_url: str) -> None:
    """Mock server must reply to JoinRequest with JoinAck."""
    async with websockets.connect(server_url) as ws:
        join = JoinRequest(session_id="ROOM1", participant_name="TestAlice")
        await ws.send(join.model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "JOIN_ACK"
        assert "participant_id" in data
        # Validate it parses as a JoinAck
        ack = JoinAck(**data)
        assert ack.participant_id.startswith("p_")


async def test_sync_request_gets_response(server_url: str) -> None:
    """Mock server must reply to TimeSyncRequest with TimeSyncResponse."""
    async with websockets.connect(server_url) as ws:
        now_ms = int(time.time() * 1000)
        sync = TimeSyncRequest(client_tx_ts=now_ms)
        await ws.send(sync.model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "SYNC_ACK"
        resp = TimeSyncResponse(**data)
        assert resp.client_tx_ts == now_ms
        assert resp.server_rx_ts > 0


async def test_binary_audio_frame_returns_caption(server_url: str) -> None:
    """Sending a valid binary audio frame should produce a CaptionEvent."""
    async with websockets.connect(server_url) as ws:
        # Build a valid audio frame: 16-byte header + some Float32 payload
        header = AudioFrameHeader(
            participant_id_hash=42,
            seq_num=0,
            capture_ts=int(time.time() * 1000),
        )
        # 10 silence samples as payload
        payload = struct.pack(">10f", *([0.0] * 10))
        frame = header.to_bytes() + payload
        await ws.send(frame)

        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "CAPTION"
        caption = CaptionEvent(**data)
        assert len(caption.text) > 0


async def test_malformed_binary_no_crash(server_url: str) -> None:
    """Server must handle malformed binary frames without crashing."""
    async with websockets.connect(server_url) as ws:
        # Send too-short frame
        await ws.send(b"\x00\x01\x02")

        # Send frame with wrong magic bytes
        await ws.send(b"\xCC\xDD" + b"\x00" * 14)

        # Server should still be alive — send a valid JOIN and get ACK
        join = JoinRequest(session_id="ROOM1", participant_name="TestBob")
        await ws.send(join.model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "JOIN_ACK"


async def test_malformed_json_no_crash(server_url: str) -> None:
    """Server must handle malformed JSON without crashing."""
    async with websockets.connect(server_url) as ws:
        # Send invalid JSON
        await ws.send("not valid json {{{")

        # Server should still be alive
        join = JoinRequest(session_id="ROOM1", participant_name="TestCharlie")
        await ws.send(join.model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "JOIN_ACK"


async def test_unknown_json_type_no_crash(server_url: str) -> None:
    """Server must handle unknown JSON message types without crashing."""
    async with websockets.connect(server_url) as ws:
        await ws.send(json.dumps({"type": "UNKNOWN_TYPE", "data": 42}))

        # Server should still be alive
        join = JoinRequest(session_id="ROOM1", participant_name="TestDave")
        await ws.send(join.model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "JOIN_ACK"
