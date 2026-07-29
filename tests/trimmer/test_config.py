from typing import Final

import pytest
from pydantic import ValidationError

from note_extractor.errors import ConfigurationError
from note_extractor.trimmer.config import MAX_CC_DECIMALS, MIN_CC_DECIMALS, TrimConfig

from .conftest import trim_config

TRIM: Final[dict[str, object]] = {"cc_decimals": 1}


def test_a_document_states_every_setting_a_run_reads_from_it() -> None:
    config = TrimConfig.from_document({"trim": TRIM}, overwrite=False)

    assert config.cc_decimals == 1
    assert config.overwrite is False


def test_replacing_an_earlier_runs_samples_is_settled_by_the_invocation() -> None:
    """One document describes a dataset, while overwriting is a decision about this run alone."""
    assert TrimConfig.from_document({"trim": TRIM}, overwrite=True).overwrite is True


def test_a_document_stating_no_trim_settings_is_reported() -> None:
    with pytest.raises(ConfigurationError, match="states no 'trim' settings"):
        TrimConfig.from_document({}, overwrite=False)


def test_a_setting_a_document_states_outside_its_range_names_the_field() -> None:
    with pytest.raises(ConfigurationError, match="invalid settings: cc_decimals"):
        TrimConfig.from_document({"trim": {"cc_decimals": MAX_CC_DECIMALS + 1}}, overwrite=False)


def test_a_document_stating_the_rolls_the_manifest_carries_is_reported() -> None:
    """The rolls reach a trim run through the manifest, so a document restating them is a mistake."""
    with pytest.raises(ConfigurationError, match="invalid settings: post_roll_seconds"):
        TrimConfig.from_document({"trim": {**TRIM, "post_roll_seconds": 0.25}}, overwrite=False)


@pytest.mark.parametrize("cc_decimals", [MIN_CC_DECIMALS, 3, MAX_CC_DECIMALS])
def test_every_supported_number_of_decimals_is_accepted(cc_decimals: int) -> None:
    assert trim_config(cc_decimals=cc_decimals).cc_decimals == cc_decimals


@pytest.mark.parametrize("cc_decimals", [MIN_CC_DECIMALS - 1, MAX_CC_DECIMALS + 1])
def test_a_number_of_decimals_outside_the_supported_range_is_rejected(cc_decimals: int) -> None:
    with pytest.raises(ValidationError):
        trim_config(cc_decimals=cc_decimals)
