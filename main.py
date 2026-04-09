"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
import argparse
from collections.abc import Callable
from pathlib import Path

from config import CLASSES, PARENT_FOLDER, ENABLE_GOOGLE_DRIVE
from src.utils.folder_manager import verify_and_create_folders
from src.utils.file_mover import setup_output_directory
from src.utils.run_manifest import RunManifest
from src.utils.logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)

BANNER_WIDTH = 70


def _log_banner(title: str) -> None:
    logger.info("=" * BANNER_WIDTH)
    logger.info(title)
    logger.info("=" * BANNER_WIDTH)


def _run_stage(
    manifest: RunManifest,
    stage_name: str,
    label: str,
    step: int,
    fn: Callable[[], None],
) -> None:
    """Run a pipeline stage with standard logging and error handling."""
    _log_banner("STEP %d: %s" % (step, label))
    try:
        fn()
    except Exception as e:
        manifest.record_stage_event(stage_name, "error", "%s failed: %s" % (label, e))
        logger.error("✗ Error in %s: %s", label, e, exc_info=True)
        manifest.finalize()
        sys.exit(1)


def main() -> None:
    """Main entry point for the law school note generator."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Law School Note Generator - Process lecture audio and reading files"
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Only process readings (skip audio processing and Google Drive operations)",
    )
    args = parser.parse_args()
    reading_only_mode = args.read_only

    # Lazy-load heavy submodules after argparse
    from src.llm.llm_processor import process_all_readings, process_all_lectures

    if not reading_only_mode:
        from src.audio.audio_processor import process_all_lectures as process_audio
        from src.audio.drive_downloader import download_from_drive

    # Initialize logging first
    setup_logging()

    class_paths = [Path(PARENT_FOLDER) / name for name in CLASSES]

    manifest = RunManifest(project_root=Path(__file__).resolve().parent)
    manifest.record_stage_event("pipeline", "start", "Pipeline run started")

    _log_banner("LAW SCHOOL NOTE GENERATOR")
    if reading_only_mode:
        logger.info("*** READING-ONLY MODE ENABLED ***")
    logger.debug("Processing %d classes", len(class_paths))

    # Setup new-outputs-safe-delete directory
    try:
        logger.debug("Setting up output directory")
        output_dir = setup_output_directory()
        logger.info("✓ Output directory ready: %s", output_dir)
    except Exception as e:
        manifest.record_stage_event(
            "pipeline", "error", "Output directory setup failed: %s" % e
        )
        logger.error("✗ Error setting up output directory: %s", e, exc_info=True)
        manifest.finalize()
        sys.exit(1)

    # Download files from Google Drive
    if not reading_only_mode and ENABLE_GOOGLE_DRIVE:
        _log_banner("STEP 0: Downloading Files from Google Drive")
        try:
            logger.debug("Starting Google Drive download")
            download_results = download_from_drive(CLASSES, Path(PARENT_FOLDER))
            total_files = sum(download_results.values())
            logger.info("✓ Downloaded %d file(s) from Google Drive", total_files)
            for class_name, count in download_results.items():
                logger.debug("%s: %d file(s)", class_name, count)
        except FileNotFoundError as e:
            logger.warning("⚠ Google Drive download skipped: %s", e)
            logger.info("Continuing with local files...")
        except Exception as e:
            manifest.record_stage_event("google_drive", "error", "Download error: %s" % e)
            logger.error("✗ Error downloading from Google Drive: %s", e, exc_info=True)
            logger.info("Continuing with local files...")
    else:
        if reading_only_mode:
            _log_banner("STEP 0: Skipped (reading-only mode)")
        else:
            _log_banner("STEP 0: Skipped (Google Drive disabled)")

    # Verify all class folders have correct structure
    _log_banner("STEP 1: Verifying Folder Structure")

    for class_folder in class_paths:
        class_name = class_folder.name
        logger.info("Verifying: %s", class_name)
        logger.debug("Class folder path: %s", class_folder)
        try:
            verify_and_create_folders(class_folder)
            logger.info("✓ Folder structure verified")
            logger.info("─" * BANNER_WIDTH)
        except Exception as e:
            manifest.record_stage_event(
                "folder_verification", "error", "Folder verification failed: %s" % e
            )
            logger.error("✗ Error: %s", e, exc_info=True)
            manifest.finalize()
            sys.exit(1)

    # Process lecture audio files to transcripts
    if not reading_only_mode:
        _run_stage(
            manifest, "audio_transcription", "Converting Lecture Audio to Text", 2,
            lambda: process_audio(class_paths, manifest),
        )
    else:
        _log_banner("STEP 2: Skipped (Reading-only mode)")

    # Process lecture transcripts with LLM
    if not reading_only_mode:
        _run_stage(
            manifest, "lecture_llm", "Generating Lecture Notes with LLM", 3,
            lambda: process_all_lectures(class_paths, output_dir, manifest, class_config=CLASSES),
        )
    else:
        _log_banner("STEP 3: Skipped (Reading-only mode)")

    # Process reading files with LLM
    _run_stage(
        manifest, "reading_llm", "Generating Reading Notes with LLM", 4,
        lambda: process_all_readings(class_paths, output_dir, manifest, class_config=CLASSES),
    )

    # Final summary
    _log_banner("PROCESSING COMPLETE!")
    logger.info("All outputs have been saved to:")
    logger.info("- Individual class folders")
    logger.info("- %s", output_dir)
    logger.info("Input folders should now be empty (files moved to processed).")
    logger.info("=" * BANNER_WIDTH)
    logger.debug("Program execution completed successfully")
    manifest.record_stage_event("pipeline", "complete", "Pipeline run completed")
    manifest.finalize()


if __name__ == "__main__":
    main()
