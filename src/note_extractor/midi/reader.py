from collections.abc import Sequence
from pathlib import Path

from mido import Message, MidiFile, merge_tracks

from ..errors import MidiSourceError
from .events import (
    ControlChange,
    EventPosition,
    MeterChange,
    MidiEvent,
    NoteOff,
    NoteOn,
    TempoChange,
)
from .source import SourceMidi


def read_midi(path: Path) -> SourceMidi:
    """Read one MIDI performance into typed events positioned in the merged message stream.

    Raises:
        MidiSourceError: If the parser rejects the file or the file uses SMPTE timing.
    """
    midi = _open_midi(path)
    messages = list(merge_tracks(midi.tracks))
    positions = _positions(messages)
    return SourceMidi(
        ticks_per_beat=midi.ticks_per_beat,
        events=_typed_events(positions, messages),
        end_position=EventPosition(
            tick=positions[-1].tick if positions else 0,
            sequence=len(messages),
        ),
    )


def _open_midi(path: Path) -> MidiFile:
    """Load a MIDI file that measures time in ticks per beat.

    Raises:
        MidiSourceError: If the parser rejects the file or the file uses SMPTE timing.
    """
    try:
        midi = MidiFile(path)
    except (OSError, EOFError, ValueError) as exception:
        raise MidiSourceError(f"cannot read MIDI file {path}: {exception}") from exception

    if midi.ticks_per_beat <= 0:
        raise MidiSourceError(f"SMPTE-timed MIDI files are not supported: {path}")

    return midi


def _positions(messages: Sequence[Message]) -> tuple[EventPosition, ...]:
    """Absolute position of every merged message.

    Each merged message consumes one sequence number, which keeps positions stable when
    message types outside the modelled set sit between the ones the pipeline keeps.
    """
    positions: list[EventPosition] = []
    tick = 0
    for sequence, message in enumerate(messages):
        tick += message.time
        positions.append(EventPosition(tick=tick, sequence=sequence))

    return tuple(positions)


def _typed_events(positions: Sequence[EventPosition], messages: Sequence[Message]) -> tuple[MidiEvent, ...]:
    """Modelled events of the stream, in stream order."""
    converted = (_to_event(position, message) for position, message in zip(positions, messages, strict=True))
    return tuple(event for event in converted if event is not None)


def _to_event(position: EventPosition, message: Message) -> MidiEvent | None:
    """Typed event for a modelled message, or `None` for any other message type."""
    if message.type == "note_on":
        return _key_press(position, message)
    if message.type == "note_off":
        return NoteOff(
            position=position,
            channel=message.channel,
            pitch=message.note,
            velocity=message.velocity,
        )
    if message.type == "control_change":
        return ControlChange(
            position=position,
            channel=message.channel,
            control=message.control,
            value=message.value,
        )
    if message.type == "set_tempo":
        return TempoChange(
            position=position,
            microseconds_per_beat=message.tempo,
        )
    if message.type == "time_signature":
        return MeterChange(
            position=position,
            numerator=message.numerator,
            denominator=message.denominator,
        )

    return None


def _key_press(position: EventPosition, message: Message) -> NoteOn | NoteOff:
    """Read a `note_on` message, where a velocity of zero releases the sounding note."""
    if message.velocity == 0:
        return NoteOff(
            position=position,
            channel=message.channel,
            pitch=message.note,
            velocity=0,
        )

    return NoteOn(
        position=position,
        channel=message.channel,
        pitch=message.note,
        velocity=message.velocity,
    )
