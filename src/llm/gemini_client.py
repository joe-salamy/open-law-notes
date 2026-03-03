"""Low-level Gemini API helpers: error checking, content generation, PDF upload/processing."""

import time
from pathlib import Path
from typing import Callable

import google.generativeai as genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    GoogleAPIError,
    InternalServerError,
    NotFound,
    ServiceUnavailable,
    TooManyRequests,
    Unauthorized,
)

import config
from ..utils.errors import (
    AuthenticationError,
    ConfigurationError,
    NonRetryableServiceError,
    RetryableServiceError,
)
from ..utils.logger_config import get_logger

logger = get_logger(__name__)


def _check_model_error(e: Exception) -> None:
    """Raise a friendly SystemExit if the error indicates an invalid or deprecated model."""
    if isinstance(e, NotFound) or "not found" in str(e).lower():
        raise ConfigurationError(
            f"\nERROR: Gemini model '{config.GEMINI_MODEL}' was not found.\n"
            f"It may have been updated or deprecated by Google.\n\n"
            f"To fix this:\n"
            f"  1. Visit https://ai.google.dev/gemini-api/docs/models to see available models\n"
            f"  2. Open  config.py  and find the GEMINI_MODEL setting\n"
            f"  3. Replace '{config.GEMINI_MODEL}' with a current model name from the list above\n"
        ) from e


def _is_retryable_error(error: Exception) -> bool:
    if isinstance(
        error,
        (
            TooManyRequests,
            ServiceUnavailable,
            DeadlineExceeded,
            InternalServerError,
            TimeoutError,
            ConnectionError,
        ),
    ):
        return True
    text = str(error).lower()
    return any(
        token in text
        for token in ("rate", "timeout", "temporar", "unavailable", "429", "503")
    )


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, Unauthorized):
        raise AuthenticationError("Gemini API authentication failed.") from error
    _check_model_error(error)
    if isinstance(error, GoogleAPIError):
        raise NonRetryableServiceError(f"Gemini API error: {error}") from error
    raise NonRetryableServiceError(f"Gemini processing failed: {error}") from error


def _execute_with_retries(
    operation: Callable[[], str | genai.types.File],
    operation_name: str,
    max_retries: int,
) -> str | genai.types.File:
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"{operation_name} attempt {attempt}/{max_retries}")
            return operation()
        except Exception as error:
            if _is_retryable_error(error):
                if attempt == max_retries:
                    raise RetryableServiceError(
                        f"{operation_name} failed after {max_retries} retries: {error}"
                    ) from error
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    f"{operation_name} transient error on attempt {attempt}, retrying in {backoff}s: {error}"
                )
                time.sleep(backoff)
                continue
            _raise_service_error(error)
    raise RetryableServiceError(f"{operation_name} failed without a result")


def process_with_gemini(
    model: genai.GenerativeModel, content: str, max_retries: int = 3
) -> str:
    """
    Send content to Gemini using a pre-created GenerativeModel and return the response.

    Includes exponential backoff retry logic for transient API errors.
    """
    logger.debug(f"Processing content with Gemini ({len(content)} characters)")

    def _operation() -> str:
        response = model.generate_content(content)
        return response.text

    result = _execute_with_retries(_operation, "Gemini text generation", max_retries)
    logger.debug(f"Gemini response received ({len(result)} characters)")
    return result


def upload_pdf_to_gemini(filepath: Path, max_retries: int = 3) -> genai.types.File:
    """Upload a PDF file to Gemini and return the file object."""
    logger.debug(f"Uploading PDF to Gemini: {filepath.name}")

    def _operation() -> genai.types.File:
        return genai.upload_file(filepath)

    uploaded_file = _execute_with_retries(_operation, "Gemini PDF upload", max_retries)
    logger.debug(f"PDF uploaded successfully: {uploaded_file.name}")
    return uploaded_file


def process_pdf_with_gemini(
    model: genai.GenerativeModel,
    uploaded_file: genai.types.File,
    prompt: str = "Process this PDF document.",
    max_retries: int = 3,
) -> str:
    """Process an uploaded PDF with Gemini."""
    logger.debug(f"Processing PDF with Gemini: {uploaded_file.name}")

    def _operation() -> str:
        response = model.generate_content([prompt, uploaded_file])
        return response.text

    result = _execute_with_retries(_operation, "Gemini PDF generation", max_retries)
    logger.debug(f"Gemini response received ({len(result)} characters)")
    return result
