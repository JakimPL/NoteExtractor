from pydantic import ValidationError


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
