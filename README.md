# MIDI note rendering toolkit

The `note_extractor` package provides two commands:

- `midi-note-splitter` reads one MIDI performance, extracts sustain-aware notes, sorts them by pitch and velocity, and writes a sequential render MIDI plus a JSON timing manifest.
- `stream-note-trimmer` uses that manifest to split the rendered WAV stream into one WAV file per note.

## Install

```bash
uv sync
```

For development:

```bash
uv sync --group dev
make check
```

`make check` runs `pylint`, `mypy`, and `pytest`. Individual targets are `lint`, `typecheck`,
`test`, `coverage`, and `format`.

## Create the isolated-note MIDI

```bash
midi-note-splitter input.mid isolated.mid \
  --tempo 115 \
  --time-signature 4/4 \
  --cc 0,1 \
  --cc-channels 0 \
  --gap-measures 0.25
```

Use `--no-sustain-pedal` to make audible release equal key release and to omit CC64 from copied controller data.

If `--cc-channels` is omitted, all note-bearing channels are used. Every actual CC event on those channels is copied inside each isolated source-note window. The CCs listed by `--cc` are also initialized at the isolated note start and receive time-weighted averages in the manifest. CC64 is initialized and copied automatically when sustain handling is enabled.

The default manifest path is `<output-stem>.notes.json`. Measure positions are zero-based continuous values. `key_end_*` represents physical note-off. `release_end_*` includes sustain pedal extension. Source seconds use the original tempo map; render seconds use the overridden constant tempo.

## Split the rendered WAV

Render `isolated.mid` to one continuous WAV, then run:

```bash
stream-note-trimmer isolated.wav isolated.notes.json samples
```

Each output segment starts at `render.start_seconds` and ends at `render.release_end_seconds`. Frame boundaries use floor for the start and ceil for the end, preventing fractional-frame truncation.

Example filename:

```text
0000_p060_v100_cc0-3_cc1-63p875.wav
```

The filename contains the render index, integer MIDI pitch, velocity, and every CC average from the manifest. Decimal points in CC values are written as `p`.

Optional timing padding and overwrite behavior:

```bash
stream-note-trimmer isolated.wav isolated.notes.json samples \
  --pre-roll-ms 5 \
  --post-roll-ms 250 \
  --cc-decimals 3 \
  --overwrite
```

Pre-roll and post-roll are clamped to the WAV boundaries. The WAV sample rate, channel layout, and NumPy dtype returned by SciPy are preserved in every output file.

## Python API

```python
from pathlib import Path

from note_extractor.trimmer import TrimConfig, trim_note_stream

result = trim_note_stream(
    Path("isolated.wav"),
    Path("isolated.notes.json"),
    Path("samples"),
    TrimConfig(post_roll_seconds=0.25),
)
```
