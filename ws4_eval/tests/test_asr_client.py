"""
Unit tests for ASR client integration and timeout resilience (ws4_eval/asr_client.py).
"""

import asyncio
import json
import numpy as np
import pytest
import httpx

from contracts.models import CaptionEvent
from ws4_eval.asr_client import (
    ASRClient,
    audio_to_pcm16_bytes,
    audio_to_wav_bytes,
)


@pytest.fixture
def mock_asr_client():
    return ASRClient(engine="mock", api_key="dummy_key")


def test_audio_to_wav_bytes_conversion():
    """Verify audio_to_wav_bytes creates valid RIFF/WAVE header and data."""
    samples = np.array([0.0, 0.5, -0.5, 1.0], dtype=np.float32)
    wav_bytes = audio_to_wav_bytes(samples, sample_rate=16000)

    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:12]
    assert b"fmt " in wav_bytes
    assert b"data" in wav_bytes


def test_audio_to_pcm16_bytes_conversion():
    """Verify audio_to_pcm16_bytes converts float samples to 16-bit PCM."""
    samples = np.array([0.0, 1.0, -1.0], dtype=np.float32)
    pcm_bytes = audio_to_pcm16_bytes(samples)
    assert len(pcm_bytes) == len(samples) * 2


def test_parse_groq_verbose_json():
    """Verify parsing Groq Whisper verbose_json into CaptionEvents."""
    client = ASRClient(engine="groq", api_key="test_key")
    sample_response = {
        "text": "Hello world. This is Roundtable.",
        "segments": [
            {"id": 0, "start": 0.0, "end": 1.2, "text": "Hello world."},
            {"id": 1, "start": 1.3, "end": 2.5, "text": "This is Roundtable."},
        ],
    }

    events = client._parse_groq_response(
        sample_response,
        speaker_id="alice",
        speaker_name="Alice",
        start_ts=1000,
    )

    assert len(events) == 2
    assert all(isinstance(e, CaptionEvent) for e in events)
    assert events[0].speaker_id == "alice"
    assert events[0].speaker_name == "Alice"
    assert events[0].text == "Hello world."
    assert events[0].start_ts == 1000
    assert events[0].end_ts == 2200
    assert events[0].is_final is True


def test_parse_assemblyai_partial_and_final():
    """Verify parsing AssemblyAI real-time WebSocket JSON into CaptionEvents."""
    client = ASRClient(engine="assemblyai", api_key="test_key")

    partial_json = json.dumps({
        "message_type": "PartialTranscript",
        "text": "Antigravity captioning",
        "audio_start": 500,
        "audio_end": 1200,
    })
    final_json = json.dumps({
        "message_type": "FinalTranscript",
        "text": "Antigravity captioning system.",
        "audio_start": 500,
        "audio_end": 1800,
        "confidence": 0.98,
    })

    part_ev = client.parse_assemblyai_message(partial_json, speaker_id="bob", speaker_name="Bob")
    assert part_ev is not None
    assert part_ev.is_final is False
    assert part_ev.text == "Antigravity captioning"
    assert part_ev.speaker_id == "bob"

    final_ev = client.parse_assemblyai_message(final_json, speaker_id="bob", speaker_name="Bob")
    assert final_ev is not None
    assert final_ev.is_final is True
    assert final_ev.text == "Antigravity captioning system."


@pytest.mark.asyncio
async def test_asr_timeout_silent_retry(monkeypatch):
    """ASR API timeouts must not crash the system; retry silently and return graceful fallback."""
    client = ASRClient(
        engine="groq",
        api_key="mock_key",
        timeout_s=0.1,
        max_retries=2,
        retry_backoff_s=0.01,
    )

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ReadTimeout("Request timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    audio_chunk = np.zeros(1600, dtype=np.float32)
    # Must not raise an exception; should return empty list or fallback
    events = await client.transcribe_chunk(audio_chunk, speaker_id="test_speaker")
    assert events == []
    assert call_count == 2  # Proves silent retries took place


@pytest.mark.asyncio
async def test_mock_transcribe_stream():
    """Verify mock transcription stream yields valid CaptionEvents."""
    client = ASRClient(engine="mock")

    async def mock_audio_stream():
        for _ in range(3):
            yield np.zeros(1600, dtype=np.float32)

    events = []
    async for ev in client.stream_audio_groq(mock_audio_stream(), speaker_id="speaker_1", buffer_duration_s=0.1):
        events.append(ev)

    assert len(events) >= 1
    assert all(isinstance(e, CaptionEvent) for e in events)
