class NoteExtractorError(Exception):
    """Base class for the failures a command line reports as a message on stderr and exit code 1."""


class MidiSourceError(NoteExtractorError):
    """Reports a MIDI source the pipeline declines to use.

    The source may carry bytes the reader fails to parse, timing the reader leaves unsupported,
    values outside the ranges the timeline accepts, or a note the render has no stretch to sound
    over.
    """


class AudioError(NoteExtractorError):
    """Reports rendered audio the trimmer declines to cut.

    The file may carry bytes the reader fails to parse, state a sample rate that places no timing,
    or run out before the notes the manifest describes.
    """


class ManifestError(NoteExtractorError):
    """Reports a note manifest that fails to load or that violates the schema."""


class ConfigurationError(NoteExtractorError):
    """Reports configuration values that fall outside their supported ranges."""


class OutputConflictError(NoteExtractorError):
    """Reports an output file a run declines to write.

    The path may hold a file an earlier run left there, or it may be claimed by more than one of the
    notes the current run carries.
    """
