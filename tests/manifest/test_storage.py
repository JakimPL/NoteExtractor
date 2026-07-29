import json
from pathlib import Path
from typing import Any

import pytest

from note_extractor.errors import ManifestError
from note_extractor.manifest.models import NoteManifest
from note_extractor.manifest.storage import read_manifest, write_manifest


def test_a_manifest_round_trips_through_a_file(tmp_path: Path, manifest: NoteManifest) -> None:
    path = tmp_path / "renders" / "render.notes.json"

    write_manifest(path, manifest)

    assert read_manifest(path) == manifest


def test_a_written_manifest_is_indented_json(tmp_path: Path, manifest: NoteManifest) -> None:
    path = tmp_path / "render.notes.json"

    write_manifest(path, manifest)

    assert path.read_text(encoding="utf-8").startswith('{\n  "schema_version": 2,')


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="cannot read manifest"):
        read_manifest(tmp_path / "absent.notes.json")


def test_text_that_is_not_json_is_reported(tmp_path: Path) -> None:
    path = _stored(tmp_path, "{not json")

    with pytest.raises(ManifestError, match="holds invalid JSON"):
        read_manifest(path)


def test_a_document_that_is_not_an_object_is_reported(tmp_path: Path) -> None:
    path = _stored(tmp_path, "[]")

    with pytest.raises(ManifestError, match="must hold a JSON object"):
        read_manifest(path)


def test_another_schema_version_is_reported(tmp_path: Path, document: dict[str, Any]) -> None:
    document["schema_version"] = 3
    path = _stored(tmp_path, json.dumps(document))

    with pytest.raises(ManifestError, match="states schema version 3, expected 2"):
        read_manifest(path)


def test_a_manifest_written_before_the_rolls_were_carried_is_reported(tmp_path: Path, document: dict[str, Any]) -> None:
    """Version 1 stated the settings without the rolls, so such a manifest is re-split to gain them."""
    del document["settings"]["rolls"]
    document["schema_version"] = 1
    path = _stored(tmp_path, json.dumps(document))

    with pytest.raises(ManifestError, match="states schema version 1, expected 2"):
        read_manifest(path)


def test_a_manifest_written_before_the_schema_was_versioned_is_reported(tmp_path: Path) -> None:
    """Releases up to now wrote a `config` block and no version, which points at the upgrade."""
    path = _stored(tmp_path, json.dumps({"config": {"note_count": 0}, "notes": []}))

    with pytest.raises(ManifestError, match="states schema version None, expected 2"):
        read_manifest(path)


def test_a_schema_problem_names_the_field_it_was_found_in(tmp_path: Path, document: dict[str, Any]) -> None:
    document["notes"][0]["pitch"] = 200
    path = _stored(tmp_path, json.dumps(document))

    with pytest.raises(ManifestError, match=r"violates the schema: notes\.0\.pitch: "):
        read_manifest(path)


def test_several_schema_problems_are_counted(tmp_path: Path, document: dict[str, Any]) -> None:
    document["notes"][0]["pitch"] = 200
    document["notes"][1]["velocity"] = 200
    path = _stored(tmp_path, json.dumps(document))

    with pytest.raises(ManifestError, match=r"\(and 1 more\)"):
        read_manifest(path)


def test_a_manifest_that_cannot_be_written_is_reported(tmp_path: Path, manifest: NoteManifest) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(ManifestError, match="cannot write manifest"):
        write_manifest(blocker / "render.notes.json", manifest)


def _stored(directory: Path, text: str) -> Path:
    path = directory / "render.notes.json"
    path.write_text(text, encoding="utf-8")
    return path
