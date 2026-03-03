"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
import argparse
from pathlib import Path
from config import CLASSES, PARENT_FOLDER, ENABLE_GOOGLE_DRIVE

CLASS_PATHS = [Path(PARENT_FOLDER) / name for name in CLASSES]
from src.llm.llm_processor import process_all_readings, process_all_lectures
from src.utils.folder_manager import verify_and_create_folders
from src.utils.file_mover import setup_output_directory
from src.audio.audio_processor import process_all_lectures as process_audio
from src.audio.drive_downloader import download_from_drive
from src.utils.run_manifest import RunManifest
from src.utils.logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)


def main():
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

    # Initialize logging first
    setup_logging()
    manifest = RunManifest(project_root=Path(__file__).resolve().parent)
    manifest.record_stage_event("pipeline", "start", "Pipeline run started")

    logger.info("=" * 70)
    logger.info("LAW SCHOOL NOTE GENERATOR")
    logger.info("=" * 70)
    if reading_only_mode:
        logger.info("*** READING-ONLY MODE ENABLED ***")
    logger.debug(f"Processing {len(CLASS_PATHS)} classes")

    # Setup new-outputs-safe-delete directory
    try:
        logger.debug("Setting up output directory")
        output_dir = setup_output_directory()
        logger.info(f"✓ Output directory ready: {output_dir}")
        logger.debug(f"Output directory path: {output_dir}")
    except Exception as e:
        manifest.record_stage_event(
            "pipeline", "error", f"Output directory setup failed: {e}"
        )
        logger.error(f"✗ Error setting up output directory: {e}", exc_info=True)
        manifest.finalize()
        sys.exit(1)

    # Download files from Google Drive
    if not reading_only_mode and ENABLE_GOOGLE_DRIVE:
        logger.info("=" * 70)
        logger.info("STEP 0: Downloading Files from Google Drive")
        logger.info("=" * 70)

        try:
            logger.debug("Starting Google Drive download")
            download_results = download_from_drive(CLASSES, Path(PARENT_FOLDER))
            total_files = sum(download_results.values())
            logger.info(f"✓ Downloaded {total_files} file(s) from Google Drive")
            for class_name, count in download_results.items():
                logger.debug(f"{class_name}: {count} file(s)")
        except FileNotFoundError as e:
            logger.warning(f"⚠ Google Drive download skipped: {e}")
            logger.info("Continuing with local files...")
        except Exception as e:
            manifest.record_stage_event("google_drive", "error", f"Download error: {e}")
            logger.error(f"✗ Error downloading from Google Drive: {e}", exc_info=True)
            logger.info("Continuing with local files...")
    else:
        logger.info("=" * 70)
        if reading_only_mode:
            logger.info("STEP 0: Skipped (reading-only mode)")
        else:
            logger.info("STEP 0: Skipped (Google Drive disabled)")
        logger.info("=" * 70)

    # Verify all class folders have correct structure
    logger.info("=" * 70)
    logger.info("STEP 1: Verifying Folder Structure")
    logger.info("=" * 70)

    for class_folder in CLASS_PATHS:
        class_name = class_folder.name
        logger.info(f"Verifying: {class_name}")
        logger.debug(f"Class folder path: {class_folder}")
        try:
            verify_and_create_folders(class_folder)
            logger.info(f"✓ Folder structure verified")
            logger.info("─" * 70)
        except Exception as e:
            manifest.record_stage_event(
                "folder_verification", "error", f"Folder verification failed: {e}"
            )
            logger.error(f"✗ Error: {e}", exc_info=True)
            manifest.finalize()
            sys.exit(1)

    # Process lecture audio files to transcripts
    if not reading_only_mode:
        logger.info("=" * 70)
        logger.info("STEP 2: Converting Lecture Audio to Text")
        logger.info("=" * 70)

        try:
            logger.debug("Starting audio processing")
            process_audio(CLASS_PATHS, manifest)
            logger.debug("Audio processing completed")
        except Exception as e:
            manifest.record_stage_event(
                "audio_transcription", "error", f"Audio processing failed: {e}"
            )
            logger.error(f"✗ Error processing lectures: {e}", exc_info=True)
            manifest.finalize()
            sys.exit(1)
    else:
        logger.info("=" * 70)
        logger.info("STEP 2: Skipped (Reading-only mode)")
        logger.info("=" * 70)

    # Process lecture transcripts with LLM
    if not reading_only_mode:
        logger.info("=" * 70)
        logger.info("STEP 3: Generating Lecture Notes with LLM")
        logger.info("=" * 70)

        try:
            logger.debug("Starting lecture transcript processing")
            process_all_lectures(CLASS_PATHS, output_dir, manifest)
            logger.debug("Lecture transcript processing completed")
        except Exception as e:
            manifest.record_stage_event(
                "lecture_llm", "error", f"Lecture LLM processing failed: {e}"
            )
            logger.error(f"✗ Error processing lecture transcripts: {e}", exc_info=True)
            manifest.finalize()
            sys.exit(1)
    else:
        logger.info("=" * 70)
        logger.info("STEP 3: Skipped (Reading-only mode)")
        logger.info("=" * 70)

    # Process reading files with LLM
    logger.info("=" * 70)
    logger.info("STEP 4: Generating Reading Notes with LLM")
    logger.info("=" * 70)

    try:
        logger.debug("Starting reading processing")
        process_all_readings(CLASS_PATHS, output_dir, manifest)
        logger.debug("Reading processing completed")
    except Exception as e:
        manifest.record_stage_event(
            "reading_llm", "error", f"Reading LLM processing failed: {e}"
        )
        logger.error(f"✗ Error processing readings: {e}", exc_info=True)
        manifest.finalize()
        sys.exit(1)

    # Final summary
    logger.info("=" * 70)
    logger.info("PROCESSING COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"All outputs have been saved to:")
    logger.info(f"- Individual class folders")
    logger.info(f"- {output_dir}")
    logger.info("Input folders should now be empty (files moved to processed).")
    logger.info("=" * 70)
    logger.debug("Program execution completed successfully")
    manifest.record_stage_event("pipeline", "complete", "Pipeline run completed")
    manifest.finalize()


if __name__ == "__main__":
    main()
