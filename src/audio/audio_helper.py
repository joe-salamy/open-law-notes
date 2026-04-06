"""
Audio preprocessing utilities for transcription optimization.
Handles audio conversion, noise reduction, filtering, and normalization.
Also includes transcript formatting utilities.
"""

import os
import tempfile
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
import noisereduce as nr
import librosa
from scipy import signal
from pydub import AudioSegment

from ..utils.logger_config import get_logger

logger = get_logger(__name__)


class TranscriptSegment(Protocol):
    """Protocol for transcript segments returned by transcription services."""

    start: float
    end: float
    text: str
    speaker: str | None


def preprocess_audio(audio_file: Path) -> tuple[np.ndarray, int]:
    """
    Preprocess audio file for optimal transcription.

    Pipeline:
    1. Convert M4A to WAV (16kHz, mono)
    2. Apply noise reduction
    3. Apply bandpass filter (80Hz - 7500Hz) for speech frequencies
    4. Normalize audio levels

    Args:
        audio_file: Path to M4A audio file

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    logger.debug(f"Starting audio preprocessing for: {audio_file.name}")
    temp_wav_path = None

    try:
        # Step 1: Convert M4A to WAV using pydub (handles M4A properly)
        logger.debug(f"[M4A→WAV] Converting {audio_file.name}")
        audio = AudioSegment.from_file(str(audio_file), format="m4a")

        # Create temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()

        # Export as WAV (16kHz mono)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(temp_wav_path, format="wav")
        logger.debug(f"[M4A→WAV DONE] Converted to WAV")

        # Load the converted WAV file
        logger.debug(f"[LOAD AUDIO] Loading converted audio at 16kHz mono")
        samples, sample_rate = librosa.load(temp_wav_path, sr=16000, mono=True)
        logger.debug(f"[LOAD AUDIO DONE] {len(samples)} samples at {sample_rate}Hz")
        # samples are already in float32 format normalized to [-1, 1]

    finally:
        # Clean up temporary file
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
            logger.debug(f"Cleaned up temporary conversion file")

    # Step 2: Apply noise reduction
    # Uses non-stationary noise reduction algorithm, and reduce sound only by 50% (1.0 = max)
    logger.debug("Applying noise reduction")
    samples = nr.reduce_noise(
        y=samples, sr=sample_rate, stationary=False, prop_decrease=0.5
    )
    logger.debug("Noise reduction completed")

    # Step 3: Apply bandpass filter (80Hz - 7500Hz)
    # Focuses on human speech frequency range
    # Adjusted to stay below Nyquist frequency (8000Hz for 16kHz sample rate)
    logger.debug("Applying bandpass filter (80Hz - 7500Hz)")
    nyquist = sample_rate / 2
    low = 80 / nyquist
    high = 7500 / nyquist  # Changed from 8000 to 7500 to ensure < 1.0

    # Validate filter frequencies
    if high >= 1.0:
        logger.warning(f"High frequency {high} >= 1.0, adjusting to 0.95")
        high = 0.95

    b, a = signal.butter(4, [low, high], btype="band")
    samples = signal.filtfilt(b, a, samples)
    logger.debug("Bandpass filter applied")

    logger.debug(f"Audio preprocessing completed for: {audio_file.name}")
    return samples, sample_rate


def format_timestamp(seconds: float) -> str:
    """
    Format seconds to [HH:MM:SS] timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"


def format_speaker_label(speaker: str) -> str:
    """
    Convert SPEAKER_00 to Speaker A, SPEAKER_01 to Speaker B, etc.

    Args:
        speaker: Raw speaker label from diarization (e.g., "SPEAKER_00")

    Returns:
        Formatted speaker label (e.g., "Speaker A")
    """
    if not speaker or speaker == "UNKNOWN":
        return "Unknown Speaker"

    try:
        # Extract number from SPEAKER_XX format
        num = int(speaker.split("_")[-1])
        if num < 26:
            return f"Speaker {chr(65 + num)}"  # 65 is ASCII 'A'
        return f"Speaker {num + 1}"
    except (ValueError, IndexError):
        return speaker  # Return as-is if parsing fails


def format_transcription_with_speakers(
    segments_list: Sequence[TranscriptSegment],
    paragraph_gap: float = 3.0,
    max_paragraph_duration: float = 30.0,
    include_speakers: bool = False,
) -> str:
    """
    Format transcription into paragraphs with optional speaker labels.

    Similar to format_transcription_paragraphs but adds speaker labels when available.
    Starts new paragraphs on:
    1. Significant pauses (>= paragraph_gap seconds)
    2. Speaker changes
    3. Max paragraph duration exceeded

    Args:
        segments_list: List of transcription segments (with optional speaker attribute)
        paragraph_gap: Seconds of silence between segments to start new paragraph (default: 3.0)
        max_paragraph_duration: Maximum duration of a paragraph in seconds (default: 30.0)
        include_speakers: Whether to include speaker labels in output (default: False)

    Returns:
        Formatted transcription string with paragraph-based timestamps and optional speakers
    """
    if not segments_list:
        return ""

    paragraphs = []
    current_paragraph = []
    paragraph_start_time = segments_list[0].start if segments_list else 0
    prev_end_time = paragraph_start_time
    current_speaker = (
        getattr(segments_list[0], "speaker", None) if segments_list else None
    )

    for segment in segments_list:
        gap = segment.start - prev_end_time
        segment_speaker = getattr(segment, "speaker", None)

        # Calculate what duration would be if we add this segment
        if current_paragraph:
            duration_with_new_segment = segment.end - paragraph_start_time
        else:
            duration_with_new_segment = segment.end - segment.start

        # Start new paragraph if:
        # 1. Significant pause detected (topic change)
        # 2. Speaker changed (when speakers are available)
        # 3. Adding this segment would exceed max duration (and we have content)
        should_break = False
        if current_paragraph:
            if gap >= paragraph_gap:
                should_break = True
            elif (
                include_speakers
                and segment_speaker
                and current_speaker
                and segment_speaker != current_speaker
            ):
                should_break = True
            elif duration_with_new_segment > max_paragraph_duration:
                should_break = True

        if should_break:
            # Save current paragraph
            timestamp = format_timestamp(paragraph_start_time)
            paragraph_text = " ".join(current_paragraph)

            if include_speakers and current_speaker:
                formatted_speaker = format_speaker_label(current_speaker)
                paragraphs.append(
                    f"{timestamp} {formatted_speaker}: {paragraph_text}\n"
                )
            else:
                paragraphs.append(f"{timestamp}\n{paragraph_text}\n")

            current_paragraph = []
            paragraph_start_time = segment.start
            current_speaker = segment_speaker

        current_paragraph.append(segment.text.strip())
        prev_end_time = segment.end

        # Update current speaker if not set
        if not current_speaker and segment_speaker:
            current_speaker = segment_speaker

    # Add final paragraph
    if current_paragraph:
        timestamp = format_timestamp(paragraph_start_time)
        paragraph_text = " ".join(current_paragraph)

        if include_speakers and current_speaker:
            formatted_speaker = format_speaker_label(current_speaker)
            paragraphs.append(f"{timestamp} {formatted_speaker}: {paragraph_text}")
        else:
            paragraphs.append(f"{timestamp}\n{paragraph_text}")

    return "\n".join(paragraphs)
