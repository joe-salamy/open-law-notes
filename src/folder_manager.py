"""
Folder structure verification and creation.
Ensures each class has the required folder hierarchy.
"""

import sys
from pathlib import Path
from typing import List
import config
from file_mover import setup_output_directory
from logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)


def verify_and_create_folders(class_folder: Path) -> None:
    """
    Verify and create the required folder structure for a class.

    Args:
        class_folder: Path to the class root folder

    Raises:
        Exception: If folder creation fails
    """
    if not isinstance(class_folder, Path):
        class_folder = Path(class_folder)

    logger.debug(f"Verifying folder structure for: {class_folder}")

    if not class_folder.exists():
        logger.error(f"Class folder does not exist: {class_folder}")
        raise Exception(f"Class folder does not exist: {class_folder}")

    # Define all required folders
    llm_base = class_folder / config.LLM_BASE

    required_folders = [
        llm_base / config.LECTURE_INPUT,
        llm_base / config.LECTURE_OUTPUT,
        llm_base / config.LECTURE_PROCESSED / config.LECTURE_PROCESSED_AUDIO,
        llm_base / config.LECTURE_PROCESSED / config.LECTURE_PROCESSED_TXT,
        llm_base / config.READING_INPUT,
        llm_base / config.READING_OUTPUT,
        llm_base / config.READING_PROCESSED,
    ]

    logger.debug(f"Creating {len(required_folders)} required folders")
    # Create all folders
    for folder in required_folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create folder {folder}: {e}", exc_info=True)
            raise Exception(f"Failed to create folder {folder}: {e}")

    logger.debug(f"Folder structure verification complete for: {class_folder.name}")
    return None


def get_class_paths(class_folder: Path) -> dict:
    """
    Get all relevant paths for a class.

    Args:
        class_folder: Path to the class root folder

    Returns:
        Dictionary with all folder paths
    """
    if not isinstance(class_folder, Path):
        class_folder = Path(class_folder)

    llm_base = class_folder / config.LLM_BASE

    return {
        "class_name": class_folder.name,
        "lecture_input": llm_base / config.LECTURE_INPUT,
        "lecture_output": llm_base / config.LECTURE_OUTPUT,
        "lecture_processed_audio": llm_base
        / config.LECTURE_PROCESSED
        / config.LECTURE_PROCESSED_AUDIO,
        "lecture_processed_txt": llm_base
        / config.LECTURE_PROCESSED
        / config.LECTURE_PROCESSED_TXT,
        "reading_input": llm_base / config.READING_INPUT,
        "reading_output": llm_base / config.READING_OUTPUT,
        "reading_processed": llm_base / config.READING_PROCESSED,
    }


def get_audio_files(class_folder: Path) -> List[Path]:
    """
    Get all M4A audio files from lecture-input folder.

    Args:
        class_folder: Path to the class root folder

    Returns:
        List of paths to M4A files
    """
    paths = get_class_paths(class_folder)
    lecture_input = paths["lecture_input"]

    if not lecture_input.exists():
        logger.debug(f"Lecture input folder does not exist: {lecture_input}")
        return []

    audio_files = list(lecture_input.glob("*.m4a"))
    logger.debug(f"Found {len(audio_files)} audio files in {lecture_input}")
    return audio_files


def get_text_files(class_folder: Path, reading: bool = False) -> List[Path]:
    """
    Get all text-based files (TXT and MD) from lecture-input or reading-input folder.

    Args:
        class_folder: Path to the class root folder
        reading: If True, get reading files; if False, get lecture files

    Returns:
        List of paths to TXT and MD files
    """
    paths = get_class_paths(class_folder)
    input_folder = paths["reading_input"] if reading else paths["lecture_input"]
    file_type = "reading" if reading else "lecture"

    logger.debug(f"Searching for {file_type} text files in: {input_folder}")

    if not input_folder.exists():
        logger.debug(f"Input folder does not exist: {input_folder}")
        return []

    txt_files = list(input_folder.glob("*.txt"))
    md_files = list(input_folder.glob("*.md"))
    text_files = txt_files + md_files
    logger.debug(
        f"Found {len(text_files)} {file_type} text files ({len(txt_files)} txt, {len(md_files)} md) in {input_folder}"
    )
    return text_files


def get_txt_files(class_folder: Path, reading: bool = False) -> List[Path]:
    """
    Get all TXT files from lecture-input or reading-input folder.

    DEPRECATED: Use get_text_files() instead to include both TXT and MD files.

    Args:
        class_folder: Path to the class root folder
        reading: If True, get reading files; if False, get lecture files

    Returns:
        List of paths to TXT files
    """
    paths = get_class_paths(class_folder)
    input_folder = paths["reading_input"] if reading else paths["lecture_input"]
    file_type = "reading" if reading else "lecture"

    logger.debug(f"Searching for {file_type} TXT files in: {input_folder}")

    if not input_folder.exists():
        logger.debug(f"Input folder does not exist: {input_folder}")
        return []

    txt_files = list(input_folder.glob("*.txt"))
    logger.debug(f"Found {len(txt_files)} {file_type} TXT files in {input_folder}")
    return txt_files


def get_pdf_files(class_folder: Path, reading: bool = True) -> List[Path]:
    """
    Get all PDF files from reading-input or lecture-input folder.

    Args:
        class_folder: Path to the class root folder
        reading: If True, get reading PDFs; if False, get lecture PDFs

    Returns:
        List of paths to PDF files
    """
    paths = get_class_paths(class_folder)
    input_folder = paths["reading_input"] if reading else paths["lecture_input"]
    file_type = "reading" if reading else "lecture"

    logger.debug(f"Searching for {file_type} PDF files in: {input_folder}")

    if not input_folder.exists():
        logger.debug(f"Input folder does not exist: {input_folder}")
        return []

    pdf_files = list(input_folder.glob("*.pdf"))
    logger.debug(f"Found {len(pdf_files)} {file_type} PDF files in {input_folder}")
    return pdf_files
