"""
Configuration settings for law school note generator.
Edit the class folders list to match your directory structure.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== EDIT THESE PATHS ==========

# List of class folders - add or remove as needed
CLASSES = [
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Con Law"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\LRW"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Property"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Quant Methods"),
]

# ========== CLOUD GPU SETTINGS ==========

# Toggle between cloud GPU (Vast.ai) and local CPU
USE_CLOUD_GPU = True  # Set to False to use local CPU

# Vast.ai API configuration (only used if USE_CLOUD_GPU = True)
CLOUD_API_URL = os.getenv("VAST_API_URL", "http://your-vast-instance:port/transcribe")
CLOUD_API_KEY = os.getenv("VAST_API_KEY")  # Required for authentication

# Validate cloud GPU configuration
if USE_CLOUD_GPU:
    if not CLOUD_API_KEY:
        raise ValueError(
            "VAST_API_KEY environment variable is required when USE_CLOUD_GPU=True. "
            "Please set it in your .env file."
        )

# ========== SPEAKER DIARIZATION SETTINGS ==========

# Enable speaker diarization (requires HF_TOKEN and cloud GPU)
ENABLE_DIARIZATION = True  # Set True to enable speaker identification

# Optional speaker count constraints (helps accuracy if you know speaker count)
MIN_SPEAKERS = None  # e.g., 2 for "at least 2 speakers"
MAX_SPEAKERS = None  # e.g., 3 for "at most 3 speakers"

# Validate HF_TOKEN if diarization enabled
if ENABLE_DIARIZATION and USE_CLOUD_GPU:
    HF_TOKEN = os.getenv("HF_TOKEN")
    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN required when ENABLE_DIARIZATION=True. "
            "Get token from: https://huggingface.co/settings/tokens\n"
            "Accept pyannote license: https://huggingface.co/pyannote/speaker-diarization-3.1"
        )
elif ENABLE_DIARIZATION and not USE_CLOUD_GPU:
    raise ValueError(
        "ENABLE_DIARIZATION=True requires USE_CLOUD_GPU=True. "
        "Speaker diarization is only available on cloud GPU."
    )

# Gemini model configuration
GEMINI_MODEL = "gemini-3-pro-preview"
GEMINI_TEMPERATURE = 0.0

# Number of parallel processes/threads
MAX_AUDIO_WORKERS_CLOUD_GPU = 2  # Threads for cloud GPU (I/O-bound)
MAX_AUDIO_WORKERS_LOCAL_CPU = 2  # Processes for local CPU (CPU-bound)
MAX_LLM_WORKERS = 5  # Multithreading for I/O-bound API calls

# ========== FOLDER STRUCTURE ==========

# These define the expected folder structure within each class
LLM_BASE = "LLM"

LECTURE_INPUT = "lecture-input"
LECTURE_OUTPUT = "lecture-output"
LECTURE_PROCESSED = "lecture-processed"
LECTURE_PROCESSED_AUDIO = "audio"
LECTURE_PROCESSED_TXT = "txt"

READING_INPUT = "reading-input"
READING_OUTPUT = "reading-output"
READING_PROCESSED = "reading-processed"

# ========== PROMPT FILES ==========

PROMPT_DIR = Path("prompts")
LECTURE_PROMPT_FILE = "lecture.md"
READING_PROMPT_FILE = "reading.md"

# ========== OUTPUT DIRECTORY ==========

NEW_OUTPUTS_DIR = Path("C:\\Users\\joesa\\Downloads")

# ========== GOOGLE DRIVE SETTINGS ==========

# Parent folder ID in Google Drive containing class subfolders (for audio downloads)
DRIVE_PARENT_FOLDER_ID = "1jtZejrszwGvEsOUwcRz4opS6evnK8yjh"

# Classes folder ID in Google Drive (for uploading notes to Google Docs)
DRIVE_CLASSES_FOLDER_ID = "1SLmIzmmq8bHErx7wMhqaYm9WHwXANVzo"
