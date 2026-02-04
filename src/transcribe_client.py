"""Cloud GPU transcription client for Vast.ai API."""

import json
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
        # Reuse HTTP session for connection pooling (faster subsequent requests)
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def transcribe(
        self,
        wav_file_path: Path,
        beam_size: int = 5,
        language: str = "en",
        word_timestamps: bool = False,
        enable_diarization: bool = False,
        min_speakers: int = None,
        max_speakers: int = None,
    ) -> Tuple[List[TranscribeSegment], Any, List[dict] | None]:
        """
        Send WAV file to cloud GPU for transcription.
        Returns (segments, info, speaker_segments) tuple.
        """
        logger.info(f"Uploading {wav_file_path.name} to cloud GPU...")

        for attempt in range(self.max_retries):
            try:
                # Prepare request (detect MIME type from file extension)
                mime_type = (
                    "audio/flac" if wav_file_path.suffix == ".flac" else "audio/wav"
                )
                with open(wav_file_path, "rb") as f:
                    files = {"file": (wav_file_path.name, f, mime_type)}
                    data = {
                        "beam_size": beam_size,
                        "language": language,
                        "word_timestamps": str(word_timestamps).lower(),
                        "enable_diarization": str(enable_diarization).lower(),
                    }
                    if min_speakers is not None:
                        data["min_speakers"] = min_speakers
                    if max_speakers is not None:
                        data["max_speakers"] = max_speakers

                    # Upload and transcribe (30 min timeout for long files)
                    response = self.session.post(
                        self.api_url,
                        files=files,
                        data=data,
                        timeout=1800,
                        stream=True,  # Enable streaming response
                    )

                # Handle response
                if response.status_code == 200:
                    # Read streaming response line by line (newline-delimited JSON)
                    result_data = None
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue

                        try:
                            message = json.loads(line)
                            msg_type = message.get("type")

                            if msg_type == "progress":
                                # Log progress updates
                                logger.debug(f"[Cloud GPU] {message.get('message')}")

                            elif msg_type == "result":
                                # Final result received
                                result_data = message.get("data")

                            elif msg_type == "error":
                                raise Exception(
                                    f"Server error: {message.get('message')}"
                                )

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Failed to parse streaming response: {line}"
                            )

                    if result_data is None:
                        raise Exception("No result received from streaming response")

                    # Parse result
                    segments = [
                        TranscribeSegment(seg) for seg in result_data["segments"]
                    ]
                    info = result_data.get("info", {})
                    speaker_segments = result_data.get("speaker_segments")

                    logger.info(
                        f"✓ Cloud transcription complete: {len(segments)} segments"
                    )
                    if speaker_segments:
                        logger.info(
                            f"✓ Diarization complete: {len(speaker_segments)} speaker segments"
                        )
                    return segments, info, speaker_segments

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

    def close(self):
        """Close the HTTP session to free resources."""
        self.session.close()
