import pytest


def todo(step: str, what: str) -> None:
    """Placeholder: fails until the step in INSTRUCTIONS.md replaces it."""
    pytest.fail(f"TODO ({step}): {what}", pytrace=False)
