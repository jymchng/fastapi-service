from enum import Enum, auto


class Scopes(int, Enum):
    SINGLETON = 30
    """Live as long as the application."""

    TRANSIENT = 40
    """Use and throw away."""
