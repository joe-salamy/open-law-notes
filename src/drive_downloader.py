"""
Google Drive file downloader for law school audio files.
Downloads m4a files from Google Drive and moves them to local lecture-input folders.
"""

import io
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pickle

from .config import LECTURE_INPUT, LLM_BASE
from .logger_config import get_logger

logger = get_logger(__name__)

# Google Drive API scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Token and credentials file paths
TOKEN_FILE = Path(__file__).parent.parent / "token.pickle"
CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"


def get_drive_service():
    """
    Authenticate and return a Google Drive service object.
    Uses OAuth 2.0 with stored credentials or prompts for login.
    """
    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # Refresh or get new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Please download it from Google Cloud Console."
                )
            logger.info("Starting OAuth flow - browser will open for authentication")
            logger.info(
                "If you see 'redirect_uri_mismatch' error, add these URIs to Google Cloud Console:"
            )
            logger.info("- http://localhost:8080/")
            logger.info("- http://localhost:8080")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Save credentials for next run
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
            logger.debug(f"Credentials saved to {TOKEN_FILE}")

    return build("drive", "v3", credentials=creds)


def find_folder_by_name(service, parent_folder_id: str, folder_name: str) -> str | None:
    """
    Find a folder by name within a parent folder.
    Returns the folder ID if found, None otherwise.
    """
    query = (
        f"'{parent_folder_id}' in parents and "
        f"name = '{folder_name}' and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"trashed = false"
    )

    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)")
        .execute()
    )

    files = results.get("files", [])
    if files:
        return files[0]["id"]
    return None


def find_or_create_processed_folder(service, parent_folder_id: str) -> str:
    """
    Find or create a 'Processed' folder inside the given parent folder.
    Returns the folder ID.
    """
    # Try to find existing Processed folder
    folder_id = find_folder_by_name(service, parent_folder_id, "Processed")

    if folder_id:
        logger.debug("Found existing 'Processed' folder in Drive")
        return folder_id

    # Create the Processed folder
    logger.debug("Creating 'Processed' folder in Drive")
    folder_metadata = {
        "name": "Processed",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }

    folder = service.files().create(body=folder_metadata, fields="id").execute()

    return folder["id"]


def get_m4a_files(service, folder_id: str) -> list[dict]:
    """
    Get all m4a files in a folder.
    Returns a list of file metadata dictionaries.
    """
    query = (
        f"'{folder_id}' in parents and "
        f"(mimeType = 'audio/mp4' or mimeType = 'audio/x-m4a' or name contains '.m4a') and "
        f"trashed = false"
    )

    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name, mimeType)")
        .execute()
    )

    return results.get("files", [])


def download_file(service, file_id: str, destination_path: Path) -> bool:
    """
    Download a file from Google Drive to a local path.
    Returns True if successful, False otherwise.
    """
    try:
        request = service.files().get_media(fileId=file_id)

        with io.BytesIO() as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            # Write to file
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            with open(destination_path, "wb") as f:
                f.write(fh.getvalue())

        return True
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return False


def move_file_to_folder(service, file_id: str, new_folder_id: str) -> bool:
    """
    Move a file to a different folder in Google Drive.
    Returns True if successful, False otherwise.
    """
    try:
        # Get current parents
        file = service.files().get(fileId=file_id, fields="parents").execute()

        previous_parents = ",".join(file.get("parents", []))

        # Move file to new folder
        service.files().update(
            fileId=file_id,
            addParents=new_folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

        return True
    except Exception as e:
        logger.error(f"Error moving file in Drive: {e}")
        return False


def download_class_files(service, class_folder: Path, drive_folder_id: str) -> int:
    """
    Download all m4a files for a single class from Google Drive.
    Returns the number of files downloaded.
    """
    class_name = class_folder.name
    logger.info(f"Processing class: {class_name}")

    # Get m4a files in the class Drive folder
    m4a_files = get_m4a_files(service, drive_folder_id)

    if not m4a_files:
        logger.info(f"No m4a files found for {class_name}")
        return 0

    logger.info(f"Found {len(m4a_files)} m4a file(s) to download")

    # Get or create the Processed folder in Drive
    processed_folder_id = find_or_create_processed_folder(
        service, drive_folder_id
    )

    # Local destination folder
    local_destination = class_folder / LLM_BASE / LECTURE_INPUT
    local_destination.mkdir(parents=True, exist_ok=True)

    downloaded_count = 0

    for file_info in m4a_files:
        file_id = file_info["id"]
        file_name = file_info["name"]

        logger.info(f"Downloading: {file_name}")

        # Download to local folder
        local_path = local_destination / file_name

        if download_file(service, file_id, local_path):
            logger.info(f"✓ Downloaded to: {local_path}")

            # Move file to Processed folder in Drive
            if move_file_to_folder(service, file_id, processed_folder_id):
                logger.info(f"✓ Moved to Processed folder in Drive")
                downloaded_count += 1
            else:
                logger.warning(f"⚠ Downloaded but failed to move in Drive")
                downloaded_count += (
                    1  # Still count as success since file was downloaded
                )
        else:
            logger.error(f"✗ Failed to download: {file_name}")

    return downloaded_count


def download_from_drive(classes: dict, parent_folder: Path) -> dict[str, int]:
    """
    Download m4a files from Google Drive for all classes that have a Drive folder ID.

    Args:
        classes: Dict mapping class name to Drive folder ID (or None to skip)
        parent_folder: Local parent folder containing all class subfolders

    Returns:
        Dictionary mapping class names to number of files downloaded
    """
    logger.info("Initializing Google Drive connection...")

    try:
        service = get_drive_service()
        logger.info("✓ Connected to Google Drive")
    except FileNotFoundError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"Failed to connect to Google Drive: {e}")
        raise

    results = {}
    total_downloaded = 0

    for class_name, drive_id in classes.items():
        if not drive_id:
            logger.info(f"Skipping {class_name}: no Drive folder ID configured")
            results[class_name] = 0
            logger.info("─" * 70)
            continue

        class_folder = parent_folder / class_name
        count = download_class_files(service, class_folder, drive_id)
        results[class_name] = count
        total_downloaded += count
        logger.info("─" * 70)

    logger.info(f"Total files downloaded: {total_downloaded}")

    return results
