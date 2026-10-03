"""
Audio Alignment via Generalized Cross-Correlation with Phase Transform (GCC-PHAT).

Provides delay estimation between audio chunks (e.g., 100ms frames at 16kHz)
to synchronize multi-device capture streams in Roundtable.
"""

from __future__ import annotations

import struct
from typing import Sequence, Union

import numpy as np
from scipy import fft, signal


def _to_float_array(audio: Union[np.ndarray, Sequence[float], bytes]) -> np.ndarray:
    """Convert input audio (ndarray, list, or Float32 bytes) to a 1D float64 array."""
    if isinstance(audio, bytes):
        # Check if it has 16-byte header
        if len(audio) >= 16 and audio[:2] == b"\xAA\xBB":
            payload = audio[16:]
        else:
            payload = audio
        n_floats = len(payload) // 4
        # Contracts specify big-endian Float32: ">...f"
        # We also check native float32 fallback if big-endian is not packed
        try:
            samples = struct.unpack(f">{n_floats}f", payload[: n_floats * 4])
        except struct.error:
            samples = struct.unpack(f"<{n_floats}f", payload[: n_floats * 4])
        return np.asarray(samples, dtype=np.float64)

    arr = np.asarray(audio, dtype=np.float64)
    if arr.ndim > 1:
        arr = arr.flatten()
    return arr


def gcc_phat(
    sig: Union[np.ndarray, Sequence[float], bytes],
    refsig: Union[np.ndarray, Sequence[float], bytes],
    fs: int = 16000,
    max_delay: int | None = None,
    alpha: float = 0.1,
) -> int:
    """Compute the sample delay between two audio chunks using GCC-PHAT.

    Parameters
    ----------
    sig : array-like or bytes
        The target audio signal (e.g., 100ms chunk, 1600 samples at 16kHz).
    refsig : array-like or bytes
        The reference audio signal.
    fs : int, optional
        Sampling frequency in Hz (default: 16000).
    max_delay : int, optional
        Maximum allowable delay in samples (searched symmetrically in [-max_delay, max_delay]).
    alpha : float, optional
        Tukey window shape parameter (0.0 to disable windowing, default: 0.1)
        used to taper frame boundaries and minimize spectral leakage.

    Returns
    -------
    int
        The estimated sample delay D such that sig[n] ≈ refsig[n - D].
        - Positive value: sig is delayed relative to refsig (arrives later).
        - Negative value: sig is advanced relative to refsig (arrives earlier).
        - 0: aligned, or audio is silent / below noise threshold.
    """
    x1 = _to_float_array(sig)
    x2 = _to_float_array(refsig)

    n1 = len(x1)
    n2 = len(x2)

    # Empty chunks or invalid input fallback to 0
    if n1 == 0 or n2 == 0:
        return 0

    # Silence check: if audio is completely silent or negligible energy, fallback to 0 offset
    energy1 = np.max(np.abs(x1))
    energy2 = np.max(np.abs(x2))
    if energy1 < 1e-6 or energy2 < 1e-6:
        return 0

    # Apply windowing to mitigate edge discontinuity effects in short chunks
    if alpha > 0.0:
        w1 = signal.windows.tukey(n1, alpha=alpha)
        w2 = signal.windows.tukey(n2, alpha=alpha)
        x1_w = x1 * w1
        x2_w = x2 * w2
    else:
        x1_w = x1
        x2_w = x2

    # Linear cross-correlation via zero padding
    n_conv = n1 + n2 - 1

    # Compute FFT using scipy.fft
    X1 = fft.rfft(x1_w, n=n_conv)
    X2 = fft.rfft(x2_w, n=n_conv)

    # Cross-power spectrum
    R = X1 * np.conj(X2)
    mag = np.abs(R)
    max_mag = np.max(mag)

    if max_mag < 1e-12:
        return 0

    # PHAT weighting with spectral noise floor thresholding
    # This prevents division-by-zero on pure sine tones and low-energy bands
    threshold = 0.005 * max_mag
    mask = mag > threshold
    R_phat = np.zeros_like(R, dtype=np.complex128)
    R_phat[mask] = R[mask] / mag[mask]

    # Inverse FFT to get generalized cross-correlation
    cc = fft.irfft(R_phat, n=n_conv)

    # Map FFT output indices to physical lags:
    # Index 0..n1-1 corresponds to lag 0..n1-1 (sig delayed relative to ref)
    # Index n_conv-(n2-1)..n_conv-1 corresponds to lag -(n2-1)..-1 (sig advanced)
    lags = np.concatenate([np.arange(0, n1), np.arange(-(n2 - 1), 0)])

    # Restrict to max_delay if specified
    if max_delay is not None and max_delay > 0:
        valid_mask = (lags >= -max_delay) & (lags <= max_delay)
        cc = np.where(valid_mask, cc, -np.inf)

    peak_idx = int(np.argmax(cc))
    # R = X1 * conj(X2), so peak lag is the lag where x1 aligns with x2
    # delay of sig relative to ref:
    delay = -int(lags[peak_idx])

    return delay
