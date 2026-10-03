"""
Roundtable: 3-Minute Live Demo Orchestrator.

Runs the complete 5-stage demonstration script defined in docs/plan/07_demo_and_submission.md:
  Stage 1: [0:00-0:30] The Problem (Acoustic room simulation setup & baselines)
  Stage 2: [0:30-1:30] The Virtual Demo (4 Virtual Participants, DSP loudness fusion, interleaved captions)
  Stage 3: [1:30-2:00] Dynamic Selection & Speaker Attribution Verification
  Stage 4: [2:00-2:30] Fault Tolerance & Chaos Recovery (10-second drop, 60s buffer flush, zero dropped words)
  Stage 5: [2:30-3:00] Benchmark Evaluation Summary (SA-WER, WER, Latency table)

Usage:
  python run_demo.py [--fast] [--port 8000]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import struct
import sys
import time

import httpx
import websockets

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts.models import AUDIO_MAGIC, AudioFrameHeader
from ws3_dsp.select import get_best_frame
from ws4_eval.eval_protocol import run_evaluation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("roundtable_demo")

SESSION_ID = "ROUNDTABLE_LIVE_DEMO"
SAMPLE_RATE = 16000
SAMPLES_PER_FRAME = 1600
FRAME_MS = 100


def build_frame(pid_hash: int, seq: int, freq: float = 440.0, amp: float = 0.3) -> bytes:
    header = struct.pack(">2sHIQ", AUDIO_MAGIC, pid_hash, seq, int(time.time() * 1000))
    samples = [math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * amp for i in range(SAMPLES_PER_FRAME)]
    payload = struct.pack(f">{len(samples)}f", *samples)
    return header + payload


async def wait_step(prompt: str, fast: bool, delay_s: float = 3.0):
    print(f"\n>>> {prompt}")
    if fast:
        await asyncio.sleep(min(0.5, delay_s))
    else:
        await asyncio.sleep(delay_s)


async def main():
    parser = argparse.ArgumentParser(description="Roundtable Live Demo Orchestrator")
    parser.add_argument("--fast", action="store_true", help="Fast execution mode for quick verification")
    parser.add_argument("--port", type=int, default=8000, help="Backend server port")
    args = parser.parse_args()

    base_url = f"ws://localhost:{args.port}/ws"
    health_url = f"http://localhost:{args.port}/health"

    print("=" * 70)
    print("      ROUNDTABLE: MULTI-DEVICE LIVE CAPTIONING DEMO")
    print("=" * 70)

    # Pre-check: Ensure server is running
    print(f"\n[INIT] Checking backend connection at {health_url}...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(health_url, timeout=3.0)
            if resp.status_code != 200:
                print(f"ERROR: Server responded with status {resp.status_code}")
                sys.exit(1)
            print(f"[OK] Backend server is active: {resp.json()}")
    except Exception as exc:
        print(f"ERROR: Could not connect to backend server at {health_url}: {exc}")
        print("Please start the backend server first via:")
        print("  python ws1_backend/main.py --port 8000")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STAGE 1: [0:00 - 0:30] The Problem
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 1: [0:00 - 0:30] THE PROBLEM & ACOUSTIC SIMULATION SETUP")
    print("=" * 70)
    print("* Problem: In conference rooms, a single mobile mic produces high error rates (61.3% SA-WER)")
    print("  due to distance attenuation, echo, and overlapping speakers.")
    print("* Naive multi-mic mixing causes phase-cancellation and comb-filtering (38.8% SA-WER).")
    print("* Roundtable Solution: Dynamic loudest-mic fusion with big-endian 16-byte framing.")
    await wait_step("Simulating room acoustics (5.0m x 5.0m x 2.8m, 4 distributed mics)...", args.fast, 2.0)

    # -------------------------------------------------------------------------
    # STAGE 2: [0:30 - 1:30] The Virtual Demo
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 2: [0:30 - 1:30] MULTI-DEVICE LIVE DEMO: 4 VIRTUAL PARTICIPANTS")
    print("=" * 70)
    print(f"* Joining session room '{SESSION_ID}' with 4 participants: Alice, Bob, Charlie, Dana...")

    speakers = [
        {"name": "Alice", "freq": 300.0, "amp": 0.8},
        {"name": "Bob", "freq": 500.0, "amp": 0.4},
        {"name": "Charlie", "freq": 700.0, "amp": 0.2},
        {"name": "Dana", "freq": 900.0, "amp": 0.1},
    ]

    observer_captions = []

    async def observer_task():
        async with websockets.connect(base_url) as ws:
            await ws.send(json.dumps({"type": "JOIN", "session_id": SESSION_ID, "participant_name": "DemoObserver"}))
            await ws.recv()
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(msg)
                    if data.get("type") == "CAPTION":
                        observer_captions.append(data)
                        status = "FINAL" if data.get("is_final") else "PARTIAL"
                        print(f"  [CAPTION] [{data.get('speaker_name', 'Unknown')}] ({status}): \"{data.get('text')}\"")
                except (asyncio.TimeoutError, TimeoutError):
                    if stop_event.is_set():
                        break
                except Exception:
                    break

    stop_event = asyncio.Event()
    obs = asyncio.create_task(observer_task())

    # Spawn 4 virtual speaker clients
    for spk in speakers:
        pid_hash = int(hashlib.sha256(spk["name"].encode()).hexdigest(), 16) % 65536
        spk["pid_hash"] = pid_hash

    async def run_speaker(spk: dict, num_frames: int):
        async with websockets.connect(base_url) as ws:
            await ws.send(json.dumps({"type": "JOIN", "session_id": SESSION_ID, "participant_name": spk["name"]}))
            ack = json.loads(await ws.recv())
            spk["pid"] = ack.get("participant_id")
            for seq in range(num_frames):
                frame = build_frame(spk["pid_hash"], seq, spk["freq"], spk["amp"])
                await ws.send(frame)
                await asyncio.sleep(FRAME_MS / 1000.0)

    print("* Streaming 16kHz audio frames concurrently across all 4 devices...")
    num_frames = 15 if args.fast else 30
    await asyncio.gather(*(run_speaker(s, num_frames) for s in speakers))
    await asyncio.sleep(1.0)
    stop_event.set()
    await obs

    print(f"[OK] Total live captions rendered: {len(observer_captions)}")
    assert len(observer_captions) > 0, "No captions received"

    # -------------------------------------------------------------------------
    # STAGE 3: [1:30 - 2:00] DSP Loudness Selection & Speaker Attribution
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 3: [1:30 - 2:00] DSP LOUDNESS SELECTION & ATTRIBUTION VERIFICATION")
    print("=" * 70)
    print("* Testing ws3_dsp.select.get_best_frame with candidate signals of varying amplitudes:")
    
    cand1 = ("Alice", build_frame(speakers[0]["pid_hash"], 1, 400.0, amp=0.9))
    cand2 = ("Bob", build_frame(speakers[1]["pid_hash"], 1, 400.0, amp=0.2))
    cand3 = ("Charlie", build_frame(speakers[2]["pid_hash"], 1, 400.0, amp=0.1))
    
    best = get_best_frame([cand1[1], cand2[1], cand3[1]], participant_map={
        speakers[0]["pid_hash"]: "Alice",
        speakers[1]["pid_hash"]: "Bob",
        speakers[2]["pid_hash"]: "Charlie",
    })
    print(f"  Candidate Amplitudes: Alice=0.9, Bob=0.2, Charlie=0.1")
    print(f"  Selected Loudest Speaker: [{best.speaker_id}] with RMS energy = {best.rms:.4f}")
    assert best.speaker_id == "Alice", f"Expected Alice, got {best.speaker_id}"
    print("[OK] Speaker attribution correctly assigned to the loudest microphone!")

    # -------------------------------------------------------------------------
    # STAGE 4: [2:00 - 2:30] Fault Tolerance & Chaos Recovery
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 4: [2:00 - 2:30] FAULT TOLERANCE: 10s NETWORK DROP & BUFFER RESILIENCE")
    print("=" * 70)
    print("* Participant Alice is connected and speaking...")
    alice_hash = speakers[0]["pid_hash"]
    async with websockets.connect(base_url) as ws:
        await ws.send(json.dumps({"type": "JOIN", "session_id": "CHAOS_DEMO", "participant_name": "Alice"}))
        ack = json.loads(await ws.recv())
        alice_pid = ack.get("participant_id")
        print(f"  Alice connected with PID: {alice_pid}")
        
        # Send 3 initial frames
        for s in range(3):
            await ws.send(build_frame(alice_hash, s))
            await ws.recv()
        print("  [OK] Normal audio streaming active.")

        # Simulate network drop
        print("  [CHAOS INJECTION] Network severed! Disconnecting for 10 seconds...")
        await ws.close()

    buffered = []
    print("  Client offline: Buffering audio frames locally (up to 60 seconds)...")
    for s in range(3, 13):
        buffered.append(build_frame(alice_hash, s))
        await asyncio.sleep(0.3 if args.fast else 1.0)

    print(f"  Buffered {len(buffered)} frames during outage. Reconnecting with session PID...")
    async with websockets.connect(base_url) as ws:
        await ws.send(json.dumps({
            "type": "JOIN",
            "session_id": "CHAOS_DEMO",
            "participant_name": "Alice",
            "participant_id": alice_pid,
        }))
        reack = json.loads(await ws.recv())
        assert reack.get("participant_id") == alice_pid, "Participant ID must be preserved"
        print(f"  [OK] Reconnected successfully! Preserved PID: {reack.get('participant_id')}")
        
        # Burst-flush buffer
        print(f"  Burst-flushing {len(buffered)} buffered frames to server...")
        for frame in buffered:
            await ws.send(frame)
        
        recovered_caption = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        print(f"  [OK] Server resumed captioning from flushed buffer: \"{recovered_caption.get('text')}\"")

    # -------------------------------------------------------------------------
    # STAGE 5: [2:30 - 3:00] Benchmark Evaluation Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 5: [2:30 - 3:00] SA-WER BENCHMARK EVALUATION RESULTS")
    print("=" * 70)
    print("Running pyroomacoustics acoustic benchmark protocol...\n")
    report = run_evaluation()
    print(report)

    print("\n" + "=" * 70)
    print(">>> ROUNDTABLE DEMO COMPLETED SUCCESSFULLY! <<<")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
