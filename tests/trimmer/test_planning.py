from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from note_extractor.errors import AudioError, OutputConflictError
from note_extractor.manifest.models import NoteRecord, RollSettings
from note_extractor.trimmer.naming import MIN_INDEX_WIDTH, SampleNaming
from note_extractor.trimmer.planning import SamplePlanner, TrimmedSample

from .conftest import NO_ROLLS, SAMPLE_RATE, note_record, ramp, stream_of, trim_config

FIFTY_MILLISECONDS: Final = RollSettings(pre_roll_seconds=0.05, post_roll_seconds=0.05)
FIRST_SAMPLE_NAME: Final = "0000_p060_v100_cc0-3_cc1-63p875.wav"


def test_a_cut_opens_at_the_frame_its_note_starts_on(tmp_path: Path) -> None:
    planned = _plan(tmp_path, [note_record(0, 0.1, 0.3001)], frame_count=2000)

    assert planned[0].start_frame == 100
    assert planned[0].end_frame == 301


def test_the_rolls_the_manifest_states_widen_a_cut_around_the_note_it_holds(tmp_path: Path) -> None:
    planned = _plan(tmp_path, [note_record(0, 0.1, 0.3)], frame_count=2000, rolls=FIFTY_MILLISECONDS)

    assert planned[0].start_frame == 50
    assert planned[0].end_frame == 350
    assert planned[0].start_clamped is False
    assert planned[0].end_clamped is False


def test_a_cut_reaching_past_both_ends_of_the_stream_is_held_within_it(tmp_path: Path) -> None:
    planned = _plan(tmp_path, [note_record(0, 0.01, 0.79)], frame_count=800, rolls=FIFTY_MILLISECONDS)

    assert planned[0].start_frame == 0
    assert planned[0].end_frame == 800
    assert planned[0].start_clamped is True
    assert planned[0].end_clamped is True


def test_a_cut_states_where_it_lands_in_the_stream(tmp_path: Path) -> None:
    planned = _plan(tmp_path, [note_record(0, 0.25, 0.75)], frame_count=2000)

    assert planned[0].sample_rate == SAMPLE_RATE
    assert planned[0].frame_count == 500
    assert planned[0].start_seconds == 0.25
    assert planned[0].end_seconds == 0.75


def test_every_cut_names_a_file_under_the_directory_the_run_writes_to(tmp_path: Path) -> None:
    output_directory = tmp_path / "samples"

    planned = _plan(tmp_path, [note_record(0, 0.1, 0.3), note_record(1, 0.4, 0.6)], frame_count=2000)

    assert [sample.output_path.parent for sample in planned] == [output_directory, output_directory]
    assert planned[0].output_path.name == FIRST_SAMPLE_NAME


def test_the_notes_of_a_run_are_planned_in_the_order_they_arrive(tmp_path: Path) -> None:
    notes = [note_record(2, 0.8, 1.0), note_record(0, 0.1, 0.3)]

    planned = _plan(tmp_path, notes, frame_count=2000)

    assert [sample.note.render.index for sample in planned] == [2, 0]


def test_a_run_of_no_notes_plans_no_cuts(tmp_path: Path) -> None:
    assert not _plan(tmp_path, [], frame_count=2000)


def test_a_note_laid_out_past_the_end_of_the_stream_is_reported(tmp_path: Path) -> None:
    """A render cut short leaves the notes after it with no audio to sound."""
    notes = [note_record(0, 0.1, 0.3), note_record(1, 0.9, 1.1)]

    with pytest.raises(AudioError, match="note 1 opens after the audio ends: 0.900000s into 0.800000s"):
        _plan(tmp_path, notes, frame_count=800)


def test_two_notes_claiming_one_file_are_reported(tmp_path: Path) -> None:
    """Writing both would leave one note's sample holding the other note's audio."""
    notes = [note_record(0, 0.1, 0.3), note_record(0, 0.4, 0.6)]

    with pytest.raises(OutputConflictError, match="claimed by more than one note"):
        _plan(tmp_path, notes, frame_count=2000)


def test_a_sample_an_earlier_run_wrote_is_kept(tmp_path: Path) -> None:
    existing = _written_earlier(tmp_path)

    with pytest.raises(OutputConflictError, match=f"sample file already exists: {existing}"):
        _plan(tmp_path, [note_record(0, 0.1, 0.3)], frame_count=2000)


def test_a_run_asked_to_overwrite_plans_over_an_earlier_sample(tmp_path: Path) -> None:
    _written_earlier(tmp_path)

    planned = _plan(tmp_path, [note_record(0, 0.1, 0.3)], frame_count=2000, overwrite=True)

    assert planned[0].output_path.name == FIRST_SAMPLE_NAME


def test_a_cut_closing_before_it_opens_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must close after it opens"):
        TrimmedSample(
            note=note_record(0, 0.1, 0.3),
            output_path=tmp_path / "sample.wav",
            sample_rate=SAMPLE_RATE,
            start_frame=300,
            end_frame=100,
            start_clamped=False,
            end_clamped=False,
        )


def _plan(
    tmp_path: Path,
    notes: Sequence[NoteRecord],
    frame_count: int,
    rolls: RollSettings = NO_ROLLS,
    overwrite: bool = False,
) -> tuple[TrimmedSample, ...]:
    """Cuts one planner settles on for the given notes against a stream of the given length."""
    config = trim_config(overwrite=overwrite)
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=config.cc_decimals)
    planner = SamplePlanner(config, rolls, naming, tmp_path / "samples")
    return planner.plan(notes, stream_of(ramp(frame_count)))


def _written_earlier(tmp_path: Path) -> Path:
    """A sample file left where the run about to be planned would write its first cut."""
    output_directory = tmp_path / "samples"
    output_directory.mkdir()
    existing = output_directory / FIRST_SAMPLE_NAME
    existing.write_bytes(b"earlier")
    return existing
