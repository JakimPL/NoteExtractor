from typing import Final, Self

from pydantic import Field, ValidationError

from ..config import ConfigDocument, section
from ..models import FrozenModel
from ..validation import configuration_failure

TRIM_SECTION: Final = "trim"

MIN_CC_DECIMALS: Final = 0
MAX_CC_DECIMALS: Final = 9


class TrimConfig(FrozenModel):
    """Settings one trim run is asked to carry out.

    `cc_decimals` states how many decimal places a controller average keeps in a sample file name,
    and `overwrite` lets a run replace the samples an earlier run wrote. The audio each cut keeps
    around its note comes from the manifest, which records what the split run stated.
    """

    cc_decimals: int = Field(ge=MIN_CC_DECIMALS, le=MAX_CC_DECIMALS)
    overwrite: bool

    @classmethod
    def from_document(cls, document: ConfigDocument, *, overwrite: bool) -> Self:
        """Settings a trim run reads from one configuration document.

        Replacing an earlier run's samples is settled per invocation rather than per dataset, so
        `overwrite` arrives from the command line and every other setting from the document.

        Raises:
            ConfigurationError: If the document states no trim settings, or states a value outside
                the range one supports.
        """
        settings = {**section(document, TRIM_SECTION), "overwrite": overwrite}
        try:
            return cls.model_validate(settings)
        except ValidationError as error:
            raise configuration_failure(error) from error
