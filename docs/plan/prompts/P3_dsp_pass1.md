# P3: DSP, ASR & Eval: Pass 1
Run in: a fresh Antigravity agent session. Model: Claude Opus or Gemini 3.8 Flash (High Reasoning).
Settings: Planning mode for Pass 1. Time-box: ~2 hours.

## 1. Mission
Build the audio fusion core (alignment and loudness selection) and integrate the Groq/AssemblyAI cloud API. Also, build the evaluation scenario using `pyroomacoustics`. Roundtable is a multi-device live captioning system.

## 2. Ownership
You may create or edit ONLY these paths: `/ws3_dsp` and `/ws4_eval` (Eval script only).
Read-only paths: `/contracts`.
Forbidden paths: `/ws1_backend`, `/ws2_client`.

## 3. Contracts (authoritative, version 1.0; do not modify)
[verbatim excerpts from 02_contracts.md]
**Binary Audio Frame:** 16-byte header (`[0:1] 0xAA 0xBB`, `[2:3] Participant ID Hash`, `[4:7] SeqNum`, `[8:15] CaptureTS`) + Float32 PCM.

## 4. Dependencies and mocks
`scipy`, `numpy`, `pyroomacoustics`, `jiwer`, `httpx`, `websockets`. 

## 5. Environment
Python 3.10+. 

## 6. Build steps
1. **Alignment:** Create `ws3_dsp/align.py`. Write a GCC-PHAT function using `scipy.fft` to find the sample delay between two 100ms audio chunks.
2. **Selection logic:** Create `ws3_dsp/select.py`. Given N audio frames from different participants for the same time window (aligned), compute the RMS energy. Output the frame with the highest energy and its associated `speaker_id`.
   [CHECKPOINT]
3. **ASR Integration:** Create `ws4_eval/asr_client.py`. A client that sends a continuous audio stream to Groq Whisper or AssemblyAI and parses the returning JSON stream into `CaptionEvent` objects.
4. **Eval Scenario:** Create `ws4_eval/scenario_gen.py`. Use `pyroomacoustics` to simulate a 5x5m room, 4 mics, 2 overlapping speakers from WAV files. Output the 4 generated noisy WAV files.
   [CHECKPOINT]

## 7. Edge cases and failure handling to implement
- GCC-PHAT will fail if audio is completely silent. Catch this and fallback to 0 offset.
- ASR API timeouts must not crash the system; retry silently.

## 8. Tests that must pass
Write `pytest ws3_dsp/tests/test_align.py` providing two synthetically shifted sine waves. GCC-PHAT must recover the exact offset.

## 9. Rules of engagement
- Evidence rule: report a command or test as passing only if you ran it in this session.

## 10. Git and integration handoff
Work only on branch `ws3_dsp`. At each CHECKPOINT run: `git add -A && git commit -m "step N" && git push origin ws3_dsp`.

## 11. Definition of done and final report
Done means: tests pass, pyroom script outputs WAVs.
