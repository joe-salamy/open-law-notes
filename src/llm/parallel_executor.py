"""Thread-pool-based parallel executors for text, PDF, and Word file processing."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import google.generativeai as genai

import config

try:
    from .file_processors import process_single_file, process_single_pdf, process_single_word
    from ..utils.logger_config import get_logger
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.llm.file_processors import process_single_file, process_single_pdf, process_single_word
    from src.utils.logger_config import get_logger

logger = get_logger(__name__)


def execute_parallel_processing(
    task_args: List[Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool]],
    total_files: int,
) -> Tuple[int, int]:
    """Execute parallel processing of text files. Returns (successful, failed)."""
    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel processing of {total_files} text files with {config.MAX_LLM_WORKERS} workers"
    )
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(process_single_file, args): args[0] for args in task_args
        }

        for future in as_completed(futures):
            input_file = futures[future]
            try:
                success, message, original_file = future.result()

                if success:
                    successful += 1
                    logger.info(
                        f"✓ [{successful + failed}/{total_files}] {original_file.name}"
                    )
                    logger.debug(f"Successfully processed {original_file.name}")
                else:
                    failed += 1
                    logger.info(
                        f"✗ [{successful + failed}/{total_files}] {original_file.name}: {message}"
                    )
                    logger.error(f"Failed to process {original_file.name}: {message}")

            except Exception as e:
                failed += 1
                logger.error(
                    f"Unexpected error processing {input_file.name}: {e}", exc_info=True
                )
                logger.info(
                    f"✗ [{successful + failed}/{total_files}] {input_file.name}: Unexpected error: {e}"
                )

    logger.debug(
        f"Parallel processing complete: {successful} successful, {failed} failed"
    )
    return successful, failed


def execute_parallel_pdf_processing(
    task_args: List[Tuple[Path, genai.GenerativeModel, Path, Path, Path]],
    total_files: int,
) -> Tuple[int, int]:
    """Execute parallel processing of PDF files. Returns (successful, failed)."""
    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel processing of {total_files} PDF files with {config.MAX_LLM_WORKERS} workers"
    )
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(process_single_pdf, args): args[0] for args in task_args
        }

        for future in as_completed(futures):
            input_file = futures[future]
            try:
                success, message, original_file = future.result()

                if success:
                    successful += 1
                    logger.info(
                        f"✓ [{successful + failed}/{total_files}] {original_file.name}"
                    )
                    logger.debug(f"Successfully processed PDF {original_file.name}")
                else:
                    failed += 1
                    logger.info(
                        f"✗ [{successful + failed}/{total_files}] {original_file.name}: {message}"
                    )
                    logger.error(
                        f"Failed to process PDF {original_file.name}: {message}"
                    )

            except Exception as e:
                failed += 1
                logger.error(
                    f"Unexpected error processing PDF {input_file.name}: {e}",
                    exc_info=True,
                )
                logger.info(
                    f"✗ [{successful + failed}/{total_files}] {input_file.name}: Unexpected error: {e}"
                )

    logger.debug(
        f"PDF parallel processing complete: {successful} successful, {failed} failed"
    )
    return successful, failed


def execute_parallel_word_processing(
    task_args: List[Tuple[Path, genai.GenerativeModel, Path, Path, Path]],
    total_files: int,
) -> Tuple[int, int]:
    """Execute parallel processing of Word files. Returns (successful, failed)."""
    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel processing of {total_files} Word files with {config.MAX_LLM_WORKERS} workers"
    )
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(process_single_word, args): args[0] for args in task_args
        }

        for future in as_completed(futures):
            input_file = futures[future]
            try:
                success, message, original_file = future.result()

                if success:
                    successful += 1
                    logger.info(
                        f"✓ [{successful + failed}/{total_files}] {original_file.name}"
                    )
                    logger.debug(
                        f"Successfully processed Word file {original_file.name}"
                    )
                else:
                    failed += 1
                    logger.info(
                        f"✗ [{successful + failed}/{total_files}] {original_file.name}: {message}"
                    )
                    logger.error(
                        f"Failed to process Word file {original_file.name}: {message}"
                    )

            except Exception as e:
                failed += 1
                logger.error(
                    f"Unexpected error processing Word file {input_file.name}: {e}",
                    exc_info=True,
                )
                logger.info(
                    f"✗ [{successful + failed}/{total_files}] {input_file.name}: Unexpected error: {e}"
                )

    logger.debug(
        f"Word parallel processing complete: {successful} successful, {failed} failed"
    )
    return successful, failed
