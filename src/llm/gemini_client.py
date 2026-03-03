"""Low-level Gemini API helpers: error checking, content generation, PDF upload/processing."""

import time
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from google.api_core.exceptions import NotFound

import config

try:
    from ..utils.logger_config import get_logger
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.utils.logger_config import get_logger

logger = get_logger(__name__)


def _check_model_error(e: Exception) -> None:
    """Raise a friendly SystemExit if the error indicates an invalid or deprecated model."""
    if isinstance(e, NotFound) or "not found" in str(e).lower():
        raise SystemExit(
            f"\nERROR: Gemini model '{config.GEMINI_MODEL}' was not found.\n"
            f"It may have been updated or deprecated by Google.\n\n"
            f"To fix this:\n"
            f"  1. Visit https://ai.google.dev/gemini-api/docs/models to see available models\n"
            f"  2. Open  config.py  and find the GEMINI_MODEL setting\n"
            f"  3. Replace '{config.GEMINI_MODEL}' with a current model name from the list above\n"
        )


def process_with_gemini(
    model: genai.GenerativeModel, content: str, max_retries: int = 3
) -> Optional[str]:
    """
    Send content to Gemini using a pre-created GenerativeModel and return the response.

    Includes exponential backoff retry logic for transient API errors.
    """
    logger.debug(f"Processing content with Gemini ({len(content)} characters)")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Gemini API call attempt {attempt}/{max_retries}")
            response = model.generate_content(content)
            logger.debug(f"Gemini response received ({len(response.text)} characters)")
            return response.text
        except Exception as e:
            if attempt == max_retries:
                _check_model_error(e)
                logger.error(
                    f"Gemini API error after {max_retries} attempts: {e}", exc_info=True
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"Gemini API error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
            time.sleep(backoff)


def upload_pdf_to_gemini(
    filepath: Path, max_retries: int = 3
) -> Optional[genai.types.File]:
    """Upload a PDF file to Gemini and return the file object."""
    logger.debug(f"Uploading PDF to Gemini: {filepath.name}")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Upload attempt {attempt}/{max_retries}")
            uploaded_file = genai.upload_file(filepath)
            logger.debug(f"PDF uploaded successfully: {uploaded_file.name}")
            return uploaded_file
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    f"PDF upload failed after {max_retries} attempts: {e}",
                    exc_info=True,
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"PDF upload error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
            time.sleep(backoff)


def process_pdf_with_gemini(
    model: genai.GenerativeModel,
    uploaded_file: genai.types.File,
    prompt: str = "Process this PDF document.",
    max_retries: int = 3,
) -> Optional[str]:
    """Process an uploaded PDF with Gemini."""
    logger.debug(f"Processing PDF with Gemini: {uploaded_file.name}")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Gemini API call attempt {attempt}/{max_retries}")
            response = model.generate_content([prompt, uploaded_file])
            logger.debug(f"Gemini response received ({len(response.text)} characters)")
            return response.text
        except Exception as e:
            if attempt == max_retries:
                _check_model_error(e)
                logger.error(
                    f"Gemini API error after {max_retries} attempts: {e}", exc_info=True
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"Gemini API error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
            time.sleep(backoff)
