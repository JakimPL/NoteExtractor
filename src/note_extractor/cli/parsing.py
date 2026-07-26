import argparse
from typing import Final

from pydantic import ValidationError

from ..errors import ConfigurationError
from ..midi.constants import MAX_CHANNEL, MAX_DATA_BYTE, MIN_CHANNEL, MIN_DATA_BYTE, DataByte, MidiChannel
from ..timeline.meter import TimeSignature
from ..trimmer.config import MAX_CC_DECIMALS, MIN_CC_DECIMALS
from ..validation import describe_validation_problems

SIGNATURE_SEPARATOR: Final = "/"
LIST_SEPARATOR: Final = ","

CONTROLLER_LABEL: Final = "controller"
CHANNEL_LABEL: Final = "channel"
DECIMALS_LABEL: Final = "decimal places"


def time_signature(value: str) -> TimeSignature:
    """Time signature one flag states, written as a count over a note value such as `4/4`.

    Raises:
        argparse.ArgumentTypeError: If the text holds anything other than two whole numbers around a
            slash, or states a count or a note value below one.
    """
    numerator_text, _, denominator_text = value.partition(SIGNATURE_SEPARATOR)
    try:
        numerator, denominator = int(numerator_text), int(denominator_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"time signature must look like 4/4: {value!r}") from error

    try:
        return TimeSignature(numerator=numerator, denominator=denominator)
    except ValidationError as error:
        raise argparse.ArgumentTypeError(f"time signature must count at least one note value: {value!r}") from error


def controller_numbers(value: str) -> frozenset[DataByte]:
    """Controllers one flag names, written as a comma separated list such as `0,1,64`.

    Raises:
        argparse.ArgumentTypeError: If a part is not a whole number, or falls outside the range a
            MIDI controller number spans.
    """
    return _bounded_integers(value, MIN_DATA_BYTE, MAX_DATA_BYTE, CONTROLLER_LABEL)


def channel_numbers(value: str) -> frozenset[MidiChannel]:
    """Channels one flag names, written as a comma separated list such as `0,1`.

    Raises:
        argparse.ArgumentTypeError: If a part is not a whole number, or falls outside the range a
            MIDI channel number spans.
    """
    return _bounded_integers(value, MIN_CHANNEL, MAX_CHANNEL, CHANNEL_LABEL)


def decimal_places(value: str) -> int:
    """Decimal places a controller average keeps in a sample file name.

    Raises:
        argparse.ArgumentTypeError: If the text is not a whole number, or falls outside the range the
            trimmer writes.
    """
    return _bounded_integer(value, MIN_CC_DECIMALS, MAX_CC_DECIMALS, DECIMALS_LABEL)


def positive_float(value: str) -> float:
    """Number one flag states, which sits above zero.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number, or states zero or less.
    """
    number = _number(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"value must be positive: {value!r}")

    return number


def non_negative_float(value: str) -> float:
    """Number one flag states, which sits at zero or above.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number, or states less than zero.
    """
    number = _number(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"value must be zero or more: {value!r}")

    return number


def configuration_failure(error: ValidationError) -> ConfigurationError:
    """Failure naming the setting a run states outside the range it supports.

    The command line checks the shape of each value it is given, so the settings the models turn
    away are the ones only they can judge, such as a number written as an infinity.
    """
    return ConfigurationError(f"invalid settings: {describe_validation_problems(error)}")


def _bounded_integers(value: str, minimum: int, maximum: int, label: str) -> frozenset[int]:
    """Whole numbers one comma separated list states, each held within the given range.

    Raises:
        argparse.ArgumentTypeError: If a part is not a whole number or falls outside the range.
    """
    parts = (part.strip() for part in value.split(LIST_SEPARATOR))
    return frozenset(_bounded_integer(part, minimum, maximum, label) for part in parts if part)


def _bounded_integer(value: str, minimum: int, maximum: int, label: str) -> int:
    """Whole number one part of a flag states, held within the given range.

    Raises:
        argparse.ArgumentTypeError: If the text is not a whole number or falls outside the range.
    """
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{label} must be a whole number: {value!r}") from error

    if not minimum <= number <= maximum:
        raise argparse.ArgumentTypeError(f"{label} must be in {minimum}..{maximum}: {number}")

    return number


def _number(value: str) -> float:
    """Number one flag states.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number.
    """
    try:
        return float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"value must be a number: {value!r}") from error
