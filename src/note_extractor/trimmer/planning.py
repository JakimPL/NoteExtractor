import math
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Self

from pydantic import Field, model_validator

from ..errors import AudioError, OutputConflictError
from ..manifest.models import NoteRecord
from ..models import FrozenModel
from .audio import AudioStream
from .config import TrimConfig
from .naming import SampleNaming

FIRST_FRAME: Final = 0
SECONDS_PRECISION: Final = 6


class TrimmedSample(FrozenModel):
    """One note's cut of the rendered stream, together with the file it is written to.

    The frames bound the stretch that is cut and `sample_rate` places them in time. `start_clamped`
    and `end_clamped` report the ends where the stream was shorter than the roll reached for, so the
    cut states how much of the requested stretch it holds.
    """

    note: NoteRecord
    output_path: Path
    sample_rate: int = Field(gt=0)
    start_frame: int = Field(ge=FIRST_FRAME)
    end_frame: int = Field(gt=FIRST_FRAME)
    start_clamped: bool
    end_clamped: bool

    @model_validator(mode="after")
    def _require_frames_to_sound(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError(
                f"note {self.note.render.index} must close after it opens, stated as frames "
                f"{self.start_frame} to {self.end_frame}"
            )

        return self

    @property
    def frame_count(self) -> int:
        """Frames the cut holds."""
        return self.end_frame - self.start_frame

    @property
    def start_seconds(self) -> float:
        """Where the cut opens in the rendered stream."""
        return self.start_frame / self.sample_rate

    @property
    def end_seconds(self) -> float:
        """Where the cut closes in the rendered stream."""
        return self.end_frame / self.sample_rate


class SamplePlanner:
    """Places every note of one manifest against the stream its render was recorded into.

    A note is cut from its onset to the moment its sound was let go, widened by the rolls the run
    asks for and held within the frames the stream holds. One planner plans one run, so the samples it
    returns name one file each.
    """

    def __init__(self, config: TrimConfig, naming: SampleNaming, output_directory: Path) -> None:
        self._config = config
        self._naming = naming
        self._output_directory = output_directory

    def plan(self, notes: Sequence[NoteRecord], stream: AudioStream) -> tuple[TrimmedSample, ...]:
        """Cut planned for each of the given notes, in the order they arrive.

        Raises:
            AudioError: If a note opens after the stream ends.
            OutputConflictError: If two notes claim one file, or a file an earlier run wrote is kept.
        """
        planned = tuple(self._plan_note(note, stream) for note in notes)
        self._require_one_file_per_note(planned)
        self._require_free_output_paths(planned)
        return planned

    def _plan_note(self, note: NoteRecord, stream: AudioStream) -> TrimmedSample:
        """Cut holding one note, reaching as far past its ends as the stream allows.

        The cut opens at the frame the requested second falls in and closes at the frame its
        requested end reaches, so a note laid out over a stretch of the render keeps a frame of its
        own to sound over.

        Raises:
            AudioError: If the note opens after the stream ends.
        """
        requested_start = note.render.start_seconds - self._config.pre_roll_seconds
        requested_end = note.render.release_end_seconds + self._config.post_roll_seconds
        requested_start_frame = math.floor(requested_start * stream.sample_rate)
        requested_end_frame = math.ceil(requested_end * stream.sample_rate)
        start_frame = max(FIRST_FRAME, requested_start_frame)
        end_frame = min(stream.frame_count, requested_end_frame)
        self._require_audio_for_note(note, stream, start_frame)

        return TrimmedSample(
            note=note,
            output_path=self._output_directory / self._naming.filename_for(note),
            sample_rate=stream.sample_rate,
            start_frame=start_frame,
            end_frame=end_frame,
            start_clamped=start_frame != requested_start_frame,
            end_clamped=end_frame != requested_end_frame,
        )

    def _require_audio_for_note(self, note: NoteRecord, stream: AudioStream, start_frame: int) -> None:
        """Confirm the stream still sounds where one note was laid out.

        Raises:
            AudioError: If the note opens at or after the frame the stream ends on.
        """
        if start_frame >= stream.frame_count:
            raise AudioError(
                f"note {note.render.index} opens after the audio ends: "
                f"{note.render.start_seconds:.{SECONDS_PRECISION}f}s into "
                f"{stream.duration_seconds:.{SECONDS_PRECISION}f}s of audio"
            )

    def _require_one_file_per_note(self, planned: Sequence[TrimmedSample]) -> None:
        """Confirm each planned cut claims a file of its own.

        Raises:
            OutputConflictError: If two of the planned cuts claim one file.
        """
        claims = Counter(sample.output_path for sample in planned)
        shared = sorted(path for path, count in claims.items() if count > 1)
        if shared:
            raise OutputConflictError(f"{len(shared)} sample files are claimed by more than one note: {shared[0]}")

    def _require_free_output_paths(self, planned: Sequence[TrimmedSample]) -> None:
        """Confirm the run may write every file it plans.

        Raises:
            OutputConflictError: If a file an earlier run wrote is kept by the current settings.
        """
        if self._config.overwrite:
            return

        existing = next((sample.output_path for sample in planned if sample.output_path.exists()), None)
        if existing is not None:
            raise OutputConflictError(f"sample file already exists: {existing}")
