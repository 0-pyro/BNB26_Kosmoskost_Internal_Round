# Feature Expansions (v2)

This document outlines the architecture and requirements for the post-hackathon feature expansions: Session Persistence, LLM Assists, Airtime HUD, and "Hey Roundtable" Voice Copilot.

## 1. Session Persistence & LLM Assists (WS1_Storage & WS2_UI)

### 1.1 Backend Storage (WS1)
- **Goal:** Persist transcripts after a room closes or periodically.
- **Storage:** Use a local SQLite database (`sessions.db`) or simple JSON files in `ws1_backend/data/`.
- **API Endpoints:**
  - `GET /api/sessions`: Returns a list of past sessions (ID, timestamp, duration).
  - `GET /api/sessions/{session_id}`: Returns the full transcript of a specific session.
  - `POST /api/ai/assist`: Accepts `{ session_id: str, query_type: str, query: Optional[str], target_language: Optional[str] }`.
    - `query_type` can be `summary`, `translation`, or `custom`.
    - **LLM Integration:** Use `qwen/qwen3.8-27b` via Groq API. The backend fetches the transcript for `session_id`, constructs a prompt, and returns the LLM's string response.

### 1.2 Frontend Dashboard (WS2)
- **Goal:** A UI Drawer to access past sessions and query the LLM.
- **Components:**
  - `SessionDrawer.tsx`: Slides out to show a list of past sessions.
  - `PastSessionView.tsx`: Displays the static transcript of a selected session.
  - `AIAssistPanel.tsx`: UI with buttons for "Summarize", "Translate to [Lang]", and a text input for custom queries. Calls `POST /api/ai/assist` and displays the result.

## 2. Speaker Airtime HUD (WS2_UI)

- **Goal:** A pure client-side retro visualization of speaker participation.
- **Mechanism:** In `useWebSocket.ts` or a new hook `useAirtime.ts`, track the number of words or characters spoken by each `speaker_id` from incoming `is_final=true` `CaptionEvent`s.
- **UI:** Render a persistent HUD (e.g., a retro terminal-style bar chart) overlaying the meeting view, updating in real-time to show who is dominating the conversation.

## 3. "Hey Roundtable" Voice Copilot (WS3_Voice)

- **Goal:** Allow participants to ask the AI questions live during the meeting using voice commands.
- **Trigger:** In the backend ASR processing loop (`ws1_backend/main.py` or `ws1_backend/session.py`), check every incoming finalized text segment.
- **Condition:** If `text` matches regex `(?i)^hey roundtable[,]?\s*(.*)`, intercept it. Do NOT broadcast it as a normal user caption (or broadcast it, but immediately trigger the AI).
- **Execution:** 
  1. Extract the query: `(.*)`
  2. Fetch the last N lines of the room's transcript buffer.
  3. Send the transcript + query to Groq (`qwen/qwen3.8-27b`) asynchronously.
- **Broadcast:** Once the LLM responds, create a synthetic `CaptionEvent` with `speaker_id="Roundtable AI"` and `text=<LLM Response>`, and broadcast it to all WebSocket clients in the room.

## 4. Integration
All these features must be implemented in isolated branches (`ws1_storage`, `ws2_ui`, `ws3_voice`), thoroughly tested, and merged into an `integration` branch. The `integration` branch resolves conflicts and runs end-to-end tests to ensure the core live captioning is unaffected by the new features.
