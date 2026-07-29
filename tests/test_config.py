from pathlib import Path

import pytest

from note_extractor.config import BUNDLED_CONFIG_PATH, load_config, section
from note_extractor.errors import ConfigurationError
from note_extractor.splitter.config import SplitConfig
from note_extractor.trimmer.config import TrimConfig

DOCUMENT = """
split:
  tempo_bpm: 115.0
rolls:
  post_roll_seconds: 0.4
"""


def test_a_run_naming_no_document_is_carried_out_under_the_bundled_one() -> None:
    """The shipped file is where a setting's value is stated, so a run reads it without being told to."""
    assert load_config(None) == load_config(BUNDLED_CONFIG_PATH)


def test_the_bundled_document_states_everything_both_stages_take() -> None:
    """Neither model declares a default, so a run only starts if the shipped file states every field."""
    document = load_config(None)

    assert SplitConfig.from_document(document)
    assert TrimConfig.from_document(document, overwrite=False)


def test_a_document_is_read_as_the_sections_it_states(tmp_path: Path) -> None:
    document = load_config(_stored(tmp_path, DOCUMENT))

    assert section(document, "split") == {"tempo_bpm": 115.0}
    assert section(document, "rolls") == {"post_roll_seconds": 0.4}


def test_a_section_a_document_leaves_out_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="states no 'trim' settings"):
        section(load_config(_stored(tmp_path, DOCUMENT)), "trim")


def test_a_document_that_was_never_written_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cannot read configuration"):
        load_config(tmp_path / "absent.yaml")


def test_text_that_is_not_yaml_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="holds invalid YAML"):
        load_config(_stored(tmp_path, "split: [unclosed\n"))


@pytest.mark.parametrize("text", ["- split\n- rolls\n", "split: 115.0\n", "42\n", "\n"])
def test_a_document_holding_anything_other_than_named_sections_is_reported(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigurationError, match="must hold named sections of settings"):
        load_config(_stored(tmp_path, text))


def _stored(directory: Path, text: str) -> Path:
    path = directory / "noteextractor.yaml"
    path.write_text(text, encoding="utf-8")
    return path
