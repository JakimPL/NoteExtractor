from pathlib import Path
from typing import Final

import pytest

from note_extractor.cli.reporting import FAILURE_EXIT_CODE, SUCCESS_EXIT_CODE
from note_extractor.cli.splitter import PROGRAM_NAME, main
from note_extractor.manifest.storage import read_manifest

from .conftest import WriteConfig, WritePerformance

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


def test_the_settings_a_document_states_reach_the_manifest(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
) -> None:
    source = write_performance()
    config = write_config(
        split={
            "tempo_bpm": 115.0,
            "signature": "3/4",
            "tracked_ccs": [0, 1, 64],
            "cc_channels": [0],
            "gap_measures": 0.5,
        }
    )

    main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    manifest = read_manifest(tmp_path / "render.notes.json")
    assert manifest.render.tempo_bpm == 115.0
    assert manifest.render.time_signature == "3/4"
    assert manifest.render.gap_measures == 0.5
    assert manifest.settings.tracked_ccs == (0, 1, 64)
    assert manifest.settings.cc_channels == (0,)


def test_the_rolls_a_document_states_are_recorded_for_the_trimmer(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
) -> None:
    """The split run is where a roll is stated, and the manifest is how it reaches the cut."""
    source = write_performance()
    config = write_config(rolls={"pre_roll_seconds": 0.01, "post_roll_seconds": 0.4})

    main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    rolls = read_manifest(tmp_path / "render.notes.json").settings.rolls
    assert (rolls.pre_roll_seconds, rolls.post_roll_seconds) == (0.01, 0.4)


def test_a_document_naming_a_shortest_note_leaves_the_briefer_ones_out(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
) -> None:
    """The spans a note sounds between arrive in the document, like every other value a run takes."""
    source = write_performance()
    config = write_config(split={"min_note_seconds": 2.0})

    main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert read_manifest(tmp_path / "render.notes.json").notes == ()


def test_a_document_naming_a_longest_note_lets_a_held_one_go_where_it_runs_out(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
) -> None:
    source = write_performance()
    config = write_config(split={"min_note_seconds": None, "max_note_seconds": 1.0})

    main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    notes = read_manifest(tmp_path / "render.notes.json").notes
    assert [note.render.release_end_seconds - note.render.start_seconds for note in notes] == [1.0, 1.0]


def test_a_shortest_note_outlasting_the_longest_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()
    config = write_config(split={"min_note_seconds": 5.0, "max_note_seconds": 1.0})

    code = main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert code == FAILURE_EXIT_CODE
    assert "shortest note must not outlast the longest" in capsys.readouterr().err


@pytest.mark.parametrize("sustain_pedal", [True, False])
def test_a_run_holds_each_note_as_long_as_its_document_asks_it_to(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
    sustain_pedal: bool,
) -> None:
    source = write_performance()
    config = write_config(split={"sustain_pedal": sustain_pedal})

    main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert read_manifest(tmp_path / "render.notes.json").settings.sustain_pedal is sustain_pedal


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


def test_a_configuration_that_was_never_written_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()

    code = main([str(source), str(tmp_path / "render.mid"), "--config", str(tmp_path / "absent.yaml")])

    assert code == FAILURE_EXIT_CODE
    assert f"{PROGRAM_NAME}: cannot read configuration" in capsys.readouterr().err


@pytest.mark.parametrize(
    "setting",
    [
        {"tempo_bpm": -5},
        {"gap_measures": -1},
        {"tracked_ccs": [200]},
        {"min_note_seconds": 0},
        {"max_note_seconds": -1},
    ],
)
def test_a_setting_outside_the_range_it_supports_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
    capsys: pytest.CaptureFixture[str],
    setting: dict[str, object],
) -> None:
    source = write_performance()
    config = write_config(split=setting)

    code = main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert code == FAILURE_EXIT_CODE
    assert f"{PROGRAM_NAME}: invalid settings" in capsys.readouterr().err


def test_a_signature_a_midi_header_cannot_state_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    write_config: WriteConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()
    config = write_config(split={"signature": "4/5"})

    code = main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert code == FAILURE_EXIT_CODE
    assert "denominator must be a power of two" in capsys.readouterr().err


def test_a_document_holding_no_settings_is_reported_on_stderr(
    tmp_path: Path,
    write_performance: WritePerformance,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = write_performance()
    config = tmp_path / "noteextractor.yaml"
    config.write_text("- split\n- rolls\n", encoding="utf-8")

    code = main([str(source), str(tmp_path / "render.mid"), "--config", str(config)])

    assert code == FAILURE_EXIT_CODE
    assert "must hold named sections of settings" in capsys.readouterr().err


def test_a_command_line_missing_the_paths_it_needs_exits_as_a_usage_failure() -> None:
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == USAGE_EXIT_CODE
