from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import numpy.typing as npt
import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack
from scipy.io import wavfile

from note_extractor.splitter import SplitConfig, split_midi
from note_extractor.timeline.meter import TimeSignature
from note_extractor.trimmer import TrimConfig, trim_note_stream

GOLDEN_DIRECTORY: Final = Path(__file__).parent / "golden"
UPDATE_VARIABLE: Final = "UPDATE_GOLDEN"

TICKS_PER_BEAT: Final = 480
SAMPLE_RATE: Final = 8000
TAIL_FRAMES: Final = 1_000
RAMP_STRIDE: Final = 37
RAMP_PERIOD: Final = 8_192
RAMP_OFFSET: Final = 4_096

SPLIT_CONFIG: Final = SplitConfig(
    tempo_bpm=115.0,
    signature=TimeSignature(numerator=4, denominator=4),
    tracked_ccs=frozenset({0, 1, 64}),
    cc_channels=None,
    gap_measures=0.25,
    sustain_pedal=True,
)
TRIM_CONFIG: Final = TrimConfig(
    pre_roll_seconds=0.005,
    post_roll_seconds=0.05,
    cc_decimals=3,
    overwrite=False,
)


@dataclass(frozen=True, slots=True)
class GoldenRun:
    """Outputs of one end-to-end split-then-trim run, reduced to comparable values."""

    run_metadata: dict[str, Any]
    note_records: list[dict[str, Any]]
    sample_digests: dict[str, Any]


def test_manifest_note_records_match_golden(golden_run: GoldenRun) -> None:
    """Per-note manifest records are the contract the trimmer and its filenames depend on."""
    expected = _load_or_update("expected_notes.json", golden_run.note_records)
    assert golden_run.note_records == expected


def test_manifest_run_metadata_matches_golden(golden_run: GoldenRun) -> None:
    """Top-level manifest metadata describes the run as a whole, which the note records sit under."""
    expected = _load_or_update("expected_run.json", golden_run.run_metadata)
    assert golden_run.run_metadata == expected


def test_trimmed_samples_match_golden(golden_run: GoldenRun) -> None:
    """Sample filenames and bytes are the user-visible product and must not drift."""
    expected = _load_or_update("expected_samples.json", golden_run.sample_digests)
    assert golden_run.sample_digests == expected


@pytest.fixture(name="golden_run", scope="module")
def fixture_golden_run(tmp_path_factory: pytest.TempPathFactory) -> GoldenRun:
    """Run both pipelines once over a fixed source performance and reduce the outputs."""
    directory = tmp_path_factory.mktemp("golden")
    source_path = directory / "source.mid"
    render_path = directory / "render.mid"
    manifest_path = directory / "render.notes.json"
    wav_path = directory / "render.wav"
    sample_directory = directory / "samples"

    _write_source_midi(source_path)
    split_midi(source_path, render_path, manifest_path, SPLIT_CONFIG)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    note_records = _note_records(manifest)

    _write_render_wav(wav_path, note_records)
    result = trim_note_stream(wav_path, manifest_path, sample_directory, TRIM_CONFIG)

    return GoldenRun(
        run_metadata=_run_metadata(manifest),
        note_records=note_records,
        sample_digests={
            "sample_rate": result.sample_rate,
            "count": len(result.samples),
            "files": {
                path.name: {"bytes": path.stat().st_size, "sha256": _digest(path)}
                for path in sorted(sample_directory.iterdir())
            },
        },
    )


def _note_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    notes = manifest["notes"]
    assert isinstance(notes, list)
    return list(notes)


def _run_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    """Reduce the manifest to everything except `notes`, with temporary paths made stable."""
    return {key: _replace_paths(value) for key, value in manifest.items() if key != "notes"}


def _replace_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _replace_paths(item) for key, item in value.items()}
    if isinstance(value, str) and value.endswith((".mid", ".json", ".wav")):
        return Path(value).name
    return value


def _load_or_update(name: str, produced: Any) -> Any:
    path = GOLDEN_DIRECTORY / name
    if os.environ.get(UPDATE_VARIABLE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(produced, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not path.exists():
        raise AssertionError(f"missing golden file {path}; regenerate with {UPDATE_VARIABLE}=1 pytest")
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_render_wav(path: Path, note_records: list[dict[str, Any]]) -> None:
    """Stand in for an external renderer with a deterministic stereo ramp long enough for every note."""
    last_second = max(float(note["render"]["release_end_seconds"]) for note in note_records)
    frame_count = math.ceil(last_second * SAMPLE_RATE) + TAIL_FRAMES
    left: npt.NDArray[np.int16] = ((np.arange(frame_count) * RAMP_STRIDE) % RAMP_PERIOD - RAMP_OFFSET).astype(np.int16)
    wavfile.write(path, SAMPLE_RATE, np.column_stack((left, -left)))


def _write_source_midi(path: Path) -> None:
    """Build a performance covering sustain, mid-note controllers, tempo and meter changes.

    The material deliberately includes overlapping notes, a repeated pitch and velocity pair,
    a `note_on` with zero velocity used as a release, and a key still down where the stream ends.
    """
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    midi.tracks.append(_build_track("Timing", _timing_events()))
    midi.tracks.append(_build_track("Right hand", _lead_events()))
    midi.tracks.append(_build_track("Left hand", _bass_events()))
    midi.save(path)


def _timing_events() -> list[tuple[int, MetaMessage]]:
    return [
        (0, MetaMessage("set_tempo", tempo=500_000)),
        (0, MetaMessage("time_signature", numerator=4, denominator=4)),
        (1920, MetaMessage("set_tempo", tempo=400_000)),
        (3840, MetaMessage("time_signature", numerator=3, denominator=4)),
    ]


def _lead_events() -> list[tuple[int, Message]]:
    return [
        (0, Message("control_change", channel=0, control=0, value=10)),
        (0, Message("control_change", channel=0, control=1, value=100)),
        (0, Message("note_on", channel=0, note=60, velocity=100)),
        (0, Message("note_on", channel=0, note=64, velocity=90)),
        (240, Message("control_change", channel=0, control=1, value=20)),
        (480, Message("control_change", channel=0, control=64, value=127)),
        (720, Message("note_off", channel=0, note=64, velocity=10)),
        (960, Message("note_off", channel=0, note=60, velocity=20)),
        (1200, Message("control_change", channel=0, control=1, value=90)),
        (1440, Message("control_change", channel=0, control=64, value=0)),
        (1920, Message("note_on", channel=0, note=60, velocity=100)),
        (2400, Message("note_off", channel=0, note=60, velocity=30)),
        (2880, Message("control_change", channel=0, control=0, value=64)),
        (2880, Message("note_on", channel=0, note=72, velocity=40)),
        (3360, Message("note_off", channel=0, note=72, velocity=50)),
        (3840, Message("note_on", channel=0, note=55, velocity=127)),
        (4320, Message("control_change", channel=0, control=1, value=5)),
    ]


def _bass_events() -> list[tuple[int, Message]]:
    return [
        (0, Message("control_change", channel=1, control=1, value=70)),
        (0, Message("note_on", channel=1, note=48, velocity=60)),
        (960, Message("note_off", channel=1, note=48, velocity=0)),
        (1440, Message("note_on", channel=1, note=50, velocity=70)),
        (1920, Message("note_on", channel=1, note=50, velocity=0)),
    ]


def _build_track(name: str, events: list[tuple[int, Any]]) -> MidiTrack:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    previous_tick = 0
    for tick, message in events:
        track.append(message.copy(time=tick - previous_tick))
        previous_tick = tick
    return track
