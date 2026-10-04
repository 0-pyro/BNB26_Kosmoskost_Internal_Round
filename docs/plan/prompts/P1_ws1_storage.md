# P1: Backend Storage & AI Assist (WS1)
Run in: a fresh Antigravity agent session. Model: Gemini 3.8 Flash.
Settings: Execution mode. Time-box: ~1 hour.

## 1. Mission
Implement session persistence (SQLite or JSON) to save transcripts, and build the `/api/ai/assist` backend endpoint powered by `qwen/qwen3.8-27b` via Groq for Post-Meeting AI Assists. Refer to `docs/plan/09_feature_expansions.md` for architectural details.

## 2. Ownership
You may create or edit ONLY these paths: `/ws1_backend`.
Read-only paths: `/contracts`, `/docs`.
Forbidden paths: everything else.

## 3. Dependencies and Context
- Read `docs/plan/01_architecture.md` and `docs/plan/02_contracts.md` to understand the current system.
- Read `docs/plan/09_feature_expansions.md` Section 1.1 for your specific requirements.
- The system currently runs a FastAPI server (`ws1_backend/main.py`) maintaining active WebSocket rooms in `session.py`.
- You MUST use Groq for the LLM. Read the existing Groq usage in the codebase if needed, or use the official python `groq` SDK.

## 4. Build Steps
0. **Repo Setup:** Run `git checkout main && git pull origin main`. Then run `git checkout -b ws1_storage`.
1. **Storage Layer:** Create `ws1_backend/storage.py`. Implement a mechanism to persist a room's transcript (list of `CaptionEvent`s) to disk (`data/sessions.db` SQLite, or JSON files) when a room is closed or cleared.
2. **Read API:** In `ws1_backend/main.py`, expose two REST endpoints:
   - `GET /api/sessions`: Returns a list of saved sessions (id, timestamp).
   - `GET /api/sessions/{session_id}`: Returns the transcript for that session.
   [CHECKPOINT] Run tests (`pytest ws1_backend/`), `git add -A && git commit -m "storage and read api" && git push origin ws1_storage`.
3. **AI Assist API:** In `ws1_backend/main.py`, expose `POST /api/ai/assist`.
   - Payload: `{ session_id: str, query_type: str, query: Optional[str], target_language: Optional[str] }`
   - Logic: Retrieve the session transcript from storage. Construct a prompt based on `query_type` (summary, translation, custom). Query Groq model `qwen/qwen3.8-27b`. Return the text response.
   [CHECKPOINT] Run tests, `git add -A && git commit -m "ai assist api" && git push origin ws1_storage`.

## 5. Tests that must pass
Write unit tests in `ws1_backend/tests/test_storage.py` and `test_api.py`. Mock the Groq client. Ensure `pytest ws1_backend/` passes completely.

## 6. Rules of Engagement
- Do NOT modify the WebSocket captioning logic.
- Do NOT assume any prior context; read the code in `ws1_backend` to understand how `CaptionEvent`s are currently stored in memory.

## 7. Definition of Done
Tests pass, endpoints work, changes pushed to `ws1_storage`.
