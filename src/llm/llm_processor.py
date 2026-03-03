"""
LLM processing orchestration using Gemini with multithreading.
Generates notes from lecture transcripts and reading texts.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import google.generativeai as genai
from dotenv import load_dotenv

import config
from ..utils.errors import ConfigurationError, PromptLoadError
from ..utils.folder_manager import (
    get_class_paths,
    get_pdf_files,
    get_text_files,
    get_word_files,
)
from ..utils.logger_config import get_logger
from ..utils.run_manifest import RunManifest
from .file_processors import (
    load_system_prompt,
    process_single_file,
    process_single_pdf,
    process_single_word,
)
from .gemini_client import _check_model_error

load_dotenv()
logger = get_logger(__name__)


def _get_required_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ConfigurationError("GEMINI_API_KEY not found in .env file")
    return api_key


def _build_model(system_prompt: str) -> genai.GenerativeModel:
    try:
        return genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                temperature=config.GEMINI_TEMPERATURE,
            ),
        )
    except (RuntimeError, ValueError, TypeError) as error:
        _check_model_error(error)
        raise


def process_all_lectures(
    classes: List[Path], new_outputs_dir: Path, manifest: RunManifest
) -> None:
    """Process lecture transcript files for all classes."""
    api_key = _get_required_api_key()
    genai.configure(api_key=api_key)

    manifest.record_stage_event(
        "lecture_llm", "start", "Starting lecture LLM processing"
    )
    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")

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
                raise PromptLoadError("Prompt content was empty")
            model = _build_model(system_prompt)
        except (PromptLoadError, RuntimeError, ValueError, TypeError) as error:
            logger.error(
                f"Error preparing model for {class_name}: {error}", exc_info=True
            )
            continue

        for text_file in text_files:
            all_text_task_args.append(
                (
                    text_file,
                    model,
                    paths["lecture_output"],
                    paths["lecture_processed_txt"],
                    new_outputs_dir,
                    False,
                    class_name,
                    manifest,
                )
            )

        for pdf_file in pdf_files:
            all_pdf_task_args.append(
                (
                    pdf_file,
                    model,
                    paths["lecture_output"],
                    paths["lecture_processed_txt"],
                    new_outputs_dir,
                    "lecture_llm",
                    class_name,
                    manifest,
                )
            )

    total_files = len(all_text_task_args) + len(all_pdf_task_args)
    if total_files == 0:
        logger.info("No lecture transcript files found in any class")
        manifest.record_stage_event(
            "lecture_llm", "complete", "No lecture files to process"
        )
        return

    logger.info(f"Total lecture files to process: {total_files}")
    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        text_futures = {
            executor.submit(process_single_file, args): args
            for args in all_text_task_args
        }
        pdf_futures = {
            executor.submit(process_single_pdf, args): args
            for args in all_pdf_task_args
        }
        all_futures = {**text_futures, **pdf_futures}

        for future in as_completed(all_futures):
            args = all_futures[future]
            input_file = args[0]
            class_name = args[-2]

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
            except (RuntimeError, OSError, ValueError, TypeError) as error:
                total_failed += 1
                class_results[class_name]["failed"] += 1
                logger.error(
                    f"Unexpected error processing {input_file.name}: {error}",
                    exc_info=True,
                )
                manifest.record_file_result(
                    stage="lecture_llm",
                    class_name=class_name,
                    input_file=input_file,
                    status="failed",
                    message=str(error),
                    error_type=type(error).__name__,
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
    manifest.record_stage_event(
        "lecture_llm",
        "complete",
        f"Completed lecture LLM processing ({total_successful} successful, {total_failed} failed)",
    )


def process_all_readings(
    classes: List[Path], new_outputs_dir: Path, manifest: RunManifest
) -> None:
    """Process reading files for all classes."""
    api_key = _get_required_api_key()
    genai.configure(api_key=api_key)

    manifest.record_stage_event(
        "reading_llm", "start", "Starting reading LLM processing"
    )
    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")

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
        class_file_counts[class_name] = (
            len(text_files) + len(pdf_files) + len(word_files)
        )

        if not text_files and not pdf_files and not word_files:
            logger.info(f"{class_name}: No reading files found")
            continue

        logger.info(
            f"{class_name}: {len(text_files)} text, {len(pdf_files)} PDF, {len(word_files)} Word file(s)"
        )

        try:
            system_prompt = load_system_prompt(config.READING_PROMPT_FILE, class_name)
            if system_prompt is None:
                raise PromptLoadError("Prompt content was empty")
            model = _build_model(system_prompt)
        except (PromptLoadError, RuntimeError, ValueError, TypeError) as error:
            logger.error(
                f"Error preparing model for {class_name}: {error}", exc_info=True
            )
            continue

        for text_file in text_files:
            all_text_task_args.append(
                (
                    text_file,
                    model,
                    paths["reading_output"],
                    paths["reading_processed"],
                    new_outputs_dir,
                    True,
                    class_name,
                    manifest,
                )
            )

        for pdf_file in pdf_files:
            all_pdf_task_args.append(
                (
                    pdf_file,
                    model,
                    paths["reading_output"],
                    paths["reading_processed"],
                    new_outputs_dir,
                    "reading_llm",
                    class_name,
                    manifest,
                )
            )

        for word_file in word_files:
            all_word_task_args.append(
                (
                    word_file,
                    model,
                    paths["reading_output"],
                    paths["reading_processed"],
                    new_outputs_dir,
                    "reading_llm",
                    class_name,
                    manifest,
                )
            )

    total_files = (
        len(all_text_task_args) + len(all_pdf_task_args) + len(all_word_task_args)
    )
    if total_files == 0:
        logger.info("No reading files found in any class")
        manifest.record_stage_event(
            "reading_llm", "complete", "No reading files to process"
        )
        return

    logger.info(f"Total reading files to process: {total_files}")
    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        text_futures = {
            executor.submit(process_single_file, args): args
            for args in all_text_task_args
        }
        pdf_futures = {
            executor.submit(process_single_pdf, args): args
            for args in all_pdf_task_args
        }
        word_futures = {
            executor.submit(process_single_word, args): args
            for args in all_word_task_args
        }

        all_futures = {**text_futures, **pdf_futures, **word_futures}

        for future in as_completed(all_futures):
            args = all_futures[future]
            input_file = args[0]
            class_name = args[-2]

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
            except (RuntimeError, OSError, ValueError, TypeError) as error:
                total_failed += 1
                class_results[class_name]["failed"] += 1
                logger.error(
                    f"Unexpected error processing {input_file.name}: {error}",
                    exc_info=True,
                )
                manifest.record_file_result(
                    stage="reading_llm",
                    class_name=class_name,
                    input_file=input_file,
                    status="failed",
                    message=str(error),
                    error_type=type(error).__name__,
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
    manifest.record_stage_event(
        "reading_llm",
        "complete",
        f"Completed reading LLM processing ({total_successful} successful, {total_failed} failed)",
    )
