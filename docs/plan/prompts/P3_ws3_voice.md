# P3: "Hey Roundtable" Voice Copilot (WS3)
Run in: a fresh Antigravity agent session. Model: Gemini 3.8 Flash.
Settings: Execution mode. Time-box: ~1 hour.

## 1. Mission
Implement the live "Hey Roundtable" wake-word interception. When a user says the wake word, intercept the transcript, query the fast LLM with the recent context, and broadcast the response as a system caption. Refer to `docs/plan/09_feature_expansions.md`.

## 2. Ownership
You may edit `/ws1_backend/main.py`, `/ws1_backend/session.py`, and related backend event files.
Read-only paths: `/contracts`, `/docs`.
Forbidden paths: frontend client.

## 3. Dependencies and Context
- Read `docs/plan/09_feature_expansions.md` Section 3.
- Familiarize yourself with `ws1_backend/session.py` (how `CaptionEvent`s are broadcast) and the ASR processing loop (where transcripts are received and finalized).
- You will need to use the Groq Python SDK for LLM generation (`qwen/qwen3.8-27b`).

## 4. Build Steps
0. **Repo Setup:** Run `git checkout main && git pull origin main`. Then run `git checkout -b ws3_voice`.
1. **Wake-Word Interceptor:** In the backend code where text segments are marked `is_final` and prepared for broadcasting, add a regex check: `(?i)^hey roundtable[,]?\s*(.*)`.
   - If it matches, extract the query group. Do NOT broadcast this segment as a normal user caption (or if you do, proceed to step 2 immediately).
   [CHECKPOINT] Run tests, `git add -A && git commit -m "wake word regex" && git push origin ws3_voice`.
2. **Context & LLM Call:** When intercepted:
   - Fetch the last 50 lines of the room's transcript buffer.
   - Send the context + the user's query to Groq asynchronously (`qwen/qwen3.8-27b`).
3. **Broadcast Response:** Await the LLM response. Create a new `CaptionEvent` with `speaker_id="Roundtable AI"`, `is_final=True`, and `text=<LLM_Response>`.
   - Broadcast this event to the room so all connected clients see it.
   [CHECKPOINT] Run tests (`pytest ws1_backend/`), `git add -A && git commit -m "llm and broadcast" && git push origin ws3_voice`.

## 5. Tests that must pass
Write unit tests for the regex interceptor. Mock the Groq client and test the broadcast logic. Ensure the existing `pytest ws1_backend/` suite still passes.

## 6. Rules of Engagement
- Ensure the LLM call is non-blocking to the main WebSocket audio ingestion loop. Use `asyncio.create_task` or similar.

## 7. Definition of Done
Tests pass, wake word correctly broadcasts AI responses, changes pushed to `ws3_voice`.
