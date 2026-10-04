# I3: Final Integration
Run in: a fresh Antigravity agent session. Model: Gemini 3.8 Flash.
Settings: Execution mode. Time-box: ~1 hour.

## 1. Mission
Merge the three feature branches (`ws1_storage`, `ws2_ui`, `ws3_voice`), resolve any merge conflicts, run comprehensive integration tests, and push the final hardened build to `main`. Refer to `docs/plan/09_feature_expansions.md`.

## 2. Ownership
Full repository.

## 3. Dependencies and Context
- Read `docs/plan/09_feature_expansions.md`.
- You are responsible for ensuring the backend API endpoints (from WS1), the Voice Copilot (from WS3), and the frontend UI (from WS2) all work together smoothly.

## 4. Build Steps
0. **Repo Setup:** Run `git checkout main && git pull origin main`. Then run `git checkout -b integration`.
1. **Merge Branches:**
   - `git fetch origin`
   - `git merge origin/ws1_storage`
   - `git merge origin/ws2_ui`
   - `git merge origin/ws3_voice`
2. **Resolve Conflicts:** Carefully resolve any git conflicts. Pay special attention to `ws1_backend/main.py` and `session.py`, as multiple features touch the WebSocket routing and FastAPI app setup.
   [CHECKPOINT] `git commit -m "resolved merge conflicts"` and `git push origin integration`.
3. **E2E Validation:** 
   - Start the backend (`uvicorn ws1_backend.main:app`).
   - Start the frontend (`cd ws2_client && npm run dev`).
   - Verify that Session Storage, Airtime HUD, and Voice Copilot all function together without breaking the core live transcription.

## 5. Tests that must pass
Run the complete backend (`pytest ws1_backend/`) and frontend (`npm run test` or `vitest`) test suites. Build the production frontend bundle (`cd ws2_client && npm run build`).

## 6. Definition of Done
All tests pass, bundle builds cleanly, `integration` branch is pushed, and a Pull Request is opened against `main` (or merged directly into `main` and pushed to `origin/main` depending on repo permissions).
