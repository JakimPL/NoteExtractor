import pytest
from pydantic import ValidationError

from note_extractor.trimmer.naming import MIN_INDEX_WIDTH, SampleNaming

from .conftest import note_record


def test_a_name_states_the_index_pitch_velocity_and_controllers_of_its_note() -> None:
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=3)

    name = naming.filename_for(note_record(0, 0.1, 0.3, pitch=60, velocity=100))

    assert name == "0000_p060_v100_cc0-3_cc1-63p875.wav"


def test_a_run_keeping_no_decimals_names_whole_controller_values() -> None:
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=0)

    name = naming.filename_for(note_record(1, 0.1, 0.3, cc_averages={0: 3.4, 1: 63.875, 11: 100.0}))

    assert name == "0001_p060_v100_cc0-3_cc1-64_cc11-100.wav"


def test_a_run_keeping_every_decimal_writes_the_places_that_carry_a_value() -> None:
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=9)

    name = naming.filename_for(note_record(2, 0.1, 0.3, cc_averages={1: 63.123456789}))

    assert name == "0002_p060_v100_cc1-63p123456789.wav"


def test_controllers_are_named_in_ascending_order() -> None:
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=1)

    name = naming.filename_for(note_record(3, 0.1, 0.3, cc_averages={11: 1.0, 1: 2.0, 64: 3.0}))

    assert name == "0003_p060_v100_cc1-2_cc11-1_cc64-3.wav"


def test_a_note_played_with_no_tracked_controllers_is_named_by_its_note_alone() -> None:
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=3)

    name = naming.filename_for(note_record(4, 0.1, 0.3, pitch=127, velocity=1, cc_averages={}))

    assert name == "0004_p127_v001.wav"


def test_a_controller_average_of_negative_zero_keeps_its_sign_out_of_the_name() -> None:
    """A file name stays to characters every filesystem accepts, whatever sign a value carries."""
    naming = SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=3)

    name = naming.filename_for(note_record(5, 0.1, 0.3, cc_averages={1: -0.0}))

    assert name == "0005_p060_v100_cc1-m0.wav"


@pytest.mark.parametrize(
    ("highest_index", "expected_width"),
    [(0, 4), (9, 4), (999, 4), (9999, 4), (10_000, 5), (123_456, 6)],
)
def test_indices_are_written_wide_enough_for_the_longest_render(highest_index: int, expected_width: int) -> None:
    notes = [note_record(0, 0.1, 0.3), note_record(highest_index, 0.4, 0.6)]

    assert SampleNaming.for_notes(notes, cc_decimals=3).index_width == expected_width


def test_the_names_of_one_run_sort_in_the_order_the_render_sounds_them() -> None:
    notes = [note_record(index, index + 0.1, index + 0.3) for index in (0, 9, 10, 10_000)]
    naming = SampleNaming.for_notes(notes, cc_decimals=3)

    names = [naming.filename_for(note) for note in notes]

    assert names == sorted(names)
    assert names[0] == "00000_p060_v100_cc0-3_cc1-63p875.wav"


def test_a_render_of_no_notes_is_named_at_the_smallest_supported_width() -> None:
    assert SampleNaming.for_notes([], cc_decimals=3).index_width == MIN_INDEX_WIDTH


@pytest.mark.parametrize("index_width", [0, MIN_INDEX_WIDTH - 1])
def test_a_width_too_narrow_to_order_a_render_is_rejected(index_width: int) -> None:
    with pytest.raises(ValidationError):
        SampleNaming(index_width=index_width, cc_decimals=3)


@pytest.mark.parametrize("cc_decimals", [-1, 10])
def test_a_number_of_decimals_outside_the_supported_range_is_rejected(cc_decimals: int) -> None:
    with pytest.raises(ValidationError):
        SampleNaming(index_width=MIN_INDEX_WIDTH, cc_decimals=cc_decimals)
