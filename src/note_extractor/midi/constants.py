from typing import Annotated, Final

from pydantic import Field

MIN_CHANNEL: Final = 0
MAX_CHANNEL: Final = 15
MIN_DATA_BYTE: Final = 0
MAX_DATA_BYTE: Final = 127

SUSTAIN_PEDAL_CONTROL: Final = 64
PEDAL_DOWN_THRESHOLD: Final = 64

MidiChannel = Annotated[int, Field(ge=MIN_CHANNEL, le=MAX_CHANNEL)]
DataByte = Annotated[int, Field(ge=MIN_DATA_BYTE, le=MAX_DATA_BYTE)]
