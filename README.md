# Law School Note Generator

Automated system for generating lecture and reading notes from audio files and text documents using faster-whisper and Gemini AI.

## Quick Start

1. Install Python 3.8+ and FFmpeg
2. Run: `pip install -r requirements.txt`
3. Create `.env` with your Gemini API key
4. **Set up Google Drive API credentials:**
   - Copy `credentials.json.example` to `credentials.json`
   - Replace with your actual OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the Google Drive API for your project
   - Download OAuth 2.0 credentials and paste into `credentials.json`
   - **Never commit `credentials.json` or `token.pickle` to git!**
5. Configure class paths in `src/config.py`
6. Create prompt files in `prompts/`
7. Place M4A files in `lecture-input/` folders
8. Run: `python src/main.py` or `python src/main.py --read-only`

### Monitor Progress in Real-Time

Audio transcription can take a while (15-20 min per hour of audio). To monitor detailed progress while the script runs:

```powershell
# In a separate terminal (automatically uses most recent log file):
Get-Content (Get-ChildItem "logs\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1) -Wait -Tail 50
```

This shows the last 50 log lines and streams new entries as they're written. You can also open the log file in a text editor, but it won't auto-update. `Get-Content -Wait` is recommended for live monitoring.

## Features

### Audio Transcription

- **faster-whisper** with large-v3 model for highest accuracy
- **CPU-optimized**: int8 quantization, 4 threads for AMD Ryzen 7 processors
- **Audio preprocessing pipeline**:
  - Automatic M4A to WAV conversion (16kHz, mono)
  - Noise reduction to remove background sounds
  - Bandpass filtering (80Hz-8000Hz) to focus on human speech
  - Audio normalization to -20dB LUFS for consistent volume
- **Segment-level timestamps** in [HH:MM:SS] format for easy navigation
- **Real-time progress bars** showing transcription status
- **Performance**: 3-4x real-time speed (1 hour lecture = 15-20 minutes)

### AI Note Generation

- **Google Gemini** for structured note creation
- **Parallel processing** with multithreading for fast API calls
- **Custom prompts** for lectures and readings
- **Multi-class support** processes all classes simultaneously

### File Management

- **Automatic folder structure** creation and verification
- **Organized output** with separate folders for each class
- **Backup system** with consolidated outputs in `new-outputs-safe-delete/`
- **Smart file moving** preserves originals in processed folders

## Project Structure

```
.
├── src/
│   ├── main.py                 # Central orchestrator
│   ├── config.py               # Configuration settings
│   ├── folder_manager.py       # Folder structure management
│   ├── audio_processor.py      # Audio transcription with faster-whisper
│   ├── llm_processor.py        # LLM processing with Gemini
│   └── file_mover.py           # File management utilities
├── prompts/
│   ├── reading.md              # Reading notes prompt template
│   └── lecture.md              # Lecture notes prompt template
├── new-outputs-safe-delete/    # Consolidated backup of all outputs
├── requirements.txt            # Python dependencies
├── .env                        # API keys (create this, not in git)
└── README.md                   # This file
```

## Class Folder Structure

Each class requires this structure (created automatically):

```
Class Name/
└── LLM/
    ├── lecture-input/          # Place M4A audio files here
    ├── lecture-output/         # Generated lecture notes appear here
    ├── lecture-processed/
    │   ├── audio/              # Processed M4A files moved here
    │   └── txt/                # Timestamped transcripts moved here
    ├── reading-input/          # Place reading TXT files here
    ├── reading-output/         # Generated reading notes appear here
    └── reading-processed/      # Processed reading files moved here
```

## Complete Setup Guide

### 1. Check Prerequisites

**Verify Python installation:**

```bash
python --version  # Should show 3.8 or higher
```

If not installed, download from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH" during installation.

### 2. Install FFmpeg

FFmpeg is **required** for audio processing.

**Windows (using Chocolatey):**

```bash
choco install ffmpeg
```

**Windows (manual):**

1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH

**Mac:**

```bash
brew install ffmpeg
```

**Verify installation:**

