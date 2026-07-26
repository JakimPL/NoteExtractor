from dataclasses import dataclass

from .events import PerformanceEvent


@dataclass(frozen=True, slots=True)
class RenderScore:
    """One MIDI file to write: a constant timing header plus events already in write order.

    Each event carries its absolute tick in the rendered file as `position.tick`, and the
    sequence of its position records the rank the arrangement gave it within that tick.
    """

    ticks_per_beat: int
    microseconds_per_beat: int
    numerator: int
    denominator: int
    events: tuple[PerformanceEvent, ...]
