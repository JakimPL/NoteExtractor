from pathlib import Path
from typing import Final

import pytest

from note_extractor.cli.reporting import FAILURE_EXIT_CODE, SUCCESS_EXIT_CODE
from note_extractor.cli.trimmer import PROGRAM_NAME, main
from note_extractor.manifest.models import RollSettings

from .conftest import SAMPLE_RATE, WriteConfig, WriteManifest, WriteRender, frames_of, note_record

USAGE_EXIT_CODE: Final = 2
FIRST_SAMPLE_NAME: Final = "0000_p060_v100_cc1-63p875.wav"


def test_a_run_cuts_one_sample_for_every_note_of_the_manifest(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3), note_record(1, 0.5, 0.75)])
    samples = tmp_path / "samples"

    code = main([str(wav_path), str(manifest_path), str(samples)])

    assert code == SUCCESS_EXIT_CODE
    assert [path.name for path in sorted(samples.iterdir())] == [FIRST_SAMPLE_NAME, "0001_p060_v100_cc1-63p875.wav"]
    assert capsys.readouterr().out == f"wrote 2 samples to {samples}\nsample rate: {SAMPLE_RATE} Hz\n"


def test_a_run_states_how_many_samples_the_stream_ran_out_for(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(800)
    rolls = RollSettings(pre_roll_seconds=0.0, post_roll_seconds=0.1)
    manifest_path = write_manifest_file([note_record(0, 0.01, 0.79)], rolls)

    code = main([str(wav_path), str(manifest_path), str(tmp_path / "samples")])

    assert code == SUCCESS_EXIT_CODE
    assert "segments clamped to WAV bounds: 1" in capsys.readouterr().out


def test_a_run_whose_samples_all_fit_states_nothing_about_clamping(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])

    main([str(wav_path), str(manifest_path), str(tmp_path / "samples")])

    assert "clamped" not in capsys.readouterr().out


def test_a_run_cuts_by_the_rolls_the_manifest_carries(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    """A trim run asks for no rolls of its own: the split run stated them and the manifest holds them."""
    wav_path = write_render(2000)
    rolls = RollSettings(pre_roll_seconds=0.05, post_roll_seconds=0.1)
    manifest_path = write_manifest_file([note_record(0, 0.5, 0.7)], rolls)
    samples = tmp_path / "samples"

    main([str(wav_path), str(manifest_path), str(samples)])

    frames = frames_of(samples / FIRST_SAMPLE_NAME)
    assert frames[0] == 450
    assert len(frames) == 350


def test_the_decimal_places_a_document_states_reach_the_sample_names(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    write_config: WriteConfig,
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    samples = tmp_path / "samples"
    config = write_config(trim={"cc_decimals": 0})

    main([str(wav_path), str(manifest_path), str(samples), "--config", str(config)])

    assert [path.name for path in samples.iterdir()] == ["0000_p060_v100_cc1-64.wav"]


def test_a_stream_that_was_never_written_is_reported_on_stderr(
    tmp_path: Path,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    samples = tmp_path / "samples"

    code = main([str(tmp_path / "absent.wav"), str(manifest_path), str(samples)])

    captured = capsys.readouterr()
    assert code == FAILURE_EXIT_CODE
    assert captured.out == ""
    assert captured.err.startswith(f"{PROGRAM_NAME}: cannot read audio")
    assert not samples.exists()


def test_a_manifest_outside_the_schema_is_reported_on_stderr(
    tmp_path: Path,
    write_render: WriteRender,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = tmp_path / "render.notes.json"
    manifest_path.write_text('{"notes": []}', encoding="utf-8")

    code = main([str(wav_path), str(manifest_path), str(tmp_path / "samples")])

    assert code == FAILURE_EXIT_CODE
    assert "states schema version None" in capsys.readouterr().err


def test_a_sample_an_earlier_run_wrote_is_left_as_it_stands(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    existing = _written_earlier(tmp_path)

    code = main([str(wav_path), str(manifest_path), str(existing.parent)])

    assert code == FAILURE_EXIT_CODE
    assert "already exists" in capsys.readouterr().err
    assert existing.read_bytes() == b"earlier"


def test_a_run_asked_to_overwrite_replaces_an_earlier_sample(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    existing = _written_earlier(tmp_path)

    code = main([str(wav_path), str(manifest_path), str(existing.parent), "--overwrite"])

    assert code == SUCCESS_EXIT_CODE
    assert existing.read_bytes() != b"earlier"


def test_a_configuration_that_was_never_written_is_reported_on_stderr(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])

    code = main(
        [str(wav_path), str(manifest_path), str(tmp_path / "samples"), "--config", str(tmp_path / "absent.yaml")]
    )

    assert code == FAILURE_EXIT_CODE
    assert f"{PROGRAM_NAME}: cannot read configuration" in capsys.readouterr().err


def test_a_setting_outside_the_range_it_supports_is_reported_on_stderr(
    tmp_path: Path,
    write_render: WriteRender,
    write_manifest_file: WriteManifest,
    write_config: WriteConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = write_render(2000)
    manifest_path = write_manifest_file([note_record(0, 0.1, 0.3)])
    config = write_config(trim={"cc_decimals": 10})

    code = main([str(wav_path), str(manifest_path), str(tmp_path / "samples"), "--config", str(config)])

    assert code == FAILURE_EXIT_CODE
    assert f"{PROGRAM_NAME}: invalid settings" in capsys.readouterr().err


def test_a_command_line_missing_the_paths_it_needs_exits_as_a_usage_failure() -> None:
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == USAGE_EXIT_CODE


def _written_earlier(tmp_path: Path) -> Path:
    """A sample file left where the run about to be carried out would write its first cut."""
    samples = tmp_path / "samples"
    samples.mkdir()
    existing = samples / FIRST_SAMPLE_NAME
    existing.write_bytes(b"earlier")
    return existing
