# I2: Lead: Final Integration and Demo Hardening
Run in: a fresh Antigravity agent session. Model: Claude Opus or Gemini 3.1 Pro (High).
Settings: Execution mode. Time-box: ~1.5 hours.

## 1. Mission
Merge Pass 2 branches (if any). Wire the real DSP pipeline (Alignment & Selection) into the Backend server routing. Swap Mock ASR for Real Cloud ASR. Run the Evaluation Suite.

## 2. Ownership
You own the whole repository.

## 3. Build steps
1. `git checkout integration && git merge origin/ws_updates...`
2. In `ws1_backend/main.py`, route incoming binary frames through `ws3_dsp.select.get_best_frame()` before sending to ASR.
3. Hook up `ws4_eval/asr_client.py` to receive the selected frames.
4. Run the Chaos Proxy (`ws4_eval/proxy.py`). Drop connection for 10s. Verify React UI recovers.
5. Run the evaluation protocol: feed the 4 `pyroomacoustics` WAVs through Virtual Participants. Calculate final SA-WER.

## 4. Smoke Test
The SA-WER report must be generated and printed. The UI must handle overlapping speakers using the interleaved UI logic.
