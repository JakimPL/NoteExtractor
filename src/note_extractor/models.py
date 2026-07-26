from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base for the validated value objects the layers pass between one another.

    Instances accept exactly the declared fields and hold their values for their whole lifetime,
    so a model that passes construction stays valid, comparable, and hashable wherever it travels.
    Every number a model holds is finite, which keeps a value that survives validation usable in the
    tick, frame, and second arithmetic the layers carry out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
