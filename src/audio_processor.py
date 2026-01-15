"""
Audio transcription using faster-whisper with CPU optimization.
Orchestrates transcription workflow: preprocessing, transcription, and file management.
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from dotenv import load_dotenv

import soundfile as sf
from faster_whisper import WhisperModel
from tqdm import tqdm

import config
from folder_manager import get_class_paths, get_audio_files
from file_mover import move_audio_to_processed
from logger_config import get_logger
from audio_helper import preprocess_audio, format_transcription_paragraphs

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


# Module-level cache for the worker process
_WORKER_MODEL = None
_LOG_FILE_PATH = None  # Store log file path for workers


def _worker_init(
    model_name: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
    log_file_path: str = None,
):
    """Initializer for worker processes: load the faster-whisper model once per worker.

    Args:
        model_name: Whisper model size (e.g., 'large-v3')
        device: 'cpu' or 'cuda'
        compute_type: 'int8' for CPU, 'float16' for GPU
        cpu_threads: Number of CPU threads to use
        log_file_path: Path to the log file (for worker logging)
    """
    global _WORKER_MODEL

    worker_logger = logging.getLogger("law_school_notes")
    worker_logger.setLevel(logging.INFO)  # Use INFO for workers to reduce clutter

    # Add handlers for worker logging
    if not worker_logger.handlers:
        # Console handler for immediate output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "[WORKER-%(process)d] %(levelname)s: %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        worker_logger.addHandler(console_handler)

        # File handler to write to the same log file as main process
        if log_file_path:
            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)  # Capture all worker details
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | [PID-%(process)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            worker_logger.addHandler(file_handler)

    try:
        # Set HuggingFace token for authenticated downloads
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            worker_logger.debug(f"HF_TOKEN configured for model download")

        worker_logger.info(
            f"Worker initializing: {model_name} on {device} with {compute_type} (this may take a minute...)"
        )
        worker_logger.info(f"Loading Whisper model...")
        _WORKER_MODEL = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
        worker_logger.info(
            f"✓ Whisper model loaded successfully in worker process {os.getpid()}"
        )
    except Exception as e:
        worker_logger.error(f"Error loading model in worker: {e}", exc_info=True)
        _WORKER_MODEL = None
        raise  # Re-raise to prevent silent failures


def transcribe_single_file(
    args: Tuple[Path, Path, Path, str],
) -> Tuple[bool, str, Path, Path | None, Path, str]:
    """
    Transcribe a single audio file with preprocessing and timestamps.

    Args:
        args: Tuple of (audio_file, output_folder, processed_audio_folder, class_name)

    Returns:
        Tuple of (success, message, audio_file, wav_file_path, processed_audio_folder, class_name)
    """
    audio_file, output_folder, processed_audio_folder, class_name = args
    wav_file_path = None

    try:
        logger.info(f"[WORKER START] Processing: {audio_file.name}")
        # Use the worker-global model
        global _WORKER_MODEL
        if _WORKER_MODEL is None:
            logger.error(f"[ERROR] Model not loaded in worker for {audio_file.name}")
            return False, "Model not loaded in worker", audio_file, None, processed_audio_folder, class_name

        logger.debug(f"[MODEL CHECK] Worker model ready for {audio_file.name}")

        # Step 1: Preprocess audio
        logger.info(f"[PREPROCESSING START] {audio_file.name}")
        audio_data, sample_rate = preprocess_audio(audio_file)
        duration_minutes = len(audio_data) / sample_rate / 60
        total_duration_seconds = len(audio_data) / sample_rate
        logger.info(
            f"[PREPROCESSING DONE] {audio_file.name} - Audio Length: {duration_minutes:.1f} minutes"
        )

        # Save preprocessed audio to permanent WAV file in input folder
        wav_filename = audio_file.stem + ".wav"
        wav_file_path = output_folder / wav_filename
        logger.debug(f"Saving preprocessed WAV file: {wav_filename}")

        # Save audio data using soundfile
        sf.write(str(wav_file_path), audio_data, sample_rate)
        logger.debug(f"Saved preprocessed audio to {wav_filename}")

        # Step 2: Transcribe with timestamps
        logger.info(
            f"[TRANSCRIPTION START] {audio_file.name} - Will take ~{(3*duration_minutes):.1f} minutes"
        )
        segments, info = _WORKER_MODEL.transcribe(
            str(wav_file_path),
            beam_size=5,
            language="en",
            word_timestamps=False,  # Use segment-level timestamps
        )

        # Process segments as they're generated (this is the bottleneck)
        start_time = time.time()
        segments_list = []
        segment_count = 0
        last_segment_end = 0.0  # Track audio time processed (in seconds)
        for segment in segments:
            segments_list.append(segment)
            segment_count += 1
            last_segment_end = segment.end  # Update audio time processed

            # Log progress every 25 segments
            if segment_count % 25 == 0:
                elapsed_time = time.time() - start_time
                percent_complete = (last_segment_end / total_duration_seconds) * 100

                # Calculate ETA based on audio processed
                if last_segment_end > 0:
                    estimated_total_time = elapsed_time / (
                        last_segment_end / total_duration_seconds
                    )
                    eta_seconds = estimated_total_time - elapsed_time
                    eta_minutes = eta_seconds / 60

                    # Calculate actual ETA time
                    eta_time = datetime.now() + timedelta(seconds=eta_seconds)
                    eta_time_str = eta_time.strftime("%I:%M %p")

                    logger.info(
                        f"[PROGRESS] {audio_file.name} - {segment_count} segments | "
                        f"{percent_complete:.1f}% audio processed | "
                        f"Elapsed: {elapsed_time/60:.1f} min | Time remaining: {eta_minutes:.1f} min | ETA: {eta_time_str}"
                    )
                else:
                    logger.info(
                        f"[PROGRESS] {audio_file.name} - {segment_count} segments | "
                        f"Elapsed: {elapsed_time/60:.1f} min"
                    )

        total_segments = len(segments_list)
        elapsed_time = time.time() - start_time
        logger.info(
            f"[TRANSCRIPTION COMPLETE] {audio_file.name} - Total: {total_segments} segments in {elapsed_time/60:.1f} min"
        )

        # Step 3: Format transcription with paragraph-based timestamps (token-efficient)
        transcription = format_transcription_paragraphs(
            segments_list,
            paragraph_gap=3.0,  # Start new paragraph after 3+ seconds of silence
            max_paragraph_duration=120.0,  # Max 2 minutes per paragraph
        )

        # Count paragraphs for logging
        paragraph_count = transcription.count("[")
        logger.info(
            f"[FORMATTING COMPLETE] {audio_file.name} - Created {paragraph_count} paragraphs from {total_segments} segments"
        )
        logger.info(
            f"Token reduction: ~{((total_segments - paragraph_count) / total_segments * 100):.0f}% fewer timestamps"
        )

        # Step 4: Save to txt file
        txt_filename = audio_file.stem + ".txt"
        txt_output_path = output_folder / txt_filename
        logger.info(
            f"[SAVING] {audio_file.name} - Writing transcript to {txt_filename}"
        )

        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        logger.info(f"[SAVE COMPLETE] {txt_filename}")
        logger.info(f"[WORKER COMPLETE] ✓ Successfully transcribed: {audio_file.name}")
        logger.info(f"Preprocessed WAV saved as: {wav_filename}")
        return True, "Successfully transcribed", audio_file, wav_file_path, processed_audio_folder, class_name

    except Exception as e:
        logger.error(f"Error transcribing {audio_file.name}: {e}", exc_info=True)
        return False, f"Error: {str(e)}", audio_file, None, processed_audio_folder, class_name


def process_class_lectures(
    class_folder: Path,
    model_name: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
) -> Tuple[int, int]:
    """
    Process all lecture audio files for a single class.

    Args:
        class_folder: Path to the class root folder
        model_name: Whisper model to use
        device: 'cpu' or 'cuda'
        compute_type: 'int8' for CPU, 'float16' for GPU
        cpu_threads: Number of CPU threads to use

    Returns:
        Tuple of (successful_count, failed_count)
    """
    paths = get_class_paths(class_folder)
    class_name = paths["class_name"]

    audio_files = get_audio_files(class_folder)

    if not audio_files:
        logger.info(f"No audio files found")
        logger.debug(f"No audio files in {paths['lecture_input']}")
        return 0, 0

    logger.info(f"Found {len(audio_files)} audio file(s)")
    logger.debug(f"Audio files: {[f.name for f in audio_files]}")

    # Prepare arguments for parallel processing
    task_args = [(audio_file, paths["lecture_input"]) for audio_file in audio_files]

    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel transcription with {config.MAX_AUDIO_WORKERS} workers"
    )

    # Get log file path from the main logger to pass to workers
    log_file_path = None
    main_logger = logging.getLogger("law_school_notes")
    for handler in main_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            log_file_path = handler.baseFilename
            break

    # Log explanation (progress bar only updates when files complete)
    logger.info(
        f"Note: Progress bar updates when files complete. Watch log file for detailed progress."
    )
    if log_file_path:
        logger.info(f"Monitor with: Get-Content '{log_file_path}' -Wait -Tail 50")

    # Process files in parallel with progress bar
    with ProcessPoolExecutor(
        max_workers=config.MAX_AUDIO_WORKERS,
        initializer=_worker_init,
        initargs=(model_name, device, compute_type, cpu_threads, log_file_path),
    ) as executor:
        futures = {
            executor.submit(transcribe_single_file, args): args[0] for args in task_args
        }

        # Progress bar for transcription
        with tqdm(total=len(audio_files), desc="Transcribing", unit="file") as pbar:
            for future in as_completed(futures):
                audio_file = futures[future]
                try:
                    success, message, original_file, wav_file = future.result()

                    if success:
                        successful += 1
                        logger.debug(f"Transcription successful: {original_file.name}")
                        # Move the original audio file to the processed audio folder
                        moved = move_audio_to_processed(
                            original_file, paths["lecture_processed_audio"]
                        )

                        # Move the WAV file to the processed audio folder
                        wav_moved = False
                        if wav_file and wav_file.exists():
                            wav_moved = move_audio_to_processed(
                                wav_file, paths["lecture_processed_audio"]
                            )
                            if wav_moved:
                                logger.debug(
                                    f"WAV file moved to processed: {wav_file.name}"
                                )
                            else:
                                logger.warning(
                                    f"Failed to move WAV file: {wav_file.name}"
                                )

                        if moved and wav_moved:
                            moved_msg = "moved to processed audio"
                            logger.debug(
                                f"Audio files moved to processed: {original_file.name}, {wav_file.name}"
                            )
                        elif moved:
                            moved_msg = "original moved, WAV failed"
                            logger.warning(
                                f"Only original audio moved: {original_file.name}"
                            )
                        else:
                            moved_msg = "failed to move audio"
                            logger.warning(
                                f"Failed to move audio file: {original_file.name}"
                            )

                        pbar.write(f"✓ {original_file.name} (d{moved_msg})")
                    else:
                        failed += 1
                        logger.error(
                            f"Transcription failed for {original_file.name}: {message}"
                        )
                        pbar.write(f"✗ {original_file.name}: {message}")

                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Unexpected error processing {audio_file.name}: {e}",
                        exc_info=True,
                    )
                    pbar.write(f"✗ {audio_file.name}: Unexpected error: {e}")

                pbar.update(1)

    logger.debug(
        f"Class transcription complete: {successful} successful, {failed} failed"
    )
    return successful, failed


def process_all_lectures(classes: List[Path]) -> None:
    """
    Process lecture audio files for all classes with CPU-optimized settings.
    Parallelizes across ALL classes, not just within each class.

    Args:
        classes: List of class folder paths
    """
    # CPU-optimized configuration (per instructions)
    device = "cpu"
    compute_type = "int8"  # Faster CPU inference with minimal accuracy loss
    cpu_threads = 4  # Safe limit to avoid overheating/crashing
    model_name = "large-v3"  # Most accurate Whisper model

    logger.info(f"Using faster-whisper model: {model_name}")
    logger.info(f"Device: {device} (compute_type: {compute_type})")
    logger.info(f"CPU threads: {cpu_threads}")
    logger.info(f"Parallel workers: {config.MAX_AUDIO_WORKERS}")
    logger.debug(f"Processing {len(classes)} classes for audio transcription")

    # Collect all audio files from all classes
    all_task_args = []
    class_file_counts = {}

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]
        audio_files = get_audio_files(class_folder)

        class_file_counts[class_name] = len(audio_files)

        for audio_file in audio_files:
            # Include processed_audio_folder and class_name for post-processing
            all_task_args.append((
                audio_file,
                paths["lecture_input"],
                paths["lecture_processed_audio"],
                class_name
            ))

    # Log what we found
    for class_name, count in class_file_counts.items():
        logger.info(f"{class_name}: {count} audio file(s)")

    if not all_task_args:
        logger.info("No audio files found in any class")
        return

    total_files = len(all_task_args)
    logger.info(f"Total audio files to process: {total_files}")

    # Get log file path from the main logger to pass to workers
    log_file_path = None
    main_logger = logging.getLogger("law_school_notes")
    for handler in main_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            log_file_path = handler.baseFilename
            break

    logger.info(
        f"Note: Progress bar updates when files complete. Watch log file for detailed progress."
    )
    if log_file_path:
        logger.info(f"Monitor with: Get-Content '{log_file_path}' -Wait -Tail 50")

    # Track results by class
    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

    # Process ALL files from ALL classes in a single pool
    with ProcessPoolExecutor(
        max_workers=config.MAX_AUDIO_WORKERS,
        initializer=_worker_init,
        initargs=(model_name, device, compute_type, cpu_threads, log_file_path),
    ) as executor:
        futures = {
            executor.submit(transcribe_single_file, args): args for args in all_task_args
        }

        with tqdm(total=total_files, desc="Transcribing (all classes)", unit="file") as pbar:
            for future in as_completed(futures):
                args = futures[future]
                audio_file = args[0]
                try:
                    success, message, original_file, wav_file, processed_audio_folder, class_name = future.result()

                    if success:
                        total_successful += 1
                        class_results[class_name]["successful"] += 1
                        logger.debug(f"Transcription successful: {original_file.name}")

                        # Move the original audio file to the processed audio folder
                        moved = move_audio_to_processed(
                            original_file, processed_audio_folder
                        )

                        # Move the WAV file to the processed audio folder
                        wav_moved = False
                        if wav_file and wav_file.exists():
                            wav_moved = move_audio_to_processed(
                                wav_file, processed_audio_folder
                            )
                            if wav_moved:
                                logger.debug(f"WAV file moved to processed: {wav_file.name}")
                            else:
                                logger.warning(f"Failed to move WAV file: {wav_file.name}")

                        if moved and wav_moved:
                            moved_msg = "moved to processed audio"
                        elif moved:
                            moved_msg = "original moved, WAV failed"
                        else:
                            moved_msg = "failed to move audio"

                        pbar.write(f"✓ [{class_name}] {original_file.name} ({moved_msg})")
                    else:
                        total_failed += 1
                        class_results[class_name]["failed"] += 1
                        logger.error(f"Transcription failed for {original_file.name}: {message}")
                        pbar.write(f"✗ [{class_name}] {original_file.name}: {message}")

                except Exception as e:
                    total_failed += 1
                    # Extract class_name from args
                    class_name = args[3]
                    class_results[class_name]["failed"] += 1
                    logger.error(
                        f"Unexpected error processing {audio_file.name}: {e}",
                        exc_info=True,
                    )
                    pbar.write(f"✗ [{class_name}] {audio_file.name}: Unexpected error: {e}")

                pbar.update(1)

    # Print per-class summary
    logger.info("─" * 70)
    logger.info("Per-class summary:")
    for class_name, results in class_results.items():
        if results["successful"] > 0 or results["failed"] > 0:
            logger.info(f"  {class_name}: {results['successful']} successful, {results['failed']} failed")

    logger.info("─" * 70)
    logger.info(
        f"Transcription Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Audio transcription completed: {total_successful} successful, {total_failed} failed"
    )
