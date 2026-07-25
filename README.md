# midi-note-splitter

The package reads one MIDI performance, extracts sustain-aware notes, sorts them by pitch and velocity, and writes a sequential render MIDI plus a JSON timing manifest.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

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
