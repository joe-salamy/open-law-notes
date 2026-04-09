"""Single-file processors for text, PDF, and Word documents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import google.generativeai as genai

import config
from ..utils.errors import FileProcessingError, PromptLoadError
from ..utils.file_mover import move_to_processed, copy_to_new_outputs
from ..utils.logger_config import get_logger
from ..utils.run_manifest import RunManifest
from .gemini_client import (
    process_pdf_with_gemini,
    process_with_gemini,
    upload_pdf_to_gemini,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class FileTaskArgs:
    """Arguments for a single file processing task."""

    input_file: Path
    model: genai.GenerativeModel
    output_folder: Path
    processed_folder: Path
    new_outputs_dir: Path
    stage: str
    class_name: str
    manifest: RunManifest


def read_file(filepath: Path) -> str | None:
    """Read and return contents of a file."""
    try:
        logger.debug("Reading file: %s", filepath.name)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        logger.debug(
            "File read successfully: %s (%d characters)", filepath.name, len(content)
        )
        return content
    except (OSError, UnicodeDecodeError) as e:
        logger.error("Error reading %s: %s", filepath.name, e, exc_info=True)
        return None


def load_system_prompt(prompt_file: str, class_name: str) -> str | None:
    """Load system prompt from prompts folder and substitute class name."""
    prompt_path = config.PROMPT_DIR / prompt_file
    logger.debug("Loading system prompt from: %s", prompt_path)

    if not prompt_path.exists():
        logger.error("Prompt file not found: %s", prompt_path)
        raise PromptLoadError(f"Prompt file not found: {prompt_path}")

    base_prompt = read_file(prompt_path)
    if base_prompt is None:
        logger.error("Failed to read prompt file: %s", prompt_path)
        return None

    try:
        formatted_prompt = base_prompt.format(class_name=class_name)
    except KeyError as e:
        raise PromptLoadError(
            f"Prompt formatting failed for {prompt_file}: {e}"
        ) from e
    logger.debug("System prompt loaded and formatted for class: %s", class_name)
    return formatted_prompt


def extract_text_from_word(filepath: Path) -> str | None:
    """Convert a .doc or .docx file to markdown using markitdown."""
    try:
        from markitdown import MarkItDown
    except ImportError:
        logger.error("markitdown is not installed. Run: pip install markitdown[docx]")
        return None

    try:
        logger.debug("Converting Word document to markdown: %s", filepath.name)
        md = MarkItDown()
        result = md.convert(str(filepath))
        content = result.text_content
        logger.debug("Converted %d characters from %s", len(content), filepath.name)
        return content
    except (OSError, RuntimeError, ValueError) as e:
        logger.error("Error converting %s: %s", filepath.name, e, exc_info=True)
        return None


def _process_file_lifecycle(
    args: FileTaskArgs,
    generate: Callable[[], str],
) -> tuple[bool, str, Path]:
    """Shared lifecycle: skip check, generate, save, copy, move, record manifest."""
    output_file = args.output_folder / f"{args.input_file.stem}.md"
    det_name = f"{args.class_name}__{args.stage}__{output_file.name}"

    try:
        logger.debug("Processing file: %s", args.input_file.name)

        if output_file.exists() and output_file.stat().st_size > 0:
            logger.info("Skipping already-generated output: %s", output_file.name)
            copy_to_new_outputs(
                output_file, args.new_outputs_dir, destination_name=det_name
            )
            move_to_processed(args.input_file, args.processed_folder)
            args.manifest.record_file_result(
                stage=args.stage,
                class_name=args.class_name,
                input_file=args.input_file,
                status="skipped",
                output_files=[output_file],
                message="Resumed from existing output",
            )
            return True, "Skipped (already processed)", args.input_file

        result = generate()

        logger.debug("Saving output to: %s", output_file)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)

        copy_to_new_outputs(
            output_file, args.new_outputs_dir, destination_name=det_name
        )
        move_to_processed(args.input_file, args.processed_folder)
        args.manifest.record_file_result(
            stage=args.stage,
            class_name=args.class_name,
            input_file=args.input_file,
            status="success",
            output_files=[output_file],
        )

        logger.info("Successfully processed: %s", args.input_file.name)
        return True, "Success", args.input_file

    except (OSError, RuntimeError, ValueError, FileProcessingError) as e:
        logger.error(
            "Error processing %s: %s", args.input_file.name, e, exc_info=True
        )
        args.manifest.record_file_result(
            stage=args.stage,
            class_name=args.class_name,
            input_file=args.input_file,
            status="failed",
            message=str(e),
            error_type=type(e).__name__,
        )
        return False, f"Error: {e}", args.input_file


def process_single_file(args: FileTaskArgs) -> tuple[bool, str, Path]:
    """Process a single text file with Gemini."""

    def generate() -> str:
        content = read_file(args.input_file)
        if content is None:
            raise FileProcessingError(
                f"Failed to read file: {args.input_file.name}"
            )
        return process_with_gemini(args.model, content)

    return _process_file_lifecycle(args, generate)


def process_single_pdf(args: FileTaskArgs) -> tuple[bool, str, Path]:
    """Process a single PDF file with Gemini."""
    import google.generativeai as genai  # noqa: F811

    uploaded_file = None

    def generate() -> str:
        nonlocal uploaded_file
        uploaded_file = upload_pdf_to_gemini(args.input_file)
        return process_pdf_with_gemini(
            args.model, uploaded_file, "Process this reading material."
        )

    try:
        return _process_file_lifecycle(args, generate)
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                logger.debug(
                    "Deleted uploaded file from Gemini: %s", uploaded_file.name
                )
            except (RuntimeError, ValueError, OSError):
                logger.warning(
                    "Failed to delete uploaded file from Gemini: %s",
                    uploaded_file.name,
                )


def process_single_word(args: FileTaskArgs) -> tuple[bool, str, Path]:
    """Process a single Word document by extracting text and sending to Gemini."""

    def generate() -> str:
        content = extract_text_from_word(args.input_file)
        if content is None:
            raise FileProcessingError("Failed to extract text from Word file")
        if not content.strip():
            raise FileProcessingError("No text content found in Word file")
        return process_with_gemini(args.model, content)

    return _process_file_lifecycle(args, generate)
