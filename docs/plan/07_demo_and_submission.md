# Demo and Submission Plan

## Demo Script (3 Minutes)
1.  **[0:00-0:30] The Problem:** Explain that single-mic setups fail in noisy rooms. The judges are shown a slide of the `pyroomacoustics` scenario.
2.  **[0:30-1:30] The Virtual Demo:** Switch to the live dashboard. Spawn 4 Virtual Participants reading an overlapping LibriSpeech script. Show the UI displaying interleaved captions with correct speaker attribution.
3.  **[1:30-2:00] The Physical Proof:** Play the pre-recorded video of the Lead in a room with 4 phones. The Lead talks, then walks across the room to another phone and talks. Show the UI correctly attributing the speech to the closest phone in real-time.
4.  **[2:00-2:30] Fault Tolerance:** In the live dashboard, trigger a "network drop" on one Virtual Participant for 10 seconds. Show that they buffer, reconnect, and the server receives their missed audio without dropping captions.
5.  **[2:30-3:00] Evaluation Results:** Show the SA-WER graph comparing our Fusion method against the Naive Mix and Single Mic baselines.

## Backup Plans
*   *Live Demo Fails:* Play the 3-minute fully pre-recorded video.
*   *ASR Fails:* Switch environment variable `ASR_ENGINE=mock`. The demo will play a hardcoded script seamlessly.

## Submission Checklist
- [x] GitHub Repo (Public) with MIT License ([LICENSE](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/LICENSE)).
- [x] README.md (Usage, Architecture diagram, Framing protocol, Evaluation, 3-minute demo guide) ([README.md](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/README.md)).
- [x] Automated 5-Stage Demo Script ([run_demo.py](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/run_demo.py)).
- [x] Slide Deck Markdown / Handout ([docs/presentation_deck.md](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/docs/presentation_deck.md)).
- [x] Evaluation Report & Benchmark Suite ([README.md#evaluation-results--benchmarks](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/README.md), [ws4_eval/eval_benchmark.py](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/ws4_eval/eval_benchmark.py)).
- [x] Containerization & Orchestration ([Dockerfile](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/Dockerfile), [docker-compose.yml](file:///d:/Arnav/BNB26_Kosmoskost_Internal_Round/docker-compose.yml)).
- [ ] 3-Minute Demo Video Recording / YouTube Link.

