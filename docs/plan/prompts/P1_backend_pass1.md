# P1: Backend & Sessions: Pass 1
Run in: a fresh Antigravity agent session. Model: Claude Opus/Sonnet or Gemini 3.8 Flash.
Settings: Planning mode for Pass 1. Time-box: ~2 hours.

## 1. Mission
Build the real FastAPI WebSocket backend. It handles routing, rooms, participant session state, and history buffering. Roundtable is a multi-device live captioning system.

## 2. Ownership
You may create or edit ONLY these paths: `/ws1_backend`.
Read-only paths: `/contracts`.
Forbidden paths: everything else.

## 3. Contracts (authoritative, version 1.0; do not modify)
[verbatim excerpts from 02_contracts.md]
**Direction: Client -> Server**
*   `JoinRequest`: `{ "type": "JOIN", "session_id": "ROOM1", "participant_name": "Alice" }`
*   `TimeSyncRequest`: `{ "type": "SYNC", "client_tx_ts": 1700000000123 }`
**Direction: Server -> Client**
*   `CaptionEvent`: `{ "type": "CAPTION", "segment_id": "seg_88", "speaker_id": "p_123", "text": "Hello world", "is_final": false }`

## 4. Dependencies and mocks
Use `/contracts/models.py`. Assume ASR is a mock for now.

## 5. Environment
Python 3.10+. `pip install fastapi uvicorn websockets pydantic`.

## 6. Build steps
0. **Repo Setup:** Run git clone https://github.com/0-pyro/BNB26_Kosmoskost_Internal_Round . (if the directory is empty). Ensure you are inside the repository, then run git checkout -b ws1_backend.
1. **Server Setup:** Create `ws1_backend/main.py`. Set up FastAPI app and WebSocket endpoint `/ws`.
2. **Session Manager:** Create `ws1_backend/session.py`. Maintain a dict of active `ROOMS`. Each room holds connected Websockets and a history list of `CaptionEvent`.
3. **Join Flow:** Handle `JoinRequest`. Generate a `participant_id`. Reply with `JoinAck` and historical captions.
   [CHECKPOINT]
4. **Time Sync:** Implement NTP-like time sync. On `TimeSyncRequest`, reply immediately with `TimeSyncResponse` injecting `server_rx_ts` and `server_tx_ts`.
5. **Audio Routing:** Handle incoming binary audio frames. For Pass 1, just print the header (Participant ID, SeqNum).

## 7. Edge cases and failure handling to implement
- If a client disconnects, mark them inactive but keep them in the room for 60 seconds (for reconnects).
- Handle concurrent WebSocket writes properly (use asyncio locks if needed).

## 8. Tests that must pass
Run `pytest ws1_backend/tests/`. Test joining, disconnecting, and history retrieval.

## 9. Rules of engagement
- Stay in scope. Do not refactor beyond it. No new features.
- Ambiguity: choose the most conservative reading.
- Never edit contracts. 
- Evidence rule: report a command or test as passing only if you ran it in this session.

## 10. Git and integration handoff
Work only on branch `ws1_backend`. At each CHECKPOINT run: `git add -A && git commit -m "step N" && git push origin ws1_backend`.
Write `ws1_backend/INTEGRATION.md` detailing how to start the FastAPI server on port 8000.

## 11. Definition of done and final report
Done means: tests pass, INTEGRATION.md exists, branch pushed. 

## 12. Reminder
Planning only. Do not edit forbidden paths. Contracts are authoritative.
