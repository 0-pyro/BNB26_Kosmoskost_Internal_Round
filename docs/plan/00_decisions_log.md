# Decisions Log

## Q&A Decisions & Assumptions
*   **Logistics:** 24-hour deadline. The team is geographically distributed (not on the same LAN). Demo will be a pre-recorded physical test by the Lead (using multiple phones in one room) plus a live screen-share of the virtual participant dashboard.
*   **Hardware/Team:** Lead (C/Hardware). Person 2 (Frontend), Person 3 (Backend), Person 4 (ML/DSP). Testing on Android phones and Windows laptops.
*   **Architecture & Stack:** Python (FastAPI) backend. WebSocket transport for audio.
*   **ASR Strategy:** Cloud API free tier (e.g., Groq Whisper or AssemblyAI). Zero budget. Scripted Mock ASR as fallback.
*   **DSP & Audio Fusion:** 
    *   *Alignment:* Network time sync + GCC-PHAT cross-correlation.
    *   *Attribution:* Relative energy/volume levels across devices (loudest mic wins).
    *   *Fusion:* Dynamic audio selection (routing the single loudest device's audio to the ASR), not complex signal mixing.
*   **Scope:** Target 4, Max 8 participants. English with Indian accents. 
*   **UI/UX:** Interleaved lines with overlap markers. Screen Wake Lock API to prevent mobile sleep.
*   **Resilience:** 60-second client-side buffering during drops. Server sends history to late joiners.
*   **Evaluation:** Synthetic overlapping speech generated via `pyroomacoustics` played through virtual clients. Primary metric is Speaker-Attributed Word Error Rate (SA-WER). Strict automated tests before merge.

## [UNVERIFIED] items to resolve in Spikes
*   `[UNVERIFIED]` Groq/AssemblyAI exact latency and concurrent stream limits (Though we send 1 fused stream, rate limits apply).
*   `[UNVERIFIED]` iOS Safari Web Audio / AudioWorklet behavior when screen locks, despite Wake Lock.
*   `[UNVERIFIED]` The exact processing time of GCC-PHAT in pure Python on a standard laptop (may need Cython/C++ fallback).

## Rationale
*   *Why selection over mixing?* In 24 hours, dealing with phase-cancellation and comb-filtering from mixing unaligned streams is too risky. Selection is robust.
*   *Why Virtual Participants?* Since the team is remote, physical multi-device testing is a bottleneck. Virtual clients replaying room simulations ensure everyone can test fusion.
