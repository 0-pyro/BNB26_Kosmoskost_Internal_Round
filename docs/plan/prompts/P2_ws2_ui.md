# P2: Frontend UI - Dashboard & Airtime HUD (WS2)
Run in: a fresh Antigravity agent session. Model: Gemini 3.8 Flash.
Settings: Execution mode. Time-box: ~1 hour.

## 1. Mission
Build the client-side Speaker Airtime HUD, a Session Archive Drawer, and the UI for Post-Meeting AI Assists. Refer to `docs/plan/09_feature_expansions.md` for architectural details.

## 2. Ownership
You may create or edit ONLY these paths: `/ws2_client`.
Read-only paths: `/contracts`, `/docs`.
Forbidden paths: everything else.

## 3. Dependencies and Context
- Read `docs/plan/01_architecture.md` and `docs/plan/09_feature_expansions.md` Section 1.2 and 2 to understand your specific requirements.
- The frontend is a React application built with Vite and Tailwind CSS.
- Current live transcripts arrive via WebSocket (`useWebSocket.ts`).
- The backend will provide `GET /api/sessions`, `GET /api/sessions/{session_id}`, and `POST /api/ai/assist`. (Assume these contracts as defined in the docs, even if the backend isn't merged yet).

## 4. Build Steps
0. **Repo Setup:** Run `git checkout main && git pull origin main`. Then run `git checkout -b ws2_ui`.
1. **Airtime HUD:** Create a pure client-side component (`src/components/AirtimeHUD.tsx`).
   - Hook into the live transcript state. Track words or characters spoken by each `speaker_id` for `is_final=true` events.
   - Render a retro terminal-style bar chart overlaying the main meeting view.
   [CHECKPOINT] Run `npm run test` or `vitest`, `git add -A && git commit -m "airtime hud" && git push origin ws2_ui`.
2. **Session Drawer:** Create `src/components/SessionDrawer.tsx`.
   - Add a button to the main UI to open the drawer.
   - Fetch and list past sessions from `GET /api/sessions`.
   - Clicking a session opens a static view of its transcript (`GET /api/sessions/{session_id}`).
3. **AI Assist Panel:** Inside the static session view, build an AI Assist UI.
   - Buttons: "Summarize", "Translate". Text input: "Custom Query".
   - Wire these to `POST /api/ai/assist` and display the loading state and final response.
   [CHECKPOINT] Run tests, `git add -A && git commit -m "dashboard and ai assist ui" && git push origin ws2_ui`.

## 5. Tests that must pass
Write React component tests using your preferred testing library (Vitest/Testing Library is configured). Ensure `npm run build` succeeds without TypeScript errors.

## 6. Rules of Engagement
- Do NOT break the existing live WebSocket meeting UI.
- Use mock data if the backend endpoints are not reachable during your dev loop.

## 7. Definition of Done
Tests pass, build succeeds, UI looks cohesive, changes pushed to `ws2_ui`.
