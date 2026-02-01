FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /models

RUN pip install --upgrade pip setuptools wheel

# Pin NumPy <2.0 for torch 2.1.0 compatibility
RUN pip install --no-cache-dir "numpy<2"

# Install pyannote.audio FIRST (it will pull CPU torch)
RUN pip install --no-cache-dir pyannote.audio==3.1.1

# Pin ctranslate2 for CUDA 12.1/cuDNN8 compatibility
RUN pip install --no-cache-dir ctranslate2==4.4.0 faster-whisper==1.0.3

# REINSTALL torch+torchaudio with CUDA *after* pyannote (overwrites CPU versions)
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121

# Add other dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    python-multipart==0.0.6 \
    requests

COPY transcribe_api.py /app/transcribe_api.py
WORKDIR /app

ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"

RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8', download_root='/models')"

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "transcribe_api:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "3600"]