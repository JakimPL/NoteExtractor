from typing import Any, Final

import pytest
from pydantic import ValidationError

from note_extractor.errors import ConfigurationError
from note_extractor.splitter.config import MIN_GAP_TICKS, RenderSettings, SplitConfig
from note_extractor.timeline.meter import TimeSignature

from .conftest import COMMON_TIME, MEASURE_TICKS, TICKS_PER_BEAT, settings, split_config

ROLLS: Final[dict[str, object]] = {"pre_roll_seconds": 0.0, "post_roll_seconds": 0.25}
SPLIT: Final[dict[str, object]] = {
    "tempo_bpm": 115.0,
    "signature": "3/4",
    "tracked_ccs": [0, 1],
    "cc_channels": None,
    "gap_measures": 0.5,
    "sustain_pedal": False,
}


def test_a_document_states_every_setting_a_run_is_carried_out_with() -> None:
    config = SplitConfig.from_document({"split": SPLIT, "rolls": ROLLS})

    assert config.tempo_bpm == 115.0
    assert config.signature == TimeSignature(numerator=3, denominator=4)
    assert config.tracked_ccs == frozenset({0, 1})
    assert config.cc_channels is None
    assert config.gap_measures == 0.5
    assert config.sustain_pedal is False
    assert (config.rolls.pre_roll_seconds, config.rolls.post_roll_seconds) == (0.0, 0.25)


def test_the_rolls_travel_beside_the_split_settings_they_are_recorded_with() -> None:
    """One document states the rolls once, and the split run is what carries them to the manifest."""
    config = SplitConfig.from_document({"split": SPLIT, "rolls": {**ROLLS, "post_roll_seconds": 1.5}})

    assert config.rolls.post_roll_seconds == 1.5


@pytest.mark.parametrize("missing", ["split", "rolls"])
def test_a_document_leaving_a_section_out_names_the_one_it_states_nothing_for(missing: str) -> None:
    document: dict[str, dict[str, object]] = {"split": SPLIT, "rolls": ROLLS}
    del document[missing]

    with pytest.raises(ConfigurationError, match=f"states no {missing!r} settings"):
        SplitConfig.from_document(document)


def test_a_setting_a_document_states_outside_its_range_names_the_field() -> None:
    with pytest.raises(ConfigurationError, match="invalid settings: tempo_bpm"):
        SplitConfig.from_document({"split": {**SPLIT, "tempo_bpm": 0.0}, "rolls": ROLLS})


def test_a_roll_a_document_states_outside_its_range_names_the_field() -> None:
    with pytest.raises(ConfigurationError, match=r"invalid settings: rolls\.post_roll_seconds"):
        SplitConfig.from_document({"split": SPLIT, "rolls": {**ROLLS, "post_roll_seconds": -0.1}})


def test_a_setting_a_document_does_not_declare_is_reported() -> None:
    with pytest.raises(ConfigurationError, match="invalid settings: bpm"):
        SplitConfig.from_document({"split": {**SPLIT, "bpm": 115.0}, "rolls": ROLLS})


@pytest.mark.parametrize("written", ["3/4", "7/8", "4/4"])
def test_a_signature_a_document_writes_is_read_the_way_it_was_written(written: str) -> None:
    assert str(SplitConfig.from_document({"split": {**SPLIT, "signature": written}, "rolls": ROLLS}).signature) == (
        written
    )


@pytest.mark.parametrize("written", ["4", "4/", "four/four", "0/4"])
def test_a_signature_a_document_writes_unreadably_is_reported(written: str) -> None:
    with pytest.raises(ConfigurationError, match="invalid settings: signature"):
        SplitConfig.from_document({"split": {**SPLIT, "signature": written}, "rolls": ROLLS})


@pytest.mark.parametrize("denominator", [3, 5, 6, 7, 12])
def test_a_signature_a_midi_header_cannot_state_is_rejected(denominator: int) -> None:
    """A MIDI header states the note value as a power of two, so any other value never reaches a file."""
    with pytest.raises(ValidationError, match="must be a power of two"):
        split_config(signature=TimeSignature(numerator=4, denominator=denominator))


