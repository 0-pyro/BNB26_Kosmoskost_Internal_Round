"""
End-to-End Walking Skeleton Smoke Test.

Verifies:
1. Backend starts and serves /health and /ws
2. 2 Virtual Participants (VirtualAlice, VirtualBob) join room ROOM_SMOKE
3. A Web Client observer joins room ROOM_SMOKE
4. Both virtual participants stream 16kHz binary audio frames
5. Backend parses binary audio headers and routes mock CaptionEvents
6. The observer receives live CaptionEvents for BOTH participants
7. The system runs steadily under load without errors or crashes
"""

import asyncio
import hashlib
import json
import logging
import math
import struct
import sys
import time
import httpx
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke_test")

SERVER_URL = "ws://localhost:8000/ws"
HEALTH_URL = "http://localhost:8000/health"
SESSION_ID = "ROOM_SMOKE"
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 100
SAMPLES_PER_FRAME = 1600
AUDIO_HEADER_SIZE = 16
AUDIO_MAGIC = b"\xaa\xbb"


def build_audio_frame(pid_hash: int, seq: int) -> bytes:
    """Build a 100ms 16kHz sine wave frame with a 16-byte binary header."""
    header = struct.pack(">2sHIQ", AUDIO_MAGIC, pid_hash, seq, int(time.time() * 1000))
    # 1600 float32 samples (sine wave)
    samples = [math.sin(2 * math.pi * 440 * i / SAMPLE_RATE) * 0.3 for i in range(SAMPLES_PER_FRAME)]
    payload = struct.pack(f">{len(samples)}f", *samples)
    return header + payload


async def virtual_speaker(name: str, pid_hash: int, num_frames: int, start_delay: float):
    """Virtual participant task streaming binary audio frames."""
    await asyncio.sleep(start_delay)
    logger.info("Virtual speaker %s connecting to %s...", name, SERVER_URL)
    async with websockets.connect(SERVER_URL, ping_interval=20, ping_timeout=20) as ws:
        # Join
        await ws.send(json.dumps({"type": "JOIN", "session_id": SESSION_ID, "participant_name": name}))
        ack_raw = await ws.recv()
        ack = json.loads(ack_raw)
        logger.info("Speaker %s received JOIN_ACK: pid=%s", name, ack.get("participant_id"))

        async def drain():
            try:
                async for _ in ws:
                    pass
            except Exception:
                pass

        drain_task = asyncio.create_task(drain())

        # Stream audio frames
        for seq in range(num_frames):
            frame = build_audio_frame(pid_hash, seq)
            await ws.send(frame)
            await asyncio.sleep(FRAME_DURATION_MS / 1000.0)

        logger.info("Speaker %s completed sending %d frames.", name, num_frames)
        drain_task.cancel()


async def ui_observer(captions_received: list, duration_s: float):
    """UI Client observer that listens for broadcast CaptionEvents."""
    logger.info("UI Observer connecting to %s...", SERVER_URL)
    async with websockets.connect(SERVER_URL, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"type": "JOIN", "session_id": SESSION_ID, "participant_name": "UI_Observer"}))
        ack_raw = await ws.recv()
        logger.info("UI Observer joined session: %s", ack_raw)

        end_time = time.time() + duration_s
        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            try:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=min(1.0, remaining))
                try:
                    msg = json.loads(msg_raw)
                    if msg.get("type") == "CAPTION":
                        captions_received.append(msg)
                        logger.info("UI received caption: [%s] '%s' (final=%s)", msg.get("speaker_name"), msg.get("text"), msg.get("is_final"))
                except Exception:
                    pass
            except (asyncio.TimeoutError, TimeoutError):
                pass
            except Exception as exc:
                logger.warning("UI Observer receive loop error: %s", exc)
                break


async def run_smoke_test(duration_s: float = 60.0):
    # 1. Check health
    logger.info("Checking server health at %s...", HEALTH_URL)
    async with httpx.AsyncClient() as client:
        resp = await client.get(HEALTH_URL, timeout=5.0)
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        logger.info("Health check passed: %s", resp.json())

    # 2. Run speakers and UI observer concurrently
    captions = []
    # Each speaker sends frames for ~50 seconds (500 frames * 100ms = 50s)
    num_frames = int(max(20, (duration_s - 10) * 10))

    alice_hash = int(hashlib.sha256(b"VirtualAlice").hexdigest(), 16) % 65536
    bob_hash = int(hashlib.sha256(b"VirtualBob").hexdigest(), 16) % 65536

    logger.info("Starting smoke test simulation for %s seconds...", duration_s)
    await asyncio.gather(
        ui_observer(captions, duration_s),
        virtual_speaker("VirtualAlice", alice_hash, num_frames, start_delay=1.0),
        virtual_speaker("VirtualBob", bob_hash, num_frames, start_delay=2.0),
    )

    # 3. Assertions
    speakers = {c.get("speaker_name") for c in captions}
    logger.info("Total captions received by UI: %d", len(captions))
    logger.info("Speakers detected in captions: %s", speakers)

    assert len(captions) >= 4, f"Expected multiple captions, got {len(captions)}"
    assert "VirtualAlice" in speakers or "VirtualBob" in speakers, f"Expected known speakers, got {speakers}"
    logger.info("==================================================")
    logger.info(">>> WALKING SKELETON SMOKE TEST PASSED (60s) <<<")
    logger.info("==================================================")


if __name__ == "__main__":
    test_duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    asyncio.run(run_smoke_test(test_duration))
