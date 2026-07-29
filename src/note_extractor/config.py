from collections.abc import Mapping
from pathlib import Path
from typing import Final

import yaml

from .errors import ConfigurationError

BUNDLED_CONFIG_PATH: Final = Path(__file__).parent / "noteextractor.yaml"

ConfigSection = Mapping[str, object]
ConfigDocument = Mapping[str, ConfigSection]


def load_config(path: Path | None) -> ConfigDocument:
    """Settings document one run is carried out under, read from `path` or from the bundled file.

    A document states every setting both stages take, which is what lets one file describe a dataset
    and both commands be given it. A run naming no file of its own is carried out under the document
    shipped with the tool, so that file is where a setting's value is stated once and read everywhere.

    The values a section holds arrive as whatever YAML wrote them as, and each stage validates the
    section it reads into a model of its own.

    Raises:
        ConfigurationError: If the file resists reading, holds text that is not YAML, or states
            anything other than named sections of settings.
    """
    source = BUNDLED_CONFIG_PATH if path is None else path
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigurationError(f"cannot read configuration {source}: {error}") from error

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigurationError(f"configuration {source} holds invalid YAML: {error}") from error

    return _sections(source, document)


def section(document: ConfigDocument, name: str) -> ConfigSection:
    """Settings one named section of a document states.

    Raises:
        ConfigurationError: If the document states no section under that name.
    """
    if name not in document:
        raise ConfigurationError(f"configuration states no {name!r} settings")

    return document[name]


def _sections(source: Path, document: object) -> ConfigDocument:
    """Named sections one document holds, each mapping settings onto the values they were given.

    Raises:
        ConfigurationError: If the document states anything other than named sections of settings.
    """
    if not isinstance(document, dict) or not all(
        isinstance(name, str) and isinstance(settings, dict) for name, settings in document.items()
    ):
        raise ConfigurationError(f"configuration {source} must hold named sections of settings")

    return document
