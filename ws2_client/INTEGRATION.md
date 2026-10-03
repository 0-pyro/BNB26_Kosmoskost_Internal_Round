# Roundtable Client UI & AudioWorklet — Integration Guide

## Overview

The `ws2_client` package implements the web frontend and audio capture pipeline for Roundtable live captioning:
- **React 19 + TypeScript + Vite** UI for joining rooms, viewing live captions (timeline and speaker-grouped views), and managing session state.
- **AudioWorklet Processor (`processor.js`)** capturing microphone input, downsampling to 16kHz, accumulating 100ms frames (1600 samples), and prepending the authoritative 16-byte binary header.
- **WebSocket Client (`useWebSocket`)** managing session joins, auto-reconnection with exponential backoff, and offline frame buffering (up to 60s).
- **Screen Wake Lock (`useWakeLock`)** preventing display sleep during active captioning sessions with auto-reacquisition on visibility change.
- **Audio Capture (`useAudioCapture`)** handling microphone acquisition and iOS Safari user-gesture requirements.

---

## Prerequisites

- **Node.js**: v18+ (tested on Node.js v20+)
- **npm**: v9+
- **Mock Server (Python)**: For local testing (see Root `INTEGRATION.md`)

---

## Quick Start

### 1. Install Dependencies

```bash
cd ws2_client
npm install
```

### 2. Run Unit & Component Tests

```bash
npm test
```

Or for watch mode:
```bash
npm run test:watch
```

### 3. Build for Production

```bash
npm run build
```

### 4. Start the Dev Server

```bash
npm run dev
```

By default, Vite serves the application on `http://localhost:5173`.

---

## End-to-End Integration Testing with Mock Server

### 1. Start the Mock Server (from project root)

In a separate terminal:
```bash
# Windows
venv\Scripts\python ws4_eval/mock_server.py --port 8000

# Linux / macOS
venv/bin/python ws4_eval/mock_server.py --port 8000
```

The mock server will listen on `ws://0.0.0.0:8000`.

### 2. Start the Client

```bash
cd ws2_client
npm run dev
```

### 3. Join a Session

1. Open `http://localhost:5173` in your browser.
2. Enter Room Code: `ROOM1` (or any string).
3. Enter Participant Name: `Alice`.
4. Click **Join Session**.
   - The user gesture triggers microphone permission request (iOS Safari compliant) and AudioContext resumption.
   - The client connects to `ws://localhost:8000` and transmits a `JOIN` request.
   - The mock server responds with `JOIN_ACK` and assigns a participant ID (e.g. `p_12345678`).
   - The Screen Wake Lock is requested.
   - Audio is captured at 16kHz, packed into 100ms chunks with the 16-byte binary header, and streamed over WebSocket.
   - The mock server receives binary frames and emits scripted `CaptionEvent` responses.
   - Captions appear live on the UI with partial captions at lower opacity (`0.55`) and final captions at full opacity (`1.0`).

---

## Binary Audio Frame Specification

Binary audio frames transmitted by the client match the authoritative specification in `contracts/models.py`:

```
+-------------------+-------------------+-------------------+-------------------+
|  Magic (2 bytes)  |  PID Hash (2 B)   |   SeqNum (4 B)    | CaptureTS (8 B)   |
|    0xAA 0xBB      |   UInt16 (BE)     |    UInt32 (BE)    |   UInt64 (BE)     |
+-------------------+-------------------+-------------------+-------------------+
|                     Float32 PCM Payload (1600 samples = 6400 bytes)           |
+-------------------------------------------------------------------------------+
```

- **Byte Order**: Big-endian (network byte order).
- **Header Size**: 16 bytes.
- **Audio Payload**: 100ms at 16,000 Hz mono Float32 PCM (1600 floats = 6400 bytes).
- **Total Frame Size**: 6416 bytes.

---

## Edge Case & Failure Handling

1. **WebSocket Disconnection & Offline Buffering**:
   - If the WebSocket connection drops, `useWebSocket` automatically attempts reconnection using exponential backoff (1s, 2s, 4s, 8s, max 16s).
   - Audio frames produced during disconnect are buffered in memory up to 60 seconds (`maxBufferSecs`).
   - Upon reconnect and receiving `JOIN_ACK`, all buffered frames are burst-sent to the server.
2. **iOS Safari AudioContext Policy**:
   - `AudioContext` and `getUserMedia` require a user gesture on iOS Safari.
   - In `App.tsx`, `audio.startCapture()` is triggered directly from the "Join Session" submit click handler.
   - The AudioContext automatically handles resuming if created in a `suspended` state.
3. **Screen Sleep Prevention**:
   - `navigator.wakeLock.request('screen')` is acquired upon receiving `JOIN_ACK`.
   - Listens to `visibilitychange` events; if the browser tab is hidden and reopened, the lock is automatically re-acquired.
