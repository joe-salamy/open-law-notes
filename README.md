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

**Verify it worked** — you'll do this in a terminal.

> **What is a terminal?** It's a plain text window where you type commands and press Enter to run them.
>
> - **Windows:** Press the **Start** button, type **Command Prompt**, and press Enter.
> - **Mac:** Press **Command + Space**, type **Terminal**, and press Enter.

Type the command for your system into the terminal and press Enter:

**Windows:**

```
python --version
```

**Mac:**

```
python3 --version
```

You should see something like `Python 3.12.0`. If you get an error instead, Python was not installed correctly — re-run the installer and make sure to check **"Add Python to PATH"** before clicking Install.

### Step 2 — Install FFmpeg

FFmpeg converts your .m4a recordings to the format AssemblyAI expects. You only need to do this once.

**Windows** — Install with [Chocolatey](https://chocolatey.org/install). Once Chocolatey is installed, open an **Administrator PowerShell** (press Start, type **PowerShell**, right-click it, and choose **"Run as administrator"**), then run:

```
choco install ffmpeg
```

**Mac** — Install with [Homebrew](https://brew.sh). Once Homebrew is installed, open Terminal and run:

```
brew install ffmpeg
```

**Verify it worked** — in your terminal (Command Prompt on Windows, Terminal on Mac), run:

```
ffmpeg -version
```

You should see a version number printed out. If you get an error, restart your terminal and try the install step again.

### Step 3 — Install OpenLawNotes

**Download the project.** Click the green **Code** button on this GitHub page and choose **Download ZIP**. Unzip it somewhere easy to find — like your Desktop or Documents folder. Note the full path to the folder (you'll need it in a moment).

**Open a terminal and navigate to the project folder.**

> **What does "navigate" mean?** You use the `cd` command (short for "change directory") to tell the terminal which folder to work in. You only need to do this once per session.

**Windows** — open Command Prompt and run (replace the path with wherever you unzipped the project):

```
cd C:\Users\YourName\Desktop\smart-law-notes
```

**Mac** — open Terminal and run:

```
cd /Users/YourName/Desktop/smart-law-notes
```

> **Tip:** The easiest way to get the right path is to open the folder in File Explorer (Windows) or Finder (Mac), then copy the address from the address bar. On Windows you can also type `cmd` directly into the File Explorer address bar to open a terminal already in that folder.

**Create a virtual environment.** This keeps OpenLawNotes's packages separate from anything else on your computer. Run this once, from inside the project folder:

**Windows:**

```
python -m venv venv
```

**Mac:**

```
python3 -m venv venv
```

**Activate the virtual environment.** You must do this every time you open a new terminal before running the tool:

**Windows:**

```
venv\Scripts\activate
```

**Mac:**

```
source venv/bin/activate
```

Your terminal prompt will change to show `(venv)` at the start — that means it worked.

> **Every time you want to run OpenLawNotes:** open a terminal, `cd` to the project folder, then activate the venv. The `QUICKSTART.md` file in this project has all three commands in one place for easy copy-paste.

**Install the required packages** (only needed once, after activating the venv):

**Windows:**

```
pip install -r requirements.txt
```

**Mac:**

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
copy config.py.example config.py
```

**Mac**

```
cp config.py.example config.py
```

**Open `config.py` and set your `PARENT_FOLDER`** — the folder that contains all your class folders:

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

Open `config.py` and update the `CLASSES` dict to your new class names. That's it — the folder structure is auto-created fresh for each new entry.

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

All settings live in `config.py` (your local copy of `config.py.example`).

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
5. Paste each ID into `config.py` next to the class name:
   ```python
   CLASSES = {
       "Contracts": "1aBcDeFgHiJkLmNoPqRsTuV",   # Drive folder ID
       "Torts":     "2xYzAbCdEfGhIjKlMnOpQr",    # Drive folder ID
       "Civ Pro":   None,                          # no Drive sync
   }
   ```

On first run, a browser window will open to authorize access. After that, auth is saved automatically.

**If you don't use Google Drive**, set `ENABLE_GOOGLE_DRIVE = False` in `config.py` and skip this section entirely. Just drop files into the input folders manually.

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

## Architecture

- System architecture and data flow: [docs/architecture.md](docs/architecture.md)
