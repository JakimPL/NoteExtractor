import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack

from note_extractor.errors import MidiSourceError
from note_extractor.manifest.models import SCHEMA_VERSION, NoteManifest
from note_extractor.manifest.storage import read_manifest
from note_extractor.splitter.config import SplitConfig
from note_extractor.splitter.pipeline import split_midi

from .conftest import split_config

TICKS_PER_BEAT: Final = 480
SUSTAIN: Final = 64


def _config(**overrides: object) -> SplitConfig:
    """The bundled settings with the spans a note sounds between left open.

    These performances are written a few hundred ticks long, so a test about the pedal, the
    controllers, or the order a render is written in states no bounds and reads every note it plays.
    """
    return split_config(**{"min_note_seconds": None, "max_note_seconds": None, **overrides})


def test_a_run_writes_a_render_and_the_manifest_timing_it(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(tempo_bpm=115.0))

    assert paths.render.exists()
    assert read_manifest(paths.manifest) == manifest
    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.source.path == paths.source
    assert manifest.render.path == paths.render
    assert manifest.source.ticks_per_beat == TICKS_PER_BEAT


def test_the_notes_of_a_render_are_grouped_by_pitch_and_strike(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config())

    assert [note.pitch for note in manifest.notes] == [60, 67]
    assert [note.render.index for note in manifest.notes] == [0, 1]


def test_a_note_held_by_the_pedal_sounds_past_its_key_release(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(sustain_pedal=True))

    middle_c = next(note for note in manifest.notes if note.pitch == 60)
    assert middle_c.source.key_end_tick == 480
    assert middle_c.source.release_end_tick == 720


def test_a_run_leaving_the_pedal_alone_ends_each_note_at_its_key_release(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(sustain_pedal=False))

    middle_c = next(note for note in manifest.notes if note.pitch == 60)
    assert middle_c.source.release_end_tick == 480


