"""Tests for Concurrency and Connection Safety in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import pytest
import websockets

from contracts.models import CaptionEvent, JoinRequest


@pytest.mark.asyncio
async def test_concurrent_writes_no_corruption(server_url: str):
    """Concurrent sends to the same connection are serialized and do not raise errors."""
    async with websockets.connect(server_url) as ws:
        await ws.send(JoinRequest(session_id="ROOM_CONCUR", participant_name="Alice").model_dump_json())
        await ws.recv()

        # Send multiple caption events concurrently
        async def send_event(idx: int):
            cap = CaptionEvent(
                segment_id=f"seg_{idx}",
                speaker_id="p_alice",
                speaker_name="Alice",
                text=f"Concurrent message {idx}",
                is_final=True,
            )
            await ws.send(cap.model_dump_json())

        await asyncio.gather(*[send_event(i) for i in range(10)])

        # Read back all 10 broadcasts
        received = []
        for _ in range(10):
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(raw)
            if data.get("type") == "CAPTION":
                received.append(data["segment_id"])

        assert len(received) == 10
        assert set(received) == {f"seg_{i}" for i in range(10)}
