# Roundtable WebSocket Backend (`ws1_backend`) — Integration Guide

## 1. Overview
`ws1_backend` provides the FastAPI WebSocket server for the Roundtable live captioning system. It manages:
- **Routing & Rooms:** Multi-tenant session state (`ROOMS`) with room isolation.
- **Participant State:** Connection tracking (`ACTIVE`, `DISCONNECTED`) with 60-second reconnect grace periods.
- **History Buffering:** In-memory timeline buffering of `CaptionEvent` objects, sent to late joiners in `JoinAck`.
- **Clock Synchronization:** NTP-like time sync (`SYNC` -> `SYNC_ACK`) injecting server RX and TX timestamps.
- **Audio Routing:** 16-byte binary audio frame header parsing (`AUDIO_MAGIC`, participant hash, sequence number, capture timestamp) and mock caption fan-out.
- **Concurrency Safety:** Per-connection `asyncio.Lock` serialization for WebSocket writes.

---

## 2. Environment & Prerequisites
- Python 3.10+
- Required packages:
  ```bash
  pip install fastapi uvicorn websockets pydantic pytest pytest-asyncio
  ```

---

## 3. Starting the Server

### Starting on Port 8000 (Default)
Run from the repository root:
```bash
uvicorn ws1_backend.main:app --host 0.0.0.0 --port 8000
```
Or directly using the Python entrypoint:
```bash
python ws1_backend/main.py --host 0.0.0.0 --port 8000
```

### Environment Variables
| Variable | Description | Default |
|---|---|---|
| `PORT` | Bind port for the server | `8000` |
| `ASR_ENGINE` | ASR engine selection (`mock`, `groq`, `assemblyai`) | `mock` |
| `ENABLE_MOCK_ASR` | Toggle scripted caption replies for audio frames (`true`/`false`) | `true` |

---

## 4. Endpoints & Protocol

### HTTP Endpoints
- `GET /health` — Health check endpoint returning service status and active room count:
  ```json
  { "status": "ok", "service": "ws1_backend", "active_rooms": 0 }
  ```

### WebSocket Endpoints
- `ws://localhost:8000/ws` (primary)
- `ws://localhost:8000/` (alias for compatibility)

### Protocol Messages (JSON)
1. **Join Request (Client -> Server):**
   ```json
   { "type": "JOIN", "session_id": "ROOM1", "participant_name": "Alice" }
   ```
   **Join Acknowledgment (Server -> Client):**
   ```json
   {
     "type": "JOIN_ACK",
     "participant_id": "p_a1b2c3d4",
     "history": [ ... ]
   }
   ```
2. **Time Sync (Client -> Server):**
   ```json
   { "type": "SYNC", "client_tx_ts": 1700000000123 }
   ```
   **Time Sync Response (Server -> Client):**
   ```json
   {
     "type": "SYNC_ACK",
     "client_tx_ts": 1700000000123,
     "server_rx_ts": 1700000000140,
     "server_tx_ts": 1700000000142
   }
   ```
3. **Caption Event (Server -> Client Broadcast):**
   ```json
   {
     "type": "CAPTION",
     "segment_id": "seg_1",
     "speaker_id": "p_a1b2c3d4",
     "speaker_name": "Alice",
     "start_ts": 1700000005000,
     "end_ts": 1700000007000,
     "text": "Hello world",
     "is_final": false,
     "revision": 1
   }
   ```

### Binary Audio Frames
- **16-byte Header:**
  - `[0:1]`: Magic bytes `0xAA 0xBB`
  - `[2:3]`: Participant ID Hash (UInt16 big-endian)
  - `[4:7]`: Sequence Number (UInt32 big-endian)
  - `[8:15]`: Capture Timestamp (UInt64 big-endian, ms)
- **Payload:** Raw Float32 PCM samples (16kHz mono).
- The server validates magic bytes and header length, logs/prints the header, and routes/broadcasts captions.

---

## 5. Running Tests
Run the complete test suite:
```bash
pytest ws1_backend/tests/
```
Or with verbose output:
```bash
pytest ws1_backend/tests/ -v
```

### Test Coverage Summary
- `test_join.py`: Single join, multiple joins in same room, isolated rooms, duplicate name disambiguation.
- `test_disconnect.py`: Disconnect marks participant inactive, reconnect restores participant ID and state within grace period, grace period timeout cleans up inactive participants and empty rooms.
- `test_history.py`: Caption buffering, late joiner receives full history in `JoinAck`, live caption fan-out to all active clients in room.
- `test_sync.py`: NTP roundtrip time synchronization and sequential measurements.
- `test_audio.py`: Valid audio frame header parsing and printing, malformed frames (short payload, bad magic) handled gracefully without server crash.
- `test_concurrency.py`: Concurrent WebSocket writes handled safely using per-connection asyncio locks.

---

## 6. End-to-End Verification with Virtual Client
1. Start the backend:
   ```bash
   python ws1_backend/main.py --port 8000
   ```
2. In another terminal, run the virtual client:
   ```bash
   python ws4_eval/virtual_client.py --url ws://localhost:8000/ws --name VirtualAlice
   ```
3. Observe:
   - Client sends `JoinRequest`, receives `JoinAck` with assigned `participant_id`.
   - Client streams 30 audio frames (100ms each).
   - Backend prints `Audio frame received - Participant ID Hash: ..., SeqNum: ...`.
   - Backend fans out `CaptionEvent` responses back to the client.
