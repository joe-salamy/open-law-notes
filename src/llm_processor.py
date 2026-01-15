"""
LLM processing using Gemini with multithreading.
Generates notes from lecture transcripts and reading texts.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import google.generativeai as genai
from dotenv import load_dotenv

import config
from folder_manager import get_class_paths, get_text_files, get_pdf_files
from file_mover import move_to_processed, copy_to_new_outputs
from logger_config import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
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
    """
    Load system prompt from prompts folder and substitute class name.

    Args:
        prompt_file: Name of the prompt file to load
        class_name: Name of the class for context
    """
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


def process_with_gemini(
    model: genai.GenerativeModel, content: str, max_retries: int = 3
) -> Optional[str]:
    """
    Send content to Gemini using a pre-created `GenerativeModel` and return the response.

    This function includes a small retry/backoff loop to handle transient API errors.

    Args:
        model: Pre-configured genai.GenerativeModel instance (created once per class)
        content: Text content to process
        max_retries: Number of attempts (default 3)

    Returns:
        Generated text or None if error
    """
    logger.debug(f"Processing content with Gemini ({len(content)} characters)")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Gemini API call attempt {attempt}/{max_retries}")
            response = model.generate_content(content)
            logger.debug(f"Gemini response received ({len(response.text)} characters)")
            return response.text
        except Exception as e:
            # Simple exponential backoff for transient failures
            if attempt == max_retries:
                logger.error(
                    f"Gemini API error after {max_retries} attempts: {e}", exc_info=True
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"Gemini API error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
            time.sleep(backoff)
            continue


def upload_pdf_to_gemini(
    filepath: Path, max_retries: int = 3
) -> Optional[genai.types.File]:
    """
    Upload a PDF file to Gemini and return the file object.

    Args:
        filepath: Path to the PDF file
        max_retries: Number of upload attempts

    Returns:
        Gemini File object or None if upload failed
    """
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
            continue


def process_pdf_with_gemini(
    model: genai.GenerativeModel,
    uploaded_file: genai.types.File,
    prompt: str = "Process this PDF document.",
    max_retries: int = 3,
) -> Optional[str]:
    """
    Process an uploaded PDF with Gemini.

    Args:
        model: Pre-configured GenerativeModel instance
        uploaded_file: Gemini File object from upload_pdf_to_gemini
        prompt: Text prompt to accompany the PDF
        max_retries: Number of attempts

    Returns:
        Generated text or None if error
    """
    logger.debug(f"Processing PDF with Gemini: {uploaded_file.name}")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Gemini API call attempt {attempt}/{max_retries}")
            response = model.generate_content([prompt, uploaded_file])
            logger.debug(f"Gemini response received ({len(response.text)} characters)")
            return response.text
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    f"Gemini API error after {max_retries} attempts: {e}", exc_info=True
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"Gemini API error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
            time.sleep(backoff)
            continue


def process_single_pdf(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path],
) -> Tuple[bool, str, Path]:
    """
    Process a single PDF file with Gemini.

    Args:
        args: Tuple of (input_file, model, output_folder, processed_folder, new_outputs_dir)

    Returns:
        Tuple of (success, message, input_file)
    """
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
    ) = args

    try:
        logger.debug(f"Processing PDF file: {input_file.name}")

        # Upload PDF to Gemini
        uploaded_file = upload_pdf_to_gemini(input_file)
        if uploaded_file is None:
            logger.error(f"Failed to upload PDF: {input_file.name}")
            return False, "Failed to upload PDF", input_file

        # Process with Gemini using the uploaded file
        logger.debug(f"Sending PDF to Gemini: {input_file.name}")
        result = process_pdf_with_gemini(
            model, uploaded_file, "Process this reading material."
        )
        if result is None:
            logger.error(f"Gemini API error for PDF: {input_file.name}")
            return False, "Gemini API error", input_file

        # Save output markdown
        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        # Copy to new-outputs-safe-delete
        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        # Move input to processed
        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        # Clean up uploaded file from Gemini
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


def process_single_file(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool],
) -> Tuple[bool, str, Path]:
    """
    Process a single text file with Gemini.

    Args:
        args: Tuple of (input_file, model, output_folder, processed_folder,
                       new_outputs_dir, is_reading)

    Returns:
        Tuple of (success, message, input_file)
    """
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
        is_reading,
    ) = args

    try:
        logger.debug(f"Processing file: {input_file.name}")
        # Read input file
        content = read_file(input_file)
        if content is None:
            logger.error(f"Failed to read file: {input_file.name}")
            return False, "Failed to read file", input_file

        # Process with Gemini using the shared per-class model
        logger.debug(f"Sending to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)
        if result is None:
            logger.error(f"Gemini API error for file: {input_file.name}")
            return False, "Gemini API error", input_file

        # Save output markdown
        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        # Copy to new-outputs-safe-delete
        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        # Move input to processed
        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except Exception as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
        return False, f"Error: {str(e)}", input_file


def execute_parallel_processing(
    task_args: List[Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool]],
    total_files: int,
) -> Tuple[int, int]:
    """
    Execute parallel processing of text files using ThreadPoolExecutor.

    Args:
        task_args: List of argument tuples for process_single_file
        total_files: Total number of files to process

    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel processing of {total_files} text files with {config.MAX_LLM_WORKERS} workers"
    )
    # Process files in parallel with threads (I/O bound)
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
    """
    Execute parallel processing of PDF files using ThreadPoolExecutor.

    Args:
        task_args: List of argument tuples for process_single_pdf
        total_files: Total number of PDF files to process

    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel processing of {total_files} PDF files with {config.MAX_LLM_WORKERS} workers"
    )
    # Process files in parallel with threads (I/O bound)
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


def process_class_files(
    class_folder: Path, is_reading: bool, new_outputs_dir: Path, api_key: str
) -> Tuple[int, int]:
    """
    Process all files (reading or lecture) for a single class.
    Handles text files (txt, md) and PDF files.

    Args:
        class_folder: Path to the class root folder
        is_reading: True for reading files, False for lecture files
        new_outputs_dir: Path to new-outputs-safe-delete directory
        api_key: Gemini API key

    Returns:
        Tuple of (successful_count, failed_count)
    """
    paths = get_class_paths(class_folder)
    class_name = paths["class_name"]

    # Get appropriate folders and files
    if is_reading:
        text_files = get_text_files(class_folder, reading=True)
        pdf_files = get_pdf_files(class_folder, reading=True)
        output_folder = paths["reading_output"]
        processed_folder = paths["reading_processed"]
        prompt_file = config.READING_PROMPT_FILE
        file_type = "reading"
    else:
        text_files = get_text_files(class_folder, reading=False)
        pdf_files = get_pdf_files(class_folder, reading=False)
        output_folder = paths["lecture_output"]
        processed_folder = paths["lecture_processed_txt"]
        prompt_file = config.LECTURE_PROMPT_FILE
        file_type = "lecture transcript"

    logger.debug(f"Processing {file_type} files for {class_name}")

    total_files = len(text_files) + len(pdf_files)
    if total_files == 0:
        logger.info(f"No {file_type} files found")
        return 0, 0

    logger.info(
        f"Found {total_files} {file_type} file(s) ({len(text_files)} text, {len(pdf_files)} PDF)"
    )
    logger.debug(f"{file_type} text files: {[f.name for f in text_files]}")
    logger.debug(f"{file_type} PDF files: {[f.name for f in pdf_files]}")

    # Load system prompt
    try:
        # Get class name from the folder path
        logger.debug(f"Loading system prompt for {class_name}")
        system_prompt = load_system_prompt(prompt_file, class_name)
        if system_prompt is None:
            logger.error(f"Error loading prompt for {class_name}")
            logger.info(f"✗ Error loading prompt")
            return 0, total_files
    except Exception as e:
        logger.error(f"Error loading prompt for {class_name}: {e}", exc_info=True)
        logger.info(f"✗ Error loading prompt: {e}")
        return 0, total_files

    # Configure API and create a single GenerativeModel for this class.
    # Calling genai.configure once and reusing a model instance reduces per-task overhead.
    logger.debug(f"Configuring Gemini API for {class_name}")
    genai.configure(api_key=api_key)
    try:
        logger.debug(f"Creating GenerativeModel: {config.GEMINI_MODEL}")
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                temperature=config.GEMINI_TEMPERATURE,
            ),
        )
        logger.debug(f"GenerativeModel created successfully")
    except Exception as e:
        logger.error(
            f"Error creating GenerativeModel for {class_name}: {e}", exc_info=True
        )
        logger.info(f"✗ Error creating GenerativeModel: {e}")
        return 0, total_files

    total_successful = 0
    total_failed = 0

    # Process text files (txt, md)
    if text_files:
        logger.debug(f"Processing {len(text_files)} text files for {class_name}")
        text_task_args = [
            (
                text_file,
                model,
                output_folder,
                processed_folder,
                new_outputs_dir,
                is_reading,
            )
            for text_file in text_files
        ]
        successful, failed = execute_parallel_processing(
            text_task_args, len(text_files)
        )
        total_successful += successful
        total_failed += failed

    # Process PDF files
    if pdf_files:
        logger.debug(f"Processing {len(pdf_files)} PDF files for {class_name}")
        pdf_task_args = [
            (
                pdf_file,
                model,
                output_folder,
                processed_folder,
                new_outputs_dir,
            )
            for pdf_file in pdf_files
        ]
        successful, failed = execute_parallel_pdf_processing(
            pdf_task_args, len(pdf_files)
        )
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

    # Configure API once
    genai.configure(api_key=api_key)

    # Collect all files and create models for each class
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

        # Create model for this class
        try:
            system_prompt = load_system_prompt(config.LECTURE_PROMPT_FILE, class_name)
            if system_prompt is None:
                logger.error(f"Error loading prompt for {class_name}")
                continue
            model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            logger.error(f"Error creating model for {class_name}: {e}", exc_info=True)
            continue

        # Add text file tasks
        for text_file in text_files:
            all_text_task_args.append(
                (
                    text_file,
                    model,
                    paths["lecture_output"],
                    paths["lecture_processed_txt"],
                    new_outputs_dir,
                    False,  # is_reading
                    class_name,  # for tracking
                )
            )

        # Add PDF file tasks
        for pdf_file in pdf_files:
            all_pdf_task_args.append(
                (
                    pdf_file,
                    model,
                    paths["lecture_output"],
                    paths["lecture_processed_txt"],
                    new_outputs_dir,
                    class_name,  # for tracking
                )
            )

    total_files = len(all_text_task_args) + len(all_pdf_task_args)
    if total_files == 0:
        logger.info("No lecture transcript files found in any class")
        return

    logger.info(f"Total lecture files to process: {total_files}")

    # Track results by class
    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    # Process ALL files from ALL classes in a single thread pool
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        # Submit text file tasks
        text_futures = {
            executor.submit(process_single_file, args[:6]): args
            for args in all_text_task_args
        }
        # Submit PDF file tasks
        pdf_futures = {
            executor.submit(process_single_pdf, args[:5]): args
            for args in all_pdf_task_args
        }

        all_futures = {**text_futures, **pdf_futures}

        for future in as_completed(all_futures):
            args = all_futures[future]
            input_file = args[0]
            class_name = args[-1]  # Last element is class_name

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

    # Print per-class summary
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

    # Configure API once
    genai.configure(api_key=api_key)

    # Collect all files and create models for each class
    all_text_task_args = []
    all_pdf_task_args = []
    class_file_counts = {}

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]

        text_files = get_text_files(class_folder, reading=True)
        pdf_files = get_pdf_files(class_folder, reading=True)
        class_file_counts[class_name] = len(text_files) + len(pdf_files)

        if not text_files and not pdf_files:
            logger.info(f"{class_name}: No reading files found")
            continue

        logger.info(
            f"{class_name}: {len(text_files)} text, {len(pdf_files)} PDF file(s)"
        )

        # Create model for this class
        try:
            system_prompt = load_system_prompt(config.READING_PROMPT_FILE, class_name)
            if system_prompt is None:
                logger.error(f"Error loading prompt for {class_name}")
                continue
            model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            logger.error(f"Error creating model for {class_name}: {e}", exc_info=True)
            continue

        # Add text file tasks
        for text_file in text_files:
            all_text_task_args.append(
                (
                    text_file,
                    model,
                    paths["reading_output"],
                    paths["reading_processed"],
                    new_outputs_dir,
                    True,  # is_reading
                    class_name,  # for tracking
                )
            )

        # Add PDF file tasks
        for pdf_file in pdf_files:
            all_pdf_task_args.append(
                (
                    pdf_file,
                    model,
                    paths["reading_output"],
                    paths["reading_processed"],
                    new_outputs_dir,
                    class_name,  # for tracking
                )
            )

    total_files = len(all_text_task_args) + len(all_pdf_task_args)
    if total_files == 0:
        logger.info("No reading files found in any class")
        return

    logger.info(f"Total reading files to process: {total_files}")

    # Track results by class
    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    # Process ALL files from ALL classes in a single thread pool
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        # Submit text file tasks
        text_futures = {
            executor.submit(process_single_file, args[:6]): args
            for args in all_text_task_args
        }
        # Submit PDF file tasks
        pdf_futures = {
            executor.submit(process_single_pdf, args[:5]): args
            for args in all_pdf_task_args
        }

        all_futures = {**text_futures, **pdf_futures}

        for future in as_completed(all_futures):
            args = all_futures[future]
            input_file = args[0]
            class_name = args[-1]  # Last element is class_name

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

    # Print per-class summary
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
