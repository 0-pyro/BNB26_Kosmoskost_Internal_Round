# Integration Guide

## Prerequisites
- Python 3.10+
- Install dependencies:
  ```bash
  python -m venv venv
  # Windows:
  venv\Scripts\pip install pydantic fastapi websockets pytest pytest-asyncio
  # Linux/Mac:
  venv/bin/pip install pydantic fastapi websockets pytest pytest-asyncio
  ```

## Quick Start

### 1. Start the Mock Server
```bash
# Windows:
venv\Scripts\python ws4_eval/mock_server.py --port 8000

# Linux/Mac:
venv/bin/python ws4_eval/mock_server.py --port 8000
```
The mock server listens on `ws://0.0.0.0:8000` and:
- Responds to `JOIN` messages with `JOIN_ACK`
- Responds to `SYNC` messages with `SYNC_ACK`
- Responds to binary audio frames with scripted `CaptionEvent` JSON (after ~300ms simulated ASR delay)
- Handles malformed frames gracefully (logs warning, does not crash)

### 2. Run the Virtual Client
```bash
# With synthetic audio (3s sine tone):
venv\Scripts\python ws4_eval/virtual_client.py --url ws://localhost:8000 --name Alice

# With a WAV file:
venv\Scripts\python ws4_eval/virtual_client.py --url ws://localhost:8000 --name Alice --wav path/to/audio.wav
```
The virtual client:
- Sends a `JOIN` request and waits for `JOIN_ACK`
- Chunks audio into 100ms frames with 16-byte binary headers (per contract)
- Streams frames at ~real-time pace
- Prints received `CaptionEvent` messages

### 3. Run the Fault-Injection Proxy
```bash
# Add 200ms latency:
venv\Scripts\python ws4_eval/proxy.py --listen-port 8001 --target-port 8000 --latency-ms 200

# 10% message drop rate:
venv\Scripts\python ws4_eval/proxy.py --listen-port 8001 --target-port 8000 --drop-rate 0.1
```
Then point clients at `ws://localhost:8001` instead of `8000`.

The proxy:
- Forwards all WebSocket messages bidirectionally
- Injects configurable latency per message
- Drops messages with configurable probability, cleanly closing both ends

### 4. Run Tests
```bash
venv\Scripts\python -m pytest ws4_eval/tests/ -v
```

## Using Contracts in Other Workstreams

```python
# From any workstream directory, ensure project root is on sys.path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts.models import (
    JoinRequest, JoinAck,
    TimeSyncRequest, TimeSyncResponse,
    CaptionEvent,
    AudioFrameHeader, AUDIO_HEADER_SIZE, AUDIO_MAGIC,
    Session, Participant, ConnectionState,
    parse_message,
)
```

## Architecture

```
Client (virtual_client.py)
    |
    | ws://localhost:8001  (optional proxy)
    v
Fault Proxy (proxy.py) ---> Mock Server (mock_server.py)
    ws://localhost:8001        ws://localhost:8000
```

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Mock server listen port |
| `ASR_ENGINE` | `mock` | ASR engine selector (only `mock` implemented) |
