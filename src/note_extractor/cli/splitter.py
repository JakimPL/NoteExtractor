import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ..config import load_config
from ..errors import NoteExtractorError
from ..splitter.config import SplitConfig
from ..splitter.pipeline import split_midi
from .reporting import SUCCESS_EXIT_CODE, report_failure

PROGRAM_NAME: Final = "midi-note-splitter"
MANIFEST_SUFFIX: Final = ".notes.json"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the splitter over the command line it is given.

    Returns:
        `SUCCESS_EXIT_CODE` once the render and its manifest are written, and `FAILURE_EXIT_CODE`
        when the run reports why it wrote neither.
    """
    arguments = _build_parser().parse_args(argv)
    try:
        return _split(arguments)
    except NoteExtractorError as error:
        return report_failure(PROGRAM_NAME, error)


def _split(arguments: argparse.Namespace) -> int:
    """Carry out one split run and state where it wrote.

    Raises:
        ConfigurationError: If the configuration resists reading, or states a setting outside the
            range it supports.
        MidiSourceError: If the source resists parsing or states timing the reader leaves unsupported.
        RenderError: If the render resists writing.
        ManifestError: If the manifest resists writing.
    """
    manifest_path = arguments.manifest or arguments.output.with_suffix(MANIFEST_SUFFIX)
    config = SplitConfig.from_document(load_config(arguments.config))
    manifest = split_midi(arguments.input, arguments.output, manifest_path, config)

    print(f"wrote {arguments.output}")
    print(f"wrote {manifest_path}")
    print(f"notes: {len(manifest.notes)}")
    return SUCCESS_EXIT_CODE


def _build_parser() -> argparse.ArgumentParser:
    """Paths the splitter reads and writes, and where it takes its settings from."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Split a MIDI performance into a render sounding one note at a time.",
    )
    parser.add_argument("input", type=Path, help="MIDI performance to extract the notes from")
    parser.add_argument("output", type=Path, help="MIDI render to write the isolated notes to")
    parser.add_argument(
        "--manifest",
        type=Path,
        help=f"where to write the note timings, by default the render named with {MANIFEST_SUFFIX}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="settings to carry the run out under, by default the ones shipped with the tool",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
