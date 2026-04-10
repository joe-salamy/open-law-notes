## Overview

OpenLawNotes is a CLI pipeline for law students that transcribes lecture recordings (M4A via AssemblyAI with speaker diarization) and summarizes readings (PDF/DOCX/TXT/MD) into structured Markdown study notes using Google Gemini. The orchestrator (`main.py`) runs a 5-stage pipeline—Google Drive download (`src/audio/drive_downloader`), folder verification (`src/utils/folder_manager`), audio transcription (`src/audio/audio_processor`), lecture note generation, and reading note generation (`src/llm/llm_processor` → `src/llm/gemini_client`)—with parallel workers controlled by `config.py` settings `MAX_AUDIO_WORKERS` and `MAX_LLM_WORKERS`. All user configuration lives in `config.py` (not checked in) and `.env` for API keys; input files are moved (not deleted) to `*-processed/` folders after each run, and a convenience copy of all outputs lands in `new-outputs-safe-delete/` at the project root.

## Environment

- Activate venv before any pip/python commands: `venv\Scripts\Activate.ps1`
- Never pip install into the global or user environment — always use the venv.

## Git & Commits

- Read `.gitignore` before running any git commit to know what files to exclude.

## Off-Limits Files

- Never read from, write to, or git diff `scratchpad.md`.
- When running `/code-reviewer` or `/python-pro`, exclude diffs of files in `.claude/` and `docs/` — these are settings/prose, not reviewable code.

## Plan Mode

- When asking clarifying questions in plan mode, be liberal; when in doubt, ask more rather than fewer.

## Documentation

- Keep READMEs concise.
