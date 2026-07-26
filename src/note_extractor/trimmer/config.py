from typing import Final

from pydantic import Field

from ..models import FrozenModel

DEFAULT_PRE_ROLL_SECONDS: Final = 0.0
DEFAULT_POST_ROLL_SECONDS: Final = 0.0
DEFAULT_CC_DECIMALS: Final = 3
DEFAULT_OVERWRITE: Final = False

MIN_CC_DECIMALS: Final = 0
MAX_CC_DECIMALS: Final = 9


class TrimConfig(FrozenModel):
    """Settings one trim run is asked to carry out.

    The rolls widen the stretch cut for each note: `pre_roll_seconds` reaches back before the onset,
    and `post_roll_seconds` carries on past the moment the sound was let go, which keeps the tail of
    the release. `cc_decimals` states how many decimal places a controller average keeps in a sample
    file name, and `overwrite` lets a run replace the samples an earlier run wrote.
    """

    pre_roll_seconds: float = Field(default=DEFAULT_PRE_ROLL_SECONDS, ge=0)
    post_roll_seconds: float = Field(default=DEFAULT_POST_ROLL_SECONDS, ge=0)
    cc_decimals: int = Field(default=DEFAULT_CC_DECIMALS, ge=MIN_CC_DECIMALS, le=MAX_CC_DECIMALS)
    overwrite: bool = DEFAULT_OVERWRITE
