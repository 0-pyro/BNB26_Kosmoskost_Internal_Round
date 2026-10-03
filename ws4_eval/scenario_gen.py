"""
Room Acoustic Simulation Scenario Generator.

Uses pyroomacoustics to simulate a 5x5m room, 4 microphones, and 2 overlapping
speakers playing speech from WAV files (or synthesized realistic speech signals).
Outputs 4 simulated noisy WAV files for multi-device evaluation.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import wave
from typing import List, Optional, Tuple

import numpy as np
import pyroomacoustics as pra
from scipy.io import wavfile

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scenario_gen")

DEFAULT_FS = 16000
DEFAULT_ROOM_DIMS = [5.0, 5.0, 2.8]  # 5x5m floor, 2.8m height


def load_or_generate_wav(
    wav_path: Optional[str],
    speaker_id: int,
    duration_s: float = 4.0,
    fs: int = DEFAULT_FS,
) -> np.ndarray:
    """Load audio from WAV file (resampled/converted to mono float32) or generate synthetic speech."""
    if wav_path and os.path.exists(wav_path):
        logger.info("Loading speaker %d from WAV: %s", speaker_id, wav_path)
        file_fs, data = wavfile.read(wav_path)
        if data.ndim > 1:
            data = data[:, 0]  # Take first channel
        # Normalize to [-1.0, 1.0] float
        if data.dtype == np.int16:
            audio = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            audio = data.astype(np.float32) / 2147483648.0
        else:
            audio = data.astype(np.float32)

        # If sample rate differs, simple interpolation
        if file_fs != fs:
            num_samples = int(len(audio) * fs / file_fs)
            audio = np.interp(
                np.linspace(0, len(audio), num_samples, endpoint=False),
                np.arange(len(audio)),
                audio,
            )
        return audio

    # Synthesize rich multi-harmonic speech-like signal with amplitude modulation
    logger.info("Generating synthetic speech signal for speaker %d (%.1fs)", speaker_id, duration_s)
    t = np.linspace(0, duration_s, int(fs * duration_s), endpoint=False)
    f0 = 130.0 if speaker_id == 1 else 210.0  # Male / Female fundamental pitch

    # Formant resonances and harmonics
    harmonics = [1.0, 0.8, 0.5, 0.3, 0.2, 0.1]
    signal = np.zeros_like(t)
    for i, amp in enumerate(harmonics, start=1):
        signal += amp * np.sin(2 * np.pi * f0 * i * t)

    # Speech cadence / syllabic envelope modulation (~4 Hz)
    envelope = 0.5 * (1.0 + np.sin(2 * np.pi * 3.5 * t))
    # Add slight random fluctuation
    noise = np.random.normal(0, 0.05, size=len(t))

    synthetic = (signal * envelope + noise).astype(np.float32)
    # Normalize peak
    max_val = np.max(np.abs(synthetic))
    if max_val > 0:
        synthetic /= max_val
    return synthetic * 0.8


def generate_scenario(
    speaker1_wav: Optional[str] = None,
    speaker2_wav: Optional[str] = None,
    output_dir: str = "output",
    room_dims: Optional[List[float]] = None,
    absorption: float = 0.2,
    max_order: int = 8,
    snr_db: float = 25.0,
    fs: int = DEFAULT_FS,
) -> List[str]:
    """Simulate a 5x5m room with 4 mics and 2 overlapping speakers, outputting 4 noisy WAVs.

    Parameters
    ----------
    speaker1_wav : str, optional
        Path to WAV file for Speaker 1. If None, synthetic speech is used.
    speaker2_wav : str, optional
        Path to WAV file for Speaker 2. If None, synthetic speech is used.
    output_dir : str
        Directory where mic_0.wav through mic_3.wav will be written.
    room_dims : list of float, optional
        Room dimensions [x, y, z] in meters (default: 5x5x2.8m).
    absorption : float
        Room wall absorption coefficient (default: 0.2).
    max_order : int
        Image source method reflection order (default: 8).
    snr_db : float
        Signal-to-Noise Ratio in dB for ambient background noise (default: 25.0).
    fs : int
        Sampling frequency in Hz (default: 16000).

    Returns
    -------
    List[str]
        List of 4 file paths corresponding to mic_0.wav .. mic_3.wav.
    """
    dims = room_dims or DEFAULT_ROOM_DIMS
    os.makedirs(output_dir, exist_ok=True)

    # 1. Create 5x5m ShoeBox room
    room = pra.ShoeBox(
        dims,
        fs=fs,
        materials=pra.Material(absorption),
        max_order=max_order,
    )
    logger.info("Created %.1fx%.1fx%.1fm room with absorption=%.2f", dims[0], dims[1], dims[2], absorption)

    # 2. Position 4 microphones around a central table (center at [2.5, 2.5, 0.75])
    # Array layout: square around table, 40cm spacing
    cx, cy, cz = dims[0] / 2.0, dims[1] / 2.0, 0.75
    mic_coords = np.array([
        [cx - 0.25, cx + 0.25, cx + 0.25, cx - 0.25],  # X
        [cy - 0.25, cy - 0.25, cy + 0.25, cy + 0.25],  # Y
        [cz,        cz,        cz,        cz       ],  # Z
    ])
    room.add_microphone_array(mic_coords)
    logger.info("Placed 4 microphones around central table at height %.2fm", cz)

    # 3. Load or generate audio for 2 overlapping speakers
    s1_audio = load_or_generate_wav(speaker1_wav, speaker_id=1, duration_s=4.0, fs=fs)
    s2_audio = load_or_generate_wav(speaker2_wav, speaker_id=2, duration_s=4.0, fs=fs)

    # Position 2 speakers at different locations around the room
    # Speaker 1 closer to Mic 0/1; Speaker 2 closer to Mic 2/3
    spk1_loc = [cx - 1.2, cy, 1.2]
    spk2_loc = [cx + 1.2, cy, 1.2]

    # Add sources with overlapping audio
    room.add_source(spk1_loc, signal=s1_audio)
    room.add_source(spk2_loc, signal=s2_audio)
    logger.info("Placed Speaker 1 at %s and Speaker 2 at %s", spk1_loc, spk2_loc)

    # 4. Run acoustic simulation with SNR noise modeling
    logger.info("Running pyroomacoustics simulation (snr=%.1f dB)...", snr_db)
    room.simulate(snr=snr_db)

    mic_signals = room.mic_array.signals  # shape: (4, num_samples)
    logger.info("Simulation complete. Signals shape: %s", mic_signals.shape)

    # 5. Output the 4 generated noisy WAV files
    output_files = []
    for mic_idx in range(mic_signals.shape[0]):
        sig = mic_signals[mic_idx]

        # Normalize signal to avoid clipping while preserving relative volume across mics
        max_abs = np.max(np.abs(mic_signals))
        if max_abs > 0:
            norm_sig = sig / max_abs * 0.95
        else:
            norm_sig = sig

        int16_sig = (norm_sig * 32767.0).astype(np.int16)
        out_path = os.path.join(output_dir, f"mic_{mic_idx}.wav")
        wavfile.write(out_path, fs, int16_sig)
        output_files.append(out_path)
        logger.info("Saved noisy mic WAV: %s (%d samples)", out_path, len(int16_sig))

    return output_files


def main():
    parser = argparse.ArgumentParser(description="Roundtable Pyroomacoustics Scenario Generator")
    parser.add_argument("--speaker1", default=None, help="Path to WAV file for Speaker 1")
    parser.add_argument("--speaker2", default=None, help="Path to WAV file for Speaker 2")
    parser.add_argument("--output-dir", default="ws4_eval/output", help="Directory for generated mic WAVs")
    parser.add_argument("--snr", type=float, default=25.0, help="SNR in dB for background noise")
    args = parser.parse_args()

    files = generate_scenario(
        speaker1_wav=args.speaker1,
        speaker2_wav=args.speaker2,
        output_dir=args.output_dir,
        snr_db=args.snr,
    )
    print(f"Generated {len(files)} noisy WAV files in {args.output_dir}:")
    for f in files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
