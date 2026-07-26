from collections.abc import Sequence
from typing import Final, Self

from ..errors import ConfigurationError
from ..midi.events import TempoChange
from .piecewise import PiecewiseTimeline, Segment

DEFAULT_TEMPO_MICROSECONDS: Final = 500_000
MICROSECONDS_PER_SECOND: Final = 1_000_000
MICROSECONDS_PER_MINUTE: Final = 60_000_000


def microseconds_per_beat(beats_per_minute: float) -> int:
    """Length of one beat at the given tempo, rounded to whole microseconds.

    Raises:
        ConfigurationError: If the tempo is zero or negative.
    """
    if beats_per_minute <= 0:
        raise ConfigurationError(f"tempo must be positive: {beats_per_minute}")

    return round(MICROSECONDS_PER_MINUTE / beats_per_minute)


class TempoMap:
    """Tempo along a MIDI timeline, converting tick positions into elapsed seconds.

    Each change holds from its own tick onwards, and `DEFAULT_TEMPO_MICROSECONDS` holds over the
    ticks ahead of the first change, which is the tempo a sequencer assumes for a file that states
    one late or states none at all.
    """

    def __init__(self, ticks_per_beat: int, changes: Sequence[tuple[int, int]]) -> None:
        self.ticks_per_beat = ticks_per_beat
        self._timeline: PiecewiseTimeline[int] = PiecewiseTimeline(changes, DEFAULT_TEMPO_MICROSECONDS)
        self._elapsed_seconds = _elapsed_seconds(self._timeline.segments, ticks_per_beat)

    @classmethod
    def from_changes(cls, ticks_per_beat: int, changes: Sequence[TempoChange]) -> Self:
        """Map of the tempo changes carried by one performance."""
        return cls(ticks_per_beat, [(change.position.tick, change.microseconds_per_beat) for change in changes])

    @classmethod
    def constant(cls, ticks_per_beat: int, beats_per_minute: float) -> Self:
        """Map holding one tempo along the whole timeline.

        Raises:
            ConfigurationError: If the tempo is zero or negative.
        """
        return cls(ticks_per_beat, [(0, microseconds_per_beat(beats_per_minute))])

    def seconds_at(self, tick: int) -> float:
        """Seconds elapsed from tick zero up to the given tick."""
        index = self._timeline.index_at(tick)
        segment = self._timeline.segments[index]
        return self._elapsed_seconds[index] + _ticks_to_seconds(
            tick - segment.start_tick,
            self.ticks_per_beat,
            segment.value,
        )

    def seconds_between(self, start_tick: int, end_tick: int) -> float:
        """Seconds elapsed between two ticks."""
        return self.seconds_at(end_tick) - self.seconds_at(start_tick)


def _elapsed_seconds(segments: Sequence[Segment[int]], ticks_per_beat: int) -> tuple[float, ...]:
    """Seconds elapsed from tick zero up to the start of each segment."""
    elapsed = [0.0]
    for previous, segment in zip(segments, segments[1:], strict=False):
        span = _ticks_to_seconds(segment.start_tick - previous.start_tick, ticks_per_beat, previous.value)
        elapsed.append(elapsed[-1] + span)

    return tuple(elapsed)


def _ticks_to_seconds(ticks: int, ticks_per_beat: int, tempo_microseconds: int) -> float:
    return ticks * tempo_microseconds / MICROSECONDS_PER_SECOND / ticks_per_beat
