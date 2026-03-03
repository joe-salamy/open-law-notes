"""
LLM processing orchestration using Gemini with multithreading.
Generates notes from lecture transcripts and reading texts.
"""

import os
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai
from dotenv import load_dotenv

try:
    from . import config
    from .folder_manager import get_class_paths, get_text_files, get_pdf_files, get_word_files
    from .logger_config import get_logger
    from .gemini_client import _check_model_error
    from .file_processors import load_system_prompt, process_single_file, process_single_pdf, process_single_word
    from .parallel_executor import (
        execute_parallel_processing,
        execute_parallel_pdf_processing,
        execute_parallel_word_processing,
    )
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    import src.config as config
    from src.folder_manager import get_class_paths, get_text_files, get_pdf_files, get_word_files
    from src.logger_config import get_logger
    from src.gemini_client import _check_model_error
    from src.file_processors import load_system_prompt, process_single_file, process_single_pdf, process_single_word
    from src.parallel_executor import (
        execute_parallel_processing,
        execute_parallel_pdf_processing,
        execute_parallel_word_processing,
    )

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


def process_class_files(
    class_folder: Path, is_reading: bool, new_outputs_dir: Path, api_key: str
) -> Tuple[int, int]:
    """
    Process all files (reading or lecture) for a single class.
    Handles text files (txt, md), PDF files, and Word files.
    """
    paths = get_class_paths(class_folder)
    class_name = paths["class_name"]

    if is_reading:
        text_files = get_text_files(class_folder, reading=True)
        pdf_files = get_pdf_files(class_folder, reading=True)
        word_files = get_word_files(class_folder, reading=True)
        output_folder = paths["reading_output"]
        processed_folder = paths["reading_processed"]
        prompt_file = config.READING_PROMPT_FILE
        file_type = "reading"
    else:
        text_files = get_text_files(class_folder, reading=False)
        pdf_files = get_pdf_files(class_folder, reading=False)
        word_files = get_word_files(class_folder, reading=False)
        output_folder = paths["lecture_output"]
        processed_folder = paths["lecture_processed_txt"]
        prompt_file = config.LECTURE_PROMPT_FILE
        file_type = "lecture transcript"

    logger.debug(f"Processing {file_type} files for {class_name}")

    total_files = len(text_files) + len(pdf_files) + len(word_files)
    if total_files == 0:
        logger.info(f"No {file_type} files found")
        return 0, 0

    logger.info(
        f"Found {total_files} {file_type} file(s) ({len(text_files)} text, {len(pdf_files)} PDF, {len(word_files)} Word)"
    )
    logger.debug(f"{file_type} text files: {[f.name for f in text_files]}")
    logger.debug(f"{file_type} PDF files: {[f.name for f in pdf_files]}")
    logger.debug(f"{file_type} Word files: {[f.name for f in word_files]}")

    try:
        logger.debug(f"Loading system prompt for {class_name}")
        system_prompt = load_system_prompt(prompt_file, class_name)
        if system_prompt is None:
            logger.error(f"Error loading prompt for {class_name}")
            logger.info("✗ Error loading prompt")
            return 0, total_files
    except Exception as e:
        logger.error(f"Error loading prompt for {class_name}: {e}", exc_info=True)
        logger.info(f"✗ Error loading prompt: {e}")
        return 0, total_files

    logger.debug(f"Configuring Gemini API for {class_name}")
    genai.configure(api_key=api_key)
    try:
        logger.debug(f"Creating GenerativeModel: {config.GEMINI_MODEL}")
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                temperature=config.GEMINI_TEMPERATURE,
            ),
        )
        logger.debug("GenerativeModel created successfully")
    except Exception as e:
        _check_model_error(e)
        logger.error(
            f"Error creating GenerativeModel for {class_name}: {e}", exc_info=True
        )
        logger.info(f"✗ Error creating GenerativeModel: {e}")
        return 0, total_files

    total_successful = 0
    total_failed = 0

    if text_files:
        logger.debug(f"Processing {len(text_files)} text files for {class_name}")
        text_task_args = [
            (text_file, model, output_folder, processed_folder, new_outputs_dir, is_reading)
            for text_file in text_files
        ]
        successful, failed = execute_parallel_processing(text_task_args, len(text_files))
        total_successful += successful
        total_failed += failed

    if pdf_files:
        logger.debug(f"Processing {len(pdf_files)} PDF files for {class_name}")
        pdf_task_args = [
            (pdf_file, model, output_folder, processed_folder, new_outputs_dir)
            for pdf_file in pdf_files
        ]
        successful, failed = execute_parallel_pdf_processing(pdf_task_args, len(pdf_files))
        total_successful += successful
        total_failed += failed

    if word_files:
        logger.debug(f"Processing {len(word_files)} Word files for {class_name}")
        word_task_args = [
            (word_file, model, output_folder, processed_folder, new_outputs_dir)
            for word_file in word_files
        ]
        successful, failed = execute_parallel_word_processing(word_task_args, len(word_files))
        total_successful += successful
        total_failed += failed

    logger.debug(
        f"Completed processing for {class_name}: {total_successful} successful, {total_failed} failed"
    )
    return total_successful, total_failed


