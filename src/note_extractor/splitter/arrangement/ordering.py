from dataclasses import dataclass, field
from enum import IntEnum
from typing import Self

from ...midi.events import PerformanceEvent
from ..notes import SourceNote


class OrderBand(IntEnum):
    """Rank of an event among the events sharing one tick of the render.

    A controller snapshot comes first, so the note it prepares sounds with those settings in place.
    The events read from the source follow, keeping the order the source posted them in. A pedal
    release comes last, which lets the note it closes sound for the whole tick.
    """

    SNAPSHOT = 0
    SOURCE = 1
    PEDAL_LIFT = 2


@dataclass(frozen=True, slots=True, order=True)
class ScheduledMessage:
    """One event placed in the render, carrying the ranks that settle ties within its tick.

    Comparison runs tick, then band, then the sequence the source posted the event at, then the
    order the scheduler emitted it in, which together give the render one total write order.
    """

    tick: int
    band: OrderBand
    sequence: int
    serial: int
    event: PerformanceEvent = field(compare=False)

    @classmethod
    def for_event(cls, event: PerformanceEvent, band: OrderBand, serial: int) -> Self:
        """Message placing one event at the render position the event already carries."""
        return cls(
            tick=event.position.tick,
            band=band,
            sequence=event.position.sequence,
            serial=serial,
            event=event,
        )


def render_order(note: SourceNote) -> tuple[int, int, int, int]:
    """Sort key laying notes out by pitch, then by strike, then by when they were played.

    Grouping a render this way puts every reading of one pitch and velocity pair side by side,
    which is the order a sampler expects to step through them in.
    """
    return note.pitch, note.velocity, note.start.tick, note.source_id
