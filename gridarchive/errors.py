class ValidationError(ValueError):
    """Input violates a domain invariant."""


class Conflict(ValueError):
    """An immutable name or request is already bound differently."""


class NotFound(LookupError):
    """The requested persisted identity does not exist."""
