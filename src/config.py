"""
Configuration settings for law school note generator.
Edit the class folders list to match your directory structure.
"""

from pathlib import Path

# ========== EDIT THESE PATHS ==========

# List of class folders - add or remove as needed
CLASSES = [
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Con Law"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Property"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Quant Methods"),
]

# ========== PROCESSING SETTINGS ==========

# Whisper model size for transcription
# Options: 'tiny', 'base', 'small', 'medium', 'large'
# 'tiny' = fastest, 'large' = most accurate
WHISPER_MODEL = "tiny"

# Gemini model configuration
# GEMINI_MODEL = "gemini-3-pro-preview"
# 2.5 Pro gives longer responses than 3 Pro, for whatever reason (maybe trying to preserve tokens on highest-demand model?)
GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_MAX_OUTPUT_TOKENS = 10000
GEMINI_TEMPERATURE = 0.9

# Number of parallel processes/threads
MAX_AUDIO_WORKERS = 3  # Multiprocessing for CPU-intensive transcription
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
