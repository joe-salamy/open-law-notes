"""
Test script for Step 5: Google Docs upload functionality.
Tests uploading LLM-generated markdown files to Google Docs.
Tests with the file "Bussel 10.21.2025.md" for the "Contracts" class.
"""

from pathlib import Path

from src.docs_uploader import (
    get_drive_service,
    get_docs_service,
    prepend_filename_to_h3,
    find_notes_document,
    append_markdown_to_doc,
    process_markdown_file,
)
from src.logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)

# Test file path
TEST_FILE_PATH = Path("tests/markdown/Bussel 10.21.2025.md")
TEST_CLASS_NAME = "Contracts"


def test_prepend_filename_to_h3():
    """Test the prepend_filename_to_h3 function."""
    logger.info("Testing prepend_filename_to_h3...")

    # Test case 1: Standard h3 header
    test_content = """### Main Title

Some intro text.

- Topic One

Content here.

- Topic Two

More content.
"""
    filename = "Test File 2025.01.03"
    result = prepend_filename_to_h3(test_content, filename)

    # Check that the first h3 was modified
    assert (
        f"### {filename}: Topic One" in result
    ), "First h3 should have filename prepended"
    assert "### Topic Two" in result, "Second h3 should be unchanged"
    logger.info("✓ prepend_filename_to_h3 test passed")
    return True


def test_find_notes_document():
    """Test finding the notes document in Google Drive."""
    logger.info("Testing find_notes_document...")

    try:
        drive_service = get_drive_service()

        # Try to find the Contracts Lecture Notes document
        doc = find_notes_document(drive_service, TEST_CLASS_NAME, "lecture")

        if doc:
            logger.info(f"✓ Found document: {doc['name']} (ID: {doc['id']})")
            return True
        else:
            logger.warning("⚠ No Lecture Notes document found for Contracts")
            logger.info("This may be expected if the document doesn't exist yet")
            return False

    except Exception as e:
        logger.error(f"✗ Error finding notes document: {e}")
        return False


def test_upload_single_file():
    """Test uploading a single markdown file to Google Docs."""
    logger.info("Testing single file upload...")

    # Check if test file exists
    if not TEST_FILE_PATH.exists():
        logger.error(f"✗ Test file not found: {TEST_FILE_PATH}")
        logger.info("Please ensure the test file exists at the specified path")
        return False

    try:
        drive_service = get_drive_service()
        docs_service = get_docs_service()

        # Find the target document
        target_doc = find_notes_document(drive_service, TEST_CLASS_NAME, "lecture")

        if not target_doc:
            logger.error(
                f"✗ Could not find Lecture Notes document for {TEST_CLASS_NAME}"
            )
            return False

        # Read the markdown file
        with open(TEST_FILE_PATH, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        logger.info(
            f"Read {len(markdown_content)} characters from {TEST_FILE_PATH.name}"
        )

        # Prepend filename to h3
        filename = TEST_FILE_PATH.stem
        modified_content = prepend_filename_to_h3(markdown_content, filename)

        # Append to the document
        success = append_markdown_to_doc(
            docs_service, target_doc["id"], modified_content
        )

        if success:
            logger.info(
                f"✓ Successfully uploaded {TEST_FILE_PATH.name} to {target_doc['name']}"
            )
            doc_url = f"https://docs.google.com/document/d/{target_doc['id']}/edit"
            logger.info(f"Document URL: {doc_url}")
            return True
        else:
            logger.error(f"✗ Failed to upload {TEST_FILE_PATH.name}")
            return False

    except Exception as e:
        logger.error(f"✗ Error uploading file: {e}", exc_info=True)
        return False


def test_full_process():
    """Test the full process_markdown_file function."""
    logger.info("Testing full markdown file processing...")

    # Check if test file exists
    if not TEST_FILE_PATH.exists():
        logger.error(f"✗ Test file not found: {TEST_FILE_PATH}")
        return False

    try:
        drive_service = get_drive_service()
        docs_service = get_docs_service()

        success = process_markdown_file(
            TEST_FILE_PATH, TEST_CLASS_NAME, "lecture", drive_service, docs_service
        )

        if success:
            logger.info("✓ Full process test passed")
        else:
            logger.error("✗ Full process test failed")

        return success

    except Exception as e:
        logger.error(f"✗ Error in full process test: {e}", exc_info=True)
        return False


def run_all_tests():
    """Run all tests for the docs upload functionality."""
    setup_logging()

    logger.info("=" * 70)
    logger.info("TESTING: Google Docs Upload (Step 5)")
    logger.info("=" * 70)
    logger.info(f"Test file: {TEST_FILE_PATH}")
    logger.info(f"Test class: {TEST_CLASS_NAME}")
    logger.info("=" * 70)

    results = {}

    # Test 1: prepend_filename_to_h3
    logger.info("─" * 70)
    logger.info("TEST 1: prepend_filename_to_h3")
    logger.info("─" * 70)
    try:
        results["prepend_filename"] = test_prepend_filename_to_h3()
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results["prepend_filename"] = False

    # Test 2: find_notes_document
    logger.info("─" * 70)
    logger.info("TEST 2: find_notes_document")
    logger.info("─" * 70)
    try:
        results["find_document"] = test_find_notes_document()
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results["find_document"] = False

    # Test 3: Upload single file (only if previous tests passed)
    if results.get("find_document"):
        logger.info("─" * 70)
        logger.info("TEST 3: upload_single_file")
        logger.info("─" * 70)
        try:
            results["upload_file"] = test_upload_single_file()
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            results["upload_file"] = False
    else:
        logger.info("─" * 70)
        logger.info("TEST 3: upload_single_file (SKIPPED - no document found)")
        logger.info("─" * 70)
        results["upload_file"] = None

    # Summary
    logger.info("=" * 70)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 70)

    all_passed = True
    for test_name, passed in results.items():
        if passed is None:
            status = "SKIPPED"
        elif passed:
            status = "PASSED"
        else:
            status = "FAILED"
            all_passed = False
        logger.info(f"{test_name}: {status}")

    logger.info("=" * 70)
    if all_passed:
        logger.info("✓ ALL TESTS PASSED")
    else:
        logger.info("✗ SOME TESTS FAILED")
    logger.info("=" * 70)

    return all_passed


if __name__ == "__main__":
    # success = run_all_tests()
    success = test_upload_single_file()
    sys.exit(0 if success else 1)
