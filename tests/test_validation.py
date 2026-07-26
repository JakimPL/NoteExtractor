from typing import Self

import pytest
from pydantic import Field, ValidationError, model_validator

from note_extractor.models import FrozenModel
from note_extractor.validation import describe_validation_problems


class _Nested(FrozenModel):
    """Inner value object, so a problem carries the path leading down to it."""

    amount: float = Field(ge=0)


class _Setting(FrozenModel):
    """Outer value object holding one bound field, one nested field, and one rule of its own."""

    count: int = Field(ge=1)
    nested: _Nested

    @model_validator(mode="after")
    def _require_a_counted_amount(self) -> Self:
        if self.count > 1 and self.nested.amount == 0:
            raise ValueError("a counted setting must state an amount")

        return self


def test_a_problem_is_stated_against_the_field_that_carries_it() -> None:
    with pytest.raises(ValidationError) as raised:
        _Setting(count=0, nested=_Nested(amount=1.0))

    assert describe_validation_problems(raised.value) == "count: Input should be greater than or equal to 1"


def test_a_problem_inside_a_nested_model_carries_the_path_down_to_it() -> None:
    with pytest.raises(ValidationError) as raised:
        _Setting.model_validate({"count": 1, "nested": {"amount": -1.0}})

    assert describe_validation_problems(raised.value) == "nested.amount: Input should be greater than or equal to 0"


def test_a_rule_the_whole_model_carries_is_stated_on_its_own() -> None:
    """A rule spanning several fields sits at no one field, so its own words carry the report."""
    with pytest.raises(ValidationError) as raised:
        _Setting(count=2, nested=_Nested(amount=0.0))

    assert describe_validation_problems(raised.value) == "Value error, a counted setting must state an amount"


def test_the_problems_after_the_first_are_counted() -> None:
    with pytest.raises(ValidationError) as raised:
        _Setting.model_validate({"count": 0, "nested": {"amount": -1.0}})

    assert describe_validation_problems(raised.value) == (
        "count: Input should be greater than or equal to 1 (and 1 more)"
    )
