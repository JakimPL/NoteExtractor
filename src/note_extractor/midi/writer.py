from collections.abc import Sequence
from pathlib import Path
from typing import Final, assert_never

from mido import Message, MetaMessage, MidiFile, MidiTrack

from .events import ControlChange, NoteOff, NoteOn, PerformanceEvent
from .score import RenderScore

TIMING_TRACK_NAME: Final = "Timing"
PERFORMANCE_TRACK_NAME: Final = "Isolated notes"

MIDI_FILE_TYPE: Final = 1


def write_midi(path: Path, score: RenderScore) -> None:
    """Write a score as a MIDI file with one timing track and one performance track.

    Missing parent directories of `path` are created.
    """
    midi = MidiFile(type=MIDI_FILE_TYPE, ticks_per_beat=score.ticks_per_beat)
    midi.tracks.append(_timing_track(score))
    midi.tracks.append(_performance_track(score.events))
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)


def _timing_track(score: RenderScore) -> MidiTrack:
    """Track holding the tempo and time signature that hold for the whole score."""
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=TIMING_TRACK_NAME, time=0))
    track.append(MetaMessage("set_tempo", tempo=score.microseconds_per_beat, time=0))
    track.append(
        MetaMessage(
            "time_signature",
            numerator=score.numerator,
            denominator=score.denominator,
            time=0,
        )
    )
    return track


def _performance_track(events: Sequence[PerformanceEvent]) -> MidiTrack:
    """Track holding the scheduled events, timed as deltas between consecutive ticks."""
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=PERFORMANCE_TRACK_NAME, time=0))
    previous_tick = 0
    for event in events:
        track.append(_to_message(event, event.position.tick - previous_tick))
        previous_tick = event.position.tick

    return track


def _to_message(event: PerformanceEvent, delta_ticks: int) -> Message:
    """Message for one event, timed relative to the event written before it."""
    if isinstance(event, NoteOn):
        return Message(
            "note_on",
            channel=event.channel,
            note=event.pitch,
            velocity=event.velocity,
            time=delta_ticks,
        )
    if isinstance(event, NoteOff):
        return Message(
            "note_off",
            channel=event.channel,
            note=event.pitch,
            velocity=event.velocity,
            time=delta_ticks,
        )
    if isinstance(event, ControlChange):
        return Message(
            "control_change",
            channel=event.channel,
            control=event.control,
            value=event.value,
            time=delta_ticks,
        )

    assert_never(event)
