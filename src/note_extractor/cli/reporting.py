import sys
from typing import Final

from ..errors import NoteExtractorError

SUCCESS_EXIT_CODE: Final = 0
FAILURE_EXIT_CODE: Final = 1


def report_failure(program: str, error: NoteExtractorError) -> int:
    """State one failure on stderr and give the code the command exits with.

    A run that fails on the material it was given — a file it cannot read, a manifest outside the
    schema, a sample another run wrote — reports the reason and exits with `FAILURE_EXIT_CODE`, which
    keeps it apart from the code argparse exits with when a flag itself is unusable.
    """
    print(f"{program}: {error}", file=sys.stderr)
    return FAILURE_EXIT_CODE
