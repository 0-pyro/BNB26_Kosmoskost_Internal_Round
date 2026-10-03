"""
Unit tests for frame selection logic (ws3_dsp/select.py).
"""

import math
import struct
import numpy as np
import pytest

from contracts.models import AudioFrameHeader
from ws3_dsp.select import compute_rms, select_loudest_frame


def test_compute_rms_array_and_bytes():
    """Verify RMS calculation for known waveforms and formats."""
    # Constant signal of amplitude 2.0 -> RMS = 2.0
    arr = np.array([2.0, -2.0, 2.0, -2.0], dtype=np.float32)
    assert pytest.approx(compute_rms(arr), rel=1e-5) == 2.0

    # Sine wave of amplitude A -> RMS = A / sqrt(2)
    A = 1.5
    t = np.linspace(0, 1, 1600, endpoint=False)
    sine = A * np.sin(2 * math.pi * 10 * t)
    assert pytest.approx(compute_rms(sine), rel=1e-2) == A / math.sqrt(2.0)

    # Empty and silence
    assert compute_rms(np.zeros(100)) == 0.0
    assert compute_rms([]) == 0.0
    assert compute_rms(b"") == 0.0

    # Bytes packing
    packed = struct.pack(">4f", 2.0, -2.0, 2.0, -2.0)
    assert pytest.approx(compute_rms(packed), rel=1e-5) == 2.0


def test_select_loudest_frame_tuples():
    """Given N audio frames with different amplitudes, select the loudest."""
    t = np.linspace(0, 0.1, 1600, endpoint=False)
    audio_quiet = 0.1 * np.sin(2 * math.pi * 440 * t)
    audio_loud = 0.9 * np.sin(2 * math.pi * 440 * t)
    audio_medium = 0.4 * np.sin(2 * math.pi * 440 * t)

    frames = [
        ("alice", audio_quiet),
        ("bob", audio_loud),
        ("charlie", audio_medium),
    ]

    selected_frame, winner_id = select_loudest_frame(frames)
    assert winner_id == "bob"
    assert selected_frame[0] == "bob"


def test_select_loudest_frame_binary_contracts():
    """Given binary frames with 16-byte header, select the loudest frame."""
    t = np.linspace(0, 0.1, 1600, endpoint=False)
    audio_low = 0.2 * np.sin(2 * math.pi * 440 * t)
    audio_high = 0.8 * np.sin(2 * math.pi * 440 * t)

    hdr1 = AudioFrameHeader(participant_id_hash=101, seq_num=1, capture_ts=1000)
    hdr2 = AudioFrameHeader(participant_id_hash=202, seq_num=1, capture_ts=1000)

    frame1 = hdr1.to_bytes() + struct.pack(f">{len(audio_low)}f", *audio_low)
    frame2 = hdr2.to_bytes() + struct.pack(f">{len(audio_high)}f", *audio_high)

    participant_map = {101: "Alice", 202: "Bob"}
    res = select_loudest_frame([frame1, frame2], participant_map=participant_map)

    assert res.speaker_id == "Bob"
    assert res.frame == frame2
    assert res.rms > 0.5


def test_select_loudest_frame_empty_raises():
    """Empty list should raise ValueError."""
    with pytest.raises(ValueError):
        select_loudest_frame([])


def test_select_loudest_frame_all_silent():
    """When all frames are silent, gracefully return the first frame."""
    f1 = ("p1", np.zeros(1600))
    f2 = ("p2", np.zeros(1600))
    res = select_loudest_frame([f1, f2])
    assert res.speaker_id == "p1"
    assert res.rms == 0.0
