from dataclasses import dataclass
from typing import Final, Self

BEFORE_FIRST_SEQUENCE: Final = -1


@dataclass(frozen=True, slots=True, order=True)
class EventPosition:
    """Place of an event in a MIDI stream: its absolute tick and its rank within that tick.

    Comparison runs tick first and sequence second, which makes a position usable both as a
    `bisect` key over a stream and as the tie-break rule between events sharing a tick.
    """

    tick: int
    sequence: int

    @classmethod
    def at_tick_start(cls, tick: int) -> Self:
        """Position that sorts ahead of every event carrying the given tick."""
        return cls(tick=tick, sequence=BEFORE_FIRST_SEQUENCE)


@dataclass(frozen=True, slots=True)
class NoteOn:
    """Key press that starts a note."""

    position: EventPosition
    channel: int
    pitch: int
    velocity: int


@dataclass(frozen=True, slots=True)
class NoteOff:
    """Key release that ends a note, carrying the velocity of the release."""

    position: EventPosition
    channel: int
    pitch: int
    velocity: int


@dataclass(frozen=True, slots=True)
class ControlChange:
    """Value posted by one continuous controller."""

    position: EventPosition
    channel: int
    control: int
    value: int


@dataclass(frozen=True, slots=True)
class TempoChange:
    """Tempo that holds from this position onwards."""

    position: EventPosition
    microseconds_per_beat: int


@dataclass(frozen=True, slots=True)
class MeterChange:
    """Time signature that holds from this position onwards."""

    position: EventPosition
    numerator: int
    denominator: int


PerformanceEvent = NoteOn | NoteOff | ControlChange
TimingEvent = TempoChange | MeterChange
MidiEvent = PerformanceEvent | TimingEvent
