from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base for the validated value objects the layers pass between one another.

    Instances accept exactly the declared fields and hold their values for their whole lifetime,
    so a model that passes construction stays valid, comparable, and hashable wherever it travels.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
