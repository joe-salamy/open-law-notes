"""Single-file processors for text, PDF, and Word documents."""

from pathlib import Path
from typing import Optional, Tuple

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


def read_file(filepath: Path) -> Optional[str]:
    """Read and return contents of a file."""
    try:
        logger.debug(f"Reading file: {filepath.name}")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        logger.debug(
            f"File read successfully: {filepath.name} ({len(content)} characters)"
        )
        return content
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Error reading {filepath.name}: {e}", exc_info=True)
        return None


def load_system_prompt(prompt_file: str, class_name: str) -> Optional[str]:
    """Load system prompt from prompts folder and substitute class name."""
    prompt_path = config.PROMPT_DIR / prompt_file
    logger.debug(f"Loading system prompt from: {prompt_path}")

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise PromptLoadError(f"Prompt file not found: {prompt_path}")

    base_prompt = read_file(prompt_path)
    if base_prompt is None:
        logger.error(f"Failed to read prompt file: {prompt_path}")
        return None

    try:
        formatted_prompt = base_prompt.format(class_name=class_name)
    except KeyError as e:
        raise PromptLoadError(f"Prompt formatting failed for {prompt_file}: {e}") from e
    logger.debug(f"System prompt loaded and formatted for class: {class_name}")
    return formatted_prompt


def extract_text_from_word(filepath: Path) -> Optional[str]:
    """Convert a .doc or .docx file to markdown using markitdown."""
    try:
        from markitdown import MarkItDown
    except ImportError:
        logger.error("markitdown is not installed. Run: pip install markitdown[docx]")
        return None

    try:
        logger.debug(f"Converting Word document to markdown: {filepath.name}")
        md = MarkItDown()
        result = md.convert(str(filepath))
        content = result.text_content
        logger.debug(f"Converted {len(content)} characters from {filepath.name}")
        return content
    except (OSError, RuntimeError, ValueError) as e:
        logger.error(f"Error converting {filepath.name}: {e}", exc_info=True)
        return None


def process_single_file(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool, str, RunManifest],
) -> Tuple[bool, str, Path]:
    """Process a single text file with Gemini."""
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
        is_reading,
        class_name,
        manifest,
    ) = args
    stage = "reading_llm" if is_reading else "lecture_llm"
    output_file = output_folder / f"{input_file.stem}.md"
    deterministic_new_outputs_name = f"{class_name}__{stage}__{output_file.name}"

    try:
        logger.debug(f"Processing file: {input_file.name}")

        if output_file.exists() and output_file.stat().st_size > 0:
            logger.info(f"Skipping already-generated output: {output_file.name}")
            copy_to_new_outputs(
                output_file,
                new_outputs_dir,
                destination_name=deterministic_new_outputs_name,
            )
            move_to_processed(input_file, processed_folder)
            manifest.record_file_result(
                stage=stage,
                class_name=class_name,
                input_file=input_file,
                status="skipped",
                output_files=[output_file],
                message="Resumed from existing output",
            )
            return True, "Skipped (already processed)", input_file

        content = read_file(input_file)
        if content is None:
            logger.error(f"Failed to read file: {input_file.name}")
            return False, "Failed to read file", input_file

        logger.debug(f"Sending to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)

        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(
            output_file,
            new_outputs_dir,
            destination_name=deterministic_new_outputs_name,
        )

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="success",
            output_files=[output_file],
        )

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except (OSError, RuntimeError, ValueError, FileProcessingError) as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="failed",
            message=str(e),
            error_type=type(e).__name__,
        )
        return False, f"Error: {str(e)}", input_file


def process_single_pdf(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, str, str, RunManifest],
) -> Tuple[bool, str, Path]:
    """Process a single PDF file with Gemini."""
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
        stage,
        class_name,
        manifest,
    ) = args
    output_file = output_folder / f"{input_file.stem}.md"
    deterministic_new_outputs_name = f"{class_name}__{stage}__{output_file.name}"
    uploaded_file = None

    try:
        logger.debug(f"Processing PDF file: {input_file.name}")

        if output_file.exists() and output_file.stat().st_size > 0:
            logger.info(f"Skipping already-generated PDF output: {output_file.name}")
            copy_to_new_outputs(
                output_file,
                new_outputs_dir,
                destination_name=deterministic_new_outputs_name,
            )
            move_to_processed(input_file, processed_folder)
            manifest.record_file_result(
                stage=stage,
                class_name=class_name,
                input_file=input_file,
                status="skipped",
                output_files=[output_file],
                message="Resumed from existing output",
            )
            return True, "Skipped (already processed)", input_file

        uploaded_file = upload_pdf_to_gemini(input_file)

        logger.debug(f"Sending PDF to Gemini: {input_file.name}")
        result = process_pdf_with_gemini(
            model, uploaded_file, "Process this reading material."
        )

        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(
            output_file,
            new_outputs_dir,
            destination_name=deterministic_new_outputs_name,
        )

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="success",
            output_files=[output_file],
        )

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except (OSError, RuntimeError, ValueError, FileProcessingError) as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="failed",
            message=str(e),
            error_type=type(e).__name__,
        )
        return False, f"Error: {str(e)}", input_file
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                logger.debug(f"Deleted uploaded file from Gemini: {uploaded_file.name}")
            except (RuntimeError, ValueError, OSError):
                logger.warning(
                    f"Failed to delete uploaded file from Gemini: {uploaded_file.name}"
                )


def process_single_word(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, str, str, RunManifest],
) -> Tuple[bool, str, Path]:
    """Process a single Word document (.doc/.docx) by extracting text and sending to Gemini."""
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
        stage,
        class_name,
        manifest,
    ) = args
    output_file = output_folder / f"{input_file.stem}.md"
    deterministic_new_outputs_name = f"{class_name}__{stage}__{output_file.name}"

    try:
        logger.debug(f"Processing Word file: {input_file.name}")

        if output_file.exists() and output_file.stat().st_size > 0:
            logger.info(f"Skipping already-generated Word output: {output_file.name}")
            copy_to_new_outputs(
                output_file,
                new_outputs_dir,
                destination_name=deterministic_new_outputs_name,
            )
            move_to_processed(input_file, processed_folder)
            manifest.record_file_result(
                stage=stage,
                class_name=class_name,
                input_file=input_file,
                status="skipped",
                output_files=[output_file],
                message="Resumed from existing output",
            )
            return True, "Skipped (already processed)", input_file

        content = extract_text_from_word(input_file)
        if content is None:
            logger.error(f"Failed to extract text from Word file: {input_file.name}")
            raise FileProcessingError("Failed to extract text from Word file")

        if not content.strip():
            logger.error(f"No text content found in Word file: {input_file.name}")
            raise FileProcessingError("No text content found in Word file")

        logger.debug(f"Sending Word document text to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)

        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(
            output_file,
            new_outputs_dir,
            destination_name=deterministic_new_outputs_name,
        )

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="success",
            output_files=[output_file],
        )

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except (OSError, RuntimeError, ValueError, FileProcessingError) as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        manifest.record_file_result(
            stage=stage,
            class_name=class_name,
            input_file=input_file,
            status="failed",
            message=str(e),
            error_type=type(e).__name__,
        )
        return False, f"Error: {str(e)}", input_file
