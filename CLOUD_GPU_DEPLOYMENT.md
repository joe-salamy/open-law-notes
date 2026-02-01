# Joe's Handwritten Guide to Cloud Deployment

1. Go to [vast.ai](https://cloud.vast.ai/create/)
2. Filters:
   - 1 GPU
   - RTX 3090
   - North America
   - Price (inc.)
3. Pick whatever the first one is
4. Let it load
5. Click the blue IP address
6. Run curl http://[IP]:[PORT]/health (open ports listed at bottom)
7. Change .env url to http://[IP]:[PORT]/transcribe (open ports listed at bottom)
8. Run code, check GPU utilization
9. Delete instance when done (incurs costs when not in use, so fast to set up that not worth to leave on)

# If I make a new docker image:

- Change .env var names to vast.ai (I could now in all except the cloud.py)

# Cloud GPU Deployment Guide

This guide covers deploying the faster-whisper transcription service to **vast.ai** using Docker ENTRYPOINT launch mode.

## What Was Changed

### Local Code

- **`src/transcribe_client.py`**: HTTP client for cloud GPU API
- **`src/config.py`**: Added `USE_CLOUD_GPU`, API settings, diarization settings
- **`src/audio_processor.py`**: Cloud GPU integration with speaker alignment
- **`src/audio_helper.py`**: Speaker-to-transcript alignment functions

### Cloud Service Files (`cloud/`)

- **`transcribe_api.py`**: FastAPI server with /transcribe endpoint
- **`Dockerfile`**: CUDA + faster-whisper + pyannote.audio
- **`requirements.txt`**: Python dependencies

## Deploy to Vast.ai

### Step 1: Build and Push Docker Image

```bash
cd cloud
docker build -t faster-whisper-api:latest .
docker tag faster-whisper-api:latest yourusername/faster-whisper-api:latest
docker login
docker push yourusername/faster-whisper-api:latest
```

### Step 2: Generate API Keys

Generate a strong API key:

```bash
# Linux/Mac: openssl rand -hex 32
# Windows (PowerShell): -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
```

Get HuggingFace token (for speaker diarization):

- Token: https://huggingface.co/settings/tokens
- Accept license: https://huggingface.co/pyannote/speaker-diarization-3.1

### Step 3: Create Vast.ai Account

1. Go to https://vast.ai and sign up
2. Add payment method and credit ($5-10 minimum)

### Step 4: Rent a GPU Instance

1. Go to https://console.vast.ai/ → Search
2. Filter: RTX 3090, 24GB+ VRAM, 20GB+ disk, verified hosts
3. Click "Rent" on a suitable instance (~$0.20-0.30/hour)

### Step 5: Configure Instance (Docker ENTRYPOINT Launch Mode)

**Image Path/Tag:** `yourusername/faster-whisper-api:latest`

**Launch Mode:** Select **"Docker ENTRYPOINT"**

**Environment Variables:**

```
MODEL_NAME=large-v3
COMPUTE_TYPE=float16
CUDA_VISIBLE_DEVICES=0
VAST_API_KEY=your-api-key-from-step-2
HF_TOKEN=your-huggingface-token-here
```

**Disk Space:** 20 GB minimum

**Expose TCP Port:** `8000:8000`

Click "Rent" to create the instance.

### Step 6: Get Your API URL

Wait for instance to start (1-3 minutes). In "Open Ports" section:

```
Example: 74.48.78.46:25264 -> 8000/tcp
```

Your API URL: `http://74.48.78.46:25264/transcribe` (use external port, not 8000)

Test health: `curl http://74.48.78.46:25264/health`

### Step 7: Configure Local Environment

Update `.env` file:

```bash
VAST_API_URL=http://74.48.78.46:25264/transcribe
VAST_API_KEY=your-api-key-from-step-2
HF_TOKEN=your-huggingface-token-here
```

### Step 8: Test Transcription

```bash
python src/main.py
```

### Instance Management

**Viewing Logs:** Instances tab → Click instance → Logs

**Stopping (to save money):** Destroy instance when done

**Restarting:** Rent new instance, update `.env` with new IP

## API Reference

### POST /transcribe

```bash
# With speaker diarization
curl -X POST \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@audio.wav" \
  -F "enable_diarization=true" \
  -F "min_speakers=2" \
  -F "max_speakers=3" \
  http://your-ip:port/transcribe
```

**Parameters:** `file` (required), `enable_diarization`, `min_speakers`, `max_speakers`, `beam_size`, `language`

### GET /health

```bash
curl http://your-ip:port/health
```

Response: `{"status": "healthy", "model_loaded": true}`

## Speaker Diarization

Identifies "who spoke when" by running faster-whisper + pyannote.audio in parallel on GPU.

### Enable Diarization

1. Get HuggingFace token: https://huggingface.co/settings/tokens
2. Accept license: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Add to `.env`: `HF_TOKEN=hf_your_token_here`
4. Edit `src/config.py`:
   ```python
   ENABLE_DIARIZATION = True
   MIN_SPEAKERS = 2  # Optional: constrain speaker count
   MAX_SPEAKERS = 3
   ```

### Output Comparison

**Without:** `[00:00:00] Welcome to the lecture`

**With:** `[00:00:00] Speaker A: Welcome to the lecture`

### Performance

- Processing time: ~same (parallel GPU execution)
- GPU memory: ~10-12GB total (fits RTX 3090 24GB)

## Performance & Cost

**Local CPU:** 1 hour lecture = ~18 minutes transcription

**Cloud GPU (RTX 3090):** 1 hour lecture = ~6 minutes total (3x faster)

- Upload: ~3-5 minutes
- GPU transcription: ~1-2 minutes (20-30x real-time)
- Download: ~5 seconds

**Cost:** ~$0.20-0.30/hour (pay-per-second)

- Typical: 8 hours audio/week = ~$1-2/month

## Troubleshooting

**Connection refused:** Instance still starting (wait 2-3 minutes), check port mapping

**Invalid API key (401):** Verify same key in `.env` and instance environment variables

**Model not loaded (503):** Wait for model download to complete (check logs)

**GPU out of memory:** Ensure RTX 3090 24GB, don't run multiple transcriptions simultaneously

**Upload slow:** Limited by your internet upload speed

## Rollback to Local CPU

Set `USE_CLOUD_GPU = False` in `src/config.py`
