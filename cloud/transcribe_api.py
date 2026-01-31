"""FastAPI server for cloud GPU transcription with faster-whisper."""
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from faster_whisper import WhisperModel
import uvicorn

app = FastAPI(title="Faster-Whisper Cloud GPU API")

# Global model instance (loaded once on startup)
MODEL = None

# API Key for authentication (set via environment variable)
API_KEY = os.getenv("SALAD_API_KEY")

if not API_KEY:
    raise ValueError("SALAD_API_KEY environment variable must be set")


def verify_api_key(authorization: str = Header(None)) -> None:
    """Verify the API key from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Expected format: "Bearer <api_key>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    provided_key = parts[1]
    if provided_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")



@app.on_event("startup")
async def load_model():
    """Load faster-whisper model on GPU at startup."""
    global MODEL
    model_name = os.getenv("MODEL_NAME", "large-v3")
    compute_type = os.getenv("COMPUTE_TYPE", "float16")

    print(f"Loading {model_name} on GPU with {compute_type}...")
    MODEL = WhisperModel(
        model_name,
        device="cuda",
        compute_type=compute_type,
        download_root="/models"  # Cache models
    )
    print(f"✓ Model loaded successfully")


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
    authorization: str = Header(None)
) -> Dict[str, Any]:
    """
    Transcribe uploaded WAV file using faster-whisper on GPU.

    Args:
        file: WAV audio file
        beam_size: Beam size for transcription (default: 5)
        language: Language code (default: en)
        word_timestamps: Include word-level timestamps (default: False)
        authorization: Bearer token for authentication

    Returns:
        JSON with segments and info
    """
    # Verify API key
    verify_api_key(authorization)

    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Save uploaded file to temp location
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file = tmp.name

        # Transcribe with faster-whisper
        segments, info = MODEL.transcribe(
            temp_file,
            beam_size=beam_size,
            language=language,
            word_timestamps=word_timestamps
        )

        # Convert segments to JSON-serializable format
        segments_list = [
            {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in segments
        ]

        # Convert info to dict
        info_dict = {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration
        }

        return {
            "segments": segments_list,
            "info": info_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
