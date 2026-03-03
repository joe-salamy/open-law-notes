# OpenLawNotes

Automatically transcribe lecture recordings and summarize readings into clean, structured notes — powered by AssemblyAI and Google Gemini.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)

---

## ⚠️ Recording Permissions

This tool processes audio recordings of lectures. Before recording any class session:

- **Always get explicit permission** from your professor before recording
- Check your school's academic policies on lecture recording
- Many professors prohibit recording — never record without consent
- Some jurisdictions have two-party or all-party consent laws for audio recording

This project takes no responsibility for recordings made without proper authorization.
By using this tool, you confirm that all recordings were made with appropriate permission.

---

## What It Does

- **Transcribes lecture audio** (.m4a files) using AssemblyAI — with speaker identification so you can tell professor from student
- **Generates structured lecture notes** from transcripts using Google Gemini
- **Summarizes readings** (PDF, DOCX, TXT, MD) into concise study notes
- **Copies all outputs** to a single folder for easy access after every run

---

## Quick Start (< 5 minutes)

### Step 1 — Install Python

Download Python 3.10 or newer from [python.org](https://www.python.org/downloads/). During installation, check **"Add Python to PATH"**.

Verify it worked:

**Windows**

```
python --version
```

**Mac**

```
python3 --version
```

### Step 2 — Install FFmpeg

FFmpeg converts your .m4a recordings to the format AssemblyAI expects. You only need to do this once.

**Windows** — Install with [Chocolatey](https://chocolatey.org/install) (run in Administrator PowerShell):

```
choco install ffmpeg
```

**Mac** — Install with [Homebrew](https://brew.sh):

```
brew install ffmpeg
```

Verify: `ffmpeg -version`

### Step 3 — Install OpenLawNotes

Download or clone this repo, then open a terminal in the project folder and run:

**Windows**

```
pip install -r requirements.txt
```

**Mac**

```
pip3 install -r requirements.txt
```

### Step 4 — Get API Keys

You need two free API keys:

**AssemblyAI** (for transcription)

1. Sign up at [assemblyai.com](https://www.assemblyai.com)
2. Copy your API key from the dashboard

**Google Gemini** (for note generation)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click "Get API key" and copy it

### Step 5 — Configure

**Copy the example env file:**

**Windows**

```
copy .env.example .env
```

**Mac**

```
cp .env.example .env
```

**Open `.env` and paste your keys:**

```
GEMINI_API_KEY=paste-your-gemini-key-here
ASSEMBLYAI_API_KEY=paste-your-assemblyai-key-here
```

**Copy the example config file:**

**Windows**

```
copy src\config.py.example src\config.py
```

**Mac**

```
cp src/config.py.example src/config.py
```

**Open `src/config.py` and set your `PARENT_FOLDER`** — the folder that contains all your class folders:

```python
PARENT_FOLDER = "C:/Users/YourName/Documents/Law school"
```

**How to find this path:**

- **Windows** — Right-click your law school folder in File Explorer and click **Copy address**. This gives you something like `C:\Users\YourName\Documents\Law school`. When pasting into `config.py`, replace each `\` with `/` (forward slash) — for example: `"C:/Users/YourName/Documents/Law school"`. Forward slashes always work on Windows in Python.
- **Mac** — Open Finder and navigate to your law school folder. Right-click (or Ctrl-click) it while holding the **Option** key, then click **"Copy [folder name] as Pathname"**.

**Then list your classes:**

```python
CLASSES = {
    "Contracts": None,
    "Civ Pro":   None,
}
```

Each name must exactly match the folder name on your computer. That's it. Run the pipeline:

```
python main.py
```

You should see step-by-step progress logged to your terminal.

---

## File Structure

Each class folder gets an `open-law-notes/` subfolder automatically created on the first run. Drop your files in the input folders before running.

```
Your Class Folder/
└── open-law-notes/
    ├── lecture-input/           ← Drop .m4a files here
    ├── lecture-output/          ← Generated lecture notes appear here ✓
    ├── lecture-processed/
    │   ├── audio/               ← Original .m4a files moved here after processing
    │   └── txt/                 ← Raw transcripts saved here
    ├── reading-input/           ← Drop PDFs, DOCX, TXT, MD files here
    ├── reading-output/          ← Generated reading notes appear here ✓
    └── reading-processed/       ← Original reading files moved here after processing
```

Files are **moved** (not deleted) into the processed folders after each run, so your original recordings and readings are always preserved.

A copy of every note is also placed in `new-outputs-safe-delete/` in the project folder for quick access.

---

## Updating for a New Semester

Open `src/config.py` and update the `CLASSES` dict to your new class names. That's it — the folder structure is auto-created fresh for each new entry.

```python
CLASSES = {
    "Contracts": None,
    "Civ Pro":   None,
}
```

---

## Running the Pipeline

**Full run** (transcribe audio + generate all notes):

```
python main.py
```

**Reading-only mode** (skip audio, only process reading files):

```
python main.py --read-only
```

---

## Configuration Reference

All settings live in `src/config.py` (your local copy of `src/config.py.example`).

| Setting               | Default                   | Description                                             |
| --------------------- | ------------------------- | ------------------------------------------------------- |
| `PARENT_FOLDER`       | _(your path)_             | Path to the folder containing all your class folders    |
| `CLASSES`             | _(your classes)_          | Dict of class names → Drive folder ID (or `None`)       |
| `ENABLE_GOOGLE_DRIVE` | `True`                    | Set `False` to skip Google Drive download (Step 0)      |
| `ENABLE_DIARIZATION`  | `True`                    | Identify speakers in transcripts                        |
| `MAX_SPEAKERS`        | `None`                    | Speaker count hint for diarization (None = auto)        |
| `GEMINI_MODEL`        | `gemini-3.1-pro-preview`  | Gemini model for note generation                        |
| `MAX_AUDIO_WORKERS`   | `2`                       | Parallel audio upload threads                           |
| `MAX_LLM_WORKERS`     | `5`                       | Parallel LLM processing threads                         |
| `LLM_BASE`            | `open-law-notes`          | Name of the auto-created subfolder in each class folder |
| `NEW_OUTPUTS_DIR`     | `new-outputs-safe-delete` | Local folder where copies of all outputs are placed     |

---

## Google Drive Setup (Optional)

If `ENABLE_GOOGLE_DRIVE = True`, the pipeline will automatically download new `.m4a` audio files from your Google Drive before processing. Each class can have its own Drive folder.

> **Why use this?** If you record lectures on a phone or another device, uploading the recording to Google Drive and letting the pipeline download it automatically is an easy way to move files over without manually copying them to your computer.

**To set up:**

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a project
2. Enable the **Google Drive API**
3. Create OAuth 2.0 credentials (Desktop app), download the JSON, and save it as `credentials.json` in the project root
4. For each class you want to sync, find its Drive folder ID:
   - Open the class folder in Google Drive in your browser
   - Look at the URL — it will look like:
     ```
     https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuV
     ```
   - The long string of letters and numbers at the end **is the folder ID**. Copy it.
5. Paste each ID into `src/config.py` next to the class name:
   ```python
   CLASSES = {
       "Contracts": "1aBcDeFgHiJkLmNoPqRsTuV",   # Drive folder ID
       "Torts":     "2xYzAbCdEfGhIjKlMnOpQr",    # Drive folder ID
       "Civ Pro":   None,                          # no Drive sync
   }
   ```

On first run, a browser window will open to authorize access. After that, auth is saved automatically.

**If you don't use Google Drive**, set `ENABLE_GOOGLE_DRIVE = False` in `src/config.py` and skip this section entirely. Just drop files into the input folders manually.

---

## Troubleshooting

**`ASSEMBLYAI_API_KEY environment variable is required`**
Your `.env` file is missing or the key isn't set. Open `.env` and make sure the key is pasted on the correct line with no extra spaces.

**`ffmpeg not found` or audio conversion errors**
FFmpeg isn't installed or isn't on your PATH. Re-run the FFmpeg install step and restart your terminal.

**`Class folder does not exist`**
The class name in your `CLASSES` dict doesn't match a real folder inside `PARENT_FOLDER`. Check for typos — the name must match exactly, including capitalization and spaces.

**Gemini API errors / model not available**
The model name in `GEMINI_MODEL` may be unavailable in your region or account tier. Try changing it to `gemini-1.5-pro` as a fallback.

**No files processed (empty output)**
Make sure you dropped files into the correct input folder: `open-law-notes/lecture-input/` for audio, `open-law-notes/reading-input/` for readings. The folder names must match exactly.

---

## License

MIT — see [LICENSE](LICENSE).
