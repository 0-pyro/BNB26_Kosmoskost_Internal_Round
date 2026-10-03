"""
Roundtable DSP Package (ws3_dsp).

Provides multi-device audio alignment (GCC-PHAT) and loudness-based selection/fusion.
"""

from .align import gcc_phat
from .select import compute_rms, select_loudest_frame

__all__ = ["gcc_phat", "compute_rms", "select_loudest_frame"]
