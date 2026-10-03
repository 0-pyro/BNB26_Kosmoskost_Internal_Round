"""
Virtual Participant Client for Roundtable.

Reads a WAV file (or generates synthetic audio), chunks it into 100ms
binary frames with the 16-byte header defined in the contracts, and
sends them to the mock server via WebSocket.

Usage:
    python ws4_eval/virtual_client.py [--wav FILE] [--url URL] [--name NAME]

If no --wav is supplied, generates 3 seconds of 440 Hz sine tone.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import math
import os
import struct
import sys
import time
import wave

import websockets

# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts.models import (
    AUDIO_HEADER_SIZE,
    AudioFrameHeader,
    JoinRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("virtual_client")

# Audio constants matching the contract
SAMPLE_RATE = 16000  # 16 kHz
FRAME_DURATION_MS = 100  # 100 ms per frame
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 1600 samples
BYTES_PER_SAMPLE = 4  # Float32


def participant_id_hash(name: str) -> int:
    """Compute a UInt16 hash from a participant name."""
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) % 65536


def generate_sine_samples(
    duration_s: float = 3.0, freq: float = 440.0
) -> list[float]:
    """Generate Float32 sine wave samples at 16 kHz."""
    n_samples = int(SAMPLE_RATE * duration_s)
    return [
        math.sin(2 * math.pi * freq * i / SAMPLE_RATE)
        for i in range(n_samples)
    ]


def read_wav_as_float32(path: str) -> list[float]:
    """Read a WAV file and return Float32 samples (mono, 16 kHz expected).

    If the WAV is 16-bit PCM, normalizes to [-1.0, 1.0].
    """
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 2:
        # 16-bit signed PCM
        samples = struct.unpack(f"<{n_frames * n_channels}h", raw)
        float_samples = [s / 32768.0 for s in samples]
    elif sampwidth == 4:
        # 32-bit float (unlikely but handle it)
        float_samples = list(
            struct.unpack(f"<{n_frames * n_channels}f", raw)
        )
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # If stereo, take left channel only
    if n_channels > 1:
        float_samples = float_samples[::n_channels]

    return float_samples


def chunk_samples(samples: list[float]) -> list[bytes]:
    """Split Float32 samples into 100ms frame payloads."""
    frames = []
    for i in range(0, len(samples), SAMPLES_PER_FRAME):
        chunk = samples[i : i + SAMPLES_PER_FRAME]
        # Pad last frame if needed
        if len(chunk) < SAMPLES_PER_FRAME:
            chunk.extend([0.0] * (SAMPLES_PER_FRAME - len(chunk)))
        frames.append(struct.pack(f">{len(chunk)}f", *chunk))
    return frames


async def run_client(
    url: str, name: str, wav_path: str | None = None
) -> None:
    """Connect to the server, send JOIN, then stream audio frames."""
    pid_hash = participant_id_hash(name)

    # Load or generate audio
    if wav_path and os.path.exists(wav_path):
        logger.info("Reading WAV: %s", wav_path)
        samples = read_wav_as_float32(wav_path)
    else:
        if wav_path:
            logger.warning("WAV file not found: %s — generating sine tone", wav_path)
        else:
            logger.info("No WAV file specified — generating 3s sine tone")
        samples = generate_sine_samples(3.0)

    payloads = chunk_samples(samples)
    logger.info(
        "Prepared %d frames (%d samples total)", len(payloads), len(samples)
    )

    async with websockets.connect(url) as ws:
        # Send JOIN
        join_msg = JoinRequest(session_id="ROOM1", participant_name=name)
        await ws.send(join_msg.model_dump_json())
        ack = await ws.recv()
        logger.info("JOIN_ACK: %s", ack)

        # Stream audio frames
        for seq, payload in enumerate(payloads):
            header = AudioFrameHeader(
                participant_id_hash=pid_hash,
                seq_num=seq,
                capture_ts=int(time.time() * 1000),
            )
            frame = header.to_bytes() + payload
            await ws.send(frame)
            logger.debug("Sent frame seq=%d (%d bytes)", seq, len(frame))

            # Try to receive any caption events (non-blocking)
            try:
                while True:
                    resp = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    logger.info("Caption: %s", resp)
            except (asyncio.TimeoutError, TimeoutError):
                pass

            # Pace to ~real-time
            await asyncio.sleep(FRAME_DURATION_MS / 1000.0)

        # Drain remaining responses
        logger.info("All frames sent. Draining responses...")
        try:
            while True:
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                logger.info("Caption: %s", resp)
        except (asyncio.TimeoutError, TimeoutError):
            pass

    logger.info("Virtual client done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roundtable Virtual Client")
    parser.add_argument("--url", default="ws://localhost:8000")
    parser.add_argument("--name", default="VirtualAlice")
    parser.add_argument("--wav", default=None, help="Path to WAV file (16kHz mono)")
    args = parser.parse_args()
    asyncio.run(run_client(args.url, args.name, args.wav))