```bash
ffmpeg -version  # Should display version info
```

### 3. Set Up Project

**Navigate to project directory:**

```bash
cd path/to/smart-law-notes
```

**Create virtual environment:**

```bash
python -m venv venv
```

**Activate virtual environment:**

- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

You should see `(venv)` in your terminal prompt.

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:

- `faster-whisper` - Optimized audio transcription
- `torch`, `torchvision`, `torchaudio` - PyTorch (CPU version)
- `noisereduce` - Audio noise reduction
- `soundfile` - Audio file I/O
- `librosa` - Audio loading and processing
- `scipy` - Signal processing for bandpass filtering
- `tqdm` - Progress bars
- `google-generativeai` - Gemini API
- `python-dotenv` - Environment variable management

**Verify installation:**

```bash
python -c "from faster_whisper import WhisperModel; print('Success!')"
```

### 5. Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key (save it securely!)

**Note:** Gemini API has a free tier. Check current limits at [ai.google.dev/pricing](https://ai.google.dev/pricing).

### 6. Configure Environment Variables

**Create `.env` file in project root:**

```bash
# Windows
type nul > .env
```

**Add your API key:**

Open `.env` in a text editor and add:

```
GEMINI_API_KEY=your_actual_api_key_here
```

Replace `your_actual_api_key_here` with your key from step 5.

**Important:** Never commit `.env` to git (it's in `.gitignore`).

### 7. Configure Class Paths

**Edit `src/config.py`:**

Update the `CLASSES` list with your class folder paths:

```python
CLASSES = [
    Path("C:\\Users\\YourName\\Documents\\Law school\\Contracts"),
    Path("C:\\Users\\YourName\\Documents\\Law school\\Civ pro"),
    Path("C:\\Users\\YourName\\Documents\\Law school\\Torts"),
]
```

### 8. Create Prompt Files

### 9. Prepare Your Files

**For each class, add files to:**

- `Class Name/LLM/lecture-input/` ← Put `.m4a` audio files here
- `Class Name/LLM/reading-input/` ← Put `.txt` reading files here

### 10. Test Run

```bash
cd src
python main.py
```

**Expected behavior:**

1. ✓ Folder structure verification
2. ✓ Audio transcription with progress bar
3. ✓ LLM processing with status updates
4. ✓ Files moved to processed folders
5. ✓ Success summary displayed

**Check outputs:**

- `Class Name/LLM/lecture-output/` ← Generated lecture notes (.md)
- `Class Name/LLM/reading-output/` ← Generated reading notes (.md)
- `new-outputs-safe-delete/` ← Backup of all outputs

## Usage

### Running the Pipeline

```bash
cd src
python main.py
```

### What Happens

**Step 1: Folder Verification**

- Checks each class has required folder structure
- Creates missing folders automatically

**Step 2: Audio Transcription**

- Converts M4A files to WAV (16kHz, mono)
- Applies noise reduction to remove HVAC, shuffling, background noise
- Applies bandpass filter (80Hz-8000Hz) focusing on speech frequencies
- Normalizes audio levels to -20dB LUFS for consistent volume
- Transcribes using faster-whisper large-v3 model
- Generates timestamps in [HH:MM:SS] format for each segment
- Shows real-time progress bars
- Saves timestamped transcripts to `lecture-input/` folder
- Performance: 3-4x real-time (1 hour lecture = 15-20 minutes)

**Example transcript output:**

```
[00:00:15] Welcome to Lecture 12 on Contract Formation.
[00:00:32] Let's start with a review of offer and acceptance.
[00:01:05] The key concept here is mutual assent between parties.
```

**Step 3: Lecture Note Generation**

- Processes timestamped transcripts with Gemini
- Uses multithreading for parallel API calls
- Applies custom lecture prompt template
- Saves markdown notes to `lecture-output/`
- Moves transcripts to `lecture-processed/txt/`
- Moves audio files to `lecture-processed/audio/`

**Step 4: Reading Note Generation**

- Processes reading text files with Gemini
- Uses multithreading for parallel API calls
- Applies custom reading prompt template
- Saves markdown notes to `reading-output/`
- Moves reading files to `reading-processed/`

**Step 5: Backup**

- Copies all generated notes to `new-outputs-safe-delete/`
- Organized by class for easy access

## Configuration

### Basic Settings

Edit `src/config.py`:

```python
# Gemini model selection
GEMINI_MODEL = 'gemini-2.5-pro'  # or 'gemini-2.0-flash-exp' for faster/cheaper

# Parallel processing workers
MAX_AUDIO_WORKERS = 3   # Number of audio files to process simultaneously (2-3 recommended)
MAX_LLM_WORKERS = 5     # Number of concurrent API calls (5-10 works well)

# Class folders
CLASSES = [
    Path("C:\\path\\to\\Contracts"),
    Path("C:\\path\\to\\Civ pro"),
    Path("C:\\path\\to\\Torts"),
]
```

### Audio Processing (Advanced)

Audio settings are hardcoded in `src/audio_processor.py` for optimal CPU performance:

- Model: `large-v3` (most accurate)
- Device: `cpu` (AMD Ryzen 7 optimized)
- Compute type: `int8` (faster CPU inference)
- CPU threads: `4` (safe limit to avoid overheating)

**To reduce CPU usage** (if system gets too hot), edit `src/audio_processor.py` line 275:

```python
cpu_threads = 3  # Reduce from 4 to 3
```

### Optimization Tips

**For faster processing:**

```python
MAX_AUDIO_WORKERS = 2      # Process fewer files at once
MAX_LLM_WORKERS = 10       # More API calls in parallel
GEMINI_MODEL = 'gemini-2.0-flash-exp'  # Faster model
```

**For better quality:**

```python
GEMINI_MODEL = 'gemini-2.5-pro'  # Better model
```

**For cost efficiency:**

```python
GEMINI_MODEL = 'gemini-2.0-flash-exp'  # Free tier friendly
MAX_LLM_WORKERS = 3                    # Slower rate limits
```

## Troubleshooting

### Installation Issues

**"FFmpeg not found"**

- Solution: Run `choco install ffmpeg` and restart terminal
- Verify: `ffmpeg -version`

**"faster_whisper not found"**

- Solution: `pip install faster-whisper`
- Verify: `python -c "from faster_whisper import WhisperModel; print('Success!')"`

**"Module not found" errors**

- Solution: Ensure venv is activated (`(venv)` in prompt), then `pip install -r requirements.txt`

### Configuration Issues

**"GEMINI_API_KEY not found"**

- Check `.env` file exists in project root (not in `src/`)
- Verify format: `GEMINI_API_KEY=your_key` (no quotes, no spaces around `=`)
- Ensure API key is valid at [Google AI Studio](https://makersuite.google.com/)

**"Permission denied" or "Access denied"**

- Close programs using the audio files
- Run terminal as administrator (Windows)
- Check file permissions

**Script runs but no output**

- Verify files are in correct input folders
- Check file extensions (`.m4a` for audio, `.txt` for readings)
- Review class paths in `config.py` for typos
- Check terminal for error messages

### Performance Issues

**Slow transcription**

- Current settings are optimal for CPU (3-4x real-time)
- Cannot be improved without NVIDIA GPU with CUDA
- Process overnight for very long files
- Close other applications to free CPU resources

**Computer overheating**

- Reduce CPU threads in `audio_processor.py` from 4 to 3
- Reduce `MAX_AUDIO_WORKERS` to 2 or 1
- Ensure laptop has adequate ventilation

**Out of memory errors**

- Reduce `MAX_AUDIO_WORKERS` to process fewer files simultaneously (try 2 or 1)
- Close other applications to free RAM
- Process classes one at a time if needed

## Notes

- Input folders should be empty after successful processing
- All outputs are copied to `new-outputs-safe-delete/` for backup
- Processed files are moved (not deleted) for safety
- The script creates folder structure automatically
- Duplicate filenames get timestamps to avoid overwriting

## License

Personal use for law school studies.

---

**Good luck with your studies! 📚⚖️**
