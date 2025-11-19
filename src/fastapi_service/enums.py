from enum import Enum, auto


class Scopes(Enum):
    SINGLETON = auto()
    """Live as long as the application."""

    TRANSIENT = auto()
    """Use and throw away."""