def test_a_tracked_controller_is_averaged_over_the_stretch_its_note_sounded(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    manifest = split_midi(
        paths.source,
        paths.render,
        paths.manifest,
        _config(tracked_ccs=frozenset({0, 1})),
    )

    middle_c = next(note for note in manifest.notes if note.pitch == 60)
    assert middle_c.cc_averages == {0: 3.0, 1: 64.0}


def test_a_controller_on_the_onset_tick_keeps_its_place_around_the_key_press(tmp_path: Path) -> None:
    """The order a sequencer wrote the onset tick in decides which values the strike hears."""
    paths = _paths(tmp_path)
    _write(
        paths.source,
        [
            Message("control_change", channel=0, control=7, value=90, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("control_change", channel=0, control=1, value=20, time=0),
            Message("note_off", channel=0, note=60, velocity=0, time=480),
        ],
    )

    split_midi(paths.source, paths.render, paths.manifest, _config())

    voiced = _voiced_at_tick(paths.render, tick=0)
    assert voiced.index(("control_change", 7)) < voiced.index(("note_on", None))
    assert voiced.index(("note_on", None)) < max(
        index for index, item in enumerate(voiced) if item == ("control_change", 1)
    )


def test_a_gap_rounding_down_to_nothing_still_keeps_a_pedal_release_out_of_the_next_note(
    tmp_path: Path,
) -> None:
    """A shared tick would let the pedal release closing one note land after the next note's strike."""
    paths = _paths(tmp_path)
    _write(paths.source, _sustained_pair())

    manifest = split_midi(
        paths.source,
        paths.render,
        paths.manifest,
        _config(tracked_ccs=frozenset({SUSTAIN}), gap_measures=0.0),
    )

    assert [note.render.start_tick for note in manifest.notes] == [0, 481]
    assert _ticks_releasing_the_pedal_after_a_strike(paths.render) == []


def test_a_note_let_go_of_where_it_starts_is_reported_before_anything_is_written(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write(
        paths.source,
        [
            Message("note_on", channel=0, note=60, velocity=90, time=0),
            Message("note_off", channel=0, note=60, velocity=0, time=480),
            Message("note_on", channel=0, note=64, velocity=90, time=480),
            Message("note_off", channel=0, note=64, velocity=0, time=0),
        ],
    )

    with pytest.raises(MidiSourceError, match="sounds over no ticks"):
        split_midi(paths.source, paths.render, paths.manifest, _config())

    assert not paths.render.exists()
    assert not paths.manifest.exists()


def test_a_note_too_short_to_be_worth_a_sample_reaches_neither_the_render_nor_the_manifest(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(min_note_seconds=1.0))

    assert [note.pitch for note in manifest.notes] == [72]
    assert _strikes(paths.render) == [72]


def test_a_run_naming_no_shortest_note_takes_every_note_it_finds(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(min_note_seconds=None))

    assert [note.pitch for note in manifest.notes] == [60, 72]


def test_a_note_outlasting_the_longest_span_is_let_go_of_where_that_span_runs_out(tmp_path: Path) -> None:
    """The render is laid out at 120 bpm, so one second of sample is 960 of its ticks."""
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(tempo_bpm=120.0, max_note_seconds=1.0))

    held = next(note for note in manifest.notes if note.pitch == 72)
    assert held.render.release_end_tick - held.render.start_tick == 960
    assert held.render.release_end_seconds - held.render.start_seconds == 1.0


def test_a_note_the_run_cuts_short_is_recorded_over_the_stretch_the_render_holds_of_it(tmp_path: Path) -> None:
    """The manifest ties a sample to how it was played, which for a capped note is its opening."""
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(tempo_bpm=120.0, max_note_seconds=1.0))

    held = next(note for note in manifest.notes if note.pitch == 72)
    assert held.source.start_tick == 480
    assert (held.source.key_end_tick, held.source.release_end_tick) == (1440, 1440)


def test_a_key_still_down_where_the_longest_span_runs_out_is_released_in_the_render(tmp_path: Path) -> None:
    """The render sounds the note over the span the run takes, so the key comes up where it ends."""
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(
        paths.source,
        paths.render,
        paths.manifest,
        _config(tempo_bpm=120.0, max_note_seconds=1.0),
    )

    held = next(note for note in manifest.notes if note.pitch == 72)
    assert _released_at(paths.render, pitch=72) == [held.render.start_tick + 960]


def test_a_run_whose_bounds_take_no_note_writes_a_render_holding_none(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _notes_of_two_lengths())

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config(min_note_seconds=30.0))

    assert manifest.notes == ()
    assert paths.render.exists()


