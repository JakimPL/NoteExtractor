from pathlib import Path
from typing import Final

import pytest

from note_extractor.cli.reporting import FAILURE_EXIT_CODE, SUCCESS_EXIT_CODE
from note_extractor.cli.splitter import PROGRAM_NAME, main
from note_extractor.manifest.storage import read_manifest

from .conftest import WritePerformance

USAGE_EXIT_CODE: Final = 2


def test_a_run_writes_the_render_and_the_manifest_beside_it(
    tmp_path: Path,
    write_performance: WritePerformance,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()
    render = tmp_path / "render.mid"

    code = main([str(source), str(render)])

    manifest_path = tmp_path / "render.notes.json"
    assert code == SUCCESS_EXIT_CODE
    assert render.exists()
    assert manifest_path.exists()
    assert capsys.readouterr().out == f"wrote {render}\nwrote {manifest_path}\nnotes: 2\n"


def test_a_run_writes_the_manifest_where_it_was_asked_to(
    tmp_path: Path,
    write_performance: WritePerformance,
) -> None:
    source = write_performance()
    manifest_path = tmp_path / "timings" / "notes.json"

    code = main([str(source), str(tmp_path / "render.mid"), "--manifest", str(manifest_path)])

    assert code == SUCCESS_EXIT_CODE
    assert manifest_path.exists()


def test_the_settings_a_run_states_reach_the_manifest(
    tmp_path: Path,
    write_performance: WritePerformance,
) -> None:
    source = write_performance()
    render = tmp_path / "render.mid"

    main(
        [
            str(source),
            str(render),
            "--tempo",
            "115",
            "--time-signature",
            "3/4",
            "--cc",
            "0,1,64",
            "--cc-channels",
            "0",
            "--gap-measures",
            "0.5",
        ]
    )

    manifest = read_manifest(tmp_path / "render.notes.json")
    assert manifest.render.tempo_bpm == 115.0
    assert manifest.render.time_signature == "3/4"
    assert manifest.render.gap_measures == 0.5
    assert manifest.settings.tracked_ccs == (0, 1, 64)
    assert manifest.settings.cc_channels == (0,)


def test_a_run_following_the_pedal_holds_each_note_as_long_as_it_did(
    tmp_path: Path,
    write_performance: WritePerformance,
) -> None:
    source = write_performance()

    main([str(source), str(tmp_path / "render.mid"), "--sustain-pedal"])

    manifest = read_manifest(tmp_path / "render.notes.json")
    assert manifest.settings.sustain_pedal is True


def test_a_run_leaving_the_pedal_alone_ends_each_note_at_its_key_release(
    tmp_path: Path,
    write_performance: WritePerformance,
) -> None:
    source = write_performance()

    main([str(source), str(tmp_path / "render.mid"), "--no-sustain-pedal"])

    manifest = read_manifest(tmp_path / "render.notes.json")
    assert manifest.settings.sustain_pedal is False


def test_a_source_that_was_never_written_is_reported_on_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    render = tmp_path / "render.mid"

    code = main([str(tmp_path / "absent.mid"), str(render)])

    captured = capsys.readouterr()
    assert code == FAILURE_EXIT_CODE
    assert captured.out == ""
    assert captured.err.startswith(f"{PROGRAM_NAME}: cannot read MIDI file")
    assert not render.exists()


@pytest.mark.parametrize("flag", [["--tempo", "inf"], ["--gap-measures", "inf"]])
def test_a_setting_the_models_turn_away_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    capsys: pytest.CaptureFixture[str],
    flag: list[str],
) -> None:
    source = write_performance()

    code = main([str(source), str(tmp_path / "render.mid"), *flag])

    assert code == FAILURE_EXIT_CODE
    assert f"{PROGRAM_NAME}: invalid settings" in capsys.readouterr().err


def test_a_signature_a_midi_header_cannot_state_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()

    code = main([str(source), str(tmp_path / "render.mid"), "--time-signature", "4/5"])

    assert code == FAILURE_EXIT_CODE
    assert "denominator must be a power of two" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    [
        ["--tempo", "-5"],
        ["--tempo", "fast"],
        ["--gap-measures", "-1"],
        ["--cc", "200"],
        ["--cc-channels", "16"],
        ["--time-signature", "4"],
    ],
)
def test_a_flag_the_command_line_cannot_read_exits_as_a_usage_failure(
    tmp_path: Path,
    write_performance: WritePerformance,
    flag: list[str],
) -> None:
    source = write_performance()

    with pytest.raises(SystemExit) as raised:
        main([str(source), str(tmp_path / "render.mid"), *flag])

    assert raised.value.code == USAGE_EXIT_CODE


def test_a_command_line_missing_the_paths_it_needs_exits_as_a_usage_failure() -> None:
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == USAGE_EXIT_CODE
