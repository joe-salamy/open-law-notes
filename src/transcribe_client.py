"""Cloud GPU transcription client for Salad API."""

import requests
from pathlib import Path
from typing import Tuple, List, Any
import time
from logger_config import get_logger

logger = get_logger(__name__)


class TranscribeSegment:
    """Mimics faster-whisper segment structure."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.start = data["start"]
        self.end = data["end"]
        self.text = data["text"]


class TranscribeClient:
    """HTTP client for cloud GPU transcription service."""

    def __init__(self, api_url: str, api_key: str, max_retries: int = 3):
        if not api_key:
            raise ValueError("API key is required for cloud GPU transcription")
        self.api_url = api_url
        self.api_key = api_key
        self.max_retries = max_retries

    def transcribe(
        self,
        wav_file_path: Path,
        beam_size: int = 5,
        language: str = "en",
        word_timestamps: bool = False,
    ) -> Tuple[List[TranscribeSegment], Any]:
        """
        Send WAV file to cloud GPU for transcription.
        Returns (segments, info) in same format as faster-whisper.
        """
        logger.info(f"Uploading {wav_file_path.name} to cloud GPU...")

        for attempt in range(self.max_retries):
            try:
                # Prepare request
                with open(wav_file_path, "rb") as f:
                    files = {"file": (wav_file_path.name, f, "audio/wav")}
                    data = {
                        "beam_size": beam_size,
                        "language": language,
                        "word_timestamps": str(word_timestamps).lower(),
                    }

                    headers = {"Authorization": f"Bearer {self.api_key}"}

                    # Upload and transcribe (30 min timeout for long files)
                    response = requests.post(
                        self.api_url,
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=1800,
                    )

                # Handle response
                if response.status_code == 200:
                    result = response.json()
                    segments = [TranscribeSegment(seg) for seg in result["segments"]]
                    info = result.get("info", {})
                    logger.info(
                        f"✓ Cloud transcription complete: {len(segments)} segments"
                    )
                    return segments, info

                elif response.status_code == 503:  # GPU busy
                    wait_time = 60 * (2**attempt)  # Exponential backoff
                    logger.warning(f"GPU busy, retrying in {wait_time}s...")
                    time.sleep(wait_time)

                else:
                    error_msg = f"API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except requests.Timeout:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Upload timeout, retrying (attempt {attempt + 1}/{self.max_retries})..."
                    )
                    time.sleep(30)
                else:
                    raise Exception("Upload timeout after retries")

            except Exception as e:
                logger.error(f"Transcription request failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(30)
                else:
                    raise

        raise Exception("Max retries exceeded")
