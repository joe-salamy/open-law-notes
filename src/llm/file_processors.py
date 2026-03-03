"""Single-file processors for text, PDF, and Word documents."""

from pathlib import Path
from typing import Optional, Tuple

import google.generativeai as genai

import config

try:
    from ..utils.file_mover import move_to_processed, copy_to_new_outputs
    from ..utils.logger_config import get_logger
    from .gemini_client import process_with_gemini, upload_pdf_to_gemini, process_pdf_with_gemini
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.utils.file_mover import move_to_processed, copy_to_new_outputs
    from src.utils.logger_config import get_logger
    from src.llm.gemini_client import process_with_gemini, upload_pdf_to_gemini, process_pdf_with_gemini

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
    except Exception as e:
        logger.error(f"Error reading {filepath.name}: {e}", exc_info=True)
        return None


def load_system_prompt(prompt_file: str, class_name: str) -> Optional[str]:
    """Load system prompt from prompts folder and substitute class name."""
    prompt_path = config.PROMPT_DIR / prompt_file
    logger.debug(f"Loading system prompt from: {prompt_path}")

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise Exception(f"Prompt file not found: {prompt_path}")

    base_prompt = read_file(prompt_path)
    if base_prompt is None:
        logger.error(f"Failed to read prompt file: {prompt_path}")
        return None

    formatted_prompt = base_prompt.format(class_name=class_name)
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
    except Exception as e:
        logger.error(f"Error converting {filepath.name}: {e}", exc_info=True)
        return None


def process_single_file(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool],
) -> Tuple[bool, str, Path]:
    """Process a single text file with Gemini."""
    input_file, model, output_folder, processed_folder, new_outputs_dir, is_reading = args

    try:
        logger.debug(f"Processing file: {input_file.name}")
        content = read_file(input_file)
        if content is None:
            logger.error(f"Failed to read file: {input_file.name}")
            return False, "Failed to read file", input_file

        logger.debug(f"Sending to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)
        if result is None:
            logger.error(f"Gemini API error for file: {input_file.name}")
            return False, "Gemini API error", input_file

        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except Exception as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        return False, f"Error: {str(e)}", input_file


def process_single_pdf(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path],
) -> Tuple[bool, str, Path]:
    """Process a single PDF file with Gemini."""
    input_file, model, output_folder, processed_folder, new_outputs_dir = args

    try:
        logger.debug(f"Processing PDF file: {input_file.name}")

        uploaded_file = upload_pdf_to_gemini(input_file)
        if uploaded_file is None:
            logger.error(f"Failed to upload PDF: {input_file.name}")
            return False, "Failed to upload PDF", input_file

        logger.debug(f"Sending PDF to Gemini: {input_file.name}")
        result = process_pdf_with_gemini(model, uploaded_file, "Process this reading material.")
        if result is None:
            logger.error(f"Gemini API error for PDF: {input_file.name}")
            return False, "Gemini API error", input_file

        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        try:
            genai.delete_file(uploaded_file.name)
            logger.debug(f"Deleted uploaded file from Gemini: {uploaded_file.name}")
        except Exception as e:
            logger.warning(f"Failed to delete uploaded file from Gemini: {e}")

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except Exception as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        return False, f"Error: {str(e)}", input_file


def process_single_word(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path],
) -> Tuple[bool, str, Path]:
    """Process a single Word document (.doc/.docx) by extracting text and sending to Gemini."""
    input_file, model, output_folder, processed_folder, new_outputs_dir = args

    try:
        logger.debug(f"Processing Word file: {input_file.name}")

        content = extract_text_from_word(input_file)
        if content is None:
            logger.error(f"Failed to extract text from Word file: {input_file.name}")
            return False, "Failed to extract text from Word file", input_file

        if not content.strip():
            logger.error(f"No text content found in Word file: {input_file.name}")
            return False, "No text content found in Word file", input_file

        logger.debug(f"Sending Word document text to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)
        if result is None:
            logger.error(f"Gemini API error for Word file: {input_file.name}")
            return False, "Gemini API error", input_file

        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except Exception as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        return False, f"Error: {str(e)}", input_file
