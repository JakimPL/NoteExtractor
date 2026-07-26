import itertools
from collections.abc import Sequence
from fractions import Fraction
from functools import cached_property
from typing import Final, Self

from pydantic import Field, ValidationError

from ..errors import MidiSourceError
from ..midi.events import MeterChange
from ..models import FrozenModel
from .piecewise import PiecewiseTimeline, Segment

BEATS_PER_WHOLE_NOTE: Final = 4


class TimeSignature(FrozenModel):
    """Measure written as a count of note values, such as three eighths for `3/8`."""

    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


DEFAULT_SIGNATURE: Final = TimeSignature(numerator=4, denominator=4)


class ConstantMeter(FrozenModel):
    """One time signature holding along a whole timeline, converting measures and ticks.

    A grid laid out in measures — the gap the arrangement leaves between two rendered notes —
    reads its tick span from here, which states that the whole grid shares one time signature.
    """

    ticks_per_beat: int = Field(gt=0)
    signature: TimeSignature

    @cached_property
    def measure_ticks(self) -> Fraction:
        """Ticks spanned by one measure."""
        return Fraction(
            self.ticks_per_beat * self.signature.numerator * BEATS_PER_WHOLE_NOTE,
            self.signature.denominator,
        )

    def measures_for_ticks(self, ticks: int) -> float:
        """Measures spanned by a count of ticks."""
        return float(Fraction(ticks, 1) / self.measure_ticks)

    def ticks_for_measures(self, measures: float) -> int:
        """Ticks spanned by a count of measures, rounded to the nearest whole tick."""
        return round(float(self.measure_ticks) * measures)


class MeterMap:
    """Time signature along a MIDI timeline, converting tick positions into elapsed measures.

    Each change holds from its own tick onwards, and `DEFAULT_SIGNATURE` holds over the ticks ahead
    of the first change, which is the meter a sequencer assumes for a file that states one late or
    states none at all.
    """

    def __init__(self, ticks_per_beat: int, changes: Sequence[tuple[int, TimeSignature]]) -> None:
        self.ticks_per_beat = ticks_per_beat
        self._timeline: PiecewiseTimeline[TimeSignature] = PiecewiseTimeline(changes, DEFAULT_SIGNATURE)
        self._meters = tuple(
            ConstantMeter(ticks_per_beat=ticks_per_beat, signature=segment.value) for segment in self._timeline.segments
        )
        self._elapsed_measures = _elapsed_measures(self._timeline.segments, self._meters)

    @classmethod
    def from_changes(cls, ticks_per_beat: int, changes: Sequence[MeterChange]) -> Self:
        """Map of the time signature changes carried by one performance.

        Raises:
            MidiSourceError: If a change states a numerator or a denominator below one.
        """
        return cls(ticks_per_beat, [(change.position.tick, _stated_signature(change)) for change in changes])

    @classmethod
    def constant(cls, ticks_per_beat: int, signature: TimeSignature) -> Self:
        """Map holding one time signature along the whole timeline."""
        return cls(ticks_per_beat, [(0, signature)])

    def meter_at(self, tick: int) -> ConstantMeter:
        """Meter holding at the given tick."""
        return self._meters[self._timeline.index_at(tick)]

    def measures_at(self, tick: int) -> float:
        """Measures elapsed from tick zero up to the given tick."""
        index = self._timeline.index_at(tick)
        segment = self._timeline.segments[index]
        return self._elapsed_measures[index] + self._meters[index].measures_for_ticks(tick - segment.start_tick)

    def measures_between(self, start_tick: int, end_tick: int) -> float:
        """Measures elapsed between two ticks."""
        return self.measures_at(end_tick) - self.measures_at(start_tick)


def _stated_signature(change: MeterChange) -> TimeSignature:
    """Time signature carried by one meta message.

    Raises:
        MidiSourceError: If the numerator or the denominator is below one.
    """
    try:
        return TimeSignature(numerator=change.numerator, denominator=change.denominator)
    except ValidationError as error:
        raise MidiSourceError(
            f"invalid time signature {change.numerator}/{change.denominator} at tick {change.position.tick}"
        ) from error


def _elapsed_measures(
    segments: Sequence[Segment[TimeSignature]],
    meters: Sequence[ConstantMeter],
) -> tuple[float, ...]:
    """Measures elapsed from tick zero up to the start of each segment."""
    total = Fraction(0)
    elapsed = [0.0]
    for index, (previous, segment) in enumerate(itertools.pairwise(segments)):
        total += Fraction(segment.start_tick - previous.start_tick, 1) / meters[index].measure_ticks
        elapsed.append(float(total))

    return tuple(elapsed)
