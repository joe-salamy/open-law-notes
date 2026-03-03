"""
Audio transcription using AssemblyAI.
Orchestrates transcription workflow: preprocessing, transcription, and file management.
"""

import logging
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace
from dotenv import load_dotenv

import assemblyai as aai
import soundfile as sf
from tqdm import tqdm

from .. import config
from ..utils.folder_manager import get_class_paths, get_audio_files
from ..utils.file_mover import move_audio_to_processed
from ..utils.logger_config import get_logger
from .audio_helper import (
    preprocess_audio,
    format_transcription_with_speakers,
)

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


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

        # Step 1: Preprocess audio
        logger.info(f"[PREPROCESSING START] {audio_file.name}")
        audio_data, sample_rate = preprocess_audio(audio_file)
        duration_minutes = len(audio_data) / sample_rate / 60
        logger.info(
            f"[PREPROCESSING DONE] {audio_file.name} - Audio Length: {duration_minutes:.1f} minutes"
        )

        # Save preprocessed audio to WAV file in output folder
        wav_filename = audio_file.stem + ".wav"
        wav_file_path = output_folder / wav_filename
        logger.debug(f"Saving preprocessed WAV file: {wav_filename}")
        sf.write(str(wav_file_path), audio_data, sample_rate)
        logger.debug(f"Saved preprocessed audio to {wav_filename}")

        # Step 2: Transcribe with AssemblyAI
        logger.info(f"[TRANSCRIPTION START] {audio_file.name}")

        aai.settings.api_key = config.ASSEMBLYAI_API_KEY
        transcription_config = aai.TranscriptionConfig(
            speech_model=aai.SpeechModel.best,
            language_code="en",
            speaker_labels=config.ENABLE_DIARIZATION,
            speakers_expected=config.MAX_SPEAKERS,
        )
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(
            str(wav_file_path), config=transcription_config
        )

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI transcription error: {transcript.error}")

        # Build segments list from AssemblyAI result
        if config.ENABLE_DIARIZATION:
            segments_list = [
                SimpleNamespace(
                    start=u.start / 1000.0,
                    end=u.end / 1000.0,
                    text=u.text,
                    speaker=u.speaker,
                )
                for u in transcript.utterances
            ]
        else:
            segments_list = [
                SimpleNamespace(
                    start=s.start / 1000.0,
                    end=s.end / 1000.0,
                    text=s.text,
                    speaker=None,
                )
                for s in transcript.sentences
            ]

        total_segments = len(segments_list)
        logger.info(
            f"[TRANSCRIPTION COMPLETE] {audio_file.name} - Total: {total_segments} segments"
        )

        # Step 3: Format transcription with paragraph-based timestamps
        transcription = format_transcription_with_speakers(
            segments_list,
            paragraph_gap=3.0,
            max_paragraph_duration=120.0,
            include_speakers=config.ENABLE_DIARIZATION,
        )

        paragraph_count = transcription.count("[")
        speaker_msg = " with speaker labels" if config.ENABLE_DIARIZATION else ""
        logger.info(
            f"[FORMATTING COMPLETE] {audio_file.name} - Created {paragraph_count} paragraphs from {total_segments} segments{speaker_msg}"
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

        return (
            True,
            "Successfully transcribed",
            audio_file,
            wav_file_path,
            processed_audio_folder,
            class_name,
        )

    except Exception as e:
        logger.error(f"Error transcribing {audio_file.name}: {e}", exc_info=True)
        return (
            False,
            f"Error: {str(e)}",
            audio_file,
            None,
            processed_audio_folder,
            class_name,
        )


def process_all_lectures(classes: List[Path]) -> None:
    """
    Process lecture audio files for all classes.
    Parallelizes across ALL classes using a thread pool (I/O-bound).

    Args:
        classes: List of class folder paths
    """
    logger.info(f"Using AssemblyAI transcription (Universal-2 model)")
    logger.info(f"Concurrent uploads: {config.MAX_AUDIO_WORKERS}")
    logger.info(f"Speaker diarization: {config.ENABLE_DIARIZATION}")
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
            all_task_args.append(
                (
                    audio_file,
                    paths["lecture_input"],
                    paths["lecture_processed_audio"],
                    class_name,
                )
            )

    # Log what we found
    for class_name, count in class_file_counts.items():
        logger.info(f"{class_name}: {count} audio file(s)")

    if not all_task_args:
        logger.info("No audio files found in any class")
        return

    total_files = len(all_task_args)
    logger.info(f"Total audio files to process: {total_files}")

    # Get log file path from the main logger
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

    # Process ALL files from ALL classes using ThreadPoolExecutor (I/O-bound)
    with ThreadPoolExecutor(max_workers=config.MAX_AUDIO_WORKERS) as executor:
        futures = {
            executor.submit(transcribe_single_file, args): args
            for args in all_task_args
        }

        with tqdm(
            total=total_files, desc="Transcribing (all classes)", unit="file"
        ) as pbar:
            for future in as_completed(futures):
                args = futures[future]
                audio_file = args[0]
                try:
                    (
                        success,
                        message,
                        original_file,
                        wav_file,
                        processed_audio_folder,
                        class_name,
                    ) = future.result()

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
                                logger.debug(
                                    f"WAV file moved to processed: {wav_file.name}"
                                )
                            else:
                                logger.warning(
                                    f"Failed to move WAV file: {wav_file.name}"
                                )

                        if moved and wav_moved:
                            moved_msg = "moved to processed audio"
                        elif moved:
                            moved_msg = "original moved, WAV failed"
                        else:
                            moved_msg = "failed to move audio"

                        pbar.write(
                            f"✓ [{class_name}] {original_file.name} ({moved_msg})"
                        )
                    else:
                        total_failed += 1
                        class_results[class_name]["failed"] += 1
                        logger.error(
                            f"Transcription failed for {original_file.name}: {message}"
                        )
                        pbar.write(f"✗ [{class_name}] {original_file.name}: {message}")

                except Exception as e:
                    total_failed += 1
                    class_name = args[3]
                    class_results[class_name]["failed"] += 1
                    logger.error(
                        f"Unexpected error processing {audio_file.name}: {e}",
                        exc_info=True,
                    )
                    pbar.write(
                        f"✗ [{class_name}] {audio_file.name}: Unexpected error: {e}"
                    )

                pbar.update(1)

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
        f"Transcription Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Audio transcription completed: {total_successful} successful, {total_failed} failed"
    )
