from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt
import pytest
from scipy.io import wavfile

from note_extractor.manifest.models import (
    ManifestSettings,
    NoteManifest,
    NoteRecord,
    NoteTiming,
    RenderInfo,
    RenderTiming,
    SourceInfo,
)
from note_extractor.manifest.storage import write_manifest
from note_extractor.trimmer.audio import AudioStream

SAMPLE_RATE: Final = 1000
TICKS_PER_SECOND: Final = 960
DEFAULT_CC_AVERAGES: Final = {0: 3.0, 1: 63.875}

WriteManifest = Callable[[Sequence[NoteRecord]], Path]
WriteRender = Callable[[npt.NDArray[np.int16]], Path]


@pytest.fixture(name="write_manifest_file")
def fixture_write_manifest_file(tmp_path: Path) -> WriteManifest:
    """Writer storing the given notes as the manifest a trim run reads."""

    def write(notes: Sequence[NoteRecord]) -> Path:
        path = tmp_path / "render.notes.json"
        write_manifest(path, manifest_of(notes))
        return path

    return write


@pytest.fixture(name="write_render")
def fixture_write_render(tmp_path: Path) -> WriteRender:
    """Writer storing the given frames as the rendered stream a trim run cuts."""

    def write(samples: npt.NDArray[np.int16]) -> Path:
        path = tmp_path / "render.wav"
        wavfile.write(path, SAMPLE_RATE, samples)
        return path

    return write


def manifest_of(notes: Sequence[NoteRecord]) -> NoteManifest:
    """Manifest carrying the given notes, with settings a split run would have stated."""
    return NoteManifest(
        settings=ManifestSettings(tracked_ccs=(0, 1), cc_channels=(0,), sustain_pedal=True),
        source=SourceInfo(path=Path("performance.mid"), ticks_per_beat=480),
        render=RenderInfo(path=Path("render.mid"), tempo_bpm=120.0, time_signature="4/4", gap_measures=0.25),
        notes=tuple(notes),
    )


def note_record(
    render_index: int,
    start_seconds: float,
    release_end_seconds: float,
    pitch: int = 60,
    velocity: int = 100,
    cc_averages: Mapping[int, float] = DEFAULT_CC_AVERAGES,
) -> NoteRecord:
    """One record placing a note at the given stretch of the render.

    The source timing repeats that stretch, which keeps the record valid while leaving the render
    timing the only thing a trim run reads.
    """
    timing = _timing(start_seconds, release_end_seconds)
    return NoteRecord(
        source_id=render_index,
        channel=0,
        pitch=pitch,
        pitch_name="C4",
        velocity=velocity,
        release_velocity=0,
        cc_averages=dict(cc_averages),
        source=timing,
        render=RenderTiming.at_index(render_index, timing),
    )


def stream_of(samples: npt.NDArray[np.int16], sample_rate: int = SAMPLE_RATE) -> AudioStream:
    """Stream holding the given frames at the rate the tests record at."""
    return AudioStream(sample_rate=sample_rate, samples=samples)


def ramp(frame_count: int) -> npt.NDArray[np.int16]:
    """Mono frames counting up from zero, so every frame states its own position."""
    return np.arange(frame_count, dtype=np.int16)


def _timing(start_seconds: float, release_end_seconds: float) -> NoteTiming:
    """Where one note sits, stated in the ticks, measures, and seconds its stretch spans."""
    return NoteTiming(
        start_tick=round(start_seconds * TICKS_PER_SECOND),
        key_end_tick=round(release_end_seconds * TICKS_PER_SECOND),
        release_end_tick=round(release_end_seconds * TICKS_PER_SECOND),
        onset_measures=start_seconds / 2,
        key_duration_measures=(release_end_seconds - start_seconds) / 2,
        release_duration_measures=(release_end_seconds - start_seconds) / 2,
        start_seconds=start_seconds,
        key_end_seconds=release_end_seconds,
        release_end_seconds=release_end_seconds,
    )
