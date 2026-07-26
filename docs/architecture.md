# Architecture

## What the tool does

A sampler needs one audio file per note. A performance gives you every note at once, overlapping,
pedalled, and sharing one continuous recording.

`note_extractor` gets from one to the other in two stages that meet at a single file:

1. **Split.** Read a MIDI performance, recover the notes that were played, and lay them out one at a
   time along a new timeline with a gap between them. Write that as a render MIDI, and write a
   manifest stating where each note sits in both performances.
2. **Trim.** A renderer (any DAW or synthesiser) turns the render MIDI into one continuous WAV. The
   trimmer reads the manifest, cuts that WAV at the seconds the manifest states, and names each cut
   after the note it holds.

The two stages run in separate processes, possibly days apart, with a rendering step between them
that happens outside this tool. The manifest carries the timing across that gap, which is why it is a
validated document with a version of its own.

## Layers

Each package depends only on the ones below it.

| Package | Owns | Reaches for |
| --- | --- | --- |
| `cli/` | Reading a command line, reporting failures, exit codes | `splitter`, `trimmer` |
| `splitter/` | Recovering notes from a performance and laying out a render | `midi`, `timeline`, `manifest` |
| `trimmer/` | Cutting a rendered stream into per-note samples | `manifest` |
| `manifest/` | The timing contract the two stages meet at | `midi` (value ranges) |
| `timeline/` | Tick, second, and measure arithmetic | `midi` (event types) |
| `midi/` | Typed MIDI events, reading and writing files | — |
| `errors.py`, `models.py`, `validation.py` | The failure hierarchy and the shared model base | — |

`splitter/` and `trimmer/` agree through `manifest/` alone, which is what lets the render step sit
between them and lets each stage be read on its own.

## The spine

**Split** — `splitter.split_midi`:

```
read MIDI ─→ extract notes ─→ lay out ─→ voice ─→ write render MIDI
                    │            │                        │
                    └────────────┴──→ build manifest ─→ write manifest
```

*Extract* pairs each key press with the release that ends it and works out when the sound was
actually let go, which the sustain pedal can hold past the key release. *Lay out* sorts the notes
into render order and assigns each a stretch of the render timeline, keeping the spans it was played
with. *Voice* gives each note the controller settings its source stretch held: a snapshot at its
onset, the messages posted while it sounded, and a pedal release closing it.

**Trim** — `trimmer.trim_note_stream`:

```
read manifest ─→ read WAV ─→ plan every cut ─→ write one WAV per note
```

Planning happens for the whole run before any file is written, so a run that would collide with
itself or with an earlier run's output reports that while the output directory is still untouched.

## Boundaries held deliberately narrow

**mido lives in `midi/reader.py` and `midi/writer.py`.** mido builds its message fields dynamically
and ships as untyped, so its objects type as `Any` and resist static checking. The reader turns
messages into frozen typed events at the boundary and the writer turns them back; every layer above
works with the typed events alone. This is also where a `note_on` of zero velocity becomes the key
release it means, which keeps that rule in one place.

**scipy lives in `trimmer/audio.py`.** WAV frames are read there, memory-mapped where the file's
layout allows, and every cut is a view over that one stream. The rest of the trimmer works with the
stream's frame count and rate.

**Validation happens at construction.** The shared model base freezes its fields, accepts exactly the
fields it declares, and requires every number to be finite. A model that exists is therefore a model
whose values hold, so layers carry out tick and second arithmetic on the strength of the type alone.
Commands convert the resulting report into a message naming the setting at fault.

## The manifest

`manifest/` holds the schema as pydantic models, and those models are the schema of record — reading
them is how you learn the exact shape of the document. What matters at this level:

- A manifest states the version of its own shape, so a reader can tell a document it understands from
  one written by another release.
- Each note carries its place in the **source** performance and its place in the **render**, which is
  the pairing that lets audio cut from the render be traced back to how it was played.
- Render indices are unique across a manifest, so one sample file belongs to exactly one note.
- Unknown fields are refused, so a producer that has drifted reports itself on the first read.

## Failures

Everything the tool reports as a failure of the material it was given derives from
`NoteExtractorError`, raised where the problem is found and caught once per command at the boundary.
A command prints the reason on stderr, prefixed with its own name, and exits 1.

Argparse keeps exit 2 for a flag it fails to read. The dividing line is ownership: a parser judges the
syntax of a value and the range that flag accepts, while the models judge whether the settings make a
run the pipeline can carry out. So `--tempo -5` is a usage failure, and a time signature whose note
value falls outside the powers of two a MIDI header states is a settings failure.

## Vocabulary

**Tick** — MIDI's unit of musical time, counted from the start of a file at a resolution the file
states.

**Sequence** — the rank of a message among the messages sharing one tick, taken from the order they
were read in. Ticks alone place events too coarsely to order them; a tick together with a sequence
places an event exactly, and comparing the two in that order gives one total order over a stream.

**Key end and release end** — the two ways a note ends. The key end is the moment the key came up.
The release end is the moment the sound was let go, which the sustain pedal can hold past the key
end, and which is where a sample is cut.

**Source and render** — the two timelines every note sits on. The source is the performance as it was
played, with whatever tempo and meter changes it carries. The render is the file this tool writes: one
note at a time, one tempo, one time signature. A note keeps the spans it was played with when it moves
between them, so it sounds the same length in both.

**Frame** — one moment of recorded audio, holding one value per channel. Seconds from the manifest
become frames through the WAV's own sample rate.

**Band** — the rank of a voiced event among the events sharing one render tick: a controller snapshot
opens the tick, the events read from the source keep their source order, and a pedal release closes
it. Bands are what keep a note's settings in place before it sounds and its release after it has
finished sounding.
