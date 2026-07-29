from pydantic import ValidationError

from .errors import ConfigurationError


def configuration_failure(error: ValidationError) -> ConfigurationError:
    """Failure naming the setting a run states outside the range it supports.

    Settings arrive as a document holding whatever was written in it, so the models are what judge
    each value, and this states the first one they turned away in the terms the person who wrote it
    reads.
    """
    return ConfigurationError(f"invalid settings: {describe_validation_problems(error)}")


def describe_validation_problems(error: ValidationError) -> str:
    """First problem a validator reported, followed by a count of the ones after it.

    A boundary reporting a failure to a person states the field that carries it and what it takes,
    which is what the person needs to correct the value they gave.
    """
    problems = error.errors()
    first = problems[0]
    location = ".".join(str(part) for part in first["loc"])
    summary = f"{location}: {first['msg']}" if location else first["msg"]
    if len(problems) > 1:
        return f"{summary} (and {len(problems) - 1} more)"

    return summary
