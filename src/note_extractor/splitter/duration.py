from collections.abc import Iterable
from dataclasses import dataclass

from ..midi.events import EventPosition
from .notes import SourceNote


@dataclass(frozen=True, slots=True)
class DurationBounds:
    """How long the notes of one render sound, in the ticks they are laid out along.

    `minimum_ticks` is the span a note has to sound over to be worth a sample of its own, and
    `maximum_ticks` is the span it is let go of at however long it was held. A run leaving the
    longest note open lets every note sound for as long as it was played. A run states both in
    seconds and the render's own timing turns them into ticks, since the render is the timing the
    samples are laid out at.
    """

    minimum_ticks: int
    maximum_ticks: int | None


def sounded_notes(notes: Iterable[SourceNote], bounds: DurationBounds) -> tuple[SourceNote, ...]:
    """Notes of one performance a run sounds, each let go of within the span its bounds allow.

    A note sounding over too short a span is left out, since nothing worth playing back is cut from
    it. A note outlasting the longest span is let go of where that span runs out, which is a fourth
    way a note ends alongside the key release, the pedal release, and the end of the performance.

    Every stage after this one reads a note as it is sounded rather than as it was played, so one
    cut short is laid out, voiced, averaged, and recorded over the stretch the render holds of it.
    """
    return tuple(
        _let_go_within(note, bounds.maximum_ticks)
        for note in notes
        if note.release_duration_ticks >= bounds.minimum_ticks
    )


def _let_go_within(note: SourceNote, maximum_ticks: int | None) -> SourceNote:
    """One note let go of where the longest span a run sounds runs out, or as it was played.

    The end sits ahead of everything else carrying its tick, which keeps the controller messages
    posted there out of a note that has already been let go. A key still down where the span runs
    out comes up there too, so the note keeps ending from its start onwards.
    """
    if maximum_ticks is None or note.release_duration_ticks <= maximum_ticks:
        return note

    end = EventPosition.at_tick_start(note.start.tick + maximum_ticks)
    return SourceNote(
        source_id=note.source_id,
        channel=note.channel,
        pitch=note.pitch,
        velocity=note.velocity,
        release_velocity=note.release_velocity,
        start=note.start,
        key_end=min(note.key_end, end),
        release_end=end,
    )
