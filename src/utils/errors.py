"""Shared error taxonomy for pipeline reliability and retry behavior."""


class PipelineError(Exception):
    """Base class for pipeline-specific errors."""


class ConfigurationError(PipelineError):
    """Raised when configuration is missing or invalid."""


class AuthenticationError(PipelineError):
    """Raised when credentials are invalid or unavailable."""


class RetryableServiceError(PipelineError):
    """Raised for transient external service failures that can be retried."""


class NonRetryableServiceError(PipelineError):
    """Raised for terminal external service failures that should not be retried."""


class FileProcessingError(PipelineError):
    """Raised when file parsing, conversion, or generation fails."""


class FileOperationError(PipelineError):
    """Raised when file move/copy/write operations fail."""


class PromptLoadError(PipelineError):
    """Raised when prompt files cannot be loaded or formatted."""
