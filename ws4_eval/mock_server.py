"""
Mock ASR WebSocket Server for Roundtable.

Listens on ws://localhost:{PORT} (default 8000).
- Accepts JSON messages: JOIN -> replies JOIN_ACK, SYNC -> replies SYNC_ACK.
- Accepts binary audio frames -> emits scripted CaptionEvent after a delay.
- Handles malformed binary frames gracefully (logs warning, does not crash).

Usage:
    python ws4_eval/mock_server.py [--port PORT]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import struct
import sys
import time
import uuid

import websockets
import websockets.server

# Ensure project root is on sys.path so we can import contracts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts.models import (
    AUDIO_HEADER_SIZE,
    AUDIO_MAGIC,
    AudioFrameHeader,
    CaptionEvent,
    JoinAck,
    TimeSyncResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock_server")

# ---------------------------------------------------------------------------
# Scripted caption responses for binary audio frames
# ---------------------------------------------------------------------------
SCRIPTED_CAPTIONS = [
    ("Hello, this is a test.", False),
    ("Hello, this is a test transcript.", True),
    ("The quick brown fox jumps.", False),
    ("The quick brown fox jumps over the lazy dog.", True),
]

# Per-connection state
_caption_counter: int = 0


def _next_caption(speaker_id: str, speaker_name: str) -> CaptionEvent:
    """Return the next scripted CaptionEvent, cycling through the list."""
    global _caption_counter
    text, is_final = SCRIPTED_CAPTIONS[_caption_counter % len(SCRIPTED_CAPTIONS)]
    now_ms = int(time.time() * 1000)
    event = CaptionEvent(
        segment_id=f"seg_{_caption_counter}",
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        start_ts=now_ms - 500,
        end_ts=now_ms,
        text=text,
        is_final=is_final,
        revision=1,
    )
    _caption_counter += 1
    return event


# ---------------------------------------------------------------------------
# Connection handler
# ---------------------------------------------------------------------------

async def handle_connection(
    websocket: websockets.server.WebSocketServerProtocol,
) -> None:
    """Handle a single WebSocket connection."""
    participant_id = f"p_{uuid.uuid4().hex[:8]}"
    participant_name = "Unknown"
    remote = websocket.remote_address
    logger.info("New connection from %s", remote)

    try:
        async for message in websocket:
            if isinstance(message, str):
                await _handle_json(websocket, message, participant_id, participant_name)
                # Update participant_name if JOIN was received
            elif isinstance(message, bytes):
                await _handle_binary(websocket, message, participant_id, participant_name)
            else:
                logger.warning("Unknown message type from %s", remote)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Connection closed: %s", remote)
    except Exception:
        logger.exception("Unexpected error handling connection %s", remote)


async def _handle_json(
    websocket: websockets.server.WebSocketServerProtocol,
    raw: str,
    participant_id: str,
    participant_name: str,
) -> None:
    """Dispatch a JSON text message."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Malformed JSON: %.100s", raw)
        return

    msg_type = data.get("type")

    if msg_type == "JOIN":
        pname = data.get("participant_name", "Unknown")
        ack = JoinAck(
            participant_id=participant_id,
            history=[],
        )
        logger.info("JOIN from %s -> assigned %s", pname, participant_id)
        await websocket.send(ack.model_dump_json())

    elif msg_type == "SYNC":
        now_ms = int(time.time() * 1000)
        resp = TimeSyncResponse(
            client_tx_ts=data.get("client_tx_ts", 0),
            server_rx_ts=now_ms,
            server_tx_ts=now_ms + 1,
        )
        logger.info("SYNC request, responding")
        await websocket.send(resp.model_dump_json())

    else:
        logger.warning("Unknown JSON message type: %s", msg_type)


async def _handle_binary(
    websocket: websockets.server.WebSocketServerProtocol,
    data: bytes,
    participant_id: str,
    participant_name: str,
) -> None:
    """Handle a binary audio frame: parse header, emit scripted caption."""
    # --- Malformed frame guard ---
    if len(data) < AUDIO_HEADER_SIZE:
        logger.warning(
            "Binary frame too short (%d bytes), ignoring", len(data)
        )
        return

    if data[0:2] != AUDIO_MAGIC:
        logger.warning(
            "Bad magic bytes %r, ignoring frame", data[0:2]
        )
        return

    try:
        header = AudioFrameHeader.from_bytes(data[:AUDIO_HEADER_SIZE])
    except (ValueError, struct.error) as exc:
        logger.warning("Failed to parse audio header: %s", exc)
        return

    payload_size = len(data) - AUDIO_HEADER_SIZE
    logger.debug(
        "Audio frame: pid_hash=%d seq=%d ts=%d payload=%d bytes",
        header.participant_id_hash,
        header.seq_num,
        header.capture_ts,
        payload_size,
    )

    # Simulate ASR delay (200-400ms)
    await asyncio.sleep(0.3)

    caption = _next_caption(participant_id, participant_name)
    await websocket.send(caption.model_dump_json())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(host: str, port: int) -> None:
    """Start the mock WebSocket server."""
    logger.info("Starting mock server on ws://%s:%d", host, port)
    async with websockets.serve(handle_connection, host, port):
        await asyncio.Future()  # run forever


def run(host: str = "0.0.0.0", port: int | None = None) -> None:
    """Entry point (called from CLI or tests)."""
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    asyncio.run(main(host, port))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roundtable Mock ASR Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    run(args.host, args.port)
