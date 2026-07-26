from typing import Any

import pytest
from pydantic import ValidationError

from note_extractor.trimmer.config import (
    DEFAULT_CC_DECIMALS,
    DEFAULT_POST_ROLL_SECONDS,
    DEFAULT_PRE_ROLL_SECONDS,
    MAX_CC_DECIMALS,
    MIN_CC_DECIMALS,
    TrimConfig,
)


def test_a_run_left_unconfigured_uses_the_stated_defaults() -> None:
    config = TrimConfig()

    assert config.pre_roll_seconds == DEFAULT_PRE_ROLL_SECONDS
    assert config.post_roll_seconds == DEFAULT_POST_ROLL_SECONDS
    assert config.cc_decimals == DEFAULT_CC_DECIMALS
    assert config.overwrite is False


@pytest.mark.parametrize("cc_decimals", [MIN_CC_DECIMALS, 3, MAX_CC_DECIMALS])
def test_every_supported_number_of_decimals_is_accepted(cc_decimals: int) -> None:
    assert TrimConfig(cc_decimals=cc_decimals).cc_decimals == cc_decimals


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pre_roll_seconds", -0.001),
        ("post_roll_seconds", -0.001),
        ("cc_decimals", MIN_CC_DECIMALS - 1),
        ("cc_decimals", MAX_CC_DECIMALS + 1),
    ],
)
def test_a_setting_outside_its_supported_range_is_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        TrimConfig(**{field: value})


def test_an_unknown_setting_is_rejected() -> None:
    """A caller stating the milliseconds the command line takes is told, rather than left at zero."""
    with pytest.raises(ValidationError):
        TrimConfig.model_validate({"post_roll_ms": 250.0})


def test_rolls_are_kept_as_the_seconds_they_were_asked_for() -> None:
    config = TrimConfig(pre_roll_seconds=0.005, post_roll_seconds=0.25)

    assert config.pre_roll_seconds == 0.005
    assert config.post_roll_seconds == 0.25
