"""
Test script for Step 0: Google Drive download functionality.
Tests downloading m4a files from Google Drive to local lecture-input folders.
Ensure that as main.py and drive_downloader.py change, so do the tests here.
"""

from pathlib import Path

from src.config import CLASSES
from src.drive_downloader import download_from_drive
from src.logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)


def test_drive_download():
    """Test the Google Drive download functionality (Step 0)."""
    # Initialize logging
    setup_logging()

    logger.info("=" * 70)
    logger.info("TESTING: Google Drive Download (Step 0)")
    logger.info("=" * 70)
    logger.info(f"Testing with {len(CLASSES)} class(es)")

    for class_folder in CLASSES:
        logger.info(f"  - {class_folder.name}")

    logger.info("=" * 70)

    try:
        logger.info("Starting Google Drive download test...")
        download_results = download_from_drive(CLASSES)

        logger.info("=" * 70)
        logger.info("DOWNLOAD RESULTS")
        logger.info("=" * 70)

        total_files = 0
        for class_name, count in download_results.items():
            logger.info(f"  {class_name}: {count} file(s) downloaded")
            total_files += count

        logger.info("=" * 70)
        logger.info(f"✓ TEST PASSED")
        logger.info(f"Total files downloaded: {total_files}")
        logger.info("=" * 70)

        return True

    except FileNotFoundError as e:
        logger.error("=" * 70)
        logger.error("✗ TEST FAILED: Missing credentials")
        logger.error("=" * 70)
        logger.error(str(e))
        logger.error("\nTo fix this:")
        logger.error("1. Go to https://console.cloud.google.com/")
        logger.error("2. Create/select a project and enable the Drive API")
        logger.error("3. Create OAuth 2.0 credentials (Desktop app)")
        logger.error("4. Download as 'credentials.json' and place in project root")
        logger.error("=" * 70)
        return False

    except Exception as e:
        logger.error("=" * 70)
        logger.error("✗ TEST FAILED: Unexpected error")
        logger.error("=" * 70)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("=" * 70)
        return False


if __name__ == "__main__":
    success = test_drive_download()
    sys.exit(0 if success else 1)
