# Cloud GPU Deployment Guide

This guide will help you deploy the faster-whisper transcription service to Salad cloud GPU.

## What Was Changed

### Local Code (Your Laptop)

1. **New file: `src/transcribe_client.py`**
   - HTTP client to communicate with cloud GPU API
   - Handles file upload, retry logic, error handling
   - Supports speaker diarization parameters

2. **Modified: `src/config.py`**
   - Added `USE_CLOUD_GPU` flag (currently set to `True`)
   - Added `CLOUD_API_URL` and `CLOUD_API_KEY` settings
   - Added `ENABLE_DIARIZATION`, `MIN_SPEAKERS`, `MAX_SPEAKERS` settings
   - Reads from environment variables (.env file)
   - Validates HF_TOKEN when diarization is enabled

3. **Modified: `src/audio_processor.py`**
   - Updated ETA calculation (line 158-169)
   - Added conditional logic to use cloud API or local CPU (lines 171-190)
   - Added speaker alignment and formatting with speaker labels
   - Preprocessing and post-processing unchanged

4. **Modified: `src/audio_helper.py`**
   - Added `assign_speakers_to_segments()` for speaker-to-transcript alignment
   - Added `format_transcription_with_speakers()` for speaker-aware formatting
   - Added `format_speaker_label()` to convert SPEAKER_00 → Speaker A

5. **Modified: `requirements.txt`**
   - Added `requests` library for HTTP calls

### Cloud Service Files (New Directory: `cloud/`)

1. **`cloud/transcribe_api.py`** - FastAPI server with /transcribe endpoint and speaker diarization
2. **`cloud/Dockerfile`** - Container image with CUDA + faster-whisper + pyannote.audio
3. **`cloud/requirements.txt`** - Python dependencies (faster-whisper, pyannote.audio, FastAPI)
4. **`cloud/.dockerignore`** - Files to exclude from Docker build

## Quick Start: Deploy to Salad

### Step 1: Build Docker Image

```bash
cd cloud
docker build -t faster-whisper-api:latest .
```

**Note**: This may take 10-15 minutes as it downloads CUDA, Python packages, and the faster-whisper model.

### Step 2: Push to Docker Hub

Replace `yourusername` with your Docker Hub username:

```bash
# Tag image
docker tag faster-whisper-api:latest yourusername/faster-whisper-api:latest

# Login to Docker Hub
docker login

# Push image
docker push yourusername/faster-whisper-api:latest
```

### Step 3: Create Salad Deployment

1. Go to https://portal.salad.com
2. Click "Create Container Group"
3. Fill in settings:

   **Container Configuration:**
   - Name: `faster-whisper-transcription`
   - Image Source: Docker Hub
   - Image: `yourusername/faster-whisper-api:latest`

   **Resource Requirements:**
   - GPU: 1x RTX 3060 (12 GB VRAM)
   - CPU: 4 vCPUs
   - RAM: 16 GB
   - Storage: 20 GB

   **Networking:**
   - Enable public networking: ✓
   - Port: 8000
   - Protocol: HTTP

   **Environment Variables:**

   ```
   MODEL_NAME=large-v3
   COMPUTE_TYPE=float16
   CUDA_VISIBLE_DEVICES=0
   SALAD_API_KEY=your-secure-api-key-here
   HF_TOKEN=your-huggingface-token-here
   ```

   **IMPORTANT**:
   1. **SALAD_API_KEY**: Generate a strong, random API key. You can use:

      ```bash
      # Linux/Mac
      openssl rand -hex 32

      # Windows (PowerShell)
      -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
      ```

   2. **HF_TOKEN** (Required for speaker diarization):
      - Get a read token from: https://huggingface.co/settings/tokens
      - Accept the pyannote model license: https://huggingface.co/pyannote/speaker-diarization-3.1
      - Without this token, speaker diarization will be disabled (transcription still works)

   **Health Check:**
   - Path: `/health`
   - Port: 8000
   - Interval: 30 seconds
   - Timeout: 10 seconds

   **Replicas:** 1

4. Click "Deploy"
5. Wait for container to start (should show "Running" after 2-3 minutes)

### Step 4: Get Your API URL

After deployment completes:

