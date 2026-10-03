# Contracts & Interfaces (v1.0)

## 1. Protocol Messages (WebSocket JSON)
**Direction: Client -> Server**
*   `JoinRequest`: `{ "type": "JOIN", "session_id": "ROOM1", "participant_name": "Alice" }`
*   `TimeSyncRequest`: `{ "type": "SYNC", "client_tx_ts": 1700000000123 }`

**Direction: Server -> Client**
*   `JoinAck`: `{ "type": "JOIN_ACK", "participant_id": "p_123", "history": [...] }`
*   `TimeSyncResponse`: `{ "type": "SYNC_ACK", "client_tx_ts": 1700000000123, "server_rx_ts": 1700000000140, "server_tx_ts": 1700000000142 }`
*   `CaptionEvent`: 
    ```json
    {
      "type": "CAPTION",
      "segment_id": "seg_88",
      "speaker_id": "p_123",
      "speaker_name": "Alice",
      "start_ts": 1700000005000,
      "end_ts": 1700000007000,
      "text": "Hello world",
      "is_final": false,
      "revision": 1
    }
    ```

## 2. Binary Audio Frame Layout (Client -> Server WebSocket)
Sent as binary messages to avoid base64 overhead.
*   **Header (16 bytes):**
    *   `[0:1]` Magic bytes `0xAA 0xBB`
    *   `[2:3]` Participant ID Hash (UInt16)
    *   `[4:7]` Sequence Number (UInt32)
    *   `[8:15]` Client Capture Timestamp in ms (UInt64)
*   **Payload:** Raw Float32 PCM samples, 16kHz Mono. (e.g., 1600 samples for 100ms = 6400 bytes).

## 3. Session & Participant Model
*   `Session`: Contains active `participants`, a `timeline` of caption segments, and a `start_time`.
*   `Participant`: Has `id`, `name`, `connection_state` (ACTIVE, DISCONNECTED), `clock_offset_ms`.

## 4. Environment Variables
*   `PORT`: Server port (default 8000).
*   `ASR_ENGINE`: `mock` | `groq` | `assemblyai`.
*   `GROQ_API_KEY`: Required if ASR_ENGINE=groq.

## 5. Repo Layout
```
/contracts          (Generated schemas/models, owned by Lead)
/ws1_backend        (Session/WebSocket, owned by WS1)
/ws2_client         (React App, owned by WS2)
/ws3_dsp            (Alignment & Selection, owned by WS3)
/ws4_eval           (Mock ASR, Virtual Client, pyroomacoustics, owned by WS4)
Makefile            (Owned by Lead)
docker-compose.yml  (Owned by Lead)
```
