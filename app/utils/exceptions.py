"""Custom exception hierarchy for FrameGenius."""


class FrameGeniusError(Exception):
    """Base error for every FrameGenius failure."""

    def __init__(self, message: str, *, stage: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "stage": self.stage,
            "details": self.details,
            "type": self.__class__.__name__,
        }


class ConfigError(FrameGeniusError):
    pass


class ProviderError(FrameGeniusError):
    pass


class RenderError(FrameGeniusError):
    pass


class TaskError(FrameGeniusError):
    pass


class ValidationError(FrameGeniusError):
    pass
