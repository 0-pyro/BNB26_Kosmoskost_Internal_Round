# L0: Lead: Contracts, Skeleton, and Mocks: Pass 1
Run in: a fresh Antigravity agent session. Model: Claude Opus/Sonnet or Gemini 3.8 Flash.
Settings: Planning mode for Pass 1 (review the plan, then execute). Reasoning effort: High if selectable. Time-box: ~2 hours.

## 1. Mission
You are the team lead. Set up the multi-package monorepo skeleton, generate typed models from the contracts, and build the Mock ASR and fault-injection proxy. Roundtable is a multi-device live captioning system that fuses audio from multiple phones in a room.

## 2. Ownership
You may create or edit ONLY these paths: 
- `/` (Root files: `Makefile`, `docker-compose.yml`, `.gitignore`)
- `/contracts`
- `/ws4_eval` (Mock ASR and Proxy)
Read-only paths: None.
Forbidden paths: `/ws1_backend`, `/ws2_client`, `/ws3_dsp` (unless creating empty dirs).

## 3. Contracts (authoritative, version 1.0; do not modify)
[verbatim excerpts from 02_contracts.md]
**Direction: Client -> Server**
*   `JoinRequest`: `{ "type": "JOIN", "session_id": "ROOM1", "participant_name": "Alice" }`
*   `TimeSyncRequest`: `{ "type": "SYNC", "client_tx_ts": 1700000000123 }`
**Direction: Server -> Client**
*   `CaptionEvent`: `{ "type": "CAPTION", "segment_id": "seg_88", "speaker_id": "p_123", "text": "Hello world", "is_final": false }`
**Binary Audio Frame:** 16-byte header (`[0:1] 0xAA 0xBB`, `[2:3] Participant ID Hash`, `[4:7] SeqNum`, `[8:15] CaptureTS`) + Float32 PCM.

## 4. Dependencies and mocks
None. You provide the mocks for the rest of the team.

## 5. Environment
Python 3.10+. [UNVERIFIED] Ensure `toxiproxy` or a custom Python proxy works on Windows/Linux. 
Commands: `python -m venv venv`, `pip install pydantic fastapi websockets`.

## 6. Build steps
1. **Skeleton:** Create `/ws1_backend`, `/ws2_client`, `/ws3_dsp`, `/ws4_eval`. Create `.gitignore` ignoring venvs and large files.
   Verify: run `ls`; expected: `ws1_backend ws2_client ...`
2. **Contracts:** Create `contracts/models.py` using Pydantic for `JoinRequest`, `CaptionEvent`, etc.
   Verify: run `python -c "import contracts.models"`; expected: no error.
3. **Mock Server/ASR:** In `/ws4_eval`, write `mock_server.py` that listens on WSS, accepts binary frames, and emits scripted `CaptionEvent` JSON back after a delay.
   Verify: run `python ws4_eval/mock_server.py &` then ping it.
   [CHECKPOINT]
4. **Virtual Participant:** In `/ws4_eval`, write `virtual_client.py` that reads a WAV file, chunks it into binary frames (with headers), and sends via WSS.
   Verify: run `python ws4_eval/virtual_client.py`.
5. **Fault Proxy:** In `/ws4_eval`, write `proxy.py` that forwards port 8001 to 8000 but allows injecting latency/drops via CLI.
   [CHECKPOINT]

## 7. Edge cases and failure handling to implement
- Mock server must handle malformed binary frames without crashing.
- Proxy must correctly close both ends if a drop is injected.

## 8. Tests that must pass
Run `python -m pytest ws4_eval/tests/`. Mock server must reply to JoinRequest.

## 9. Rules of engagement
- Stay in scope. Do not refactor beyond it. No new features.
- Ambiguity: choose the most conservative reading consistent with the contracts, and record it in NOTES.md.
- Never edit contracts. 
- No secrets in code or logs.
- Evidence rule: report a command or test as passing only if you ran it in this session and saw its output.
- Resume protocol: update `STATE.md` at every checkpoint.

## 10. Git and integration handoff
Work only on branch `lead_skeleton`. At each CHECKPOINT run: `git add -A && git commit -m "step N" && git push origin lead_skeleton`.
Write `INTEGRATION.md` in root detailing how to start the mock server and virtual client.

## 11. Definition of done and final report
Done means: tests pass, integration docs exist, branch pushed. 

## 12. Reminder
Planning only. Do not edit forbidden paths. Contracts are authoritative.
