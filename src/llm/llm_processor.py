"""LLM processing orchestration using Gemini with multithreading."""

import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import google.generativeai as genai

import config
from ..utils.errors import ConfigurationError, PromptLoadError
from ..utils.folder_manager import (
    get_class_paths,
    get_pdf_files,
    get_text_files,
    get_word_files,
)
from ..utils.logger_config import get_logger
from ..utils.notes_appender import append_lecture_notes, append_reading_notes
from ..utils.run_manifest import RunManifest
from .file_processors import (
    FileTaskArgs,
    load_system_prompt,
    process_single_file,
    process_single_pdf,
    process_single_word,
)
from .gemini_client import check_model_error

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
        check_model_error(error)
        raise


def _process_all_files(
    classes: list[Path],
    new_outputs_dir: Path,
    manifest: RunManifest,
    stage: str,
    prompt_file: str,
    output_key: str,
    processed_key: str,
    include_word: bool = False,
) -> tuple[dict[str, list[Path]], dict[str, Path]]:
    """Core orchestration: gather files, build models, process in parallel.

    Returns (successful_outputs_by_class, class_folders).
    """
    api_key = _get_required_api_key()
    genai.configure(api_key=api_key)

    manifest.record_stage_event(stage, "start", f"Starting {stage} processing")
    logger.info("Using model: %s", config.GEMINI_MODEL)
    logger.info("Parallel workers: %d", config.MAX_LLM_WORKERS)

    all_task_args: list[tuple[FileTaskArgs, callable]] = []
    class_file_counts: dict[str, int] = {}
    class_folders: dict[str, Path] = {}
    is_reading = stage == "reading_llm"

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]
        class_folders[class_name] = class_folder

        text_files = get_text_files(class_folder, reading=is_reading)
        pdf_files = get_pdf_files(class_folder, reading=is_reading)
        word_files = (
            get_word_files(class_folder, reading=is_reading) if include_word else []
        )
        file_count = len(text_files) + len(pdf_files) + len(word_files)
        class_file_counts[class_name] = file_count

        if file_count == 0:
            logger.info(
                "%s: No %s files found",
                class_name,
                stage.replace("_llm", ""),
            )
            continue

        parts = [f"{len(text_files)} text", f"{len(pdf_files)} PDF"]
        if include_word:
            parts.append(f"{len(word_files)} Word")
        logger.info("%s: %s file(s)", class_name, ", ".join(parts))

        try:
            system_prompt = load_system_prompt(prompt_file, class_name)
            if system_prompt is None:
                raise PromptLoadError("Prompt content was empty")
            model = _build_model(system_prompt)
        except (PromptLoadError, RuntimeError, ValueError, TypeError) as error:
            logger.error(
                "Error preparing model for %s: %s",
                class_name,
                error,
                exc_info=True,
            )
            continue

        base_kwargs = dict(
            model=model,
            output_folder=paths[output_key],
            processed_folder=paths[processed_key],
            new_outputs_dir=new_outputs_dir,
            stage=stage,
            class_name=class_name,
            manifest=manifest,
        )

        for f in text_files:
            all_task_args.append(
                (FileTaskArgs(input_file=f, **base_kwargs), process_single_file)
            )
        for f in pdf_files:
            all_task_args.append(
                (FileTaskArgs(input_file=f, **base_kwargs), process_single_pdf)
            )
        for f in word_files:
            all_task_args.append(
                (FileTaskArgs(input_file=f, **base_kwargs), process_single_word)
            )

    total_files = len(all_task_args)
    if total_files == 0:
        label = stage.replace("_llm", "")
        logger.info("No %s files found in any class", label)
        manifest.record_stage_event(
            stage, "complete", f"No {label} files to process"
        )
        return {}, class_folders

    logger.info(
        "Total %s files to process: %d", stage.replace("_llm", ""), total_files
    )
    class_results = {
        name: {"successful": 0, "failed": 0} for name in class_file_counts
    }
    successful_outputs: dict[str, list[Path]] = defaultdict(list)
    total_successful = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(processor, args): args
            for args, processor in all_task_args
        }

        for future in as_completed(futures):
            args = futures[future]
            try:
                success, message, original_file = future.result()
                if success:
                    total_successful += 1
                    class_results[args.class_name]["successful"] += 1
                    successful_outputs[args.class_name].append(
                        args.output_folder / f"{original_file.stem}.md"
                    )
                    logger.info(
                        "✓ [%s] [%d/%d] %s",
                        args.class_name,
                        total_successful + total_failed,
                        total_files,
                        original_file.name,
                    )
                else:
                    total_failed += 1
                    class_results[args.class_name]["failed"] += 1
                    logger.info(
                        "✗ [%s] [%d/%d] %s: %s",
                        args.class_name,
                        total_successful + total_failed,
                        total_files,
                        original_file.name,
                        message,
                    )
            except (RuntimeError, OSError, ValueError, TypeError) as error:
                total_failed += 1
                class_results[args.class_name]["failed"] += 1
                logger.error(
                    "Unexpected error processing %s: %s",
                    args.input_file.name,
                    error,
                    exc_info=True,
                )
                manifest.record_file_result(
                    stage=stage,
                    class_name=args.class_name,
                    input_file=args.input_file,
                    status="failed",
                    message=str(error),
                    error_type=type(error).__name__,
                )

    logger.info("─" * 70)
    logger.info("Per-class summary:")
    for class_name, results in class_results.items():
        if results["successful"] > 0 or results["failed"] > 0:
            logger.info(
                "  %s: %d successful, %d failed",
                class_name,
                results["successful"],
                results["failed"],
            )

    label = stage.replace("_llm", "").title()
    logger.info("─" * 70)
    logger.info(
        "%s Notes Summary: %d successful, %d failed",
        label,
        total_successful,
        total_failed,
    )
    logger.info("─" * 70)
    manifest.record_stage_event(
        stage,
        "complete",
        f"Completed {stage} processing ({total_successful} successful, {total_failed} failed)",
    )

    return dict(successful_outputs), class_folders