def test_a_manifest_holds_the_indented_json_a_reader_expects(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(paths.source, _performance())

    split_midi(paths.source, paths.render, paths.manifest, _config())

    document = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert set(document) == {"schema_version", "settings", "source", "render", "notes"}
    assert NoteManifest.model_validate(document).notes[0].cc_averages == {0: 3.0, 1: 64.0}


def test_a_run_naming_no_channels_copies_the_channels_carrying_notes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write(
        paths.source,
        [
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_on", channel=2, note=48, velocity=70, time=0),
            Message("note_off", channel=0, note=60, velocity=0, time=480),
            Message("note_off", channel=2, note=48, velocity=0, time=0),
        ],
    )

    manifest = split_midi(paths.source, paths.render, paths.manifest, _config())

    assert manifest.settings.cc_channels == (0, 2)


class _Paths:
    """Where one run reads from and writes to."""

    def __init__(self, directory: Path) -> None:
        self.source = directory / "performance.mid"
        self.render = directory / "renders" / "render.mid"
        self.manifest = directory / "renders" / "render.notes.json"


def _paths(directory: Path) -> _Paths:
    return _Paths(directory)


def _write(path: Path, messages: Sequence[Message]) -> None:
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    timing = MidiTrack()
    timing.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    timing.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    midi.tracks.append(timing)
    performance = MidiTrack()
    performance.extend(messages)
    midi.tracks.append(performance)
    midi.save(path)


def _performance() -> list[Message]:
    """Two overlapping notes, the lower one held past its key release by the pedal."""
    return [
        Message("control_change", channel=0, control=0, value=3, time=0),
        Message("control_change", channel=0, control=1, value=64, time=0),
        Message("note_on", channel=0, note=67, velocity=80, time=0),
        Message("note_on", channel=0, note=60, velocity=100, time=0),
        Message("control_change", channel=0, control=SUSTAIN, value=127, time=240),
        Message("note_off", channel=0, note=60, velocity=5, time=240),
        Message("note_off", channel=0, note=67, velocity=6, time=0),
        Message("control_change", channel=0, control=SUSTAIN, value=0, time=240),
    ]


def _notes_of_two_lengths() -> list[Message]:
    """One note sounding half a second and one held two and a half, laid out at 120 bpm."""
    return [
        Message("note_on", channel=0, note=60, velocity=100, time=0),
        Message("note_off", channel=0, note=60, velocity=5, time=480),
        Message("note_on", channel=0, note=72, velocity=90, time=0),
        Message("note_off", channel=0, note=72, velocity=5, time=2400),
    ]


def _sustained_pair() -> list[Message]:
    """Two notes, each held by the pedal past its key release."""
    return [
        Message("control_change", channel=0, control=SUSTAIN, value=127, time=0),
        Message("note_on", channel=0, note=60, velocity=100, time=0),
        Message("note_off", channel=0, note=60, velocity=10, time=240),
        Message("control_change", channel=0, control=SUSTAIN, value=0, time=240),
        Message("control_change", channel=0, control=SUSTAIN, value=127, time=240),
        Message("note_on", channel=0, note=62, velocity=100, time=0),
        Message("note_off", channel=0, note=62, velocity=10, time=240),
        Message("control_change", channel=0, control=SUSTAIN, value=0, time=240),
    ]


def _strikes(path: Path) -> list[int]:
    """Pitches a render strikes, in the order it writes them."""
    return [message.note for message in MidiFile(path).merged_track if message.type == "note_on"]


def _released_at(path: Path, pitch: int) -> list[int]:
    """Ticks a render lets the given key up on."""
    found: list[int] = []
    tick = 0
    for message in MidiFile(path).merged_track:
        tick += message.time
        if message.type == "note_off" and message.note == pitch:
            found.append(tick)

    return found


def _voiced_at_tick(path: Path, tick: int) -> list[tuple[str, int | None]]:
    """Kind and controller of each message a render writes on the given tick."""
    found: list[tuple[str, int | None]] = []
    current = 0
    for message in MidiFile(path).merged_track:
        current += message.time
        if current == tick and not message.is_meta:
            found.append((message.type, message.control if message.type == "control_change" else None))

    return found


def _ticks_releasing_the_pedal_after_a_strike(path: Path) -> list[int]:
    """Ticks where a pedal release follows a key press, which cuts the note just struck."""
    by_tick: dict[int, list[tuple[str, int | None, int]]] = {}
    tick = 0
    for message in MidiFile(path).merged_track:
        tick += message.time
        if message.is_meta:
            continue

        control = message.control if message.type == "control_change" else None
        value = message.value if message.type == "control_change" else message.velocity
        by_tick.setdefault(tick, []).append((message.type, control, value))

    return [tick for tick, written in sorted(by_tick.items()) if _releases_after_a_strike(written)]


def _releases_after_a_strike(written: Sequence[tuple[str, int | None, int]]) -> bool:
    """Whether one tick lets the pedal up somewhere after a key press."""
    strikes = [index for index, (kind, _, _) in enumerate(written) if kind == "note_on"]
    releases = [
        index
        for index, (kind, control, value) in enumerate(written)
        if kind == "control_change" and control == SUSTAIN and value < 64
    ]
    return any(release > strike for strike in strikes for release in releases)
