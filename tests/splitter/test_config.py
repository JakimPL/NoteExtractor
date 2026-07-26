from typing import Any

import pytest
from pydantic import ValidationError

from note_extractor.splitter.config import (
    DEFAULT_GAP_MEASURES,
    DEFAULT_TEMPO_BPM,
    MIN_GAP_TICKS,
    RenderSettings,
    SplitConfig,
)
from note_extractor.timeline.meter import TimeSignature

from .conftest import COMMON_TIME, MEASURE_TICKS, TICKS_PER_BEAT, settings


def test_a_run_left_unconfigured_uses_the_stated_defaults() -> None:
    config = SplitConfig()

    assert config.tempo_bpm == DEFAULT_TEMPO_BPM
    assert config.signature == COMMON_TIME
    assert config.gap_measures == DEFAULT_GAP_MEASURES
    assert config.tracked_ccs == frozenset({0, 1})
    assert config.cc_channels is None
    assert config.sustain_pedal is True


@pytest.mark.parametrize("denominator", [3, 5, 6, 7, 12])
def test_a_signature_a_midi_header_cannot_state_is_rejected(denominator: int) -> None:
    """A MIDI header states the note value as a power of two, so any other value never reaches a file."""
    with pytest.raises(ValidationError, match="must be a power of two"):
        SplitConfig(signature=TimeSignature(numerator=4, denominator=denominator))


@pytest.mark.parametrize("denominator", [1, 2, 4, 8, 16, 32])
def test_a_signature_a_midi_header_states_is_accepted(denominator: int) -> None:
    config = SplitConfig(signature=TimeSignature(numerator=7, denominator=denominator))

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
        SplitConfig(**{field: value})


def test_an_unknown_setting_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SplitConfig(bpm=115.0)  # type: ignore[call-arg]


def test_a_run_naming_no_channels_follows_the_channels_carrying_notes() -> None:
    resolved = settings(SplitConfig(), note_channels=frozenset({0, 3}))

    assert resolved.cc_channels == frozenset({0, 3})


def test_a_run_naming_its_channels_keeps_them() -> None:
    resolved = settings(SplitConfig(cc_channels=frozenset({2})), note_channels=frozenset({0, 3}))

    assert resolved.cc_channels == frozenset({2})


def test_the_gap_between_notes_is_read_from_the_render_meter() -> None:
    resolved = settings(SplitConfig(gap_measures=0.25))

    assert resolved.meter.measure_ticks == MEASURE_TICKS
    assert resolved.gap_ticks == MEASURE_TICKS // 4


@pytest.mark.parametrize("gap_measures", [0.0, 0.0001, 0.0002])
def test_a_gap_rounding_down_to_nothing_still_separates_two_notes(gap_measures: float) -> None:
    """A shared tick would let one note's pedal release land among the next note's messages."""
    assert settings(SplitConfig(gap_measures=gap_measures)).gap_ticks == MIN_GAP_TICKS


def test_a_run_following_the_pedal_tracks_it_alongside_the_named_controllers() -> None:
    resolved = settings(SplitConfig(tracked_ccs=frozenset({64, 1, 11}), sustain_pedal=True))

    assert resolved.applied_controls == (1, 11, 64)


def test_a_run_leaving_the_pedal_alone_leaves_it_out_of_the_tracked_controllers() -> None:
    resolved = settings(SplitConfig(tracked_ccs=frozenset({64, 1, 11}), sustain_pedal=False))

    assert resolved.applied_controls == (1, 11)


def test_the_render_states_the_beat_length_its_tempo_asks_for() -> None:
    assert settings(SplitConfig(tempo_bpm=115.0)).microseconds_per_beat == 521_739
    assert settings(SplitConfig(tempo_bpm=120.0)).microseconds_per_beat == 500_000


def test_settings_stay_comparable_once_their_derived_values_are_read() -> None:
    """The pipeline passes one settings object to several collaborators, each reading what it needs."""
    resolved = settings(SplitConfig(tempo_bpm=115.0))
    assert resolved.gap_ticks == 480
    assert resolved.microseconds_per_beat == 521_739

    assert resolved == settings(SplitConfig(tempo_bpm=115.0))
    assert hash(resolved) == hash(settings(SplitConfig(tempo_bpm=115.0)))


def test_settings_state_the_resolution_of_the_performance_they_were_settled_against() -> None:
    assert settings(SplitConfig()).ticks_per_beat == TICKS_PER_BEAT


@pytest.mark.parametrize("ticks_per_beat", [0, -480])
def test_a_performance_with_no_resolution_is_rejected(ticks_per_beat: int) -> None:
    with pytest.raises(ValidationError):
        RenderSettings.from_config(SplitConfig(), ticks_per_beat, frozenset({0}))
