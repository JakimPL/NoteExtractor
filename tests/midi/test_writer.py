from collections.abc import Sequence
from pathlib import Path
from typing import Final

from mido import MidiFile

from note_extractor.midi.events import (
    ControlChange,
    EventPosition,
    MidiEvent,
    NoteOff,
    NoteOn,
    PerformanceEvent,
)
from note_extractor.midi.reader import read_midi
from note_extractor.midi.score import RenderScore
from note_extractor.midi.writer import (
    PERFORMANCE_TRACK_NAME,
    TIMING_TRACK_NAME,
    write_midi,
)

TICKS_PER_BEAT: Final = 480
MICROSECONDS_PER_BEAT: Final = 521_739

EVENTS: Final = (
    ControlChange(position=EventPosition(tick=0, sequence=0), channel=0, control=64, value=0),
    NoteOn(position=EventPosition(tick=0, sequence=1), channel=0, pitch=60, velocity=100),
    ControlChange(position=EventPosition(tick=240, sequence=2), channel=0, control=1, value=20),
    NoteOff(position=EventPosition(tick=960, sequence=3), channel=0, pitch=60, velocity=17),
    ControlChange(position=EventPosition(tick=1200, sequence=4), channel=0, control=64, value=0),
)


def test_round_trip_preserves_ticks_and_payloads(tmp_path: Path) -> None:
    path = tmp_path / "render.mid"
    write_midi(path, _score(EVENTS))

    reread = read_midi(path)

    assert _outlines(_performance_events(reread.events)) == _outlines(EVENTS)


def test_written_events_carry_the_expected_absolute_ticks(tmp_path: Path) -> None:
    path = tmp_path / "render.mid"
    write_midi(path, _score(EVENTS))

    reread = read_midi(path)

    assert [event.position.tick for event in _performance_events(reread.events)] == [0, 0, 240, 960, 1200]


def test_timing_track_holds_the_score_header(tmp_path: Path) -> None:
    path = tmp_path / "render.mid"
    write_midi(path, _score(EVENTS))

    midi = MidiFile(path)

    assert midi.ticks_per_beat == TICKS_PER_BEAT
    assert [message.type for message in midi.tracks[0]] == [
        "track_name",
        "set_tempo",
        "time_signature",
        "end_of_track",
    ]
    assert midi.tracks[0][0].name == TIMING_TRACK_NAME
    assert midi.tracks[0][1].tempo == MICROSECONDS_PER_BEAT
    assert (midi.tracks[0][2].numerator, midi.tracks[0][2].denominator) == (3, 4)


def test_performance_track_is_named_and_holds_every_event(tmp_path: Path) -> None:
    path = tmp_path / "render.mid"
    write_midi(path, _score(EVENTS))

    midi = MidiFile(path)

    assert midi.tracks[1][0].name == PERFORMANCE_TRACK_NAME
    assert [message.type for message in midi.tracks[1][1:-1]] == [
        "control_change",
        "note_on",
        "control_change",
        "note_off",
        "control_change",
    ]


def test_empty_score_writes_both_tracks(tmp_path: Path) -> None:
    path = tmp_path / "empty.mid"
    write_midi(path, _score(()))

    midi = MidiFile(path)

    assert len(midi.tracks) == 2
    assert read_midi(path).note_channels() == frozenset()


def test_missing_parent_directories_are_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "render.mid"
    write_midi(path, _score(EVENTS))

    assert path.exists()


def _score(events: tuple[PerformanceEvent, ...]) -> RenderScore:
    return RenderScore(
        ticks_per_beat=TICKS_PER_BEAT,
        microseconds_per_beat=MICROSECONDS_PER_BEAT,
        numerator=3,
        denominator=4,
        events=events,
    )


def _performance_events(events: Sequence[MidiEvent]) -> list[PerformanceEvent]:
    """Events of the performance track, leaving the timing header of the file aside."""
    return [event for event in events if isinstance(event, PerformanceEvent)]


def _outlines(events: Sequence[PerformanceEvent]) -> list[tuple[str, int, int, int, int]]:
    """Reduce events to kind, tick, and payload, leaving stream sequence numbers aside."""
    return [_outline(event) for event in events]


def _outline(event: PerformanceEvent) -> tuple[str, int, int, int, int]:
    if isinstance(event, ControlChange):
        return (type(event).__name__, event.position.tick, event.channel, event.control, event.value)

    return (type(event).__name__, event.position.tick, event.channel, event.pitch, event.velocity)
