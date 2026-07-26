from dataclasses import dataclass
from pathlib import Path
from typing import Self

import numpy as np
import numpy.typing as npt
from scipy.io import wavfile

from ..errors import AudioError

SampleValue = np.signedinteger | np.uint8 | np.float32 | np.float64
AudioSamples = npt.NDArray[SampleValue]


@dataclass(frozen=True, slots=True, eq=False)
class AudioStream:
    """Frames of one WAV file, held at the rate they were recorded at.

    A frame carries one value per channel, so `frame_count` counts the moments the file sounds
    however many channels each of them holds. The samples keep the type they were stored with, which
    is what lets a cut of the stream be written back at the resolution it was rendered at.
    """

    sample_rate: int
    samples: AudioSamples

    def __post_init__(self) -> None:
        """Confirm the stream states a rate that places its frames in time.

        Raises:
            AudioError: If the sample rate states zero or fewer frames per second.
        """
        if self.sample_rate <= 0:
            raise AudioError(f"a sample rate of {self.sample_rate} frames per second places no timing")

    @property
    def frame_count(self) -> int:
        """Frames the stream holds."""
        return len(self.samples)

    @property
    def duration_seconds(self) -> float:
        """Time the stream sounds for."""
        return self.frame_count / self.sample_rate

    def segment(self, start_frame: int, end_frame: int) -> Self:
        """Stretch running from `start_frame` up to `end_frame`, at the rate of the whole stream."""
        return type(self)(sample_rate=self.sample_rate, samples=self.samples[start_frame:end_frame])


def read_wav(path: Path) -> AudioStream:
    """Audio stored at the given path.

    Raises:
        AudioError: If the file resists reading, carries bytes the reader fails to parse, or states
            a sample rate that places no timing.
    """
    try:
        sample_rate, samples = _read_frames(path)
        return AudioStream(sample_rate=sample_rate, samples=samples)
    except (AudioError, OSError, ValueError) as error:
        raise AudioError(f"cannot read audio {path}: {error}") from error


def write_wav(path: Path, stream: AudioStream) -> None:
    """Store one stream as a WAV file at the given path.

    Raises:
        AudioError: If the file resists writing.
    """
    try:
        wavfile.write(path, stream.sample_rate, stream.samples)
    except OSError as error:
        raise AudioError(f"cannot write audio {path}: {error}") from error


def _read_frames(path: Path) -> tuple[int, AudioSamples]:
    """Sample rate and frames of one WAV file, mapped from the file where its layout allows.

    Mapping leaves the frames on disk until a cut reads them, which keeps a long render out of
    memory. A file whose layout resists mapping is read in one pass.
    """
    try:
        return wavfile.read(path, mmap=True)
    except (OSError, ValueError):
        return wavfile.read(path, mmap=False)
