from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.io import wavfile


def read_wav(path: Path) -> tuple[int, np.ndarray]:
    try:
        return wavfile.read(path, mmap=True)
    except (ValueError, OSError):
        return wavfile.read(path, mmap=False)


def write_wav(path: Path, sample_rate: int, audio: np.ndarray) -> None:
    wavfile.write(path, sample_rate, audio)
