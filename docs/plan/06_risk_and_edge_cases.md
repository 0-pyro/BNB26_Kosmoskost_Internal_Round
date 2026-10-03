# Risk and Edge Cases

## Risk Register
| ID | Description | Likelihood | Impact | Mitigation | Contingency | Owner |
|---|---|---|---|---|---|---|
| RISK-1 | Groq ASR rate limits / blocks us. | Medium | High | Use only 1 fused stream. Keep payload small. | Switch to Mock ASR for demo. | WS4 |
| RISK-2 | iOS Safari kills audio on lock. | High | High | Use Wake Lock API to prevent lock. | Inform users not to lock phones. | WS2 |
| RISK-3 | GCC-PHAT in Python is too slow for 100ms frames. | Medium | Medium | Profile early (SPK-3). | Fallback to no-alignment (rely on network jitter buffer only). | WS3 |
| RISK-4 | Venue Wi-Fi drops WebSockets randomly. | High | High | 60s client-side buffer. | Demo on private hotspot or VPS. | WS1, WS2 |
| RISK-5 | Distributed team cannot test room fusion. | High | High | Virtual Participant architecture. | Pre-recorded demo. | Lead |

## Edge Case Catalogue
*   **WS1 (Backend):**
    *   *Late Joiner:* Send historical `FINAL` captions.
    *   *Two tabs, same name:* Append `(1)` to name or hash ID.
*   **WS2 (Client):**
    *   *User denies mic permission:* Show clear error UI with retry button.
    *   *Bluetooth disconnects:* Browser swaps mic. Re-init AudioWorklet.
*   **WS3 (DSP):**
    *   *Absolute Silence:* VAD should prevent sending empty frames to ASR to save quota.
    *   *Someone coughs loudly near a phone:* Selection algorithm might briefly pick that mic, causing a garbage caption. Filter out very short spikes.
*   **WS4 (ASR):**
    *   *ASR returns text out of order:* Backend uses segment timestamps, not arrival time, to order history.

## Lens-Coverage Matrix
| Lens | WS1 (Backend) | WS2 (Client) | WS3 (DSP) | WS4 (ASR/Eval) |
|---|---|---|---|---|
| Functional | Room routing | AudioWorklet, UI | Align, SNR | Groq REST, pyroom |
| Latency | WSS async IO | 100ms framing | Fast GCC-PHAT | Streaming partials |
| Recovery | Handle WS drop | 60s buffer, retry | Handle missing frames | Mock fallback |
| Resources | 5MB per room | Wake Lock | <50ms CPU budget | API quotas |
| Security | WSS/HTTPS | getUserMedia secure | N/A (Internal) | No logging audio |
| Browser | N/A | Chrome/Safari Audio | N/A | N/A |
