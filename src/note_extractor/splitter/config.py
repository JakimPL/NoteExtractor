from collections.abc import Set as AbstractSet
from functools import cached_property
from typing import Final, Self

from pydantic import Field, field_validator

from ..midi.constants import SUSTAIN_PEDAL_CONTROL, DataByte, MidiChannel
from ..models import FrozenModel
from ..timeline.meter import ConstantMeter, TimeSignature
from ..timeline.tempo import microseconds_per_beat

DEFAULT_TEMPO_BPM: Final = 120.0
DEFAULT_RENDER_SIGNATURE: Final = TimeSignature(numerator=4, denominator=4)
DEFAULT_TRACKED_CCS: Final = frozenset({0, 1})
DEFAULT_GAP_MEASURES: Final = 0.25
DEFAULT_SUSTAIN_PEDAL: Final = True

MIN_GAP_TICKS: Final = 1


class SplitConfig(FrozenModel):
    """Settings one split run is asked to carry out.

    `tracked_ccs` names the controllers each rendered note opens with and the manifest reports an
    average for. `cc_channels` names the channels whose controller messages reach the render; a run
    that leaves it open takes the channels carrying notes in the source performance.
    """

    tempo_bpm: float = Field(default=DEFAULT_TEMPO_BPM, gt=0)
    signature: TimeSignature = DEFAULT_RENDER_SIGNATURE
    tracked_ccs: frozenset[DataByte] = DEFAULT_TRACKED_CCS
    cc_channels: frozenset[MidiChannel] | None = None
    gap_measures: float = Field(default=DEFAULT_GAP_MEASURES, ge=0)
    sustain_pedal: bool = DEFAULT_SUSTAIN_PEDAL

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
    def applied_controls(self) -> tuple[DataByte, ...]:
        """Controllers the run follows, in ascending order.

        A run that follows the sustain pedal includes it among the tracked controllers.
        """
        return tuple(
            control for control in sorted(self.tracked_ccs) if self.sustain_pedal or control != SUSTAIN_PEDAL_CONTROL
        )
