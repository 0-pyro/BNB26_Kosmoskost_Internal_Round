# Requirements Traceability

## Key Features Mapping

| ID | Description | Component | Tests | Owner |
|---|---|---|---|---|
| **REQ-1** | **Multi-Device Conversation**: System must accept connections from multiple clients to a shared session room. | WS1 (Backend) | Client can join room; server routes to correct room. | WS1 |
| **REQ-2** | **Audio Coordination**: System aligns audio from multiple clients into a shared timeline. | WS3 (DSP) | GCC-PHAT recovers known offset within 20ms. | WS3 |
| **REQ-3** | **Speaker Identification**: Attribute speech based on the loudest device. | WS3 (DSP) | Simulated room assigns correct ID 90% of time. | WS3 |
| **REQ-4** | **Noise & Overlap Handling**: UI renders overlapping speech correctly. ASR transcribes simultaneously (if supported, otherwise gracefully interleaved). | WS2, WS4 | UI overlap test; Virtual participant overlap test. | WS2, WS4 |
| **REQ-5** | **Low-Latency Captions**: Time-to-first-partial < 1500ms. | WS4 (ASR), UI | Latency dashboard shows <1.5s p95. | WS4 |
| **REQ-6** | **Session Continuity**: Disconnected clients buffer up to 60s of audio and reconnect without history loss. | WS1, WS2 | Reconnect test (simulate 10s drop). | WS1, WS2 |
| **REQ-7** | **Evaluation**: System can be evaluated automatically using pyroomacoustics and SA-WER metrics. | WS4 (Eval) | Eval suite runs end-to-end and outputs report. | WS4 |
| **REQ-8** | **Device Quirks**: Capture 16kHz audio from Safari/Chrome without sleeping. | WS2 (Client) | Wake Lock test, AudioWorklet format test. | WS2 |

*Note: As this is a 24-hour hackathon, REQ-4 (true overlap separation) is limited to UI handling and ASR's native capability. We are not doing source separation.*