def process_all_lectures(
    classes: list[Path],
    new_outputs_dir: Path,
    manifest: RunManifest,
    class_config: dict | None = None,
) -> None:
    """Process lecture transcript files for all classes."""
    successful_outputs, class_folders = _process_all_files(
        classes,
        new_outputs_dir,
        manifest,
        stage="lecture_llm",
        prompt_file=config.LECTURE_PROMPT_FILE,
        output_key="lecture_output",
        processed_key="lecture_processed_txt",
    )

    class_config = class_config or {}
    for class_name, output_files in successful_outputs.items():
        class_folder = class_folders[class_name]
        class_info = class_config.get(class_name, {})
        meeting_days = (
            class_info.get("days", []) if isinstance(class_info, dict) else []
        )
        count = append_lecture_notes(class_folder, sorted(output_files), meeting_days)
        if count:
            logger.info("✓ %s: %d lecture note(s) appended", class_name, count)
            manifest.record_stage_event(
                "notes_append",
                "success",
                f"{class_name}: {count} lecture(s)",
            )


def process_all_readings(
    classes: list[Path],
    new_outputs_dir: Path,
    manifest: RunManifest,
    class_config: dict | None = None,
) -> None:
    """Process reading files for all classes."""
    successful_outputs, class_folders = _process_all_files(
        classes,
        new_outputs_dir,
        manifest,
        stage="reading_llm",
        prompt_file=config.READING_PROMPT_FILE,
        output_key="reading_output",
        processed_key="reading_processed",
        include_word=True,
    )

    for class_name, output_files in successful_outputs.items():
        class_folder = class_folders[class_name]
        count = append_reading_notes(class_folder, sorted(output_files))
        if count:
            logger.info("✓ %s: %d reading note(s) appended", class_name, count)
            manifest.record_stage_event(
                "notes_append",
                "success",
                f"{class_name}: {count} reading(s)",
            )
