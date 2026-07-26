# NoteExtractor

Turn a MIDI performance into one audio sample per note.

Sampling an instrument means recording each note on its own, but a performance sounds its notes
together — overlapping, pedalled, and captured in one continuous take. `note_extractor` pulls them
apart in two stages:

- `midi-note-splitter` reads a performance, recovers the notes that were played, and lays them out one
  at a time into a render MIDI, with a manifest stating where each note sits in both performances.
- `stream-note-trimmer` reads that manifest and cuts the rendered WAV into one file per note, named
  after the note it holds.

Rendering the MIDI to audio happens between the two, in whatever DAW or synthesiser you sample with.

## Install

```bash
uv sync
```

## Use

Lay the performance out one note at a time:

```bash
midi-note-splitter performance.mid isolated.mid \
  --tempo 115 \
  --cc 0,1 \
  --gap-measures 0.25
```

Render `isolated.mid` to one continuous `isolated.wav`, then cut it apart:

```bash
stream-note-trimmer isolated.wav isolated.notes.json samples \
  --post-roll-ms 250
```

Each sample is named after the note it holds — its position in the render, its pitch and velocity, and
the average of every controller the split tracked:

```text
0000_p060_v100_cc0-3_cc1-63p875.wav
```

Run either command with `--help` for the settings it takes and the values it falls back on.

## Python API

```python
from pathlib import Path

from note_extractor.splitter import SplitConfig, split_midi
from note_extractor.trimmer import TrimConfig, trim_note_stream

manifest = split_midi(
    Path("performance.mid"),
    Path("isolated.mid"),
    Path("isolated.notes.json"),
    SplitConfig(tempo_bpm=115.0),
)

result = trim_note_stream(
    Path("isolated.wav"),
    Path("isolated.notes.json"),
    Path("samples"),
    TrimConfig(post_roll_seconds=0.25),
)
```

`split_midi` returns the manifest it wrote and `trim_note_stream` returns the samples it cut, so a
caller can go straight on to work with them. Reading a manifest written by an earlier run is
`note_extractor.manifest.read_manifest`.

## Documentation

[`docs/architecture.md`](docs/architecture.md) covers how the packages are layered, what the manifest
carries between the two stages, and the vocabulary the code is written in. The pydantic models in
`note_extractor.manifest` are the schema of record for the manifest itself.

## Development

```bash
uv sync --group dev
make check
```

`make check` runs `lint`, `typecheck`, and `test`. The other targets are `format`, `coverage`, and
`golden`, which re-records the end-to-end snapshots under `tests/golden`.

The suite covers the layering and the tooling alongside the behaviour: `tests/test_architecture.py`
holds the dependency direction and the confined libraries, and `tests/test_quality.py` runs the type
checker and the linter. Those two run the checkers over the whole repository, so a tight inner loop is
`uv run pytest -m "not slow"`.