@pytest.mark.parametrize("denominator", [1, 2, 4, 8, 16, 32])
def test_a_signature_a_midi_header_states_is_accepted(denominator: int) -> None:
    config = split_config(signature=TimeSignature(numerator=7, denominator=denominator))

    assert config.signature.denominator == denominator


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tempo_bpm", 0),
        ("tempo_bpm", -115.0),
        ("gap_measures", -0.25),
        ("tracked_ccs", frozenset({128})),
        ("tracked_ccs", frozenset({-1})),
        ("cc_channels", frozenset({16})),
    ],
)
def test_a_setting_outside_its_supported_range_is_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        split_config(**{field: value})


def test_a_run_naming_no_channels_follows_the_channels_carrying_notes() -> None:
    resolved = settings(split_config(cc_channels=None), note_channels=frozenset({0, 3}))

    assert resolved.cc_channels == frozenset({0, 3})


def test_a_run_naming_its_channels_keeps_them() -> None:
    resolved = settings(split_config(cc_channels=frozenset({2})), note_channels=frozenset({0, 3}))

    assert resolved.cc_channels == frozenset({2})


def test_the_gap_between_notes_is_read_from_the_render_meter() -> None:
    resolved = settings(split_config(gap_measures=0.25, signature=COMMON_TIME))

    assert resolved.meter.measure_ticks == MEASURE_TICKS
    assert resolved.gap_ticks == MEASURE_TICKS // 4


@pytest.mark.parametrize("gap_measures", [0.0, 0.0001, 0.0002])
def test_a_gap_rounding_down_to_nothing_still_separates_two_notes(gap_measures: float) -> None:
    """A shared tick would let one note's pedal release land among the next note's messages."""
    assert settings(split_config(gap_measures=gap_measures)).gap_ticks == MIN_GAP_TICKS


def test_a_run_following_the_pedal_tracks_it_alongside_the_named_controllers() -> None:
    resolved = settings(split_config(tracked_ccs=frozenset({64, 1, 11}), sustain_pedal=True))

    assert resolved.applied_controls == (1, 11, 64)


def test_a_run_leaving_the_pedal_alone_leaves_it_out_of_the_tracked_controllers() -> None:
    resolved = settings(split_config(tracked_ccs=frozenset({64, 1, 11}), sustain_pedal=False))

    assert resolved.applied_controls == (1, 11)


def test_the_render_states_the_beat_length_its_tempo_asks_for() -> None:
    assert settings(split_config(tempo_bpm=115.0)).microseconds_per_beat == 521_739
    assert settings(split_config(tempo_bpm=120.0)).microseconds_per_beat == 500_000


def test_the_rolls_a_run_states_reach_the_settings_it_is_carried_out_under() -> None:
    """The manifest builder reads them from here, which is what carries them to the trimmer."""
    resolved = settings(split_config(rolls={"pre_roll_seconds": 0.01, "post_roll_seconds": 0.25}))

    assert (resolved.rolls.pre_roll_seconds, resolved.rolls.post_roll_seconds) == (0.01, 0.25)


def test_settings_stay_comparable_once_their_derived_values_are_read() -> None:
    """The pipeline passes one settings object to several collaborators, each reading what it needs."""
    resolved = settings(split_config(tempo_bpm=115.0))
    assert resolved.gap_ticks == 480
    assert resolved.microseconds_per_beat == 521_739

    assert resolved == settings(split_config(tempo_bpm=115.0))
    assert hash(resolved) == hash(settings(split_config(tempo_bpm=115.0)))


def test_settings_state_the_resolution_of_the_performance_they_were_settled_against() -> None:
    assert settings(split_config()).ticks_per_beat == TICKS_PER_BEAT


@pytest.mark.parametrize("ticks_per_beat", [0, -480])
def test_a_performance_with_no_resolution_is_rejected(ticks_per_beat: int) -> None:
    with pytest.raises(ValidationError):
        RenderSettings.from_config(split_config(), ticks_per_beat, frozenset({0}))
