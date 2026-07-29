from pathlib import Path
from typing import Annotated, Final, Literal, Self

from pydantic import Field, model_validator

from ..midi.constants import MAX_DATA_BYTE, MIN_DATA_BYTE, DataByte, MidiChannel
from ..models import FrozenModel

SCHEMA_VERSION: Final = 2
TIME_SIGNATURE_PATTERN: Final = r"^[1-9][0-9]*/[1-9][0-9]*$"

ControlAverage = Annotated[float, Field(ge=MIN_DATA_BYTE, le=MAX_DATA_BYTE)]


class NoteTiming(FrozenModel):
    """Where one note sits on a timeline, stated in ticks, measures, and seconds.

    The key end marks the moment the key was released; the release end marks the moment the sound
    was let go, which the sustain pedal holds past the key end.
    """

    start_tick: int = Field(ge=0)
    key_end_tick: int = Field(ge=0)
    release_end_tick: int = Field(ge=0)
    onset_measures: float = Field(ge=0)
    key_duration_measures: float = Field(ge=0)
    release_duration_measures: float = Field(ge=0)
    start_seconds: float = Field(ge=0)
    key_end_seconds: float = Field(ge=0)
    release_end_seconds: float = Field(ge=0)


class RenderTiming(NoteTiming):
    """Where one note sits in the rendered performance, under the index it was laid out at.

    The release lands after the start, so the stretch the trimmer cuts covers a positive span of
    seconds.
    """

    index: int = Field(ge=0)

    @classmethod
    def at_index(cls, index: int, timing: NoteTiming) -> Self:
        """The given span of a render, placed under the index it was laid out at."""
        return cls.model_validate({"index": index, **timing.model_dump()})

    @model_validator(mode="after")
    def _require_a_positive_span(self) -> Self:
        if self.release_end_seconds <= self.start_seconds:
            raise ValueError(
                f"render index {self.index} must release after it starts, "
                f"stated as {self.start_seconds} to {self.release_end_seconds} seconds"
            )

        return self


class NoteRecord(FrozenModel):
    """One extracted note, tying its place in the source performance to its place in the render.

    `cc_averages` holds the time-weighted average of each tracked controller over the span the
    note sounded, keyed by controller number.
    """

    source_id: int = Field(ge=0)
    channel: MidiChannel
    pitch: DataByte
    pitch_name: str
    velocity: DataByte
    release_velocity: DataByte
    cc_averages: dict[DataByte, ControlAverage]
    source: NoteTiming
    render: RenderTiming


class RollSettings(FrozenModel):
    """Audio kept around each note when the render is cut back apart.

    `pre_roll_seconds` reaches back before the onset and `post_roll_seconds` carries on past the
    moment the sound was let go, which keeps the tail of the release. One run states them, and the
    manifest carries them to the trimmer that cuts the spans they describe, so both stages of an
    extraction hold the same rolls however far apart they run.
    """

    pre_roll_seconds: float = Field(ge=0)
    post_roll_seconds: float = Field(ge=0)


class ManifestSettings(FrozenModel):
    """Extraction settings the run was carried out with."""

    tracked_ccs: tuple[DataByte, ...]
    cc_channels: tuple[MidiChannel, ...]
    sustain_pedal: bool
    rolls: RollSettings


class SourceInfo(FrozenModel):
    """Performance the notes were extracted from."""

    path: Path
    ticks_per_beat: int = Field(gt=0)


class RenderInfo(FrozenModel):
    """Performance the notes were laid out into, and the grid spacing them apart."""

    path: Path
    tempo_bpm: float = Field(gt=0)
    time_signature: str = Field(pattern=TIME_SIGNATURE_PATTERN)
    gap_measures: float = Field(ge=0)


class NoteManifest(FrozenModel):
    """Timing contract the splitter writes and the trimmer reads.

    `schema_version` states the shape of the document, so a reader can tell a manifest it
    understands from one written by another release of the tool. Every note carries its own render
    index, and those indices are unique across the manifest, which is what lets a sample file be
    traced back to exactly one note.
    """

    schema_version: Literal[2] = SCHEMA_VERSION
    settings: ManifestSettings
    source: SourceInfo
    render: RenderInfo
    notes: tuple[NoteRecord, ...]

    @model_validator(mode="after")
    def _require_unique_render_indices(self) -> Self:
        indices = [note.render.index for note in self.notes]
        if len(indices) != len(set(indices)):
            raise ValueError("render indices must be unique across the manifest")

        return self

    def notes_in_render_order(self) -> tuple[NoteRecord, ...]:
        """Notes ordered by their position in the rendered performance."""
        return tuple(sorted(self.notes, key=lambda note: note.render.index))
