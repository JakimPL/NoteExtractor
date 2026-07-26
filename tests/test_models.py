import math

import pytest
from pydantic import ValidationError

from note_extractor.models import FrozenModel


class _Setting(FrozenModel):
    """One number and one name, standing in for the value objects the layers pass between them."""

    amount: float
    name: str


def test_a_model_holds_the_values_it_was_built_with() -> None:
    setting = _Setting(amount=1.5, name="gap")

    assert setting.amount == 1.5
    assert setting.name == "gap"


def test_a_field_a_model_already_holds_stays_as_it_stands() -> None:
    """The type checker refuses the assignment outright; a caller reaching past it is refused too."""
    setting = _Setting(amount=1.5, name="gap")

    with pytest.raises(ValidationError):
        setattr(setting, "amount", 2.0)


def test_two_models_holding_the_same_values_stand_for_the_same_thing() -> None:
    assert _Setting(amount=1.5, name="gap") == _Setting(amount=1.5, name="gap")
    assert len({_Setting(amount=1.5, name="gap"), _Setting(amount=1.5, name="gap")}) == 1


def test_a_field_a_model_never_declared_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _Setting.model_validate({"amount": 1.5, "name": "gap", "colour": "blue"})


@pytest.mark.parametrize("amount", [math.inf, -math.inf, math.nan])
def test_a_number_without_a_finite_value_is_rejected(amount: float) -> None:
    """Tick, frame, and second arithmetic on such a value would overflow far from where it entered."""
    with pytest.raises(ValidationError, match="finite number"):
        _Setting(amount=amount, name="gap")
