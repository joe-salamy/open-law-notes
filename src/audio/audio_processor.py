"""
Audio transcription using AssemblyAI.
Orchestrates transcription workflow: preprocessing, transcription, and file management.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from typing import List, Tuple

import assemblyai as aai
import soundfile as sf
from tqdm import tqdm

import config
from ..utils.errors import FileProcessingError, RetryableServiceError
from ..utils.file_mover import move_audio_to_processed
from ..utils.folder_manager import get_audio_files, get_class_paths
from ..utils.logger_config import get_logger
from ..utils.run_manifest import RunManifest
from .audio_helper import format_transcription_with_speakers, preprocess_audio

logger = get_logger(__name__)


def _transcribe_with_retries(
    wav_file_path: Path, max_retries: int = 3
) -> aai.Transcript:
    aai.settings.api_key = config.ASSEMBLYAI_API_KEY
    transcription_config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        language_code="en",
        speaker_labels=config.ENABLE_DIARIZATION,
        speakers_expected=config.MAX_SPEAKERS,
    )
    transcriber = aai.Transcriber()

    for attempt in range(1, max_retries + 1):
        try:
            transcript = transcriber.transcribe(
                str(wav_file_path), config=transcription_config
            )
            if transcript.status == aai.TranscriptStatus.error:
                text = (transcript.error or "").lower()
                retryable = any(
                    token in text
                    for token in ("rate", "timeout", "temporar", "429", "503")
                )
                if retryable and attempt < max_retries:
                    backoff = 2 ** (attempt - 1)
                    logger.warning(
                        f"AssemblyAI transient error on attempt {attempt}, retrying in {backoff}s: {transcript.error}"
                    )
                    time.sleep(backoff)
                    continue
                if retryable:
                    raise RetryableServiceError(
                        f"AssemblyAI transcription failed after {max_retries} attempts: {transcript.error}"
                    )
                raise FileProcessingError(
                    f"AssemblyAI transcription error: {transcript.error}"
                )
            return transcript
        except (TimeoutError, ConnectionError) as error:
            if attempt == max_retries:
                raise RetryableServiceError(
                    f"AssemblyAI request failed after {max_retries} retries: {error}"
                ) from error
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"AssemblyAI connection error on attempt {attempt}, retrying in {backoff}s: {error}"
            )
            time.sleep(backoff)

    raise RetryableServiceError(
        "AssemblyAI transcription failed without a terminal result"
    )


def transcribe_single_file(
    args: Tuple[Path, Path, Path, str, RunManifest],
) -> Tuple[bool, str, Path, Path | None, Path, str]:
    """
    Transcribe a single audio file with preprocessing and timestamps.

    Args:
        args: Tuple of (audio_file, output_folder, processed_audio_folder, class_name, manifest)

    Returns:
        Tuple of (success, message, audio_file, wav_file_path, processed_audio_folder, class_name)
    """
    audio_file, output_folder, processed_audio_folder, class_name, manifest = args
    wav_file_path = None
    txt_output_path = output_folder / f"{audio_file.stem}.txt"

    try:
        logger.info(f"[WORKER START] Processing: {audio_file.name}")

        if txt_output_path.exists() and txt_output_path.stat().st_size > 0:
            logger.info(f"[SKIP] Existing transcript found: {txt_output_path.name}")
            move_audio_to_processed(audio_file, processed_audio_folder)
            manifest.record_file_result(
                stage="audio_transcription",
                class_name=class_name,
                input_file=audio_file,
                status="skipped",
                output_files=[txt_output_path],
                message="Resumed from existing transcript",
            )
            return (
                True,
                "Skipped (already transcribed)",
                audio_file,
                None,
                processed_audio_folder,
                class_name,
            )

        logger.info(f"[PREPROCESSING START] {audio_file.name}")
        audio_data, sample_rate = preprocess_audio(audio_file)
        duration_minutes = len(audio_data) / sample_rate / 60
        logger.info(
            f"[PREPROCESSING DONE] {audio_file.name} - Audio Length: {duration_minutes:.1f} minutes"
        )

        wav_filename = f"{audio_file.stem}__preprocessed.wav"
        wav_file_path = output_folder / wav_filename
        logger.debug(f"Saving preprocessed WAV file: {wav_filename}")
        sf.write(str(wav_file_path), audio_data, sample_rate)

        logger.info(f"[TRANSCRIPTION START] {audio_file.name}")
        transcript = _transcribe_with_retries(wav_file_path, max_retries=3)

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

        transcription = format_transcription_with_speakers(
            segments_list,
            paragraph_gap=3.0,
            max_paragraph_duration=120.0,
            include_speakers=config.ENABLE_DIARIZATION,
        )

        with open(txt_output_path, "w", encoding="utf-8") as handle:
            handle.write(transcription)

        manifest.record_file_result(
            stage="audio_transcription",
            class_name=class_name,
            input_file=audio_file,
            status="success",
            output_files=[txt_output_path, wav_file_path],
        )

        logger.info(f"[WORKER COMPLETE] ✓ Successfully transcribed: {audio_file.name}")
        return (
            True,
            "Successfully transcribed",
            audio_file,
            wav_file_path,
            processed_audio_folder,
            class_name,
        )

    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        RetryableServiceError,
        FileProcessingError,
    ) as error:
        logger.error(f"Error transcribing {audio_file.name}: {error}", exc_info=True)
        manifest.record_file_result(
            stage="audio_transcription",
            class_name=class_name,
            input_file=audio_file,
            status="failed",
            message=str(error),
            error_type=type(error).__name__,
        )
        return (
            False,
            f"Error: {error}",
            audio_file,
            None,
            processed_audio_folder,
            class_name,
        )


def process_all_lectures(classes: List[Path], manifest: RunManifest) -> None:
    """
    Process lecture audio files for all classes.
    Parallelizes across ALL classes using a thread pool (I/O-bound).

    Args:
        classes: List of class folder paths
    """
    logger.info("Using AssemblyAI transcription (Universal-2 model)")
    logger.info(f"Concurrent uploads: {config.MAX_AUDIO_WORKERS}")
    logger.info(f"Speaker diarization: {config.ENABLE_DIARIZATION}")
    manifest.record_stage_event(
        "audio_transcription", "start", "Starting audio transcription"
    )

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
                    manifest,
                )
            )

    for class_name, count in class_file_counts.items():
        logger.info(f"{class_name}: {count} audio file(s)")

    if not all_task_args:
        logger.info("No audio files found in any class")
        manifest.record_stage_event(
            "audio_transcription", "complete", "No audio files to process"
        )
        return

    total_files = len(all_task_args)
    logger.info(f"Total audio files to process: {total_files}")

    log_file_path = None
    main_logger = logging.getLogger("law_school_notes")
    for handler in main_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            log_file_path = handler.baseFilename
            break

    if log_file_path:
        logger.info(f"Monitor with: Get-Content '{log_file_path}' -Wait -Tail 50")

    class_results = {name: {"successful": 0, "failed": 0} for name in class_file_counts}
    total_successful = 0
    total_failed = 0

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
                class_name = args[3]

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

                        moved_original = move_audio_to_processed(
                            original_file, processed_audio_folder
                        )
                        moved_wav = True
                        if wav_file and wav_file.exists():
                            moved_wav = move_audio_to_processed(
                                wav_file, processed_audio_folder
                            )

                        if moved_original and moved_wav:
                            moved_msg = "moved to processed audio"
                        elif moved_original:
                            moved_msg = "original moved, WAV failed"
                        else:
                            moved_msg = "failed to move audio"
                        pbar.write(
                            f"✓ [{class_name}] {original_file.name} ({moved_msg})"
                        )
                    else:
                        total_failed += 1
                        class_results[class_name]["failed"] += 1
                        pbar.write(f"✗ [{class_name}] {original_file.name}: {message}")

                except (RuntimeError, OSError, ValueError, TypeError) as error:
                    total_failed += 1
                    class_results[class_name]["failed"] += 1
                    logger.error(
                        f"Unexpected error processing {audio_file.name}: {error}",
                        exc_info=True,
                    )
                    manifest.record_file_result(
                        stage="audio_transcription",
                        class_name=class_name,
                        input_file=audio_file,
                        status="failed",
                        message=str(error),
                        error_type=type(error).__name__,
                    )
                    pbar.write(
                        f"✗ [{class_name}] {audio_file.name}: Unexpected error: {error}"
                    )

                pbar.update(1)

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
    manifest.record_stage_event(
        "audio_transcription",
        "complete",
        f"Completed audio transcription ({total_successful} successful, {total_failed} failed)",
    )
