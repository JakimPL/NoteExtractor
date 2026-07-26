from pathlib import Path
from typing import Any

import pytest

from note_extractor.manifest.models import (
    ManifestSettings,
    NoteManifest,
    NoteRecord,
    NoteTiming,
    RenderInfo,
    RenderTiming,
    SourceInfo,
)


@pytest.fixture(name="manifest")
def fixture_manifest() -> NoteManifest:
    """Two-note manifest whose notes are stored ahead of their render order."""
    return NoteManifest(
        settings=ManifestSettings(tracked_ccs=(1, 64), cc_channels=(0,), sustain_pedal=True),
        source=SourceInfo(path=Path("performance.mid"), ticks_per_beat=480),
        render=RenderInfo(path=Path("render.mid"), tempo_bpm=115.0, time_signature="4/4", gap_measures=0.25),
        notes=(_note(source_id=1, render_index=1), _note(source_id=0, render_index=0)),
    )


@pytest.fixture(name="document")
def fixture_document(manifest: NoteManifest) -> dict[str, Any]:
    """The manifest as the JSON document a reader receives."""
    return manifest.model_dump(mode="json")


def _note(source_id: int, render_index: int) -> NoteRecord:
    """One valid record, placed in the source and in the render by its two indices."""
    source_seconds = float(source_id)
    render_seconds = float(render_index)
    return NoteRecord(
        source_id=source_id,
        channel=0,
        pitch=60,
        pitch_name="C4",
        velocity=100,
        release_velocity=20,
        cc_averages={1: 70.0, 64: 0.0},
        source=NoteTiming(
            start_tick=960 * source_id,
            key_end_tick=960 * source_id + 480,
            release_end_tick=960 * source_id + 480,
            onset_measures=0.5 * source_id,
            key_duration_measures=0.25,
            release_duration_measures=0.25,
            start_seconds=source_seconds,
            key_end_seconds=source_seconds + 0.5,
            release_end_seconds=source_seconds + 0.5,
        ),
        render=RenderTiming(
            index=render_index,
            start_tick=1440 * render_index,
            key_end_tick=1440 * render_index + 480,
            release_end_tick=1440 * render_index + 480,
            onset_measures=0.75 * render_index,
            key_duration_measures=0.25,
            release_duration_measures=0.25,
            start_seconds=render_seconds,
            key_end_seconds=render_seconds + 0.5,
            release_end_seconds=render_seconds + 0.5,
        ),
    )
