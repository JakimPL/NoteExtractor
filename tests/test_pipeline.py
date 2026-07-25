from __future__ import annotations

import json
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack

from midi_note_splitter.pipeline import SplitConfig, split_midi


def test_split_with_sustain_and_sorting(tmp_path: Path) -> None:
    source = tmp_path / "source.mid"
    output = tmp_path / "output.mid"
    manifest = tmp_path / "output.notes.json"
    _write_source(source)

    split_midi(
        source,
        output,
        manifest,
        SplitConfig(
            tempo_bpm=115,
            tracked_ccs=frozenset({0, 1}),
            gap_measures=0.25,
            sustain_pedal=True,
        ),
    )

    data = json.loads(manifest.read_text())
    assert [note["pitch"] for note in data["notes"]] == [60, 67]
    assert data["notes"][0]["source"]["key_end_tick"] == 480
    assert data["notes"][0]["source"]["release_end_tick"] == 720
    assert data["notes"][0]["cc_averages"]["1"] == 64.0
    assert output.exists()


def test_no_sustain_uses_key_release(tmp_path: Path) -> None:
    source = tmp_path / "source.mid"
    output = tmp_path / "output.mid"
    manifest = tmp_path / "output.notes.json"
    _write_source(source)

    split_midi(
        source,
        output,
        manifest,
        SplitConfig(sustain_pedal=False),
    )

    data = json.loads(manifest.read_text())
    first = next(note for note in data["notes"] if note["pitch"] == 60)
    assert first["source"]["release_end_tick"] == 480


def _write_source(path: Path) -> None:
    midi = MidiFile(type=1, ticks_per_beat=480)
    meta = MidiTrack()
    meta.append(MetaMessage("set_tempo", tempo=500000, time=0))
    meta.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    midi.tracks.append(meta)

    track = MidiTrack()
    track.append(Message("control_change", channel=0, control=0, value=3, time=0))
    track.append(Message("control_change", channel=0, control=1, value=64, time=0))
    track.append(Message("note_on", channel=0, note=67, velocity=80, time=0))
    track.append(Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(Message("control_change", channel=0, control=64, value=127, time=240))
    track.append(Message("note_off", channel=0, note=60, velocity=5, time=240))
    track.append(Message("note_off", channel=0, note=67, velocity=6, time=0))
    track.append(Message("control_change", channel=0, control=64, value=0, time=240))
    midi.tracks.append(track)
    midi.save(path)


def test_cc_on_onset_tick_keeps_event_order(tmp_path: Path) -> None:
    source = tmp_path / "ordered.mid"
    output = tmp_path / "ordered-output.mid"
    manifest = tmp_path / "ordered-output.notes.json"

    midi = MidiFile(type=0, ticks_per_beat=480)
    track = MidiTrack()
    track.append(Message("control_change", channel=0, control=7, value=90, time=0))
    track.append(Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(Message("control_change", channel=0, control=1, value=20, time=0))
    track.append(Message("note_off", channel=0, note=60, velocity=0, time=480))
    midi.tracks.append(track)
    midi.save(source)

    split_midi(source, output, manifest, SplitConfig())
    merged = MidiFile(output).merged_track
    at_zero = []
    tick = 0
    for message in merged:
        tick += message.time
        if tick == 0 and not message.is_meta:
            at_zero.append((message.type, getattr(message, "control", None)))

    cc7 = at_zero.index(("control_change", 7))
    note_on = at_zero.index(("note_on", None))
    cc1_after = max(index for index, item in enumerate(at_zero) if item == ("control_change", 1))
    assert cc7 < note_on < cc1_after
