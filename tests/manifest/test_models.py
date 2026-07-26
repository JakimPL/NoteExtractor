from typing import Any

import pytest
from pydantic import ValidationError

from note_extractor.manifest.models import NoteManifest


def test_a_manifest_round_trips_through_its_json_document(manifest: NoteManifest, document: dict[str, Any]) -> None:
    assert NoteManifest.model_validate(document) == manifest


def test_notes_are_read_in_render_order(manifest: NoteManifest) -> None:
    assert tuple(note.render.index for note in manifest.notes) == (1, 0)
    assert tuple(note.render.index for note in manifest.notes_in_render_order()) == (0, 1)


def test_controller_averages_travel_as_json_keys_and_return_as_numbers(
    manifest: NoteManifest,
    document: dict[str, Any],
) -> None:
    assert document["notes"][0]["cc_averages"] == {"1": 70.0, "64": 0.0}
    assert NoteManifest.model_validate(document).notes[0].cc_averages == {1: 70.0, 64: 0.0}
    assert manifest.notes[0].cc_averages == {1: 70.0, 64: 0.0}


@pytest.mark.parametrize(
    ("field", "value"),
    [("pitch", 128), ("pitch", -1), ("velocity", 128), ("release_velocity", 200), ("channel", 16)],
)
def test_a_note_value_outside_the_midi_range_is_rejected(
    document: dict[str, Any],
    field: str,
    value: int,
) -> None:
    document["notes"][0][field] = value

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)


def test_a_note_that_releases_before_it_starts_is_rejected(document: dict[str, Any]) -> None:
    render = document["notes"][0]["render"]
    render["release_end_seconds"] = render["start_seconds"]

    with pytest.raises(ValidationError, match="must release after it starts"):
        NoteManifest.model_validate(document)


def test_duplicate_render_indices_are_rejected(document: dict[str, Any]) -> None:
    document["notes"][1]["render"]["index"] = document["notes"][0]["render"]["index"]

    with pytest.raises(ValidationError, match="render indices must be unique"):
        NoteManifest.model_validate(document)


@pytest.mark.parametrize("cc_averages", [[], "none", {"1": "loud"}, {"1": 200.0}, {"200": 1.0}])
def test_malformed_controller_averages_are_rejected(document: dict[str, Any], cc_averages: object) -> None:
    document["notes"][0]["cc_averages"] = cc_averages

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)


@pytest.mark.parametrize("time_signature", ["4", "4/", "four/four", "0/4", "4/4 "])
def test_a_malformed_time_signature_is_rejected(document: dict[str, Any], time_signature: str) -> None:
    document["render"]["time_signature"] = time_signature

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)


@pytest.mark.parametrize(("block", "field"), [("source", "ticks_per_beat"), ("render", "tempo_bpm")])
def test_a_non_positive_grid_value_is_rejected(document: dict[str, Any], block: str, field: str) -> None:
    document[block][field] = 0

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)


def test_an_unknown_field_is_rejected(document: dict[str, Any]) -> None:
    document["notes"][0]["duration_seconds"] = 1.0

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)


def test_another_schema_version_is_rejected(document: dict[str, Any]) -> None:
    document["schema_version"] = 2

    with pytest.raises(ValidationError):
        NoteManifest.model_validate(document)
