import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPOSITORY_ROOT: Final = Path(__file__).resolve().parent.parent
TESTS_CONFIG: Final = "tests/.pylintrc"

LINT_TARGETS: Final = (
    ("src", ()),
    ("tests", (f"--rcfile={TESTS_CONFIG}",)),
)


@pytest.mark.slow
def test_the_repository_type_checks() -> None:
    """The strict settings in `pyproject.toml` hold over both the package and its tests."""
    completed = _run("mypy")

    assert completed.returncode == 0, completed.stdout


@pytest.mark.slow
@pytest.mark.parametrize(("target", "options"), LINT_TARGETS, ids=[target for target, _ in LINT_TARGETS])
def test_a_tree_lints_at_the_score_its_policy_requires(target: str, options: tuple[str, ...]) -> None:
    """Each tree carries its own policy, so each is scored against the configuration beside it."""
    completed = _run("pylint", *options, target)

    assert completed.returncode == 0, completed.stdout


def _run(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one checker over the repository, gathering what it reports as text."""
    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
