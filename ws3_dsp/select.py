"""
Audio Frame Selection Logic for Multi-Device Fusion.

Given N audio frames from different participants for the same time window,
computes the RMS energy of each frame and outputs the frame with the highest
energy and its associated speaker_id.
"""

from __future__ import annotations

import math
import struct
from typing import Any, NamedTuple, Sequence, Union

import numpy as np

from contracts.models import AUDIO_HEADER_SIZE, AUDIO_MAGIC, AudioFrameHeader


class SelectedFrame(tuple):
    """Result of loudness-based frame selection: (frame, speaker_id).

    Supports unpacking as (frame, speaker_id) as well as attribute access
    via .frame, .speaker_id, and .rms.
    """

    frame: Any
    speaker_id: str
    rms: float

    def __new__(cls, frame: Any, speaker_id: str, rms: float = 0.0):
        obj = super().__new__(cls, (frame, speaker_id))
        obj.frame = frame
        obj.speaker_id = speaker_id
        obj.rms = rms
        return obj

    def __repr__(self) -> str:
        return f"SelectedFrame(frame={self.frame!r}, speaker_id={self.speaker_id!r}, rms={self.rms:.4f})"


def compute_rms(audio: Union[np.ndarray, Sequence[float], bytes]) -> float:
    """Compute Root Mean Square (RMS) energy of an audio frame.

    Supports numpy arrays, lists of float samples, or raw Float32 PCM bytes
    (with or without 16-byte header).
    """
    if isinstance(audio, bytes):
        if len(audio) >= AUDIO_HEADER_SIZE and audio[:2] == AUDIO_MAGIC:
            payload = audio[AUDIO_HEADER_SIZE:]
        else:
            payload = audio
        n_floats = len(payload) // 4
        if n_floats == 0:
            return 0.0
        try:
            samples = struct.unpack(f">{n_floats}f", payload[: n_floats * 4])
        except struct.error:
            samples = struct.unpack(f"<{n_floats}f", payload[: n_floats * 4])
        arr = np.asarray(samples, dtype=np.float64)
    else:
        arr = np.asarray(audio, dtype=np.float64)
        if arr.ndim > 1:
            arr = arr.flatten()

    if arr.size == 0:
        return 0.0

    mean_sq = float(np.mean(arr ** 2))
    return math.sqrt(mean_sq) if mean_sq > 0.0 else 0.0


def _extract_frame_and_speaker(
    item: Any,
    participant_map: dict[int, str] | None = None,
) -> tuple[Any, str, Union[np.ndarray, Sequence[float], bytes]]:
    """Extract (frame_obj, speaker_id, audio_samples) from various input formats."""
    # 1. Raw binary audio frame (bytes)
    if isinstance(item, bytes):
        speaker_id = "unknown"
        if len(item) >= AUDIO_HEADER_SIZE and item[:2] == AUDIO_MAGIC:
            try:
                hdr = AudioFrameHeader.from_bytes(item)
                if participant_map and hdr.participant_id_hash in participant_map:
                    speaker_id = participant_map[hdr.participant_id_hash]
                else:
                    speaker_id = f"p_{hdr.participant_id_hash}"
            except Exception:
                pass
        return item, speaker_id, item

    # 2. Tuple / list: (speaker_id, audio) or (speaker_id, frame, audio)
    if isinstance(item, (tuple, list)):
        if len(item) == 2:
            speaker_id = str(item[0])
            audio = item[1]
            return item, speaker_id, audio
        elif len(item) >= 3:
            speaker_id = str(item[0])
            frame = item[1]
            audio = item[2]
            return frame, speaker_id, audio

    # 3. Dict: {"speaker_id": ..., "audio": ...} or similar
    if isinstance(item, dict):
        speaker_id = str(
            item.get("speaker_id")
            or item.get("participant_id")
            or item.get("speaker")
            or "unknown"
        )
        audio = item.get("audio") or item.get("data") or item.get("payload") or item.get("frame")
        return item, speaker_id, audio

    # 4. Object with speaker_id / participant_id and audio attributes
    speaker_id = getattr(
        item,
        "speaker_id",
        getattr(item, "participant_id", "unknown"),
    )
    audio = getattr(
        item,
        "audio",
        getattr(item, "payload", getattr(item, "frame", getattr(item, "data", item))),
    )
    return item, str(speaker_id), audio


def select_loudest_frame(
    frames: Sequence[Any],
    participant_map: dict[int, str] | None = None,
) -> SelectedFrame:
    """Select the audio frame with the highest RMS energy among N candidate frames.

    Parameters
    ----------
    frames : Sequence[Any]
        A collection of frames for the same aligned time window.
        Supported formats per item:
          - (speaker_id, audio_samples_or_bytes)
          - Raw binary frame bytes with 16-byte header
          - Dict {"speaker_id": ..., "audio": ...}
          - Custom frame object with .speaker_id and .audio attributes
    participant_map : dict[int, str], optional
        Mapping from UInt16 participant_id_hash to speaker_id string
        when raw binary frames are used.

    Returns
    -------
    SelectedFrame
        NamedTuple (frame, speaker_id, rms).
        Unpacks directly as (frame, speaker_id) or (frame, speaker_id, rms).

    Raises
    ------
    ValueError
        If frames is empty.
    """
    if not frames:
        raise ValueError("Cannot select from empty frames list")

    best_item = None
    best_speaker_id = ""
    max_rms = -1.0

    for item in frames:
        frame_obj, speaker_id, audio = _extract_frame_and_speaker(item, participant_map)
        rms = compute_rms(audio)
        if rms > max_rms:
            max_rms = rms
            best_item = frame_obj
            best_speaker_id = speaker_id

    if best_item is None:
        best_item = frames[0]
        _, best_speaker_id, _ = _extract_frame_and_speaker(best_item, participant_map)
        max_rms = 0.0

    return SelectedFrame(frame=best_item, speaker_id=best_speaker_id, rms=max_rms)
