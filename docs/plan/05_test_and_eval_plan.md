# Test and Evaluation Plan

## Test Pyramid
1.  **Unit Tests**: Python `pytest` for backend session state machines. Jest for React UI state transitions (partial -> final).
2.  **DSP Property Tests**: Provide the GCC-PHAT module with two audio arrays artificially shifted by a known sample offset. Verify the module outputs the exact offset.
3.  **Integration (Virtual Participants)**: The core of our testing. A headless script spawns 4 Virtual Participant WebSocket clients that stream predefined WAV files. 
4.  **Network Impairment (Chaos)**: 
    *   *Implementation*: A simple proxy script (or Toxiproxy) sitting between Client and Server on port 8001.
    *   *Scenarios*: 
        *   Drop connection for 10s.
        *   Throttle bandwidth to 50kbps.
    *   *Expectation*: Client buffers locally, reconnects, dumps buffer, Server processes without crashing.
5.  **Manual Real-Phone Matrix**: 
    *   Android Chrome, iOS Safari, Windows Chrome, Mac Safari. 
    *   Test locking screen, putting tab in background.

## Evaluation Protocol
Because the team is remote, we prove the multi-device fusion works via simulation.

1.  **Scenario Generator**: A Python script using `pyroomacoustics`. Defines a 5x5m room, places 4 microphones, and places 2 moving speakers playing overlapping clean speech (from a licensed dataset like LibriSpeech). Generates 4 noisy, reverberant, overlapping audio streams.
2.  **Execution**: Run the 4 streams through our system using Virtual Participants.
3.  **Metrics**:
    *   **Speaker-Attributed Word Error Rate (SA-WER)**: Computed using `jiwer`. Did we get the word right, AND was it attributed to the correct virtual microphone?
    *   **Latency**: Time difference between the end of a spoken word in the simulation and the `CaptionEvent` arriving over WebSocket.
4.  **Baselines for Comparison**:
    *   *Naive Mix*: Simply averaging all 4 audio streams before ASR.
    *   *Single Best Mic*: Running ASR on only one of the microphones.
    *   *Our System*: Should beat both by dynamically selecting the clearest signal.
