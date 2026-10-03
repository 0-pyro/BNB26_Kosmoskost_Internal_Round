"""Tests for Time Synchronization in ws1_backend."""

from __future__ import annotations

import asyncio
import json
import time
import pytest
import websockets

from contracts.models import TimeSyncRequest, TimeSyncResponse


@pytest.mark.asyncio
async def test_time_sync_roundtrip(server_url: str):
    """Client sends TimeSyncRequest and receives TimeSyncResponse immediately."""
    async with websockets.connect(server_url) as ws:
        client_tx = int(time.time() * 1000)
        req = TimeSyncRequest(client_tx_ts=client_tx)
        await ws.send(req.model_dump_json())

        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(raw)

        assert data["type"] == "SYNC_ACK"
        resp = TimeSyncResponse(**data)
        assert resp.client_tx_ts == client_tx
        assert resp.server_rx_ts > 0
        assert resp.server_tx_ts >= resp.server_rx_ts
        # Server timestamp should be reasonably close to current time (within 5 seconds)
        assert abs(resp.server_rx_ts - client_tx) < 5000


@pytest.mark.asyncio
async def test_multiple_sequential_time_syncs(server_url: str):
    """Client can perform multiple time sync measurements sequentially."""
    async with websockets.connect(server_url) as ws:
        for _ in range(3):
            client_tx = int(time.time() * 1000)
            req = TimeSyncRequest(client_tx_ts=client_tx)
            await ws.send(req.model_dump_json())

            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(raw)
            resp = TimeSyncResponse(**data)
            assert resp.client_tx_ts == client_tx
            await asyncio.sleep(0.02)
