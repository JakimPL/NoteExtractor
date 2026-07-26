import json
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from ..errors import ManifestError
from .models import SCHEMA_VERSION, NoteManifest

MANIFEST_INDENT: Final = 2


def read_manifest(path: Path) -> NoteManifest:
    """Manifest stored at the given path.

    Raises:
        ManifestError: If the file is unreadable, holds text that is not JSON, states another
            schema version, or describes a run that falls outside the schema.
    """
    document = _read_document(path)
    try:
        return NoteManifest.model_validate(document)
    except ValidationError as error:
        raise _schema_failure(path, document, error) from error


def write_manifest(path: Path, manifest: NoteManifest) -> None:
    """Store one manifest as indented JSON, creating the directories leading up to it.

    Raises:
        ManifestError: If the directories or the file resist creation.
    """
    document = manifest.model_dump(mode="json")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=MANIFEST_INDENT), encoding="utf-8")
    except OSError as error:
        raise ManifestError(f"cannot write manifest {path}: {error}") from error


def _read_document(path: Path) -> object:
    """JSON document stored at the given path.

    Raises:
        ManifestError: If the file is unreadable or holds text that is not JSON.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestError(f"cannot read manifest {path}: {error}") from error

    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ManifestError(f"manifest {path} holds invalid JSON: {error}") from error


def _schema_failure(path: Path, document: object, error: ValidationError) -> ManifestError:
    """Failure naming the reason one document falls outside the manifest schema."""
    if not isinstance(document, dict):
        return ManifestError(f"manifest {path} must hold a JSON object")

    version = document.get("schema_version")
    if version != SCHEMA_VERSION:
        return ManifestError(f"manifest {path} states schema version {version!r}, expected {SCHEMA_VERSION}")

    return ManifestError(f"manifest {path} violates the schema: {_problem_summary(error)}")


def _problem_summary(error: ValidationError) -> str:
    """First problem the validator reported, followed by a count of the ones after it."""
    problems = error.errors()
    first = problems[0]
    location = ".".join(str(part) for part in first["loc"])
    summary = f"{location}: {first['msg']}" if location else first["msg"]
    if len(problems) > 1:
        return f"{summary} (and {len(problems) - 1} more)"

    return summary