def process_all_lectures(classes: List[Path], new_outputs_dir: Path) -> None:
    """
    Process lecture transcripts for all classes.
    Parallelizes across ALL classes, not just within each class.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        raise Exception("GEMINI_API_KEY not found in .env file")

    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")
    logger.debug(f"Processing lecture transcripts for {len(classes)} classes")

    genai.configure(api_key=api_key)

    all_text_task_args = []
    all_pdf_task_args = []
    class_file_counts = {}

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]

        text_files = get_text_files(class_folder, reading=False)
        pdf_files = get_pdf_files(class_folder, reading=False)
        class_file_counts[class_name] = len(text_files) + len(pdf_files)

        if not text_files and not pdf_files:
            logger.info(f"{class_name}: No lecture transcript files found")
            continue

        logger.info(
            f"{class_name}: {len(text_files)} text, {len(pdf_files)} PDF file(s)"
        )

        try:
            system_prompt = load_system_prompt(config.LECTURE_PROMPT_FILE, class_name)
            if system_prompt is None:
                logger.error(f"Error loading prompt for {class_name}")
                continue
            model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            _check_model_error(e)
            logger.error(f"Error creating model for {class_name}: {e}", exc_info=True)
            continue

        for text_file in text_files:
            all_text_task_args.append((
                text_file,
                model,
                paths["lecture_output"],
                paths["lecture_processed_txt"],
                new_outputs_dir,
                False,       # is_reading
                class_name,  # for tracking
            ))

        for pdf_file in pdf_files:
            all_pdf_task_args.append((
                pdf_file,
                model,
                paths["lecture_output"],
                paths["lecture_processed_txt"],
                new_outputs_dir,
                class_name,  # for tracking
            ))

    total_files = len(all_text_task_args) + len(all_pdf_task_args)
    if total_files == 0:
        logger.info("No lecture transcript files found in any class")
        return

    logger.info(f"Total lecture files to process: {total_files}")

    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        text_futures = {
            executor.submit(process_single_file, args[:6]): args
            for args in all_text_task_args
        }
        pdf_futures = {
            executor.submit(process_single_pdf, args[:5]): args
            for args in all_pdf_task_args
        }

        for future in as_completed({**text_futures, **pdf_futures}):
            args = {**text_futures, **pdf_futures}[future]
            input_file = args[0]
            class_name = args[-1]

            try:
                success, message, original_file = future.result()

                if success:
                    total_successful += 1
                    class_results[class_name]["successful"] += 1
                    logger.info(
                        f"✓ [{class_name}] [{total_successful + total_failed}/{total_files}] {original_file.name}"
                    )
                else:
                    total_failed += 1
                    class_results[class_name]["failed"] += 1
                    logger.info(
                        f"✗ [{class_name}] [{total_successful + total_failed}/{total_files}] {original_file.name}: {message}"
                    )

            except Exception as e:
                total_failed += 1
                class_results[class_name]["failed"] += 1
                logger.error(
                    f"Unexpected error processing {input_file.name}: {e}", exc_info=True
                )
                logger.info(
                    f"✗ [{class_name}] [{total_successful + total_failed}/{total_files}] {input_file.name}: Unexpected error: {e}"
                )

    logger.info("─" * 70)
    logger.info("Per-class summary:")
    for class_name, results in class_results.items():
        if results["successful"] > 0 or results["failed"] > 0:
            logger.info(
                f"  {class_name}: {results['successful']} successful, {results['failed']} failed"
            )

    logger.info("─" * 70)
    logger.info(
        f"Lecture Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Lecture processing completed: {total_successful} successful, {total_failed} failed"
    )


def process_all_readings(classes: List[Path], new_outputs_dir: Path) -> None:
    """
    Process reading files for all classes.
    Parallelizes across ALL classes, not just within each class.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        raise Exception("GEMINI_API_KEY not found in .env file")

    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")
    logger.debug(f"Processing reading files for {len(classes)} classes")

    genai.configure(api_key=api_key)

    all_text_task_args = []
    all_pdf_task_args = []
    all_word_task_args = []
    class_file_counts = {}

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]

        text_files = get_text_files(class_folder, reading=True)
        pdf_files = get_pdf_files(class_folder, reading=True)
        word_files = get_word_files(class_folder, reading=True)
        class_file_counts[class_name] = len(text_files) + len(pdf_files) + len(word_files)

        if not text_files and not pdf_files and not word_files:
            logger.info(f"{class_name}: No reading files found")
            continue

        logger.info(
            f"{class_name}: {len(text_files)} text, {len(pdf_files)} PDF, {len(word_files)} Word file(s)"
        )

        try:
            system_prompt = load_system_prompt(config.READING_PROMPT_FILE, class_name)
            if system_prompt is None:
                logger.error(f"Error loading prompt for {class_name}")
                continue
            model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            _check_model_error(e)
            logger.error(f"Error creating model for {class_name}: {e}", exc_info=True)
            continue

        for text_file in text_files:
            all_text_task_args.append((
                text_file,
                model,
                paths["reading_output"],
                paths["reading_processed"],
                new_outputs_dir,
                True,        # is_reading
                class_name,  # for tracking
            ))

        for pdf_file in pdf_files:
            all_pdf_task_args.append((
                pdf_file,
                model,
                paths["reading_output"],
                paths["reading_processed"],
                new_outputs_dir,
                class_name,  # for tracking
            ))

        for word_file in word_files:
            all_word_task_args.append((
                word_file,
                model,
                paths["reading_output"],
                paths["reading_processed"],
                new_outputs_dir,
                class_name,  # for tracking
            ))

    total_files = len(all_text_task_args) + len(all_pdf_task_args) + len(all_word_task_args)
    if total_files == 0:
        logger.info("No reading files found in any class")
        return

    logger.info(f"Total reading files to process: {total_files}")

    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        text_futures = {
            executor.submit(process_single_file, args[:6]): args
            for args in all_text_task_args
        }
        pdf_futures = {
            executor.submit(process_single_pdf, args[:5]): args
            for args in all_pdf_task_args
        }
        word_futures = {
            executor.submit(process_single_word, args[:5]): args
            for args in all_word_task_args
        }

        all_futures = {**text_futures, **pdf_futures, **word_futures}

        for future in as_completed(all_futures):
            args = all_futures[future]
            input_file = args[0]
            class_name = args[-1]

            try:
                success, message, original_file = future.result()

                if success:
                    total_successful += 1
                    class_results[class_name]["successful"] += 1
                    logger.info(
                        f"✓ [{class_name}] [{total_successful + total_failed}/{total_files}] {original_file.name}"
                    )
                else:
                    total_failed += 1
                    class_results[class_name]["failed"] += 1
                    logger.info(
                        f"✗ [{class_name}] [{total_successful + total_failed}/{total_files}] {original_file.name}: {message}"
                    )

            except Exception as e:
                total_failed += 1
                class_results[class_name]["failed"] += 1
                logger.error(
                    f"Unexpected error processing {input_file.name}: {e}", exc_info=True
                )
                logger.info(
                    f"✗ [{class_name}] [{total_successful + total_failed}/{total_files}] {input_file.name}: Unexpected error: {e}"
                )

    logger.info("─" * 70)
    logger.info("Per-class summary:")
    for class_name, results in class_results.items():
        if results["successful"] > 0 or results["failed"] > 0:
            logger.info(
                f"  {class_name}: {results['successful']} successful, {results['failed']} failed"
            )

    logger.info("─" * 70)
    logger.info(
        f"Reading Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Reading processing completed: {total_successful} successful, {total_failed} failed"
    )
