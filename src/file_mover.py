"""
File movement and copying utilities.
Handles moving processed files and copying outputs.
"""

import shutil
from pathlib import Path
from datetime import datetime

import config
from logger_config import get_logger

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
    except Exception as e:
        logger.error(
            f"Failed to create output directory {output_dir}: {e}", exc_info=True
        )
        raise Exception(f"Failed to create output directory: {e}")


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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = destination.stem
            suffix = destination.suffix
            destination = processed_folder / f"{stem}_{timestamp}{suffix}"
            logger.debug(
                f"Destination exists, using timestamped name: {destination.name}"
            )

        shutil.move(str(file_path), str(destination))
        logger.debug(f"File moved successfully: {file_path.name} -> {destination}")
        return True

    except Exception as e:
        logger.error(f"Error moving {file_path.name}: {e}", exc_info=True)
        return False


def copy_to_new_outputs(file_path: Path, new_outputs_dir: Path) -> bool:
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
        destination = new_outputs_dir / file_path.name

        # If destination exists, add timestamp to avoid overwriting
        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = destination.stem
            suffix = destination.suffix
            destination = new_outputs_dir / f"{stem}_{timestamp}{suffix}"
            logger.debug(
                f"Destination exists, using timestamped name: {destination.name}"
            )

        shutil.copy2(str(file_path), str(destination))
        logger.debug(f"File copied successfully: {file_path.name} -> {destination}")
        return True

    except Exception as e:
        logger.error(
            f"Error copying {file_path.name} to new-outputs: {e}", exc_info=True
        )
        return False


def move_audio_to_processed(audio_file: Path, processed_audio_folder: Path) -> bool:
    """
    Move an audio file to the processed audio folder.

    Args:
        audio_file: Path to the audio file
        processed_audio_folder: Destination folder for processed audio

    Returns:
        True if successful, False otherwise
    """
    return move_to_processed(audio_file, processed_audio_folder)
