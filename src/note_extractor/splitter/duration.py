from collections.abc import Iterable
from dataclasses import dataclass

from ..midi.events import EventPosition
from .notes import SourceNote


@dataclass(frozen=True, slots=True)
class DurationBounds:
    """How long the notes of one render sound, in the ticks they are laid out along.

    `skip_below_ticks` is the span a note has to have been played over to be worth sampling at all.
    `minimum_ticks` is the span every note the run keeps sounds over, reached by holding on a note
    the performance let go of sooner, and `maximum_ticks` is the span a note still sounding is let
    go of at. A run leaving the longest note open lets every note sound for as long as it was
    played. A run states each of them in seconds and the render's own timing turns them into ticks,
    since the render is the timing the samples are laid out at.
    """

    skip_below_ticks: int
    minimum_ticks: int
    maximum_ticks: int | None


def sounded_notes(notes: Iterable[SourceNote], bounds: DurationBounds) -> tuple[SourceNote, ...]:
    """Notes of one performance a run sounds, each over a span its bounds allow.

    A note played over a span briefer than the run samples at all is left out, since holding one on
    that far would sample a brush of a key rather than a note. Every note the run keeps sounds over
    the shortest span it states, held on where the performance let go of it sooner, and is let go of
    where the longest span runs out.

    Every stage after this one reads a note as it is sounded rather than as it was played, so one
    the run holds on or cuts short is laid out, voiced, averaged, and recorded over the stretch the
    render holds of it.
    """
    return tuple(_sounded(note, bounds) for note in notes if note.release_duration_ticks >= bounds.skip_below_ticks)


def _sounded(note: SourceNote, bounds: DurationBounds) -> SourceNote:
    """One note over the span a run sounds it for, which its bounds settle from either end."""
    return _let_go_within(_held_for(note, bounds.minimum_ticks), bounds.maximum_ticks)


def _held_for(note: SourceNote, minimum_ticks: int) -> SourceNote:
    """One note held on to the shortest span a run sounds, or as long as it was played.

    The key stays down to the end of that span, since a key held down is what carries a note on past
    the moment the performance let go of it. The end sits ahead of everything else carrying its
    tick, which keeps the controller messages posted there out of a note already let go.
    """
    if note.release_duration_ticks >= minimum_ticks:
        return note

    end = EventPosition.at_tick_start(note.start.tick + minimum_ticks)
    return _ending_at(note, key_end=end, release_end=end)


def _let_go_within(note: SourceNote, maximum_ticks: int | None) -> SourceNote:
    """One note let go of where the longest span a run sounds runs out, or as it was played.

    A key still down where the span runs out comes up there too, so the note keeps ending from its
    start onwards.
    """
    if maximum_ticks is None or note.release_duration_ticks <= maximum_ticks:
        return note

    end = EventPosition.at_tick_start(note.start.tick + maximum_ticks)
    return _ending_at(note, key_end=min(note.key_end, end), release_end=end)


def _ending_at(note: SourceNote, key_end: EventPosition, release_end: EventPosition) -> SourceNote:
    """One note ending at the two moments a run settles on, struck as the performance struck it."""
    return SourceNote(
        source_id=note.source_id,
        channel=note.channel,
        pitch=note.pitch,
        velocity=note.velocity,
        release_velocity=note.release_velocity,
        start=note.start,
        key_end=key_end,
        release_end=release_end,
    )
