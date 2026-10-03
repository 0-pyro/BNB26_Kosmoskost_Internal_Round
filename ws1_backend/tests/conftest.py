"""Pytest fixtures for ws1_backend tests."""

from __future__ import annotations

import asyncio
import os
import sys
import pytest_asyncio
import uvicorn

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ws1_backend.main import app
from ws1_backend.session import session_manager


@pytest_asyncio.fixture()
async def server_url():
    """Start the FastAPI backend on a random port and return the WebSocket URL."""
    session_manager.reset()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    # Wait for server to be bound and started
    while not server.started:
        await asyncio.sleep(0.01)

    port = server.servers[0].sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}/ws"

    try:
        yield url
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except (asyncio.TimeoutError, Exception):
            pass
        session_manager.reset()