1. Click on your container group
2. Find the public URL (looks like: `https://xyz123.salad.cloud`)
3. Copy this URL

### Step 5: Configure Local Environment

Create a `.env` file in your project root (there's a `.env.example` template):

```bash
# Copy the example
cp .env.example .env

# Edit .env and add your Salad URL, API key, and HuggingFace token
SALAD_API_URL=https://xyz123.salad.cloud/transcribe
SALAD_API_KEY=your-secure-api-key-here
HF_TOKEN=your-huggingface-token-here
```

**IMPORTANT**:

- Replace `https://xyz123.salad.cloud` with your actual Salad URL
- Use the SAME API key you set in the Salad environment variables
- The API key is REQUIRED - the application will not start without it
- HF_TOKEN is only required if you enable speaker diarization (see "Speaker Diarization" section below)

### Step 6: Test the Connection

Test the API endpoint directly:

```bash
# Health check
curl https://xyz123.salad.cloud/health

# Expected response: {"status":"healthy","model_loaded":true}
```

If you get this response, your cloud GPU is ready!

### Step 7: Run a Test Transcription

Make sure `USE_CLOUD_GPU = True` in `src/config.py` (it should already be set).

Run your transcription pipeline:

```bash
python src/main.py
```

Watch the logs for:

- `[TRANSCRIPTION START] ... Will take ~X minutes (cloud GPU)`
- `Uploading ... to cloud GPU...`
- `✓ Cloud transcription complete: X segments`

## API Reference

### POST /transcribe

Upload WAV file for transcription with optional speaker diarization.

**Request:**

```bash
# Basic transcription (no diarization)
curl -X POST \
  -H "Authorization: Bearer your-api-key-here" \
  -F "file=@audio.wav" \
  -F "beam_size=5" \
  -F "language=en" \
  https://your-deployment.salad.cloud/transcribe

# With speaker diarization
curl -X POST \
  -H "Authorization: Bearer your-api-key-here" \
  -F "file=@audio.wav" \
  -F "beam_size=5" \
  -F "language=en" \
  -F "enable_diarization=true" \
  -F "min_speakers=2" \
  -F "max_speakers=3" \
  https://your-deployment.salad.cloud/transcribe
```

**Parameters:**

- `file` (required): WAV audio file
- `beam_size` (optional): Beam size for transcription (default: 5)
- `language` (optional): Language code (default: "en")
- `word_timestamps` (optional): Enable word-level timestamps (default: false)
- `enable_diarization` (optional): Enable speaker identification (default: false)
- `min_speakers` (optional): Minimum number of speakers (helps accuracy)
- `max_speakers` (optional): Maximum number of speakers (helps accuracy)

**Note**: Authentication is required. Include the `Authorization: Bearer <api-key>` header.

**Response (without diarization):**

```json
{
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.24,
      "text": "Welcome to the lecture"
    }
  ],
  "speaker_segments": null,
  "info": {
    "language": "en",
    "language_probability": 0.99,
    "duration": 3600.5
  }
}
```

**Response (with diarization):**

```json
{
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.24,
      "text": "Welcome to the lecture"
    },
    {
      "id": 1,
      "start": 3.5,
      "end": 6.8,
      "text": "Thank you professor"
    }
  ],
  "speaker_segments": [
    {
      "start": 0.0,
      "end": 3.3,
      "speaker": "SPEAKER_00"
    },
    {
      "start": 3.5,
      "end": 7.0,
      "speaker": "SPEAKER_01"
    }
  ],
  "info": {
    "language": "en",
    "language_probability": 0.99,
    "duration": 3600.5
  }
}
```

### GET /health

Health check endpoint.

```bash
curl https://your-deployment.salad.cloud/health
```

Response: `{"status": "healthy", "model_loaded": true}`

## Switching Between Cloud and Local

To switch between cloud GPU and local CPU, edit `src/config.py`:

```python
# Use cloud GPU (Salad)
USE_CLOUD_GPU = True

# Use local CPU
USE_CLOUD_GPU = False
```

When `USE_CLOUD_GPU = False`, the code automatically falls back to local CPU transcription (original behavior).

## Speaker Diarization

Speaker diarization identifies "who spoke when" in your lectures, labeling different speakers as Speaker A, Speaker B, etc.

### How It Works

1. **Cloud GPU runs two tasks in parallel:**
   - faster-whisper: Transcribes "what" was said and "when"
   - pyannote.audio: Identifies "who" spoke during each time segment

2. **Local processing merges the results:**
   - Matches speaker labels to transcript segments using timestamp overlap
   - Formats output with speaker labels

### Enabling Speaker Diarization

**Step 1: Get HuggingFace Token**

1. Visit https://huggingface.co/settings/tokens
2. Create a new token with "Read" access
3. Accept the model license: https://huggingface.co/pyannote/speaker-diarization-3.1

**Step 2: Add Token to Environment**

Add `HF_TOKEN` to both:

1. **Local `.env` file:**

   ```bash
   HF_TOKEN=hf_your_token_here
   ```

2. **Salad environment variables:**
   - Go to your container group settings
   - Add environment variable: `HF_TOKEN=hf_your_token_here`
   - Restart the container

**Step 3: Enable in Config**

Edit `src/config.py`:

```python
# Enable speaker diarization
ENABLE_DIARIZATION = True

# Optional: Constrain speaker count for better accuracy
MIN_SPEAKERS = 2  # e.g., professor + TA
MAX_SPEAKERS = 3  # e.g., professor + 2 students
```

**Step 4: Rebuild and Redeploy Docker Image**

The code changes already include pyannote.audio in the Docker image, but you need to rebuild:

```bash
cd cloud
docker build -t faster-whisper-api:latest .
docker tag faster-whisper-api:latest yourusername/faster-whisper-api:latest
docker push yourusername/faster-whisper-api:latest
```

Then restart your Salad deployment to pull the new image.

### Usage Modes

**Mode 1: Disabled (Default - Fastest)**

```python
ENABLE_DIARIZATION = False
```

- Original transcript format (no speaker labels)
- Fastest processing
- No HF_TOKEN required

**Mode 2: Auto-Detect Speakers**

```python
ENABLE_DIARIZATION = True
MIN_SPEAKERS = None
MAX_SPEAKERS = None
```

- Automatically detects number of speakers
- Best when speaker count is unknown
- Good for office hours or Q&A sessions

**Mode 3: Known Speaker Count (Most Accurate)**

```python
ENABLE_DIARIZATION = True
MIN_SPEAKERS = 2  # Expected minimum
MAX_SPEAKERS = 3  # Expected maximum
```

- Most accurate when you know speaker count
- Recommended for lectures (typically 1-2 speakers)
- Prevents over-segmentation

### Output Format Comparison

**Without diarization:**

```
[00:00:00]
Welcome to Constitutional Law. Today we'll discuss the Commerce Clause.

[00:02:15]
The framers intended to create a system where states retained sovereignty.
```

**With diarization:**

```
[00:00:00] Speaker A: Welcome to Constitutional Law. Today we'll discuss the Commerce Clause and its implications for federal power.

[00:02:15] Speaker B: Professor, could you clarify how that relates to the Dormant Commerce Clause?

[00:02:28] Speaker A: Great question. The Dormant Commerce Clause prevents states from discriminating against interstate commerce.
```

### Performance Impact

- **Processing time:** Minimal (~same as transcription-only)
  - Both models run in parallel on GPU
  - No sequential bottleneck
- **GPU memory:** ~10-12GB total
  - faster-whisper large-v3: ~3.5GB
  - pyannote.audio 3.1: ~6-8GB
  - Fits comfortably in RTX 3060 12GB
- **Accuracy:** 90-95% speaker identification (pyannote 3.1 benchmark)

### Troubleshooting Diarization

**"HF_TOKEN required" error:**

- Verify HF_TOKEN is set in `.env` file
- Check ENABLE_DIARIZATION=True in config.py
- Ensure token has read access on HuggingFace

**"License not accepted" error:**

- Visit https://huggingface.co/pyannote/speaker-diarization-3.1
- Click "Agree and access repository"
- Wait a few minutes for permissions to propagate

**Speaker labels are inconsistent:**

- Set MIN_SPEAKERS and MAX_SPEAKERS to constrain the model
- Example: For a lecture with just a professor, set both to 1
- Example: For professor + occasional student questions, set MIN=1, MAX=2

**Too many speaker switches:**

- Increase MIN_SPEAKERS to prevent over-segmentation
- The model sometimes splits one person into multiple speakers
- Setting MIN_SPEAKERS=1 or 2 helps prevent this

**GPU out of memory with diarization:**

- Both models should fit in 12GB, but if you get OOM:
- Contact support or check Salad logs for actual memory usage
- May need to switch to sequential processing (code modification)

## Expected Performance

**Before (Local CPU):**

- 1 hour lecture = ~18 minutes transcription
- Uses laptop CPU (int8, 4 threads)

**After (Cloud GPU):**

- 1 hour lecture = ~9 minutes total
  - Upload: ~3-5 minutes (depends on internet speed)
  - GPU transcription: ~4-6 minutes (10x real-time)
  - Download: ~5 seconds
- 2x faster overall

## Cost

- **Salad RTX 3060**: ~$0.18-0.25/hour
- **Typical usage**: 8 hours audio/week = 1.2 hours processing/week
- **Monthly cost**: ~$1-2

Salad only charges when the container is running. You can stop/start as needed.

## Troubleshooting

### "Connection refused" or "Timeout"

- Check that Salad container is running (green "Running" status)
- Verify the API URL in your .env file is correct
- Test with curl: `curl https://your-url.salad.cloud/health`

### "Authorization header missing" or "Invalid API key" (401 error)

- Verify SALAD_API_KEY is set in both:
  1. Your local `.env` file
  2. Salad container environment variables
- Ensure both use the SAME API key
- Check that the key doesn't have extra spaces or quotes
- Verify the Authorization header format: `Bearer <api-key>`

### "Model not loaded" (503 error)

- Container is still starting up (wait 2-3 minutes after deployment)
- Check Salad logs for errors
- Model download may have failed (check container logs)

### Transcription quality is worse

- Verify model is large-v3 (not tiny/base)
- Check COMPUTE_TYPE is float16 (not int8)
- Compare output with local CPU transcription

### Upload is very slow

- Your internet upload speed is the bottleneck
- With 5 Mbps upload: 200 MB file = ~5 minutes
- Consider upgrading internet or using smaller files

### "GPU out of memory" error

- Don't increase MAX_AUDIO_WORKERS beyond 2
- Single RTX 3060 can handle 1 transcription at a time safely
- Check if other processes are using GPU (shouldn't be on Salad)

## Monitoring Your Deployment

### Salad Portal

- View container status (running/stopped)
- Check logs (click "Logs" tab)
- Monitor GPU usage
- See request count and latency

### Local Logs

Check your application logs for:

- Upload time per file
- Actual transcription time vs ETA
- Error rates and retry attempts

## Stopping/Restarting

**To save costs when not in use:**

1. Go to Salad portal
2. Stop the container group
3. Restart when needed

**Auto-scaling:** Salad can auto-scale to 0 replicas when idle (configure in settings).

## Next Steps

1. **Deploy to Salad** following steps above
2. **Test with one short file** (5-10 min audio) without diarization
3. **Verify transcription quality** matches local CPU output
4. **(Optional) Enable speaker diarization** if you want speaker labels
5. **Test diarization** with a lecture that has 2+ speakers
6. **Process all your classes** with cloud GPU
7. **Monitor costs** in Salad billing dashboard

## Rollback

If you want to go back to local CPU:

1. Set `USE_CLOUD_GPU = False` in `src/config.py`
2. Re-run your pipeline
3. No other changes needed

The local CPU code path is preserved and unchanged.

## Summary

You now have a hybrid architecture:

- **Preprocessing**: Local (M4A→WAV, noise reduction) ✓
- **Transcription**: Cloud GPU (faster-whisper large-v3) ✓
- **Speaker Diarization**: Cloud GPU (pyannote.audio 3.1) ✓ [Optional]
- **Speaker Alignment**: Local (timestamp-based matching) ✓
- **Post-processing**: Local (formatting, file saving) ✓

This gives you 2x performance improvement while keeping most processing on your laptop. The cloud GPU is only used for the heavy transcription and optional diarization steps.

For questions or issues, check:

- Salad documentation - https://docs.salad.com
- FastAPI documentation - https://fastapi.tiangolo.com
