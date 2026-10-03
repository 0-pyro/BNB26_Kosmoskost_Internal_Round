# NOTES.md — L0 Design Decisions

## Ambiguity Resolutions

### 1. CaptionEvent schema: prompt §3 vs. 02_contracts.md
The prompt §3 shows a simplified `CaptionEvent`:
```json
{ "type": "CAPTION", "segment_id": "seg_88", "speaker_id": "p_123", "text": "Hello world", "is_final": false }
```
The authoritative `02_contracts.md` includes additional fields: `speaker_name`, `start_ts`, `end_ts`, `revision`.

**Decision:** Used the **full schema from 02_contracts.md** (authoritative). The extra fields have sensible defaults (`speaker_name=""`, timestamps=0, `revision=1`) so the simplified form still validates.

### 2. JoinAck.history type
The contract says `"history": [...]` without specifying the element type.

**Decision:** Typed as `List[CaptionEvent]` — the most conservative reading consistent with the system's purpose (caption history replay for late joiners).

### 3. Binary frame byte order
The contract specifies field sizes (UInt16, UInt32, UInt64) but not byte order.

**Decision:** Used **big-endian (network byte order)** — the most conservative/standard choice for network protocols.

### 4. WebSocket protocol (ws vs wss)
The prompt says "WSS" but for local development there are no TLS certificates.

**Decision:** Mock server and proxy use plain `ws://` for local dev. The architecture doc specifies "HTTPS terminated by Caddy/Nginx" for production, so TLS is an infrastructure concern, not an application-level one.

### 5. Toxiproxy vs custom proxy
The environment section says `[UNVERIFIED] Ensure toxiproxy or a custom Python proxy works on Windows/Linux`.

**Decision:** Implemented a **custom Python proxy** using `websockets`. This avoids external dependencies (toxiproxy requires Go/binary install) and is verified to work on Windows (tested in this session). The proxy supports latency injection and connection drops via CLI flags.

### 6. Audio frame struct packing
The `>HIQ` struct format packs participant_id_hash as UInt16 (H), seq_num as UInt32 (I), and capture_ts as UInt64 (Q) in big-endian. Total header bytes = 2 (magic) + 2 + 4 + 8 = 16, matching the contract.
