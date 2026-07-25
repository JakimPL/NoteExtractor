from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from stream_note_trimmer import TrimConfig, trim_note_stream


def test_trims_stereo_wav_from_render_times(tmp_path: Path) -> None:
    wav_path = tmp_path / "render.wav"
    manifest_path = tmp_path / "render.notes.json"
    output_directory = tmp_path / "samples"
    audio = np.column_stack(
        (
            np.arange(2000, dtype=np.int16),
            -np.arange(2000, dtype=np.int16),
        )
    )
    wavfile.write(wav_path, 1000, audio)
    _write_manifest(manifest_path)

    result = trim_note_stream(wav_path, manifest_path, output_directory)

    assert result.sample_rate == 1000
    assert len(result.samples) == 2
    first_path = output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav"
    second_path = output_directory / "0001_p067_v080_cc0-4_cc1-64.wav"
    assert first_path.exists()
    assert second_path.exists()

    rate, first = wavfile.read(first_path)
    assert rate == 1000
    np.testing.assert_array_equal(first, audio[100:301])


def test_padding_is_clamped_to_wav_bounds(tmp_path: Path) -> None:
    wav_path = tmp_path / "render.wav"
    manifest_path = tmp_path / "render.notes.json"
    output_directory = tmp_path / "samples"
    audio = np.arange(800, dtype=np.int16)
    wavfile.write(wav_path, 1000, audio)
    _write_manifest(
        manifest_path,
        notes=[
            {
                "pitch": 60,
                "velocity": 100,
                "cc_averages": {"1": 64.0},
                "render": {
                    "index": 0,
                    "start_seconds": 0.01,
                    "release_end_seconds": 0.79,
                },
            }
        ],
    )

    result = trim_note_stream(
        wav_path,
        manifest_path,
        output_directory,
        TrimConfig(pre_roll_seconds=0.05, post_roll_seconds=0.05),
    )

    sample = result.samples[0]
    assert sample.start_frame == 0
    assert sample.end_frame == 800
    assert sample.start_clamped
    assert sample.end_clamped


def test_refuses_existing_outputs_without_overwrite(tmp_path: Path) -> None:
    wav_path = tmp_path / "render.wav"
    manifest_path = tmp_path / "render.notes.json"
    output_directory = tmp_path / "samples"
    wavfile.write(wav_path, 1000, np.arange(1000, dtype=np.int16))
    _write_manifest(manifest_path, notes=[_single_note()])
    output_directory.mkdir()
    output = output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav"
    output.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        trim_note_stream(wav_path, manifest_path, output_directory)

    assert output.read_bytes() == b"existing"


def _write_manifest(path: Path, notes: list[dict[str, object]] | None = None) -> None:
    path.write_text(
        json.dumps(
            {
                "config": {"tracked_ccs": [0, 1]},
                "notes": notes
                or [
                    _single_note(),
                    {
                        "pitch": 67,
                        "velocity": 80,
                        "cc_averages": {"0": 4.0, "1": 64.0},
                        "render": {
                            "index": 1,
                            "start_seconds": 0.5,
                            "release_end_seconds": 0.75,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _single_note() -> dict[str, object]:
    return {
        "pitch": 60,
        "velocity": 100,
        "cc_averages": {"0": 3.0, "1": 63.875},
        "render": {
            "index": 0,
            "start_seconds": 0.1,
            "release_end_seconds": 0.3001,
        },
    }
