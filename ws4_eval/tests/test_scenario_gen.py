"""
Unit tests for scenario generator (ws4_eval/scenario_gen.py).
"""

import os
import wave
import pytest

from ws4_eval.scenario_gen import generate_scenario


def test_generate_scenario_creates_4_mics_wavs(tmp_path):
    """Scenario generator simulates room and writes 4 WAV files for the 4 mics."""
    out_dir = str(tmp_path / "scenario_out")
    files = generate_scenario(
        output_dir=out_dir,
        max_order=2,  # Small order for fast test execution
        snr_db=30.0,
    )

    assert len(files) == 4
    for idx, fpath in enumerate(files):
        assert os.path.exists(fpath)
        assert fpath.endswith(f"mic_{idx}.wav")

        # Verify WAV properties
        with wave.open(fpath, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit PCM
            assert wf.getframerate() == 16000
            assert wf.getnframes() > 0
