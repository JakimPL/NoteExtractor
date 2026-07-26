from pathlib import Path
from typing import Final

import pytest

from note_extractor.manifest.models import NoteManifest
from note_extractor.midi.events import EventPosition
from note_extractor.splitter.arrangement.layout import lay_out_notes
from note_extractor.splitter.config import RenderSettings, SplitConfig
from note_extractor.splitter.manifest_builder import ManifestBuilder, PerformanceTiming, pitch_name
from note_extractor.splitter.notes import SourceNote
from note_extractor.timeline.meter import MeterMap, TimeSignature
from note_extractor.timeline.tempo import TempoMap

TICKS_PER_BEAT: Final = 480
SOURCE_PATH: Final = Path("performance.mid")
RENDER_PATH: Final = Path("render.mid")


@pytest.mark.parametrize(
    ("pitch", "name"),
    [(0, "C-1"), (12, "C0"), (60, "C4"), (61, "C#4"), (69, "A4"), (71, "B4"), (72, "C5"), (127, "G9")],
)
def test_a_pitch_is_named_by_its_class_and_octave(pitch: int, name: str) -> None:
    assert pitch_name(pitch) == name


def test_a_manifest_states_the_settings_the_run_was_carried_out_with() -> None:
    settings = _settings(SplitConfig(tempo_bpm=115.0, tracked_ccs=frozenset({64, 1}), gap_measures=0.25))

    manifest = _build(settings, notes=[_note(source_id=0, start_tick=0, key_end_tick=480, release_end_tick=720)])

    assert manifest.settings.tracked_ccs == (1, 64)
    assert manifest.settings.cc_channels == (0,)
    assert manifest.settings.sustain_pedal is True
    assert manifest.source.path == SOURCE_PATH
    assert manifest.source.ticks_per_beat == TICKS_PER_BEAT
    assert manifest.render.path == RENDER_PATH
    assert manifest.render.tempo_bpm == 115.0
    assert manifest.render.time_signature == "4/4"
    assert manifest.render.gap_measures == 0.25


def test_a_run_in_an_uncommon_meter_states_the_signature_it_was_laid_out_in() -> None:
    settings = _settings(SplitConfig(signature=TimeSignature(numerator=7, denominator=8)))

    manifest = _build(settings, notes=[_note(source_id=0, start_tick=0, key_end_tick=480, release_end_tick=480)])

    assert manifest.render.time_signature == "7/8"


def test_a_record_states_where_its_note_was_played_alongside_where_it_was_laid_out() -> None:
    settings = _settings(SplitConfig(tempo_bpm=120.0, gap_measures=0.25))
    note = _note(source_id=0, start_tick=1920, key_end_tick=2400, release_end_tick=2640)

    record = _build(settings, notes=[note]).notes[0]

    assert record.source_id == 0
    assert record.pitch == 60
    assert record.pitch_name == "C4"
    assert record.velocity == 100
    assert record.release_velocity == 20
    assert (record.source.start_tick, record.source.key_end_tick, record.source.release_end_tick) == (1920, 2400, 2640)
    assert (record.render.index, record.render.start_tick, record.render.release_end_tick) == (0, 0, 720)
    assert record.source.onset_measures == 1.0
    assert record.render.onset_measures == 0.0
    assert record.source.start_seconds == 2.0
    assert record.render.start_seconds == 0.0
    assert record.render.release_end_seconds == 0.75


def test_the_timings_of_a_note_are_read_from_the_performance_it_belongs_to() -> None:
    """The source keeps its own tempo changes while the render holds one tempo throughout."""
    settings = _settings(SplitConfig(tempo_bpm=120.0))
    source = PerformanceTiming(
        tempo=TempoMap(TICKS_PER_BEAT, [(0, 1_000_000)]),
        meter=MeterMap.constant(TICKS_PER_BEAT, TimeSignature(numerator=4, denominator=4)),
    )
    note = _note(source_id=0, start_tick=480, key_end_tick=960, release_end_tick=960)

    record = _build(settings, notes=[note], source=source).notes[0]

    assert record.source.start_seconds == 1.0
    assert record.render.start_seconds == 0.0
    assert record.source.key_end_seconds == 2.0
    assert record.render.key_end_seconds == 0.5


def test_the_averages_of_a_note_are_stated_in_controller_order() -> None:
    settings = _settings(SplitConfig())
    note = _note(source_id=0, start_tick=0, key_end_tick=480, release_end_tick=480)

    record = _build(settings, notes=[note], averages={0: {64: 12.5, 1: 90.0}}).notes[0]

    assert list(record.cc_averages) == [1, 64]
    assert record.cc_averages == {1: 90.0, 64: 12.5}


def test_the_notes_of_a_manifest_follow_the_order_they_were_laid_out_in() -> None:
    settings = _settings(SplitConfig())
    notes = [
        _note(source_id=0, start_tick=0, key_end_tick=480, release_end_tick=480, pitch=72),
        _note(source_id=1, start_tick=960, key_end_tick=1440, release_end_tick=1440, pitch=60),
    ]

    manifest = _build(settings, notes=notes, averages={0: {}, 1: {}})

    assert [record.render.index for record in manifest.notes] == [0, 1]
    assert [record.pitch for record in manifest.notes] == [60, 72]
    assert [record.source_id for record in manifest.notes] == [1, 0]


def _settings(config: SplitConfig) -> RenderSettings:
    return RenderSettings.from_config(config, TICKS_PER_BEAT, frozenset({0}))


def _render_timing(settings: RenderSettings) -> PerformanceTiming:
    return PerformanceTiming(
        tempo=TempoMap.constant(settings.ticks_per_beat, settings.tempo_bpm),
        meter=MeterMap.constant(settings.ticks_per_beat, settings.signature),
    )


def _build(
    settings: RenderSettings,
    notes: list[SourceNote],
    source: PerformanceTiming | None = None,
    averages: dict[int, dict[int, float]] | None = None,
) -> NoteManifest:
    source_timing = source if source is not None else _render_timing(settings)
    builder = ManifestBuilder(settings, source_timing, _render_timing(settings))
    return builder.build(
        SOURCE_PATH,
        RENDER_PATH,
        lay_out_notes(notes, settings.gap_ticks),
        averages if averages is not None else {note.source_id: {} for note in notes},
    )


def _note(
    source_id: int,
    start_tick: int,
    key_end_tick: int,
    release_end_tick: int,
    pitch: int = 60,
) -> SourceNote:
    return SourceNote(
        source_id=source_id,
        channel=0,
        pitch=pitch,
        velocity=100,
        release_velocity=20,
        start=EventPosition(tick=start_tick, sequence=source_id),
        key_end=EventPosition(tick=key_end_tick, sequence=source_id + 10),
        release_end=EventPosition(tick=release_end_tick, sequence=source_id + 20),
    )
