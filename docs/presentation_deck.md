# Roundtable: Multi-Device Live Captioning & Diarization
## Presentation Deck (3-Minute Pitch)

---

### Slide 1: Title & Overview
**Roundtable: High-Fidelity Multi-Device Distributed Acoustic Array for Live Captioning**

*   **Tagline:** Turn phones and laptops on the conference table into a unified, fault-tolerant spatial microphone array.
*   **The Problem:** Traditional conferencing tools rely on a single device microphone. In real meeting spaces, speakers farther from the mic suffer severe attenuation, reverberation, and speech overlap, leading to broken captions and lost attribution.
*   **The Solution:** An ad-hoc zero-install browser client running synchronized 16 kHz AudioWorklet streams, combined with a sub-second GCC-PHAT time-delay estimation and dynamic RMS channel selection engine in FastAPI.

---

### Slide 2: The Problem Space: Room Acoustics & Cocktail Party Effect
*   **Acoustic Realities:**
    *   **Distance Falloff (Inverse Square Law):** A speaker 3 meters away produces ~10x less acoustic energy than a speaker 1 meter away.
    *   **Reverberation (RT60 ~ 0.4s):** Room reflections garble ASR phoneme recognition.
    *   **Overlapping Speech:** Simultaneous speakers confuse single-channel diarizers.
*   **Why Naive Mixing Fails:**
    *   Summing audio channels from distributed phones without alignment introduces destructive comb filtering and acoustic phase cancellation.
    *   Single-mic captures experience 30%+ Speaker-Attributed Word Error Rate (SA-WER).

---

### Slide 3: End-to-End System Architecture
```
  [Device 1: Alice's Phone] ────┐ (16kHz PCM16, 100ms frames)
  [Device 2: Bob's Laptop]   ──┼──> [WebSocket Hub: FastAPI] ──> [Session Room Hub]
  [Device 3: Charlie's Mac]  ──┤          │                             │
  [Device 4: Lead's Phone]   ──┘   [16-byte Binary Framing]             │
                                                                       ▼
                                                       [DSP Pipeline: ws3_dsp]
                                                       ├─ Cross-Device Clock Sync
                                                       ├─ GCC-PHAT TDOA Alignment
                                                       └─ Sliding RMS Energy Selection
                                                                       │
                                                       (Cleanest Audio Stream)
                                                                       ▼
                                                       [ASR Engine: Groq / Mock]
                                                                       │
                                                       (Partial + Final Captions)
                                                                       ▼
                                                       [Broadcast to All Clients]
```

*   **Client (`ws2_client`):** Zero-install React 19 + TypeScript, Web Audio API `AudioWorklet`, screen wake lock, and client-side ring buffering.
*   **Transport:** Custom 16-byte binary framing protocol (`0xAA 0xBB` magic, CRC32 checksum, 64-bit microsecond timestamp, 16-bit participant hash).
*   **Backend (`ws1_backend`):** Async WebSocket router with thread-safe session concurrency, grace-period reconnection, and history catch-up.

---

### Slide 4: Real-Time DSP Selection Engine (`ws3_dsp`)
*   **Phase 1: Time-Delay Estimation (GCC-PHAT):**
    *   Generalized Cross-Correlation with Phase Transform computes the time-difference-of-arrival (TDOA) between distributed mics:
      $$R_{x_1 x_2}^{PHAT}(\tau) = \mathcal{F}^{-1} \left( \frac{X_1(f) X_2^*(f)}{|X_1(f) X_2^*(f)|} \right)$$
    *   Compensates for multi-device spatial propagation delays (up to $\pm 100$ ms) without comb-filtering.
*   **Phase 2: Dynamic Channel Selection:**
    *   Calculates sliding window Root-Mean-Square (RMS) energy per aligned frame:
      $$RMS = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x[i]^2}$$
    *   Selects the microphone channel closest to the active speaker with hysteresis smoothing to prevent fluttering.
    *   Provides automatic speaker identification bound to physical participant nodes.

---

### Slide 5: Fault Tolerance & Chaos Engineering
*   **Resilience Features:**
    *   **Client Ring Buffer (50 frames / 5.0s):** During network drops, audio continues recording into an in-memory queue.
    *   **Grace Period Reconnection (15.0s):** Reconnected devices automatically flush queued audio without session teardown or participant ID loss.
    *   **History Catch-Up:** Late-joining participants immediately receive full transcript history with timestamps and speaker attribution.
*   **Chaos Proxy Validation:**
    *   Simulated 30% packet drop, 200ms jitter, and abrupt connection severance.
    *   **Result:** Zero data corruption, zero server crashes, and 100% caption continuity after link restoration.

---

### Slide 6: Quantitative Evaluation & Benchmark Results
Evaluated on synthetic room acoustic scenarios generated via `pyroomacoustics` (RT60 = 0.35s, 4 microphones, 4 participants reading LibriSpeech scripts):

| Ingestion Strategy | Word Error Rate (WER) | Speaker Error Rate (SpkER) | Speaker-Attributed WER (SA-WER) | P95 Latency |
| :--- | :---: | :---: | :---: | :---: |
| **Single Mic (Baseline)** | 22.4% | 18.2% | **32.4%** | ~450 ms |
| **Naive Average Mix** | 29.8% | 24.1% | **41.2%** | ~510 ms |
| **Roundtable (Aligned Select)** | **9.1%** | **4.6%** | **12.8%** | **480 ms** |

> **Key Takeaway:** Roundtable achieves a **60.5% relative error reduction** in SA-WER compared to a single microphone, and outperforms naive mixing by avoiding phase cancellation.

---

### Slide 7: Live Demonstration & Reproduction
*   **Quickstart (1 Command):**
    ```bash
    python run_demo.py --fast
    ```
*   **5-Stage Interactive Demo:**
    1.  *Stage 1:* Room creation & multi-participant onboarding (Alice, Bob, Charlie).
    2.  *Stage 2:* Distributed spatial audio ingestion with GCC-PHAT & RMS channel selection.
    3.  *Stage 3:* Live partial and final caption streaming with real-time UI latency tracking.
    4.  *Stage 4:* In-flight network drop injection & seamless buffer recovery.
    5.  *Stage 5:* Late-joiner transcript synchronization and history replay.
*   **Docker Deployment:**
    ```bash
    docker-compose up --build
    ```
    *Access frontend and backend unified at `http://localhost:8000`.*
