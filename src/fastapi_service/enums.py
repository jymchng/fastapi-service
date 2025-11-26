from enum import Enum, auto


class Scopes(int, Enum):
    SINGLETON = 30
    """Live as long as the application."""

    TRANSIENT = 40
    """Use and throw away."""


class UndefinedType(Enum):
    UNDEFINED = auto()

    def __bool__(self):
        return False

    def __repr__(self):
        return "UNDEFINED"


UNDEFINED = UndefinedType.UNDEFINED
