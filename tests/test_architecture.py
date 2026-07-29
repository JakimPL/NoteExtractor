import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

PACKAGE_ROOT: Final = Path(__file__).resolve().parent.parent / "src" / "note_extractor"
PACKAGE_NAME: Final = "note_extractor"

SHARED: Final = "shared"
LAYERS: Final = ("cli", "splitter", "trimmer", "manifest", "timeline", "midi", SHARED)
DEPTH: Final = {layer: depth for depth, layer in enumerate(LAYERS)}

CONFINED_LIBRARIES: Final = {
    "mido": frozenset({"midi/reader.py", "midi/writer.py"}),
    "scipy": frozenset({"trimmer/audio.py"}),
    "numpy": frozenset({"trimmer/audio.py"}),
    "yaml": frozenset({"config.py"}),
}


def test_every_layer_reaches_only_for_the_layers_beneath_it() -> None:
    """The layering `docs/architecture.md` states holds in the imports themselves."""
    upward = [
        f"{module} imports {imported}"
        for module, imported in _internal_imports()
        if DEPTH[_layer_of(imported)] < DEPTH[_layer_of(module)]
    ]

    assert not upward


def test_the_two_pipelines_meet_at_the_manifest_alone() -> None:
    """Either stage can be read on its own, which is what lets the render step sit between them."""
    crossings = [
        f"{module} imports {imported}"
        for module, imported in _internal_imports()
        if {_layer_of(module), _layer_of(imported)} == {"splitter", "trimmer"}
    ]

    assert not crossings


@pytest.mark.parametrize("library", sorted(CONFINED_LIBRARIES))
def test_a_confined_library_is_reached_for_at_its_own_boundary(library: str) -> None:
    """A library the layers above work without stays where its own adapter sits."""
    reached = {_relative_path(path) for path in _modules() if library in _third_party_roots(_parsed(path))}

    assert reached == CONFINED_LIBRARIES[library]


def _modules() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE_ROOT.rglob("*.py")))


def _relative_path(path: Path) -> str:
    return path.relative_to(PACKAGE_ROOT).as_posix()


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _layer_of(parts: tuple[str, ...]) -> str:
    """Layer one dotted module belongs to, taken from the subpackage holding it."""
    return parts[0] if parts and parts[0] in DEPTH else SHARED


def _internal_imports() -> Iterator[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Every import one module of the package makes of another, as dotted parts."""
    for path in _modules():
        module = path.relative_to(PACKAGE_ROOT).parts
        for imported in _imported_modules(_parsed(path), module):
            yield module, imported


def _imported_modules(tree: ast.Module, module: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    """Modules of the package one module imports, resolved to parts under the package root."""
    package = module[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = package[: len(package) - (node.level - 1)]
            yield base + _parts(node.module)
        elif isinstance(node, ast.ImportFrom) and _parts(node.module)[:1] == (PACKAGE_NAME,):
            yield _parts(node.module)[1:]
        elif isinstance(node, ast.Import):
            yield from (_parts(alias.name)[1:] for alias in node.names if _parts(alias.name)[:1] == (PACKAGE_NAME,))


def _third_party_roots(tree: ast.Module) -> frozenset[str]:
    """Top-level names of the libraries outside the package that one module imports."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(_parts(node.module)[0])
        elif isinstance(node, ast.Import):
            roots.update(_parts(alias.name)[0] for alias in node.names)

    return frozenset(roots)


def _parts(module: str | None) -> tuple[str, ...]:
    return tuple(module.split(".")) if module else ()
