"""
ASR Cloud Client for Roundtable.

Integrates with Groq Whisper and AssemblyAI real-time streaming APIs to transcribe
audio streams and parse returning JSON data into validated CaptionEvent contract models.

Resilient to network timeouts and connection drops with silent exponential-backoff retries.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import struct
import sys
import time
import uuid
import wave
from typing import AsyncIterator, List, Literal, Optional, Sequence, Union

import httpx
import numpy as np
import websockets

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts.models import (
    AUDIO_HEADER_SIZE,
    AUDIO_MAGIC,
    AudioFrameHeader,
    CaptionEvent,
)

from ws3_dsp.select import decode_float32_payload

logger = logging.getLogger("asr_client")

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
ASSEMBLYAI_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws"


def audio_to_wav_bytes(
    audio: Union[np.ndarray, Sequence[float], bytes],
    sample_rate: int = 16000,
) -> bytes:
    """Convert audio input (float samples, float array, or Float32/Int16 PCM bytes) to WAV bytes."""
    # If already a valid WAV (starts with RIFF), return as is
    if isinstance(audio, bytes) and len(audio) > 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
        return audio

    if isinstance(audio, bytes):
        # Strip Roundtable 16-byte header if present
        if len(audio) >= AUDIO_HEADER_SIZE and audio[:2] == AUDIO_MAGIC:
            frame_len = AUDIO_HEADER_SIZE + (1600 * 4)  # 6416 bytes
            if len(audio) >= frame_len and len(audio) % frame_len == 0:
                payloads = [audio[i + AUDIO_HEADER_SIZE : i + frame_len] for i in range(0, len(audio), frame_len)]
                payload = b"".join(payloads)
            else:
                payload = audio[AUDIO_HEADER_SIZE:]
        else:
            payload = audio
        float_arr = decode_float32_payload(payload)
    else:
        float_arr = np.asarray(audio, dtype=np.float32)
        if float_arr.ndim > 1:
            float_arr = float_arr.flatten()

    # Clip to [-1.0, 1.0] and convert to 16-bit signed PCM
    clipped = np.clip(float_arr, -1.0, 1.0)
    int16_samples = (clipped * 32767.0).astype(np.int16)

    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())
    return bio.getvalue()


def audio_to_pcm16_bytes(
    audio: Union[np.ndarray, Sequence[float], bytes],
) -> bytes:
    """Convert audio input to raw 16-bit mono signed PCM bytes (little-endian)."""
    if isinstance(audio, bytes):
        if len(audio) >= AUDIO_HEADER_SIZE and audio[:2] == AUDIO_MAGIC:
            payload = audio[AUDIO_HEADER_SIZE:]
        else:
            payload = audio
        float_arr = decode_float32_payload(payload)
    else:
        float_arr = np.asarray(audio, dtype=np.float32)
        if float_arr.ndim > 1:
            float_arr = float_arr.flatten()

    clipped = np.clip(float_arr, -1.0, 1.0)
    int16_samples = (clipped * 32767.0).astype("<h")
    return int16_samples.tobytes()


def _is_likely_hallucination(text: str) -> bool:
    """Detect common Whisper hallucinations triggered by background noise, clicks, or silence."""
    clean = text.lower().strip(" .?!,")
    if not clean:
        return True
    if not any(c.isalpha() for c in clean):
        return True
    known_hallucinations = {
        "thank you", "thank you very much", "all right", "okay", "oh", "hello there",
        "you", "bye", "amara.org", "subs by", "text text text images",
        "camera on the way to come", "that list", "it's just not how they want making yourself fit",
    }
    if clean in known_hallucinations:
        return True
    words = clean.split()
    # If 3 or more repeated identical words (e.g. "text text text")
    if len(words) >= 3 and len(set(words)) == 1:
        return True
    return False


class ASRClient:
    """Client for Groq Whisper and AssemblyAI ASR services.

    Handles continuous audio streaming, JSON response parsing to CaptionEvent,
    and automatic silent retry on timeout/network failure.
    """

    def __init__(
        self,
        engine: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "whisper-large-v3-turbo",
        sample_rate: int = 16000,
        timeout_s: float = 8.0,
        max_retries: int = 3,
        retry_backoff_s: float = 0.5,
    ):
        self.engine = (
            engine
            or os.getenv("ASR_ENGINE")
            or ("groq" if os.getenv("GROQ_API_KEY") else "mock")
        ).lower()
        self.model = model
        self.sample_rate = sample_rate
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s

        if self.engine == "groq":
            self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        elif self.engine == "assemblyai":
            self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY", "")
        else:
            self.api_key = api_key or ""

        self._segment_counter = 0

    def _next_segment_id(self) -> str:
        self._segment_counter += 1
        return f"seg_{self._segment_counter}_{uuid.uuid4().hex[:6]}"

    async def transcribe_chunk(
        self,
        audio_data: Union[np.ndarray, Sequence[float], bytes],
        speaker_id: str = "speaker_unknown",
        speaker_name: str = "",
        start_ts: int = 0,
    ) -> List[CaptionEvent]:
        """Transcribe a chunk of audio, returning a list of CaptionEvent objects.

        Retries silently on timeouts without crashing.
        """
        if self.engine == "mock" or not self.api_key:
            return self._mock_transcribe(speaker_id, speaker_name, start_ts)

        if self.engine == "groq":
            return await self._transcribe_groq_with_retry(
                audio_data, speaker_id, speaker_name, start_ts
            )
        elif self.engine == "assemblyai":
            # For one-off chunks with AssemblyAI, fallback to mock or REST
            return self._mock_transcribe(speaker_id, speaker_name, start_ts)
        else:
            return self._mock_transcribe(speaker_id, speaker_name, start_ts)

    def _mock_transcribe(
        self, speaker_id: str, speaker_name: str, start_ts: int
    ) -> List[CaptionEvent]:
        """Generate simulated CaptionEvent objects for testing / offline mode."""
        now_ms = int(time.time() * 1000)
        s_ts = start_ts if start_ts > 0 else now_ms - 1000
        event = CaptionEvent(
            segment_id=self._next_segment_id(),
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            start_ts=s_ts,
            end_ts=s_ts + 1000,
            text="Simulated transcription output.",
            is_final=True,
            revision=1,
        )
        return [event]

    async def _transcribe_groq_with_retry(
        self,
        audio_data: Union[np.ndarray, Sequence[float], bytes],
        speaker_id: str,
        speaker_name: str,
        start_ts: int,
    ) -> List[CaptionEvent]:
        """Send audio to Groq Whisper API with silent retry on timeout."""
        wav_bytes = audio_to_wav_bytes(audio_data, self.sample_rate)
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    files = {
                        "file": ("audio.wav", wav_bytes, "audio/wav"),
                    }
                    data = {
                        "model": self.model,
                        "response_format": "verbose_json",
                        "language": "en",
                    }
                    response = await client.post(
                        GROQ_TRANSCRIPTION_URL,
                        headers=headers,
                        files=files,
                        data=data,
                    )

                if response.status_code == 200:
                    result = response.json()
                    return self._parse_groq_response(
                        result, speaker_id, speaker_name, start_ts
                    )
                elif response.status_code == 429:
                    logger.warning(
                        "Groq ASR rate limited (HTTP 429). Cooling down for 3.5s (attempt %d/%d)...",
                        attempt,
                        self.max_retries,
                    )
                    await asyncio.sleep(3.5)
                    continue
                else:
                    logger.warning(
                        "Groq ASR returned HTTP %d: %s (attempt %d/%d)",
                        response.status_code,
                        response.text,
                        attempt,
                        self.max_retries,
                    )
            except (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError) as ex:
                # Edge case requirement: ASR API timeouts must not crash the system; retry silently.
                logger.debug(
                    "Groq API timeout on attempt %d/%d: %s. Retrying silently...",
                    attempt,
                    self.max_retries,
                    ex,
                )
            except Exception as ex:
                logger.debug(
                    "Network error during Groq ASR call (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    ex,
                )

            # Backoff before retry
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_backoff_s * (2 ** (attempt - 1)))

        logger.warning(
            "Groq ASR failed after %d retries. Falling back silently.", self.max_retries
        )
        return []

    def _parse_groq_response(
        self,
        data: dict,
        speaker_id: str,
        speaker_name: str,
        start_ts: int,
    ) -> List[CaptionEvent]:
        """Parse Groq verbose_json or standard json response into CaptionEvent objects."""
        events: List[CaptionEvent] = []
        segments = data.get("segments")

        if segments and isinstance(segments, list):
            for seg in segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                    
                if _is_likely_hallucination(text):
                    logger.debug("Filtered out likely hallucination: '%s'", text)
                    continue

                seg_start_s = float(seg.get("start", 0.0))
                seg_end_s = float(seg.get("end", seg_start_s + 1.0))
                event = CaptionEvent(
                    segment_id=self._next_segment_id(),
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    start_ts=start_ts + int(seg_start_s * 1000),
                    end_ts=start_ts + int(seg_end_s * 1000),
                    text=text,
                    is_final=True,
                    revision=1,
                )
                events.append(event)
        else:
            full_text = data.get("text", "").strip()
            if full_text:
                if _is_likely_hallucination(full_text):
                    logger.debug("Filtered out likely hallucination: '%s'", full_text)
                    return events
                    
                duration_s = float(data.get("duration", 1.0))
                event = CaptionEvent(
                    segment_id=self._next_segment_id(),
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    start_ts=start_ts,
                    end_ts=start_ts + int(duration_s * 1000),
                    text=full_text,
                    is_final=True,
                    revision=1,
                )
                events.append(event)

        return events

    def parse_assemblyai_message(
        self,
        raw_msg: Union[str, dict],
        speaker_id: str = "speaker_unknown",
        speaker_name: str = "",
    ) -> Optional[CaptionEvent]:
        """Parse an AssemblyAI real-time WebSocket JSON message into a CaptionEvent."""
        if isinstance(raw_msg, str):
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                return None
        else:
            data = raw_msg

        msg_type = data.get("message_type")
        if msg_type not in ("PartialTranscript", "FinalTranscript"):
            return None

        text = data.get("text", "").strip()
        if not text:
            return None

        audio_start = data.get("audio_start", 0)
        audio_end = data.get("audio_end", audio_start)
        is_final = msg_type == "FinalTranscript"

        return CaptionEvent(
            segment_id=self._next_segment_id(),
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            start_ts=audio_start,
            end_ts=audio_end,
            text=text,
            is_final=is_final,
            revision=1,
        )

    async def stream_audio_assemblyai(
        self,
        audio_stream: AsyncIterator[Union[np.ndarray, bytes]],
        speaker_id: str = "speaker_unknown",
        speaker_name: str = "",
    ) -> AsyncIterator[CaptionEvent]:
        """Stream continuous audio to AssemblyAI WebSocket and yield CaptionEvents.

        Automatically handles reconnection and silent timeout recovery.
        """
        if not self.api_key:
            logger.warning("No AssemblyAI API key provided; falling back to mock stream.")
            async for chunk in audio_stream:
                for ev in self._mock_transcribe(speaker_id, speaker_name, int(time.time() * 1000)):
                    yield ev
            return

        ws_url = f"{ASSEMBLYAI_WS_URL}?sample_rate={self.sample_rate}"
        headers = {"Authorization": self.api_key}

        for attempt in range(1, self.max_retries + 1):
            try:
                async with websockets.connect(
                    ws_url, additional_headers=headers
                ) as ws:
                    # Sender task
                    async def send_loop():
                        try:
                            async for chunk in audio_stream:
                                pcm_bytes = audio_to_pcm16_bytes(chunk)
                                b64 = base64.b64encode(pcm_bytes).decode("utf-8")
                                msg = json.dumps({"audio_data": b64})
                                await ws.send(msg)
                            await ws.send(json.dumps({"terminate_session": True}))
                        except Exception as e:
                            logger.debug("Error in send_loop: %s", e)

                    sender = asyncio.create_task(send_loop())

                    try:
                        async for raw_msg in ws:
                            event = self.parse_assemblyai_message(
                                raw_msg, speaker_id, speaker_name
                            )
                            if event is not None:
                                yield event
                    finally:
                        sender.cancel()
                return
            except (asyncio.TimeoutError, TimeoutError, websockets.ConnectionClosed) as ex:
                logger.debug(
                    "AssemblyAI stream timeout/drop (attempt %d/%d): %s. Retrying...",
                    attempt,
                    self.max_retries,
                    ex,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff_s * attempt)

        logger.warning("AssemblyAI streaming terminated after retries.")

    async def stream_audio_groq(
        self,
        audio_stream: AsyncIterator[Union[np.ndarray, bytes]],
        speaker_id: str = "speaker_unknown",
        speaker_name: str = "",
        buffer_duration_s: float = 2.0,
    ) -> AsyncIterator[CaptionEvent]:
        """Stream continuous audio to Groq Whisper by accumulating audio frames.

        Periodically dispatches accumulated frames to the transcription endpoint
        and yields CaptionEvents.
        """
        buffer_samples: List[float] = []
        samples_target = int(self.sample_rate * buffer_duration_s)
        session_start_ms = int(time.time() * 1000)
        accumulated_ms = 0

        async for chunk in audio_stream:
            # Convert chunk to float samples
            if isinstance(chunk, bytes):
                if len(chunk) >= AUDIO_HEADER_SIZE and chunk[:2] == AUDIO_MAGIC:
                    payload = chunk[AUDIO_HEADER_SIZE:]
                else:
                    payload = chunk
                n_floats = len(payload) // 4
                try:
                    samples = struct.unpack(f">{n_floats}f", payload[: n_floats * 4])
                except struct.error:
                    samples = struct.unpack(f"<{n_floats}f", payload[: n_floats * 4])
                buffer_samples.extend(samples)
            else:
                arr = np.asarray(chunk, dtype=np.float32).flatten()
                buffer_samples.extend(arr.tolist())

            if len(buffer_samples) >= samples_target:
                chunk_to_send = buffer_samples[:samples_target]
                buffer_samples = buffer_samples[samples_target:]

                events = await self.transcribe_chunk(
                    chunk_to_send,
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    start_ts=session_start_ms + accumulated_ms,
                )
                accumulated_ms += int(buffer_duration_s * 1000)
                for ev in events:
                    yield ev

        # Flush remaining buffer if sufficient length
        if len(buffer_samples) >= int(self.sample_rate * 0.3):
            events = await self.transcribe_chunk(
                buffer_samples,
                speaker_id=speaker_id,
                speaker_name=speaker_name,
                start_ts=session_start_ms + accumulated_ms,
            )
            for ev in events:
                yield ev
