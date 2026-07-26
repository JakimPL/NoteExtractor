from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt
import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack
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

TICKS_PER_BEAT: Final = 480
SAMPLE_RATE: Final = 1000
TRACKED_CCS: Final = (1,)
CC_AVERAGES: Final = {1: 63.875}

WritePerformance = Callable[[], Path]
WriteManifest = Callable[[Sequence[NoteRecord]], Path]
WriteRender = Callable[[int], Path]


@pytest.fixture(name="write_performance")
def fixture_write_performance(tmp_path: Path) -> WritePerformance:
    """Writes one two note MIDI performance and gives back where it landed."""

    def write() -> Path:
        path = tmp_path / "performance.mid"
        midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
        timing = MidiTrack()
        timing.append(MetaMessage("set_tempo", tempo=500_000, time=0))
        timing.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        midi.tracks.append(timing)
        performance = MidiTrack()
        performance.append(Message("control_change", channel=0, control=1, value=64, time=0))
        performance.append(Message("note_on", channel=0, note=60, velocity=100, time=0))
        performance.append(Message("note_off", channel=0, note=60, velocity=5, time=480))
        performance.append(Message("note_on", channel=0, note=67, velocity=80, time=480))
        performance.append(Message("note_off", channel=0, note=67, velocity=5, time=480))
        midi.tracks.append(performance)
        midi.save(path)
        return path

    return write


@pytest.fixture(name="write_manifest_file")
def fixture_write_manifest_file(tmp_path: Path) -> WriteManifest:
    """Writes one manifest holding the given notes and gives back where it landed."""

    def write(notes: Sequence[NoteRecord]) -> Path:
        path = tmp_path / "render.notes.json"
        write_manifest(path, _manifest(notes))
        return path

    return write


@pytest.fixture(name="write_render")
def fixture_write_render(tmp_path: Path) -> WriteRender:
    """Writes one WAV of the given length and gives back where it landed."""

    def write(frame_count: int) -> Path:
        path = tmp_path / "render.wav"
        wavfile.write(path, SAMPLE_RATE, _ramp(frame_count))
        return path

    return write


def note_record(render_index: int, start_seconds: float, release_end_seconds: float) -> NoteRecord:
    """One note sounding over the given stretch of the render, struck at middle C."""
    return NoteRecord(
        source_id=render_index,
        channel=0,
        pitch=60,
        pitch_name="C4",
        velocity=100,
        release_velocity=0,
        cc_averages=dict(CC_AVERAGES),
        source=_timing(start_seconds, release_end_seconds),
        render=RenderTiming.at_index(render_index, _timing(start_seconds, release_end_seconds)),
    )


def _manifest(notes: Sequence[NoteRecord]) -> NoteManifest:
    """Manifest carrying the given notes, settled with the settings these tests read back."""
    return NoteManifest(
        settings=ManifestSettings(tracked_ccs=TRACKED_CCS, cc_channels=(0,), sustain_pedal=True),
        source=SourceInfo(path=Path("performance.mid"), ticks_per_beat=TICKS_PER_BEAT),
        render=RenderInfo(path=Path("render.mid"), tempo_bpm=120.0, time_signature="4/4", gap_measures=0.25),
        notes=tuple(notes),
    )


def _timing(start_seconds: float, release_end_seconds: float) -> NoteTiming:
    """Timing of one note, with its ticks and measures settled from the seconds it sounds over."""
    start_tick = round(start_seconds * TICKS_PER_BEAT)
    end_tick = round(release_end_seconds * TICKS_PER_BEAT)
    return NoteTiming(
        start_tick=start_tick,
        key_end_tick=end_tick,
        release_end_tick=end_tick,
        onset_measures=start_seconds,
        key_duration_measures=release_end_seconds - start_seconds,
        release_duration_measures=release_end_seconds - start_seconds,
        start_seconds=start_seconds,
        key_end_seconds=release_end_seconds,
        release_end_seconds=release_end_seconds,
    )


def _ramp(frame_count: int) -> npt.NDArray[np.int16]:
    """Frames counting up from zero, so a cut of them states where it was taken from."""
    return np.arange(frame_count, dtype=np.int16)


def frames_of(path: Path) -> npt.NDArray[np.int16]:
    """Frames one WAV file holds."""
    _, frames = wavfile.read(path)
    assert frames.dtype == np.int16
    return frames
