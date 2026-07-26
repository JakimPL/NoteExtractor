import argparse
import math
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from note_extractor.cli.parsing import (
    channel_numbers,
    configuration_failure,
    controller_numbers,
    decimal_places,
    non_negative_float,
    positive_float,
    time_signature,
)
from note_extractor.errors import ConfigurationError
from note_extractor.timeline.meter import TimeSignature
from note_extractor.trimmer.config import TrimConfig


def test_a_time_signature_is_read_as_a_count_over_a_note_value() -> None:
    assert time_signature("3/8") == TimeSignature(numerator=3, denominator=8)


@pytest.mark.parametrize("value", ["4", "4/x", "x/4", "", "4/4/4", "4//4"])
def test_a_time_signature_written_another_way_is_reported(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must look like 4/4"):
        time_signature(value)


@pytest.mark.parametrize("value", ["0/4", "4/0", "-3/4"])
def test_a_time_signature_counting_nothing_is_reported(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must count at least one note value"):
        time_signature(value)


def test_a_signature_a_render_cannot_hold_is_left_to_the_settings_to_judge() -> None:
    """A denominator outside what a MIDI header states is the render's rule, not the flag's."""
    assert time_signature("4/5") == TimeSignature(numerator=4, denominator=5)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0,1,64", frozenset({0, 1, 64})),
        (" 0 , 1 ", frozenset({0, 1})),
        ("0,,1", frozenset({0, 1})),
        ("7", frozenset({7})),
        ("1,1", frozenset({1})),
        ("", frozenset()),
    ],
)
def test_a_list_of_controllers_is_read_as_the_set_it_names(value: str, expected: frozenset[int]) -> None:
    assert controller_numbers(value) == expected


@pytest.mark.parametrize("value", ["128", "-1"])
def test_a_controller_outside_the_numbers_midi_states_is_reported(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"controller must be in 0\.\.127"):
        controller_numbers(value)


def test_a_controller_written_as_something_other_than_a_number_is_reported() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="controller must be a whole number"):
        controller_numbers("0,volume")


def test_a_list_of_channels_is_read_as_the_set_it_names() -> None:
    assert channel_numbers("0,15") == frozenset({0, 15})


@pytest.mark.parametrize("value", ["16", "-1"])
def test_a_channel_outside_the_numbers_midi_states_is_reported(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"channel must be in 0\.\.15"):
        channel_numbers(value)


@pytest.mark.parametrize("value", ["0", "3", "9"])
def test_every_supported_count_of_decimal_places_is_read(value: str) -> None:
    assert decimal_places(value) == int(value)


@pytest.mark.parametrize("value", ["-1", "10"])
def test_a_count_of_decimal_places_the_trimmer_leaves_unwritten_is_reported(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"decimal places must be in 0\.\.9"):
        decimal_places(value)


def test_a_positive_number_is_read_as_it_was_written() -> None:
    assert positive_float("1.5") == 1.5


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_number_asked_to_be_positive_is_reported_at_zero_and_below(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must be positive"):
        positive_float(value)


def test_a_number_asked_to_be_positive_may_be_zero_when_it_only_must_not_fall_below_it() -> None:
    assert non_negative_float("0") == 0.0


def test_a_number_below_zero_is_reported_where_zero_is_the_floor() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must be zero or more"):
        non_negative_float("-0.001")


@pytest.mark.parametrize("parse", [positive_float, non_negative_float])
def test_text_holding_no_number_is_reported(parse: Callable[[str], float]) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must be a number"):
        parse("fast")


@pytest.mark.parametrize("parse", [positive_float, non_negative_float])
def test_a_number_without_end_is_left_to_the_settings_to_judge(parse: Callable[[str], float]) -> None:
    """An infinity passes every bound a flag states, so the models are what turn it away."""
    assert math.isinf(parse("inf"))


def test_settings_a_model_turns_away_are_reported_as_a_configuration_failure() -> None:
    with pytest.raises(ValidationError) as raised:
        TrimConfig(cc_decimals=99)

    failure = configuration_failure(raised.value)

    assert isinstance(failure, ConfigurationError)
    assert "invalid settings: cc_decimals" in str(failure)
