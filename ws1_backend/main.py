"""
Roundtable WebSocket Backend (FastAPI).

Handles routing, rooms, participant session state, history buffering,
NTP-like time synchronization, and binary audio frame routing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import struct
import sys
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Ensure project root is on sys.path for contracts import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contracts.models import (
    AUDIO_HEADER_SIZE,
    AUDIO_MAGIC,
    AudioFrameHeader,
    CaptionEvent,
    JoinAck,
    JoinRequest,
    TimeSyncRequest,
    TimeSyncResponse,
)
from ws1_backend.session import (
    ROOMS,
    Connection,
    Participant,
    Room,
    SessionManager,
    session_manager,
)
from ws3_dsp.select import compute_rms, get_best_frame
from ws4_eval.asr_client import ASRClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ws1_backend.main")

# FastAPI App
app = FastAPI(
    title="Roundtable Backend",
    version="1.0.0",
    description="Multi-device live captioning WebSocket backend",
)

# Enable CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scripted captions for mock ASR mode
SCRIPTED_CAPTIONS = [
    ("Hello, this is a test.", False),
    ("Hello, this is a test transcript.", True),
    ("The quick brown fox jumps.", False),
    ("The quick brown fox jumps over the lazy dog.", True),
]
_caption_seq = 0

# Initialize ASR Client instance
asr_client = ASRClient(
    engine=os.environ.get("ASR_ENGINE", "mock").lower(),
    api_key=os.environ.get("GROQ_API_KEY") or os.environ.get("ASSEMBLYAI_API_KEY"),
)


def _generate_mock_caption(speaker_id: str, speaker_name: str) -> CaptionEvent:
    """Generate a scripted CaptionEvent for mock ASR testing."""
    global _caption_seq
    text, is_final = SCRIPTED_CAPTIONS[_caption_seq % len(SCRIPTED_CAPTIONS)]
    now_ms = int(time.time() * 1000)
    event = CaptionEvent(
        segment_id=f"seg_{_caption_seq}",
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        start_ts=now_ms - 500,
        end_ts=now_ms,
        text=text,
        is_final=is_final,
        revision=1,
    )
    _caption_seq += 1
    return event


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "ws1_backend",
        "active_rooms": len(ROOMS),
    }


async def _handle_websocket_connection(websocket: WebSocket) -> None:
    """Core WebSocket handler for client sessions."""
    await websocket.accept()
    conn = Connection(websocket)
    current_room: Optional[Room] = None
    current_participant: Optional[Participant] = None

    client_str = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    logger.info("WebSocket connected from %s", client_str)

    try:
        while True:
            # Receive raw ASGI message to seamlessly handle text and binary frames
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                break

            if msg_type != "websocket.receive":
                continue

            # ---------------------------------------------------------------
            # 1. Text (JSON) Frames
            # ---------------------------------------------------------------
            if "text" in message and message["text"] is not None:
                raw_text = message["text"]
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.warning("Malformed JSON from %s: %.100s", client_str, raw_text)
                    continue

                event_type = data.get("type")

                # --- JOIN FLOW ---
                if event_type == "JOIN":
                    try:
                        join_req = JoinRequest(**data)
                    except Exception as exc:
                        logger.warning("Invalid JoinRequest schema: %s", exc)
                        continue

                    # Disconnect from previous room if switching
                    if current_room and current_participant:
                        await current_room.disconnect(current_participant.id)

                    room = await session_manager.get_or_create_room(join_req.session_id)
                    participant, history = await room.join(
                        participant_name=join_req.participant_name,
                        connection=conn,
                        requested_pid=data.get("participant_id"),
                    )
                    current_room = room
                    current_participant = participant

                    ack = JoinAck(
                        participant_id=participant.id,
                        history=history,
                    )
                    logger.info(
                        "JOIN_ACK -> session=%s, participant=%s (%s), history_len=%d",
                        room.session_id,
                        participant.name,
                        participant.id,
                        len(history),
                    )
                    await conn.send_json(ack)

                # --- TIME SYNC (NTP-like) ---
                elif event_type == "SYNC":
                    server_rx_ts = int(time.time() * 1000)
                    try:
                        sync_req = TimeSyncRequest(**data)
                        client_tx_ts = sync_req.client_tx_ts
                    except Exception:
                        client_tx_ts = data.get("client_tx_ts", 0)

                    server_tx_ts = int(time.time() * 1000)
                    sync_resp = TimeSyncResponse(
                        client_tx_ts=client_tx_ts,
                        server_rx_ts=server_rx_ts,
                        server_tx_ts=server_tx_ts,
                    )
                    await conn.send_json(sync_resp)

                # --- CAPTION EVENT (e.g. from ASR or test harness) ---
                elif event_type == "CAPTION":
                    try:
                        caption = CaptionEvent(**data)
                        if current_room:
                            await current_room.add_caption(caption, broadcast=True)
                            logger.info(
                                "CAPTION in room %s: [%s] %s",
                                current_room.session_id,
                                caption.speaker_name,
                                caption.text,
                            )
                    except Exception as exc:
                        logger.warning("Invalid CaptionEvent: %s", exc)

                else:
                    logger.warning("Unknown JSON message type: %s", event_type)

            # ---------------------------------------------------------------
            # 2. Binary Audio Frames
            # ---------------------------------------------------------------
            elif "bytes" in message and message["bytes"] is not None:
                raw_bytes = message["bytes"]

                # Malformed frame checks
                if len(raw_bytes) < AUDIO_HEADER_SIZE:
                    logger.warning(
                        "Binary frame too short (%d bytes < %d), ignoring",
                        len(raw_bytes),
                        AUDIO_HEADER_SIZE,
                    )
                    continue

                if raw_bytes[0:2] != AUDIO_MAGIC:
                    logger.warning(
                        "Bad magic bytes %r, expected %r",
                        raw_bytes[0:2],
                        AUDIO_MAGIC,
                    )
                    continue

                try:
                    header = AudioFrameHeader.from_bytes(raw_bytes[:AUDIO_HEADER_SIZE])
                except (ValueError, struct.error) as exc:
                    logger.warning("Failed to parse audio header: %s", exc)
                    continue

                # Pass 1 Audio Routing: print header (Participant ID, SeqNum)
                print(
                    f"Audio frame received - Participant ID Hash: {header.participant_id_hash}, SeqNum: {header.seq_num}"
                )
                logger.debug(
                    "Audio frame: pid_hash=%d, seq_num=%d, capture_ts=%d, payload_bytes=%d",
                    header.participant_id_hash,
                    header.seq_num,
                    header.capture_ts,
                    len(raw_bytes) - AUDIO_HEADER_SIZE,
                )

                # Multi-Device DSP Selection (ws3_dsp)
                participant_map = {}
                if current_room:
                    for p in current_room.participants.values():
                        h = int(hashlib.sha256(p.name.encode()).hexdigest(), 16) % 65536
                        participant_map[h] = p.id
                    participant_map[header.participant_id_hash] = current_participant.id

                # Route frame through DSP loudness selection
                selected = get_best_frame([raw_bytes], participant_map=participant_map)
                speaker_id = selected.speaker_id if selected.speaker_id != "unknown" else current_participant.id
                speaker_name = current_participant.name
                if current_room and speaker_id in current_room.participants:
                    speaker_name = current_room.participants[speaker_id].name

                # ASR Processing: Cloud ASR if configured, or Mock fallback
                asr_engine = os.environ.get("ASR_ENGINE", "mock").lower()
                enable_mock_asr = os.environ.get("ENABLE_MOCK_ASR", "true").lower() in ("true", "1")
                if current_room and current_participant:
                    if asr_engine in ("groq", "assemblyai") and asr_client.api_key:
                        try:
                            events = await asr_client.transcribe_chunk(
                                raw_bytes,
                                speaker_id=speaker_id,
                                speaker_name=speaker_name,
                                start_ts=header.capture_ts,
                            )
                            for ev in events:
                                await current_room.add_caption(ev, broadcast=True)
                        except Exception as exc:
                            logger.warning("Cloud ASR transcription failed: %s, falling back to mock", exc)
                            caption = _generate_mock_caption(speaker_id, speaker_name)
                            await current_room.add_caption(caption, broadcast=True)
                    elif enable_mock_asr:
                        caption = _generate_mock_caption(speaker_id, speaker_name)
                        await current_room.add_caption(caption, broadcast=True)

    except WebSocketDisconnect:
        logger.info("Client %s disconnected cleanly", client_str)
    except Exception:
        logger.exception("Error handling WebSocket connection for %s", client_str)
    finally:
        if current_room and current_participant:
            await current_room.disconnect(current_participant.id)
            logger.info(
                "Participant %s (%s) disconnected from room %s",
                current_participant.name,
                current_participant.id,
                current_room.session_id,
            )


@app.websocket("/ws")
async def websocket_ws(websocket: WebSocket):
    """Standard WebSocket endpoint at /ws."""
    await _handle_websocket_connection(websocket)


@app.websocket("/")
async def websocket_root(websocket: WebSocket):
    """WebSocket endpoint at root / for compatibility with generic clients."""
    await _handle_websocket_connection(websocket)


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI application with Uvicorn."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roundtable Backend Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Bind port",
    )
    args = parser.parse_args()
    run(host=args.host, port=args.port)
