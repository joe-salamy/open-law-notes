"""FastAPI server for cloud GPU transcription with faster-whisper."""

"""Note: Warnings are okay in this file, since it runs in Docker (not locally)."""

import os
import tempfile
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
import uvicorn

app = FastAPI(title="Faster-Whisper Cloud GPU API")

# Global model instances (loaded once on startup)
MODEL = None
DIARIZATION_PIPELINE = None

# API Key for authentication (set via environment variable)
API_KEY = os.getenv("VAST_API_KEY")

if not API_KEY:
    raise ValueError("VAST_API_KEY environment variable must be set")


def verify_api_key(authorization: str = Header(None)) -> None:
    """Verify the API key from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Expected format: "Bearer <api_key>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    provided_key = parts[1]
    if provided_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.on_event("startup")
async def load_model():
    """Load faster-whisper model and diarization pipeline on GPU at startup."""
    global MODEL, DIARIZATION_PIPELINE
    model_name = os.getenv("MODEL_NAME", "large-v3")
    compute_type = os.getenv("COMPUTE_TYPE", "float16")

    print(f"Loading {model_name} on GPU with {compute_type}...")
    MODEL = WhisperModel(
        model_name,
        device="cuda",
        compute_type=compute_type,
        download_root="/models",  # Cache models
    )
    print(f"✓ Model loaded successfully")

    # Load pyannote diarization if HF_TOKEN provided
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        try:
            from pyannote.audio import Pipeline
            import torch

            print(f"Loading pyannote.audio diarization pipeline...")
            DIARIZATION_PIPELINE = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", use_auth_token=hf_token
            )
            DIARIZATION_PIPELINE.to(torch.device("cuda"))
            print(f"✓ Diarization pipeline loaded successfully")
        except Exception as e:
            print(f"Warning: Failed to load diarization pipeline: {e}")
            print(f"Transcription will work, but diarization will be unavailable")
            DIARIZATION_PIPELINE = None
    else:
        print(f"HF_TOKEN not set - diarization will be unavailable")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "model_loaded": True}


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    beam_size: int = Form(5),
    language: str = Form("en"),
    word_timestamps: bool = Form(False),
    enable_diarization: bool = Form(False),
    min_speakers: int = Form(None),
    max_speakers: int = Form(None),
    authorization: str = Header(None),
):
    """
    Transcribe uploaded audio file using faster-whisper on GPU.
    Streams progress updates to keep connection alive during long transcriptions.

    Args:
        file: Audio file (WAV or FLAC)
        beam_size: Beam size for transcription (default: 5)
        language: Language code (default: en)
        word_timestamps: Include word-level timestamps (default: False)
        enable_diarization: Enable speaker diarization (default: False)
        min_speakers: Minimum number of speakers (optional)
        max_speakers: Maximum number of speakers (optional)
        authorization: Bearer token for authentication

    Returns:
        Streaming response with newline-delimited JSON:
        - Progress updates: {"type": "progress", "message": "..."}
        - Final result: {"type": "result", "data": {...}}
    """
    # Verify API key
    verify_api_key(authorization)

    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    async def generate_stream():
        temp_file = None
        try:
            # Save uploaded file (determine extension from filename)
            file_ext = Path(file.filename).suffix or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_file = tmp.name

            yield json.dumps({"type": "progress", "message": "File uploaded, starting transcription..."}) + "\n"

            # Run transcription in background thread (GPU operations block event loop)
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(_do_transcription, temp_file, beam_size, language, word_timestamps)

            # Send heartbeat every 30 seconds while transcription runs
            start_time = time.time()
            while not future.done():
                await asyncio.sleep(30)
                elapsed = int(time.time() - start_time)
                yield json.dumps({"type": "progress", "message": f"Transcribing... ({elapsed}s elapsed)"}) + "\n"

            # Get transcription result
            segments_list, info_dict = future.result()

            # Run diarization if enabled
            speaker_segments = None
            if enable_diarization and DIARIZATION_PIPELINE:
                try:
                    yield json.dumps({"type": "progress", "message": "Running speaker diarization..."}) + "\n"

                    diarization_kwargs = {}
                    if min_speakers is not None:
                        diarization_kwargs["min_speakers"] = min_speakers
                    if max_speakers is not None:
                        diarization_kwargs["max_speakers"] = max_speakers

                    # Run diarization in background thread
                    future_diarize = executor.submit(_do_diarization, temp_file, diarization_kwargs)

                    # Send heartbeat during diarization
                    while not future_diarize.done():
                        await asyncio.sleep(30)
                        yield json.dumps({"type": "progress", "message": "Diarization in progress..."}) + "\n"

                    speaker_segments = future_diarize.result()
                except Exception as e:
                    print(f"Warning: Diarization failed: {e}")
                    speaker_segments = None

            # Send final result
            result = {
                "segments": segments_list,
                "speaker_segments": speaker_segments,
                "info": info_dict,
            }
            yield json.dumps({"type": "result", "data": result}) + "\n"

            executor.shutdown(wait=True)

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

    return StreamingResponse(generate_stream(), media_type="application/x-ndjson")


def _do_transcription(temp_file: str, beam_size: int, language: str, word_timestamps: bool):
    """Run transcription in background thread (blocking GPU operation)."""
    segments, info = MODEL.transcribe(
        temp_file,
        beam_size=beam_size,
        language=language,
        word_timestamps=word_timestamps,
    )

    # Convert segments to JSON-serializable format
    segments_list = [
        {"id": seg.id, "start": seg.start, "end": seg.end, "text": seg.text}
        for seg in segments
    ]

    # Convert info to dict
    info_dict = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
    }

    return segments_list, info_dict


def _do_diarization(temp_file: str, diarization_kwargs: dict):
    """Run diarization in background thread (blocking GPU operation)."""
    diarization = DIARIZATION_PIPELINE(temp_file, **diarization_kwargs)
    speaker_segments = [
        {"start": turn.start, "end": turn.end, "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    return speaker_segments


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
