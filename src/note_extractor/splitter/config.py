from collections.abc import Set as AbstractSet
from functools import cached_property
from typing import Annotated, Final, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from ..config import ConfigDocument, section
from ..manifest.models import RollSettings
from ..midi.constants import SUSTAIN_PEDAL_CONTROL, DataByte, MidiChannel
from ..models import FrozenModel
from ..timeline.meter import ConstantMeter, TimeSignature
from ..timeline.tempo import microseconds_per_beat, ticks_for_seconds
from ..validation import configuration_failure
from .duration import DurationBounds

SPLIT_SECTION: Final = "split"
ROLLS_SECTION: Final = "rolls"

MIN_GAP_TICKS: Final = 1
MIN_NOTE_TICKS: Final = 1
NO_MINIMUM_TICKS: Final = 0

NoteSeconds = Annotated[float, Field(gt=0)]


class SplitConfig(FrozenModel):
    """Settings one split run is asked to carry out.

    `tracked_ccs` names the controllers each rendered note opens with and the manifest reports an
    average for. `cc_channels` names the channels whose controller messages reach the render; a run
    that leaves it open takes the channels carrying notes in the source performance. `rolls` states
    the audio each note keeps around it, which the run records for the trimmer to cut by.

    `min_note_seconds` and `max_note_seconds` state how long the notes of the render sound: one
    sounding for less than the first is left out, and one outlasting the second is let go of where
    that span runs out. A run leaving either open holds no bound of that kind.
    """

    tempo_bpm: float = Field(gt=0)
    signature: TimeSignature
    tracked_ccs: frozenset[DataByte]
    cc_channels: frozenset[MidiChannel] | None
    gap_measures: float = Field(ge=0)
    sustain_pedal: bool
    min_note_seconds: NoteSeconds | None
    max_note_seconds: NoteSeconds | None
    rolls: RollSettings

    @classmethod
    def from_document(cls, document: ConfigDocument) -> Self:
        """Settings a split run reads from one configuration document.

        A run is carried out under the `split` settings and records the `rolls` beside them, so the
        two sections travel together from the document into the manifest.

        Raises:
            ConfigurationError: If the document leaves either section out, or states a value
                outside the range one supports.
        """
        settings = {**section(document, SPLIT_SECTION), ROLLS_SECTION: section(document, ROLLS_SECTION)}
        try:
            return cls.model_validate(settings)
        except ValidationError as error:
            raise configuration_failure(error) from error

    @field_validator("signature", mode="before")
    @classmethod
    def _read_a_written_signature(cls, signature: object) -> object:
        """Signature a document writes as a count over a note value, such as `4/4`.

        Raises:
            ValueError: If the text holds anything other than two whole numbers around a slash.
        """
        return TimeSignature.parse(signature) if isinstance(signature, str) else signature

    @field_validator("signature")
    @classmethod
    def _require_a_writable_denominator(cls, signature: TimeSignature) -> TimeSignature:
        """Keep the signature to what a MIDI header states, which is a power of two note value.

        Raises:
            ValueError: If the denominator is not a power of two.
        """
        if signature.denominator & (signature.denominator - 1):
            raise ValueError(f"time signature denominator must be a power of two: {signature}")

        return signature

    @model_validator(mode="after")
    def _require_a_span_the_notes_of_a_render_fit_in(self) -> Self:
        """Keep the shortest note a run takes within the longest note it sounds.

        Raises:
            ValueError: If the shortest note outlasts the longest, which leaves a run stating two
                bounds no note meets at once.
        """
        if self.min_note_seconds is not None and self.max_note_seconds is not None:
            if self.min_note_seconds > self.max_note_seconds:
                raise ValueError(
                    f"shortest note must not outlast the longest, stated as {self.min_note_seconds} "
                    f"then {self.max_note_seconds} seconds"
                )

        return self


class RenderSettings(FrozenModel):
    """Settings settled against one source performance, driving both the render and the manifest.

    The render holds one tempo and one time signature throughout, and shares the tick resolution of
    the source so every note keeps the spans it was played with.
    """

    ticks_per_beat: int = Field(gt=0)
    tempo_bpm: float = Field(gt=0)
    signature: TimeSignature
    tracked_ccs: frozenset[DataByte]
    cc_channels: frozenset[MidiChannel]
    gap_measures: float = Field(ge=0)
    sustain_pedal: bool
    min_note_seconds: NoteSeconds | None
    max_note_seconds: NoteSeconds | None
    rolls: RollSettings

    @classmethod
    def from_config(cls, config: SplitConfig, ticks_per_beat: int, note_channels: AbstractSet[int]) -> Self:
        """Settings a run carries out against a source of the given resolution.

        A run that names no controller channels takes the channels carrying notes in the source.
        """
        return cls(
            ticks_per_beat=ticks_per_beat,
            tempo_bpm=config.tempo_bpm,
            signature=config.signature,
            tracked_ccs=config.tracked_ccs,
            cc_channels=frozenset(note_channels) if config.cc_channels is None else config.cc_channels,
            gap_measures=config.gap_measures,
            sustain_pedal=config.sustain_pedal,
            min_note_seconds=config.min_note_seconds,
            max_note_seconds=config.max_note_seconds,
            rolls=config.rolls,
        )

    @cached_property
    def meter(self) -> ConstantMeter:
        """Meter the render is laid out on."""
        return ConstantMeter(ticks_per_beat=self.ticks_per_beat, signature=self.signature)

    @cached_property
    def microseconds_per_beat(self) -> int:
        """Length of one beat of the render, as its MIDI header states it."""
        return microseconds_per_beat(self.tempo_bpm)

    @cached_property
    def gap_ticks(self) -> int:
        """Ticks separating one note's release from the next note's onset.

        The gap spans at least `MIN_GAP_TICKS`, which leaves every note a tick range of its own and
        so keeps the messages closing one note ahead of the messages opening the next.
        """
        return max(self.meter.ticks_for_measures(self.gap_measures), MIN_GAP_TICKS)

    @cached_property
    def duration_bounds(self) -> DurationBounds:
        """Spans the notes of this render sound between, in the ticks they are laid out along.

        The bounds a run writes in seconds are read against the render's own tempo and resolution,
        which is the timing the samples are rendered at, and a note keeps the ticks it was played
        with wherever it sits. A longest note spans at least `MIN_NOTE_TICKS`, which leaves the
        render a stretch to sound every note it takes over.
        """
        shortest, longest = self.min_note_seconds, self.max_note_seconds
        return DurationBounds(
            minimum_ticks=NO_MINIMUM_TICKS if shortest is None else self._note_ticks(shortest),
            maximum_ticks=None if longest is None else max(self._note_ticks(longest), MIN_NOTE_TICKS),
        )

    def _note_ticks(self, seconds: float) -> int:
        """Ticks one stretch of seconds spans on the grid this render is laid out along."""
        return ticks_for_seconds(seconds, self.ticks_per_beat, self.microseconds_per_beat)

    @cached_property
    def applied_controls(self) -> tuple[DataByte, ...]:
        """Controllers the run follows, in ascending order.

        A run that follows the sustain pedal includes it among the tracked controllers.
        """
        return tuple(
            control for control in sorted(self.tracked_ccs) if self.sustain_pedal or control != SUSTAIN_PEDAL_CONTROL
        )
