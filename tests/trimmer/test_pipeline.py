from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from note_extractor.errors import AudioError, ManifestError, OutputConflictError
from note_extractor.manifest.models import RollSettings
from note_extractor.trimmer.pipeline import trim_note_stream

from .conftest import SAMPLE_RATE, WriteManifest, WriteRender, note_record, ramp, trim_config


def test_every_note_of_a_manifest_is_cut_into_a_sample_of_its_own(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3001), note_record(1, 0.5, 0.75, pitch=67, velocity=80)])
    output_directory = tmp_path / "samples"

    result = trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    assert result.sample_rate == SAMPLE_RATE
    assert result.source_frame_count == 2000
    assert [path.name for path in sorted(output_directory.iterdir())] == [
        "0000_p060_v100_cc0-3_cc1-63p875.wav",
        "0001_p067_v080_cc0-3_cc1-63p875.wav",
    ]


def test_a_sample_holds_the_frames_its_note_sounds_over(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3001)])
    output_directory = tmp_path / "samples"

    trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    rate, frames = wavfile.read(output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav")
    assert rate == SAMPLE_RATE
    np.testing.assert_array_equal(frames, ramp(2000)[100:301])


def test_a_sample_reaches_as_far_around_its_note_as_the_manifest_states(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    """A trim run takes the rolls from the split run that laid the render out, and asks for none."""
    wav_path = write_render(ramp(2000))
    rolls = RollSettings(pre_roll_seconds=0.05, post_roll_seconds=0.1)
    manifest_path = write_manifest_file([note_record(0, 0.5, 0.7)], rolls)
    output_directory = tmp_path / "samples"

    trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    _, frames = wavfile.read(output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav")
    np.testing.assert_array_equal(frames, ramp(2000)[450:800])


def test_a_stereo_render_is_cut_with_both_channels_kept(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    frames = np.column_stack((ramp(2000), -ramp(2000)))
    wav_path = write_render(frames)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3001)])
    output_directory = tmp_path / "samples"

    trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    _, written = wavfile.read(output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav")
    np.testing.assert_array_equal(written, frames[100:301])


def test_a_run_reports_the_samples_the_stream_ran_out_for(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(800))
    rolls = RollSettings(pre_roll_seconds=0.05, post_roll_seconds=0.05)
    manifest_path = write_manifest_file([note_record(0, 0.01, 0.79)], rolls)

    result = trim_note_stream(wav_path, manifest_path, tmp_path / "samples", trim_config())

    assert result.clamped_count == 1
    assert result.samples[0].start_clamped is True
    assert result.samples[0].end_clamped is True


def test_a_run_whose_samples_all_fit_reports_none_as_clamped(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3), note_record(1, 0.5, 0.75)])

    result = trim_note_stream(wav_path, manifest_path, tmp_path / "samples", trim_config())

    assert result.clamped_count == 0


def test_samples_are_cut_in_the_order_the_render_sounds_them(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    """A manifest may hold its notes in any order, while the samples follow the render."""
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(2, 0.8, 1.0), note_record(0, 0.1, 0.3), note_record(1, 0.4, 0.6)])

    result = trim_note_stream(wav_path, manifest_path, tmp_path / "samples", trim_config())

    assert [sample.note.render.index for sample in result.samples] == [0, 1, 2]


def test_the_number_of_decimals_a_run_keeps_reaches_the_sample_names(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3, cc_averages={1: 63.875})])
    output_directory = tmp_path / "samples"

    trim_note_stream(wav_path, manifest_path, output_directory, trim_config(cc_decimals=1))

    assert [path.name for path in output_directory.iterdir()] == ["0000_p060_v100_cc1-63p9.wav"]


def test_a_sample_an_earlier_run_wrote_is_left_as_it_stands(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    output_directory = tmp_path / "samples"
    output_directory.mkdir()
    existing = output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav"
    existing.write_bytes(b"earlier")

    with pytest.raises(OutputConflictError):
        trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    assert existing.read_bytes() == b"earlier"


def test_a_run_asked_to_overwrite_replaces_an_earlier_sample(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    output_directory = tmp_path / "samples"
    output_directory.mkdir()
    existing = output_directory / "0000_p060_v100_cc0-3_cc1-63p875.wav"
    existing.write_bytes(b"earlier")

    trim_note_stream(wav_path, manifest_path, output_directory, trim_config(overwrite=True))

    assert existing.read_bytes() != b"earlier"


def test_a_render_ending_before_its_notes_is_reported_before_any_sample_is_written(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(800))
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3), note_record(1, 0.9, 1.1)])
    output_directory = tmp_path / "samples"

    with pytest.raises(AudioError, match="note 1 opens after the audio ends"):
        trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    assert not output_directory.exists()


def test_a_manifest_that_was_never_written_is_reported(
    tmp_path: Path,
    write_render: WriteRender,
) -> None:
    wav_path = write_render(ramp(2000))

    with pytest.raises(ManifestError, match="cannot read manifest"):
        trim_note_stream(wav_path, tmp_path / "absent.notes.json", tmp_path / "samples", trim_config())


def test_a_render_that_was_never_written_is_reported(
    tmp_path: Path,
    write_manifest_file: WriteManifest,
) -> None:
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])

    with pytest.raises(AudioError, match="cannot read audio"):
        trim_note_stream(tmp_path / "absent.wav", manifest_path, tmp_path / "samples", trim_config())


def test_a_manifest_of_no_notes_leaves_the_output_directory_ready(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(ramp(2000))
    manifest_path = write_manifest_file([])
    output_directory = tmp_path / "samples"

    result = trim_note_stream(wav_path, manifest_path, output_directory, trim_config())

    assert result.samples == ()
    assert output_directory.is_dir()
