from collections.abc import Sequence

from ..timeline.tempo import TempoMap
from .controllers import ControllerTimeline
from .notes import SourceNote


def average_control_values(
    controllers: ControllerTimeline,
    tempo: TempoMap,
    note: SourceNote,
    controls: Sequence[int],
) -> dict[int, float]:
    """Average value each of the given controllers held while one note sounded, in control order."""
    return {control: time_weighted_average(controllers, tempo, note, control) for control in controls}


def time_weighted_average(
    controllers: ControllerTimeline,
    tempo: TempoMap,
    note: SourceNote,
    control: int,
) -> float:
    """Average value one controller held while a note sounded, weighted by seconds.

    Each value counts for the seconds it was heard over, so a value held across a slow stretch
    carries the weight that stretch takes in time. A note whose stretch takes no time reads as the
    value holding at its onset.
    """
    total_seconds = tempo.seconds_between(note.start.tick, note.release_end.tick)
    value = controllers.value_before(note.channel, control, note.start)
    if total_seconds <= 0:
        return float(value)

    weighted = 0.0
    cursor_tick = note.start.tick
    for event in controllers.control_events_between(
        note.channel,
        control,
        note.start,
        note.release_end,
    ):
        weighted += value * tempo.seconds_between(cursor_tick, event.position.tick)
        value = event.value
        cursor_tick = event.position.tick

    weighted += value * tempo.seconds_between(cursor_tick, note.release_end.tick)
    return weighted / total_seconds
