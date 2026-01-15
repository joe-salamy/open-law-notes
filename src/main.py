"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
from pathlib import Path
from config import CLASSES
from llm_processor import process_all_readings, process_all_lectures
from folder_manager import verify_and_create_folders
from file_mover import setup_output_directory
from audio_processor import process_all_lectures as process_audio
from drive_downloader import download_from_drive
from logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)

# Toggle this to True to only process readings (skip Steps 0, 2, and 3)
READING_ONLY_MODE = True


def main():
    """Main entry point for the law school note generator."""
    # Initialize logging first
    setup_logging()

    logger.info("=" * 70)
    logger.info("LAW SCHOOL NOTE GENERATOR")
    logger.info("=" * 70)
    if READING_ONLY_MODE:
        logger.info("*** READING-ONLY MODE ENABLED ***")
    logger.debug(f"Processing {len(CLASSES)} classes")

    # Setup new-outputs-safe-delete directory
    try:
        logger.debug("Setting up output directory")
        output_dir = setup_output_directory()
        logger.info(f"✓ Output directory ready: {output_dir}")
        logger.debug(f"Output directory path: {output_dir}")
    except Exception as e:
        logger.error(f"✗ Error setting up output directory: {e}", exc_info=True)
        sys.exit(1)

    # Download files from Google Drive
    if not READING_ONLY_MODE:
        logger.info("=" * 70)
        logger.info("STEP 0: Downloading Files from Google Drive")
        logger.info("=" * 70)

        try:
            logger.debug("Starting Google Drive download")
            download_results = download_from_drive(CLASSES)
            total_files = sum(download_results.values())
            logger.info(f"✓ Downloaded {total_files} file(s) from Google Drive")
            for class_name, count in download_results.items():
                logger.debug(f"{class_name}: {count} file(s)")
        except FileNotFoundError as e:
            logger.warning(f"⚠ Google Drive download skipped: {e}")
            logger.info("Continuing with local files...")
        except Exception as e:
            logger.error(f"✗ Error downloading from Google Drive: {e}", exc_info=True)
            logger.info("Continuing with local files...")
    else:
        logger.info("=" * 70)
        logger.info("STEP 0: Skipped (Reading-only mode)")
        logger.info("=" * 70)

    # Verify all class folders have correct structure
    logger.info("=" * 70)
    logger.info("STEP 1: Verifying Folder Structure")
    logger.info("=" * 70)

    for class_folder in CLASSES:
        class_name = Path(class_folder).name
        logger.info(f"Verifying: {class_name}")
        logger.debug(f"Class folder path: {class_folder}")
        try:
            verify_and_create_folders(class_folder)
            logger.info(f"✓ Folder structure verified")
            logger.info("─" * 70)
        except Exception as e:
            logger.error(f"✗ Error: {e}", exc_info=True)
            sys.exit(1)

    # Process lecture audio files to transcripts
    if not READING_ONLY_MODE:
        logger.info("=" * 70)
        logger.info("STEP 2: Converting Lecture Audio to Text")
        logger.info("=" * 70)

        try:
            logger.debug("Starting audio processing")
            process_audio(CLASSES)
            logger.debug("Audio processing completed")
        except Exception as e:
            logger.error(f"✗ Error processing lectures: {e}", exc_info=True)
            sys.exit(1)
    else:
        logger.info("=" * 70)
        logger.info("STEP 2: Skipped (Reading-only mode)")
        logger.info("=" * 70)

    # Process lecture transcripts with LLM
    if not READING_ONLY_MODE:
        logger.info("=" * 70)
        logger.info("STEP 3: Generating Lecture Notes with LLM")
        logger.info("=" * 70)

        try:
            logger.debug("Starting lecture transcript processing")
            process_all_lectures(CLASSES, output_dir)
            logger.debug("Lecture transcript processing completed")
        except Exception as e:
            logger.error(f"✗ Error processing lecture transcripts: {e}", exc_info=True)
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
        process_all_readings(CLASSES, output_dir)
        logger.debug("Reading processing completed")
    except Exception as e:
        logger.error(f"✗ Error processing readings: {e}", exc_info=True)
        sys.exit(1)

    """
    # Upload notes to Google Docs
    logger.info("=" * 70)
    logger.info("STEP 5: Uploading Notes to Google Docs")
    logger.info("=" * 70)

    try:
        logger.debug("Starting Google Docs upload")
        upload_results = upload_to_docs(CLASSES)

        total_lectures = sum(r.get("lecture", 0) for r in upload_results.values())
        total_readings = sum(r.get("reading", 0) for r in upload_results.values())
        logger.info(
            f"✓ Uploaded {total_lectures} lecture note(s) and {total_readings} reading note(s)"
        )

        for class_name, counts in upload_results.items():
            if "error" in counts:
                logger.warning(f"{class_name}: Error - {counts['error']}")
            else:
                logger.debug(
                    f"{class_name}: {counts['lecture']} lecture(s), {counts['reading']} reading(s)"
                )
        logger.debug("Google Docs upload completed")
    except Exception as e:
        logger.error(f"✗ Error uploading to Google Docs: {e}", exc_info=True)
        logger.info("Note generation completed, but upload to Docs failed.") 
    """

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


if __name__ == "__main__":
    main()
