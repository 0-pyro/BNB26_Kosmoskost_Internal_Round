"""Tests for Binary Audio Frame Handling in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import struct
import time
import pytest
import websockets

from contracts.models import (
    AUDIO_HEADER_SIZE,
    AUDIO_MAGIC,
    AudioFrameHeader,
    JoinAck,
    JoinRequest,
    TimeSyncRequest,
    TimeSyncResponse,
)


@pytest.mark.asyncio
async def test_valid_audio_frame(server_url: str, capsys):
    """Sending a valid binary audio frame logs/prints header and doesn't crash."""
    async with websockets.connect(server_url) as ws:
        # First join a room
        await ws.send(JoinRequest(session_id="ROOM_AUDIO", participant_name="Alice").model_dump_json())
        await ws.recv()

        header = AudioFrameHeader(
            participant_id_hash=1234,
            seq_num=42,
            capture_ts=int(time.time() * 1000),
        )
        payload = struct.pack(">16f", *([0.0] * 16))
        frame = header.to_bytes() + payload

        await ws.send(frame)

        # Connection should stay open and receive mock caption or accept next command
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "CAPTION"

        # Check stdout contains expected header print
        captured = capsys.readouterr()
        assert "Participant ID Hash: 1234" in captured.out
        assert "SeqNum: 42" in captured.out


@pytest.mark.asyncio
async def test_audio_frame_short_payload(server_url: str):
    """A binary frame with fewer than 16 bytes is ignored without crashing."""
    async with websockets.connect(server_url) as ws:
        # Send 3 bytes
        await ws.send(b"\xAA\xBB\x01")

        # Verify server is still alive by sending a SYNC request
        now_ms = int(time.time() * 1000)
        await ws.send(TimeSyncRequest(client_tx_ts=now_ms).model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "SYNC_ACK"


@pytest.mark.asyncio
async def test_audio_frame_invalid_magic(server_url: str):
    """A binary frame with invalid magic bytes is ignored without crashing."""
    async with websockets.connect(server_url) as ws:
        # 16 bytes with bad magic
        bad_frame = b"\xCC\xDD" + b"\x00" * 14
        await ws.send(bad_frame)

        # Verify server is still alive
        now_ms = int(time.time() * 1000)
        await ws.send(TimeSyncRequest(client_tx_ts=now_ms).model_dump_json())
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)
        assert data["type"] == "SYNC_ACK"
