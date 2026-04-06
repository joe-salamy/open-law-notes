"""
File movement and copying utilities.
Handles moving processed files and copying outputs.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

import config
from .logger_config import get_logger
from .errors import FileOperationError

# Initialize logger
logger = get_logger(__name__)


def setup_output_directory() -> Path:
    """
    Create and return the new-outputs-safe-delete directory.

    Returns:
        Path to the output directory
    """
    output_dir = config.NEW_OUTPUTS_DIR

    try:
        logger.debug(f"Setting up output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Output directory ready: {output_dir}")
        return output_dir
    except OSError as e:
        logger.error(
            f"Failed to create output directory {output_dir}: {e}", exc_info=True
        )
        raise FileOperationError(f"Failed to create output directory: {e}") from e


def move_to_processed(file_path: Path, processed_folder: Path) -> bool:
    """
    Move a file to the processed folder.

    Args:
        file_path: Path to the file to move
        processed_folder: Destination folder

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(
            f"Moving file to processed: {file_path.name} -> {processed_folder}"
        )
        processed_folder.mkdir(parents=True, exist_ok=True)
        destination = processed_folder / file_path.name

        # If destination exists, add timestamp to avoid overwriting
        if destination.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            stem = destination.stem
            suffix = destination.suffix
            destination = processed_folder / f"{stem}_{timestamp}{suffix}"
            logger.debug(
                f"Destination exists, using timestamped name: {destination.name}"
            )

        shutil.move(file_path, destination)
        logger.debug(f"File moved successfully: {file_path.name} -> {destination}")
        return True

    except (OSError, shutil.Error) as e:
        logger.error(f"Error moving {file_path.name}: {e}", exc_info=True)
        return False


def copy_to_new_outputs(
    file_path: Path, new_outputs_dir: Path, destination_name: str | None = None
) -> bool:
    """
    Copy a file to the new-outputs-safe-delete directory.

    Args:
        file_path: Path to the file to copy
        new_outputs_dir: Destination directory

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(
            f"Copying file to new-outputs: {file_path.name} -> {new_outputs_dir}"
        )
        new_outputs_dir.mkdir(parents=True, exist_ok=True)
        resolved_name = destination_name if destination_name else file_path.name
        destination = new_outputs_dir / resolved_name

        shutil.copy2(file_path, destination)
        logger.debug(f"File copied successfully: {file_path.name} -> {destination}")
        return True

    except (OSError, shutil.Error) as e:
        logger.error(
            f"Error copying {file_path.name} to new-outputs: {e}", exc_info=True
        )
        return False


move_audio_to_processed = move_to_processed
