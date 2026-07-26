from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment[ValueT]:
    """Stretch of ticks over which one value holds, beginning at `start_tick`."""

    start_tick: int
    value: ValueT


class PiecewiseTimeline[ValueT]:
    """Value holding piecewise-constantly along a MIDI timeline, indexed for lookup by tick.

    The timeline spans ticks from zero onwards: `default` holds from tick zero up to the first
    change, and every change holds from its own tick up to the next one. Changes are read in the
    order given, so the last change on a tick is the one holding there. Ticks at or below zero
    read the first segment.
    """

    def __init__(self, changes: Sequence[tuple[int, ValueT]], default: ValueT) -> None:
        self._segments = _ordered_segments(changes, default)
        self._start_ticks = tuple(segment.start_tick for segment in self._segments)

    @property
    def segments(self) -> tuple[Segment[ValueT], ...]:
        """Segments in tick order, the first of which starts at tick zero."""
        return self._segments

    def index_at(self, tick: int) -> int:
        """Index of the segment holding at the given tick."""
        return max(bisect_right(self._start_ticks, tick) - 1, 0)

    def segment_at(self, tick: int) -> Segment[ValueT]:
        """Segment holding at the given tick."""
        return self._segments[self.index_at(tick)]

    def value_at(self, tick: int) -> ValueT:
        """Value holding at the given tick."""
        return self.segment_at(tick).value


def _ordered_segments[ValueT](changes: Sequence[tuple[int, ValueT]], default: ValueT) -> tuple[Segment[ValueT], ...]:
    """Segments in tick order, opening with the default value at tick zero."""
    by_tick: dict[int, ValueT] = {0: default}
    for tick, value in changes:
        by_tick[tick] = value

    return tuple(Segment(start_tick=tick, value=by_tick[tick]) for tick in sorted(by_tick))
