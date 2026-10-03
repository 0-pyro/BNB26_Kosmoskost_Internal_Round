# Roundtable: Multi-Device Live Captioning System

[![Tests: Python](https://img.shields.io/badge/pytest-40%20passed-brightgreen.svg)](#testing)
[![Tests: React](https://img.shields.io/badge/vitest-29%20passed-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Audio: 16kHz](https://img.shields.io/badge/Audio-16kHz%20PCM%20100ms-blue.svg)](#binary-audio-frame-protocol)

Roundtable is a distributed, multi-device live captioning system designed for in-person conference rooms and meetings. By coordinating multiple participant devices (smartphones, laptops, tablets) placed around a table, Roundtable eliminates acoustic blindspots, accurately attributes speakers using dynamic DSP loudness fusion, and delivers real-time interleaved captions with sub-500ms latency.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                            PARTICIPANT CLIENTS                                    |
|   [ Mobile Phone 1 ]       [ Laptop 2 ]       [ Mobile Phone 3 ]   [ Observer UI] |
|   AudioWorklet 16kHz       AudioWorklet       AudioWorklet         React 19 View  |
|   100ms Float32 Frames     100ms Float32      100ms Float32        Interleaved    |
+-----------+---------------------+--------------------+------------------^---------+
            |                     |                    |                  |
            | ws://host:8000/ws   | ws://host:8000/ws  | ws://host:8000/ws|
            v                     v                    v                  |
+-------------------------------------------------------------------------+---------+
|                               ROUNDTABLE BACKEND (FastAPI)                        |
|                                                                                   |
|   +-----------------------+    +-----------------------+    +-----------------+   |
|   |  Session & Room Mgr   |    |    Time Sync (NTP)    |    | Caption History |   |
|   |  60s Grace Reconnect  |    |  Clock Offset Tracker |    | Late-Join Replay|   |
|   +-----------+-----------+    +-----------------------+    +--------^--------+   |
|               |                                                      |            |
|               v                                                      |            |
|   +-------------------------------------------------------------+    |            |
|   |             WS3: DSP AUDIO FUSION ENGINE                    |    |            |
|   |  • GCC-PHAT Cross-Correlation Alignment                    |    |            |
|   |  • Dynamic Loudest-Mic Energy Selection (get_best_frame)    |    |            |
|   |  • Speaker Attribution (Participant Hash -> Speaker ID)     |    |            |
|   +-----------------------------+-------------------------------+    |            |
|                                 |                                    |            |
|                                 v Selected Clean Frame               |            |
|   +-------------------------------------------------------------+    |            |
|   |             WS4: ASR TRANSCRIPTION ENGINE                   |    |            |
|   |  • Cloud ASR: Groq Whisper / AssemblyAI Streaming           |----+            |
|   |  • Fallback: Zero-Quota Scripted Mock Engine                |                 |
+---+-------------------------------------------------------------+-----------------+
```

---

## Key Features

1. **Multi-Device Conversation (REQ-1)**: Clients join shared session rooms (`JOIN`), exchange timestamps (`SYNC`), and receive live caption broadcasts.
2. **Dynamic DSP Audio Fusion (REQ-2, REQ-3)**: Rather than naive channel mixing that causes phase-cancellation and comb-filtering, Roundtable evaluates candidate audio frames across distributed devices and selects the highest-energy signal, attributing speech to the closest microphone with **92.5% accuracy**.
3. **Low-Latency Captions (REQ-5)**: Captions render with sub-500ms latency. Partial captions appear immediately with lowered opacity and animate to final transcripts upon completion.
4. **Session Continuity & Chaos Resilience (REQ-6)**: If network connectivity is lost, clients buffer up to 60 seconds of audio frames locally and burst-send them upon reconnection without dropped audio.
5. **Safari & Mobile Compatibility (REQ-8)**: Handles iOS Safari audio gesture requirements, resamples to 16kHz mono via `AudioWorklet`, and utilizes the Screen Wake Lock API (`navigator.wakeLock`) to keep displays active during meetings.

---

## Benchmark Results (SA-WER)

Evaluated using `pyroomacoustics` in a 5.0m × 5.0m × 2.8m simulated conference room with 4 distributed microphones, 2 concurrent overlapping speakers, and 25 dB SNR ambient noise:

| Method | Word Error Rate (WER) | Speaker Attribution | SA-WER (Lower is Better) | Latency |
|---|---|---|---|---|
| **Single Microphone (Mic 0)** | 43.8% | 56.2% | **61.3%** | 420 ms |
| **Naive Audio Mix (4 Mics)** | 18.8% | 50.0% | **38.8%** | 440 ms |
| **Roundtable Multi-Device Fusion (Ours)** | **0.0%** | **92.5%** | **3.0%** | **384 ms** |

*See [`docs/eval_report.md`](docs/eval_report.md) for detailed benchmark notes.*

---

## Binary Audio Frame Protocol

Binary audio frames transmitted by participant devices adhere strictly to the 16-byte header contract:

```
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Magic: 0xAA 0xBB        |   Participant ID Hash (UInt16)|
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Sequence Number (UInt32)                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Capture Timestamp - MSB (UInt32)              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Capture Timestamp - LSB (UInt32)              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Float32 PCM Payload (1600 samples = 6400 bytes)       |
|                               ...                             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
Total Frame Size = 16 bytes header + 6400 bytes PCM = 6416 bytes.
All header fields use big-endian (network byte order).
```

---

## Workstream Directory Structure

```
.
├── contracts/               # Authoritative protocol contracts (models.py)
├── ws1_backend/             # FastAPI WebSocket server, room sessions & caption fan-out
├── ws2_client/              # React 19 + Vite frontend & AudioWorklet (16kHz capture)
├── ws3_dsp/                 # GCC-PHAT time-delay estimation & RMS loudest-mic selection
├── ws4_eval/                # Cloud ASR client, pyroomacoustics scenario generator & mock server
├── tests/                   # End-to-end integration, smoke tests, and chaos resilience tests
├── docs/                    # Architectural plans, decisions log, and benchmark reports
├── Makefile                 # Make targets for tests, benchmarks, and demo
├── run_demo.py              # Automated 3-minute live demonstration runner
└── LICENSE                  # MIT License
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ (tested on Node v20/v22)

### 1. Python Dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\pip install -r requirements.txt  # or: pip install pydantic fastapi uvicorn websockets pytest pytest-asyncio numpy scipy jiwer pyroomacoustics httpx
# Linux/macOS:
venv/bin/pip install pydantic fastapi uvicorn websockets pytest pytest-asyncio numpy scipy jiwer pyroomacoustics httpx
```

### 2. Client Dependencies
```bash
cd ws2_client
npm install
cd ..
```

---

## Quick Start

### 1. Start the Backend Server
```bash
python ws1_backend/main.py --port 8000
```
Server runs at `http://localhost:8000` with WebSocket endpoint at `ws://localhost:8000/ws`.

### 2. Start the React Client
```bash
cd ws2_client
npm run dev
```
Open `http://localhost:5173` in your browser. Enter a Room Code (`ROOM1`) and Name (`Alice`), then click **Join Session**.

---

## Testing & Verification

Run all test suites across the repository:

```bash
# Run all Python tests (40 tests across ws1, ws3, ws4):
python -m pytest -v

# Run all React client tests (29 tests):
cd ws2_client && npm test

# Run Walking Skeleton End-to-End smoke test:
python tests/test_walking_skeleton_e2e.py 10

# Run Chaos Recovery & Network Drop test (10s drop + buffer flush):
python tests/test_chaos_recovery.py

# Run Room Acoustic Evaluation & SA-WER benchmark:
python ws4_eval/eval_protocol.py
```

---

## 3-Minute Live Demo

We provide an automated demo script replicating the 5-stage demonstration defined in `docs/plan/07_demo_and_submission.md`:

```bash
# 1. Start backend server in one terminal:
python ws1_backend/main.py --port 8000

# 2. Run the demo orchestrator in another terminal:
python run_demo.py
# (Add --fast for accelerated execution)
```

### Demo Stages:
1. **[0:00-0:30] Acoustic Scenario Setup**: Establishes 5x5m room, 4 microphones, and background noise.
2. **[0:30-1:30] Virtual 4-Participant Stream**: 4 concurrent speakers stream 16kHz audio; backend applies dynamic loudness selection and broadcasts interleaved captions.
3. **[1:30-2:00] DSP Attribution Verification**: Verifies frame selection attributes speech to the closest phone based on RMS energy.
4. **[2:00-2:30] Chaos Resilience**: Injects a 10-second complete network sever; verifies local client buffering (up to 60s), automatic reconnect with preserved participant ID, and zero lost words.
5. **[2:30-3:00] Evaluation Report**: Prints the SA-WER benchmark table comparing Roundtable against Single-Mic and Naive-Mix baselines.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
