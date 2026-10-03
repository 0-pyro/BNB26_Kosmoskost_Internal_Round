"""
Unit tests for GCC-PHAT audio alignment (ws3_dsp/align.py).
"""

import math
import struct
import numpy as np
import pytest

from ws3_dsp.align import gcc_phat


@pytest.fixture
def sample_rate():
    return 16000


@pytest.fixture
def frame_samples(sample_rate):
    # 100ms at 16kHz
    return int(sample_rate * 0.1)


def generate_sine_array(freq: float, duration_s: float, fs: int = 16000) -> np.ndarray:
    """Generate a continuous sine wave array."""
    n_samples = int(fs * duration_s)
    t = np.arange(n_samples) / fs
    return np.sin(2.0 * math.pi * freq * t)


def test_align_synthetically_shifted_sine_waves(sample_rate, frame_samples):
    """GCC-PHAT must recover the exact offset between two synthetically shifted sine waves."""
    freq = 440.0
    # Generate continuous tone
    full_sine = generate_sine_array(freq, duration_s=1.0, fs=sample_rate)

    base_idx = 200
    ref = full_sine[base_idx : base_idx + frame_samples]

    # For 440 Hz at 16 kHz, T ≈ 36.36 samples.
    # Shifts within ±17 samples represent unique delay phases without cyclic ambiguity.
    test_offsets = [-16, -12, -7, -3, -1, 0, 1, 4, 8, 12, 15]

    for offset in test_offsets:
        sig = full_sine[base_idx + offset : base_idx + offset + frame_samples]
        recovered = gcc_phat(sig, ref, fs=sample_rate)
        assert recovered == offset, f"Expected offset {offset}, got {recovered}"


def test_align_silent_audio_fallback_to_zero(sample_rate, frame_samples):
    """GCC-PHAT must catch silent audio and fallback to 0 offset."""
    sine = generate_sine_array(440.0, 0.2, fs=sample_rate)[:frame_samples]
    silent = np.zeros(frame_samples, dtype=np.float64)

    # Sig is silent
    assert gcc_phat(silent, sine, fs=sample_rate) == 0

    # Ref is silent
    assert gcc_phat(sine, silent, fs=sample_rate) == 0

    # Both silent
    assert gcc_phat(silent, silent, fs=sample_rate) == 0

    # Near-zero noise
    near_zero = np.random.normal(0, 1e-8, size=frame_samples)
    assert gcc_phat(near_zero, sine, fs=sample_rate) == 0


def test_align_broadband_signal_recovery(sample_rate, frame_samples):
    """GCC-PHAT must accurately recover delays for complex broadband/noise signals."""
    np.random.seed(12345)
    full_signal = np.random.randn(sample_rate)  # 1 second of noise

    base_idx = 2000
    ref = full_signal[base_idx : base_idx + frame_samples]

    test_offsets = [-150, -75, -20, 0, 15, 60, 120]
    for offset in test_offsets:
        sig = full_signal[base_idx + offset : base_idx + offset + frame_samples]
        recovered = gcc_phat(sig, ref, fs=sample_rate)
        assert recovered == offset, f"Broadband expected offset {offset}, got {recovered}"


def test_align_with_binary_audio_bytes(sample_rate, frame_samples):
    """GCC-PHAT should accept raw Float32 PCM bytes with contracts header."""
    full_sine = generate_sine_array(440.0, 1.0, fs=sample_rate)
    base_idx = 300
    offset = 9

    ref_floats = full_sine[base_idx : base_idx + frame_samples]
    sig_floats = full_sine[base_idx + offset : base_idx + offset + frame_samples]

    # Pack as big-endian float32 with 16-byte header
    hdr_bytes = b"\xAA\xBB" + b"\x00" * 14
    ref_bytes = hdr_bytes + struct.pack(f">{frame_samples}f", *ref_floats)
    sig_bytes = hdr_bytes + struct.pack(f">{frame_samples}f", *sig_floats)

    recovered = gcc_phat(sig_bytes, ref_bytes, fs=sample_rate)
    assert recovered == offset


def test_align_empty_or_degenerate_inputs():
    """Empty inputs should gracefully return 0 offset without throwing errors."""
    assert gcc_phat([], []) == 0
    assert gcc_phat(np.array([]), np.array([])) == 0
    assert gcc_phat(b"", b"") == 0


def test_align_max_delay_constraint(sample_rate, frame_samples):
    """GCC-PHAT respects max_delay bounds."""
    full_sine = generate_sine_array(440.0, 1.0, fs=sample_rate)
    base_idx = 200
    offset = 5
    ref = full_sine[base_idx : base_idx + frame_samples]
    sig = full_sine[base_idx + offset : base_idx + offset + frame_samples]

    # With max_delay >= 5, recovers 5
    assert gcc_phat(sig, ref, max_delay=10) == 5

    # With max_delay < 5 (e.g. 3), cannot pick 5
    res = gcc_phat(sig, ref, max_delay=3)
    assert abs(res) <= 3
