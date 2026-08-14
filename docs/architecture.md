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
| `config.py`, `errors.py`, `models.py`, `validation.py` | The settings document, the failure hierarchy, the shared model base | — |

`splitter/` and `trimmer/` agree through `manifest/` alone, which is what lets the render step sit
between them and lets each stage be read on its own.

## Settings

`noteextractor.yaml`, beside the package, states every value either stage takes. No model declares a
default, so that file is where a setting's value is written once and read everywhere; a command given
`--config PATH` reads the document there instead, and the document it reads states every section.

`config.py` reads a document into its named sections and knows nothing of what any of them mean.
Each stage owns the sections it reads: `SplitConfig.from_document` takes `split` and `rolls`, and
`TrimConfig.from_document` takes `trim`. That split is what keeps the loader at the shared level while
the models that judge the values stay in the layers that use them.

Both commands take their positional paths, `--config`, and nothing else that settles a value:
`--overwrite` remains a flag because replacing an earlier run's samples is a decision about one
invocation rather than about a dataset.

## The spine

**Split** — `splitter.split_midi`:

```
read MIDI ─→ extract notes ─→ bound the spans ─→ lay out ─→ voice ─→ write render MIDI
                                      │             │                        │
                                      └─────────────┴──→ build manifest ─→ write manifest
```

*Extract* pairs each key press with the release that ends it and works out when the sound was
actually let go, which the sustain pedal can hold past the key release. *Bound the spans* settles how
long each note sounds, so every stage after it reads a note as the run sounds it rather than as it
was played. *Lay out* sorts the notes into render order and assigns each a stretch of the render
timeline, keeping the spans it sounds over. *Voice* gives each note the controller settings its
source stretch held: a snapshot at its onset, the messages posted while it sounded, and a pedal
release closing it.

Three bounds settle the spans, and they read the same note at two different moments. The briefest
span reads it **as it was played**: a key brushed for less than that was never a note worth sampling,
so the run leaves it out. The shortest and longest spans read it **as the render sounds it**: a note
the run keeps is held on until it has sounded the shortest span, and one still sounding at the
longest is let go of there. Between them, every note reaching the render is worth a sample and every
sample is worth playing back, which is the point of stating the three separately — a note played too
briefly to sample and a note simply shorter than the sample length call for opposite treatment.

A note is held on by keeping its key down to the end of the span, since a key held down is what
carries a note past the moment the performance let go of it. That leaves it ending on a key release
alone, which is why the voicing lifts the pedal wherever it is still down at a note's end: the
stretch a held or capped note covers may take in a pedal press the performance made after that note
had finished, and its sound would otherwise carry into the notes laid out after it.

The bounds a run states in seconds are read against the **render's** own tempo and resolution, since
the render is the timing the samples are laid out at and cut from, and a note carries the same ticks
on either timeline.

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
A value the models turn away is reported as a `ConfigurationError` naming the setting at fault.

## The manifest

`manifest/` holds the schema as pydantic models, and those models are the schema of record — reading
them is how you learn the exact shape of the document. What matters at this level:

- A manifest states the version of its own shape, so a reader can tell a document it understands from
  one written by another release.
- A manifest carries the rolls the split run was carried out with, which is how the trimmer learns how
  far past each end to cut. Changing a roll means re-running the splitter, which leaves the render MIDI
  untouched — the rolls take no part in the layout — so no rendering pass is repeated.
- Each note carries its place in the **source** performance and its place in the **render**, which is
  the pairing that lets audio cut from the render be traced back to how it was played.
- A manifest states the notes a run sounded rather than every note the source holds: one left out for
  being played too briefly is simply absent, and one held on or cut short carries the stretch the
  render holds of it on both timelines. The bounds themselves stay out of the document, since a
  trimmer reading it needs the spans it cuts and nothing about how they were arrived at.
- Render indices are unique across a manifest, so one sample file belongs to exactly one note.
- Unknown fields are refused, so a producer that has drifted reports itself on the first read.

## Failures

Everything the tool reports as a failure of the material it was given derives from
`NoteExtractorError`, raised where the problem is found and caught once per command at the boundary.
A command prints the reason on stderr, prefixed with its own name, and exits 1.

Argparse keeps exit 2 for the command line itself — a path left out, a flag it does not know. Every
value a run is carried out under arrives in the settings document, so the models are what judge it, and
both a tempo of `-5` and a time signature whose note value falls outside the powers of two a MIDI header
states are reported as settings failures on stderr with exit 1.

## Vocabulary

**Tick** — MIDI's unit of musical time, counted from the start of a file at a resolution the file
states.

**Sequence** — the rank of a message among the messages sharing one tick, taken from the order they
were read in. Ticks alone place events too coarsely to order them; a tick together with a sequence
places an event exactly, and comparing the two in that order gives one total order over a stream.

**Key end and release end** — the two ways a note ends. The key end is the moment the key came up.
The release end is the moment the sound was let go, which the sustain pedal can hold past the key
end, and which is where a sample is cut. A run settling how long a note sounds moves both ends to
where its span runs out: it holds the key down to reach the shortest span it sounds and brings the
key up at the longest, so a note it holds on or cuts short still ends from its start onwards.

**Source and render** — the two timelines every note sits on. The source is the performance as it was
played, with whatever tempo and meter changes it carries. The render is the file this tool writes: one
note at a time, one tempo, one time signature. A note keeps the ticks it sounds over when it moves
between them, which are the ticks it was played with unless the run settled how long it sounds.

**Frame** — one moment of recorded audio, holding one value per channel. Seconds from the manifest
become frames through the WAV's own sample rate.

**Band** — the rank of a voiced event among the events sharing one render tick: a controller snapshot
opens the tick, the events read from the source keep their source order, and a pedal release closes
it. Bands are what keep a note's settings in place before it sounds and its release after it has
finished sounding.
