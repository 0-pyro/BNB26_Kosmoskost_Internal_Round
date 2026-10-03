# Architecture

## Goals and Non-Goals
**Goals:** Provide low-latency, speaker-attributed live captions for up to 8 participants in a shared room. Demonstrate multi-device audio fusion and robust session handling. 
**Non-Goals:** Building a custom ASR engine. Handling remote/video calls (all participants are in the same physical room). Long-term persistence.

## System Context
```mermaid
flowchart TD
    Phones[Participant Phones/Browsers] <-->|WSS (Audio & Sync)| Server[FastAPI Server]
    Virtual[Virtual Participants (pyroomacoustics)] <-->|WSS| Server
    Host[Host/Display Console] <-->|WSS (Captions)| Server
    Server <-->|gRPC/WSS| ASR[Cloud ASR / Mock ASR]
```

## Pipeline & Latency Budget (Target: < 1500ms to first partial)
1. **Capture & Framing:** Browser AudioWorklet -> 16kHz Mono Float32 -> 100ms frames. *(Budget: +120ms)*
2. **Transport & Jitter Buffer:** WebSockets to server, buffered to handle network jitter. *(Budget: +150ms)*
3. **Alignment & VAD:** Network time offset applied, GCC-PHAT fine-tuning, Voice Activity Detection. *(Budget: +80ms)*
4. **Fusion & Attribution:** Calculate SNR/Energy across devices. Select the loudest device's audio frame. Tag with Participant ID. *(Budget: +50ms)*
5. **ASR:** Send fused stream to Cloud API. *(Budget: +800ms)*
6. **Revision Handling & Fan-out:** Server receives partial/final, updates segment states, broadcasts JSON to clients. *(Budget: +50ms)*
7. **UI Render:** React DOM update. *(Budget: +50ms)*

## Deployment Topologies
*   **Dev:** Local FastAPI server, Mock ASR, Virtual Participants via CLI. 
*   **Demo/Production:** Server hosted on a cloud VPS (e.g., DigitalOcean/AWS) so the distributed team and physical phones can connect without LAN isolation issues. HTTPS terminated by Caddy/Nginx. Cloud ASR.
*   **Fallback:** VPS Server + Mock ASR (scripted replay) if Cloud API rate-limits.

## UI Component State Machine
Caption segments transition through states to prevent UI flicker:
*   `PARTIAL`: Live typing, low confidence, text may rewrite rapidly. Displayed in a distinct "unstable" style (e.g., greyed).
*   `REVISED`: ASR sent a correction for an older segment. The UI animates the change if it's already displayed.
*   `FINAL`: ASR committed the segment. Text is locked, speaker is finalized. Pushed to history log.
*   *Ordering:* If a late segment finalizes out of order, it is inserted based on its absolute session timestamp. Overlapping speech is shown as interleaved lines, marked with `[ParticipantName]`. Auto-scroll pins to bottom unless the user scrolls up.

## Workspace and Dependency Isolation
*   **Mechanism:** Multi-package monorepo.
*   **Root:** Owned by Team Lead. Contains `docker-compose.yml`, `Makefile`, `.gitignore`.
*   **Workstreams:** Each WS directory has its own package manager (`requirements.txt` for Python, `package.json` for Node). 
    *   `ws1_backend/` (Python)
    *   `ws2_client/` (Node/React)
    *   `ws3_dsp/` (Python)
    *   `ws4_eval/` (Python)

## Security and Privacy
*   **Audio:** Ephemeral in-memory buffers only. No audio is saved to disk unless explicitly running the evaluation data collector (which requires console flags).
*   **Connections:** HTTPS/WSS is mandatory for `getUserMedia`.

## ASR Interface (Mockable)
The system defines an abstract `ASREngine` class. 
The `MockASREngine` reads from a predefined JSON fixture (simulating delays, partials, and finals) and yields them exactly like the real API, burning zero quota during UI/DSP development.
