# P2: Client UI & AudioWorklet: Pass 1
Run in: a fresh Antigravity agent session. Model: Claude Opus/Sonnet or Gemini 3.8 Flash.
Settings: Planning mode for Pass 1. Time-box: ~2 hours.

## 1. Mission
Build the React UI and the AudioWorklet processor that captures 16kHz audio, chunks it into 100ms frames, and sends it over WebSockets. Roundtable is a multi-device live captioning system.

## 2. Ownership
You may create or edit ONLY these paths: `/ws2_client`.
Read-only paths: `/contracts`.
Forbidden paths: everything else.

## 3. Contracts (authoritative, version 1.0; do not modify)
[verbatim excerpts from 02_contracts.md]
**Direction: Client -> Server**
*   `JoinRequest`: `{ "type": "JOIN", "session_id": "ROOM1", "participant_name": "Alice" }`
**Direction: Server -> Client**
*   `CaptionEvent`: `{ "type": "CAPTION", "segment_id": "seg_88", "speaker_id": "p_123", "text": "Hello world", "is_final": false }`
**Binary Audio Frame:** 16-byte header (`[0:1] 0xAA 0xBB`, `[2:3] Participant ID Hash`, `[4:7] SeqNum`, `[8:15] CaptureTS`) + Float32 PCM.

## 4. Dependencies and mocks
You will test against the Mock Server built by the Lead (`ws4_eval/mock_server.py`).

## 5. Environment
Node.js 18+. `npx create-react-app .` (or Vite). 

## 6. Build steps
1. **React App:** Initialize Vite/React app in `/ws2_client`.
2. **WebSocket Client:** Create `useWebSocket.ts`. Handle reconnects and buffering offline events.
3. **AudioWorklet:** Create `processor.js`. It must capture 16kHz audio, create 100ms Float32 buffers, prepend the 16-byte binary header, and postMessage to the main thread to send via WebSocket.
   [CHECKPOINT]
4. **Wake Lock:** Implement `navigator.wakeLock.request('screen')` on session join.
5. **UI Rendering:** Render incoming `CaptionEvent` objects. Group them by `speaker_id`. Interleave them by `start_ts`. If `is_final` is false, render with lower opacity.

## 7. Edge cases and failure handling to implement
- If WebSocket drops, buffer audio frames locally for up to 60s and burst-send on reconnect.
- Handle iOS Safari requiring a user gesture to start AudioContext.

## 8. Tests that must pass
Jest unit tests for the UI state transitions (partial to final updates).

## 9. Rules of engagement
- Stay in scope. Do not refactor beyond it. No new features.
- Ambiguity: choose the most conservative reading.
- Evidence rule: report a command or test as passing only if you ran it in this session.

## 10. Git and integration handoff
Work only on branch `ws2_client`. At each CHECKPOINT run: `git add -A && git commit -m "step N" && git push origin ws2_client`.
Write `ws2_client/INTEGRATION.md` detailing how to start the dev server (e.g., `npm run dev`).

## 11. Definition of done and final report
Done means: tests pass, UI renders mock events, branch pushed. 

## 12. Reminder
Planning only. Do not edit forbidden paths. Contracts are authoritative.
