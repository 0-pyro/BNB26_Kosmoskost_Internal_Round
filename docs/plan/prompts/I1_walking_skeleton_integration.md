# I1: Lead: Walking Skeleton Integration
Run in: a fresh Antigravity agent session. Model: Claude Opus or Gemini 3.1 Pro (High).
Settings: Execution mode. Time-box: ~1 hour.

## 1. Mission
You are the Lead. Merge all Pass 1 branches into the `integration` branch. Ensure the system works end-to-end with Virtual Participants, the real Backend, the React Client, and the Mock ASR (no DSP yet, just routing audio).

## 2. Ownership
You own the whole repository.

## 3. Build steps
1. `git checkout main && git checkout -b integration`
2. `git merge origin/ws1_backend` (Resolve conflicts using `contracts/` as truth).
3. `git merge origin/ws2_client`
4. `git merge origin/ws3_dsp`
5. Read all `INTEGRATION.md` files.
6. Start the Backend server.
7. Start the React UI server.
8. Start 2 Virtual Participants.
9. Verify the React UI shows `CaptionEvent`s from the Mock ASR.
10. If bugs exist, fix them. If fixed, commit and push to `integration`.

## 4. Smoke Test
The system must run successfully for 1 minute without crashing.
