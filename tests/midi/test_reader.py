from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack

from note_extractor.errors import MidiSourceError
from note_extractor.midi.events import (
    ControlChange,
    EventPosition,
    MeterChange,
    NoteOff,
    NoteOn,
    TempoChange,
)
from note_extractor.midi.reader import read_midi

TICKS_PER_BEAT: Final = 480
SMPTE_FILE: Final = bytes.fromhex("4d5468640000000600000001e8044d54726b0000000400ff2f00")


def test_zero_velocity_note_on_reads_as_a_release(tmp_path: Path) -> None:
    path = tmp_path / "release.mid"
    _write_midi_file(
        path,
        [
            [
                Message("note_on", channel=1, note=50, velocity=70, time=0),
                Message("note_on", channel=1, note=50, velocity=0, time=480),
            ]
        ],
    )

    events = read_midi(path).events

    assert events == (
        NoteOn(position=EventPosition(tick=0, sequence=0), channel=1, pitch=50, velocity=70),
        NoteOff(position=EventPosition(tick=480, sequence=1), channel=1, pitch=50, velocity=0),
    )


def test_sequence_numbers_count_every_merged_message(tmp_path: Path) -> None:
    path = tmp_path / "two-tracks.mid"
    _write_midi_file(
        path,
        [
            [
                MetaMessage("track_name", name="Timing", time=0),
                MetaMessage("set_tempo", tempo=500_000, time=0),
            ],
            [
                Message("program_change", channel=0, program=4, time=0),
                Message("note_on", channel=0, note=60, velocity=90, time=0),
            ],
        ],
    )

    source = read_midi(path)

    assert source.events == (
        TempoChange(position=EventPosition(tick=0, sequence=1), microseconds_per_beat=500_000),
        NoteOn(position=EventPosition(tick=0, sequence=3), channel=0, pitch=60, velocity=90),
    )


def test_end_position_covers_the_whole_message_stream(tmp_path: Path) -> None:
    path = tmp_path / "ending.mid"
    _write_midi_file(
        path,
        [
            [
                Message("note_on", channel=0, note=60, velocity=90, time=0),
                Message("note_off", channel=0, note=60, velocity=0, time=960),
            ]
        ],
    )

    source = read_midi(path)

    assert source.end_position == EventPosition(tick=960, sequence=3)


def test_views_narrow_the_stream_by_event_kind(tmp_path: Path) -> None:
    path = tmp_path / "mixed.mid"
    _write_midi_file(
        path,
        [
            [
                MetaMessage("set_tempo", tempo=400_000, time=0),
                MetaMessage("time_signature", numerator=3, denominator=8, time=0),
            ],
            [
                Message("control_change", channel=0, control=7, value=90, time=0),
                Message("note_on", channel=0, note=60, velocity=90, time=0),
                Message("note_off", channel=3, note=48, velocity=12, time=480),
            ],
        ],
    )

    source = read_midi(path)

    assert source.ticks_per_beat == TICKS_PER_BEAT
    assert source.control_changes() == (
        ControlChange(position=EventPosition(tick=0, sequence=2), channel=0, control=7, value=90),
    )
    assert source.tempo_changes() == (
        TempoChange(position=EventPosition(tick=0, sequence=0), microseconds_per_beat=400_000),
    )
    assert source.meter_changes() == (
        MeterChange(position=EventPosition(tick=0, sequence=1), numerator=3, denominator=8),
    )
    assert source.note_channels() == frozenset({0, 3})


def test_smpte_timing_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "smpte.mid"
    path.write_bytes(SMPTE_FILE)

    with pytest.raises(MidiSourceError, match="SMPTE"):
        read_midi(path)


def test_unparsable_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"this is not a MIDI file")

    with pytest.raises(MidiSourceError, match="cannot read MIDI file"):
        read_midi(path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(MidiSourceError, match="cannot read MIDI file"):
        read_midi(tmp_path / "absent.mid")


def _write_midi_file(path: Path, tracks: Sequence[Sequence[Message]]) -> None:
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    for messages in tracks:
        track = MidiTrack()
        track.extend(messages)
        midi.tracks.append(track)

    midi.save(path)
