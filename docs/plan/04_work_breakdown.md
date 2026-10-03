# Work Breakdown

## Team Assignment
*   **Lead**: Infrastructure, Mock ASR, Contracts, Integration, UI Dashboard.
*   **Person 2 (WS1: Backend & Sessions)**: FastAPI WebSockets, Room logic, Caption routing.
*   **Person 3 (WS2: Web Client)**: React UI, AudioWorklet capture, Wake Lock, Reconnect buffering.
*   **Person 4 (WS3 & WS4: DSP & ASR/Eval)**: Python DSP (Alignment, SNR routing), Cloud ASR integration, Virtual Participant, `pyroomacoustics`. *(Combined due to 24h constraint, WS4 is mostly scripts)*

## Milestones
*   **M0**: Contracts, skeleton, mocks, Virtual Participant, and fault proxy defined.
*   **M1 (Walking Skeleton)**: 2 Virtual Participants -> Server -> Mock ASR -> Client UI. (No DSP, just passing audio).
*   **M2 (Fusion)**: Real DSP alignment and loudness selection integrated.
*   **M3 (Evaluation & Robustness)**: Run evaluation metrics; test network drops and reconnects.
*   **M4 (Demo Polish)**: Rehearsal, UI styling, fallback scripts.

## AI Usage Budget (Per Pass)
*   **Pass 1**: Use Gemini 3.8 Flash or Claude Sonnet for bulk implementation (10-15 files, ~1000 LOC). 
*   **Pass 2**: Use Claude Opus (or high-reasoning model) for debugging complex DSP/WebSocket issues and integration fixes.

## Git & Integration Runbook
**Setup:**
`git clone https://github.com/0-pyro/BNB26_Kosmoskost_Internal_Round .`
`git checkout -b ws1_backend` (etc.)

**Daily Sync:**
`git fetch origin && git rebase origin/main`
*(Never resolve a conflict in someone else's directory. Lead's `contracts/` always wins).*

**Checkpoint:**
`git add . && git commit -m "checkpoint" && git push origin <branch>`

**Integration (Lead Only):**
1. `git checkout main`
2. `git merge origin/ws1_backend`
3. `make run-integration-test`
4. Revert if failed: `git revert HEAD`

**Smoke Test Command:**
`make test-walking-skeleton`
*(Expects: Server starts on :8000, 2 virtual participants connect, mock ASR yields text, terminal prints "Smoke test passed").*

## Task Table
| ID | Title | Owner | Dependencies | Pass |
|---|---|---|---|---|
| T1 | Root Skeleton & Mocks | Lead | None | L0 |
| T2 | Server WebSocket & Rooms | P2 | T1 | P1 |
| T3 | React AudioWorklet & UI | P3 | T1 | P1 |
| T4 | DSP Alignment & Selection | P4 | T1 | P1 |
| T5 | ASR Integration & Eval | P4 | T1 | P1 |
| T6 | Walking Skeleton Merge | Lead | T2, T3, T4, T5 | I1 |
