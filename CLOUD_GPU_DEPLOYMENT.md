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
6. Run http://[Public IP]:[External Port]/health
7. Change .env url to http://[IP]:[PORT]/transcribe (open ports listed at bottom)
8. Run code, check GPU utilization
9. Delete instance when done (incurs costs when not in use, so fast to set up that not worth to leave on)

# Cloud GPU Deployment Guide

This guide will help you deploy the faster-whisper transcription service to cloud GPU providers. Two options are covered:

- **Salad**: Easiest setup with auto-scaling and HTTPS (~$0.18-0.25/hour)
- **Vast.ai**: More affordable with flexible on-demand or interruptible instances (~$0.08-0.18/hour)

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
   - GPU: 1x RTX 3090 (24 GB VRAM)
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

## Quick Start: Deploy to Vast.ai

Vast.ai is an alternative GPU cloud provider that offers competitive pricing through a marketplace of GPU rentals. It's ideal for cost-sensitive workloads and supports Docker deployments.

### Why Vast.ai?

**Pros:**

- Often cheaper than Salad (~$0.20-0.30/hour for RTX 3090)
- Large selection of GPUs
- Flexible on-demand or interruptible instances
- Direct SSH access for debugging
- Pay-per-second billing

**Cons:**

- Instances can be interrupted (especially cheaper "interruptible" ones)
- Setup requires more manual configuration
- Network reliability varies by host
- Must handle instance restarts

### Step 1: Build and Push Docker Image

Same as Salad (if you already did this for Salad, skip to Step 2):

```bash
cd cloud
docker build -t faster-whisper-api:latest .

# Tag and push to Docker Hub
docker tag faster-whisper-api:latest yourusername/faster-whisper-api:latest
docker login
docker push yourusername/faster-whisper-api:latest
```

### Step 2: Create Vast.ai Account

1. Go to https://vast.ai
2. Sign up and verify your email
3. Add payment method (credit card or crypto)
4. Add at least $5-10 credit to your account

### Step 3: Generate API Key

**For API Key Authentication:**

1. Generate a strong API key locally:

   ```bash
   # Linux/Mac
   openssl rand -hex 32

   # Windows (PowerShell)
   -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
   ```

2. Save this key - you'll need it for both the instance and your local `.env` file

**For HuggingFace Token (if using speaker diarization):**

1. Get token from: https://huggingface.co/settings/tokens
2. Accept license: https://huggingface.co/pyannote/speaker-diarization-3.1

### Step 4: Find and Rent a GPU Instance

1. Go to https://console.vast.ai/
2. Click "Search" in the top menu
3. Filter instances:

   **Minimum Requirements:**
   - GPU: RTX 3090 (24GB VRAM) or better
   - GPU RAM: ≥ 24 GB
   - Disk Space: ≥ 20 GB
   - Upload Speed: ≥ 100 Mbps (for faster API responses)
   - CUDA Version: ≥ 11.8

   **Recommended Filters:**
   - Sort by: "$/hour" (cheapest first)
   - Reliability: ≥ 95%
   - Check "Verified" hosts only
   - Instance Type: "On-demand" (more reliable) or "Interruptible" (cheaper but can be stopped)

4. Look for RTX 3090 24GB instances around $0.20-0.30/hour
5. Click "Rent" on a suitable instance

### Step 5: Configure Instance

When renting, you'll see a configuration screen:

**Image Path/Tag:**

```
yourusername/faster-whisper-api:latest
```

**Docker Options:**

Select "Use Jupyter Notebook Template: No" (we're running a custom API server)

**On-start Script:**

Leave empty (the Docker image handles startup automatically)

**Environment Variables:**

Click "Edit Env" and add:

```
MODEL_NAME=large-v3
COMPUTE_TYPE=float16
CUDA_VISIBLE_DEVICES=0
SALAD_API_KEY=your-api-key-from-step-3
HF_TOKEN=your-huggingface-token-here
```

**Important Notes:**

- Replace `your-api-key-from-step-3` with the key you generated
- Replace `your-huggingface-token-here` if using speaker diarization
- The env var is still called `SALAD_API_KEY` (code compatibility - works with both providers)

**Disk Space:**

- Requested: 20 GB minimum

**Expose TCP Port:**

Add port mapping:

```
8000:8000
```

This exposes your API on port 8000.

Click "Rent" to create the instance.

### Step 6: Wait for Instance to Start

1. Go to "Instances" tab
2. Wait for status to show "Running" (typically 1-3 minutes)
3. Look for the instance details panel

### Step 7: Get Your API URL

Once running, click on your instance to see the details panel. Look for the **"Open Ports"** section:

**Example from vast.ai:**

```
Open Ports:
74.48.78.46:25264 -> 8000/tcp
```

This shows:

- **Public IP Address**: `74.48.78.46`
- **External Port**: `25264` (this is what you connect to)
- **Internal Port**: `8000` (your container's port)

**Your API URL format:**

```
http://[Public IP]:[External Port]/transcribe
```

**Example:**

- If Open Ports shows: `74.48.78.46:25264 -> 8000/tcp`
- Your API URL is: `http://74.48.78.46:25264/transcribe`

**Important:** Use the external port (left side of `->`) NOT port 8000!

**Note:** Vast.ai uses HTTP (not HTTPS) unless you set up a reverse proxy. For production use, consider adding nginx with SSL.

### Step 8: Test the Instance

Test the health endpoint using your Public IP and External Port from the "Open Ports" section:

```bash
# Replace with your actual Public IP and External Port
# Format: http://[Public IP]:[External Port]/health
curl http://74.48.78.46:25264/health

# Expected response: {"status":"healthy","model_loaded":true}
```

**To get your exact URL:**

1. Look at "Open Ports" in your instance details
2. Copy the Public IP (e.g., `74.48.78.46`)
3. Copy the External Port (number before `->`, e.g., `25264`)
4. Test: `curl http://74.48.78.46:25264/health`

If the model is still loading, you'll get `"model_loaded":false`. Wait 2-3 minutes and try again.

### Step 9: Configure Local Environment

Update your `.env` file using the Public IP and External Port from "Open Ports":

```bash
# For Vast.ai - Use Public IP and External Port from "Open Ports" section
# Example: If "Open Ports" shows: 74.48.78.46:25264 -> 8000/tcp
SALAD_API_URL=http://74.48.78.46:25264/transcribe
SALAD_API_KEY=your-api-key-from-step-3
HF_TOKEN=your-huggingface-token-here
```

**How to find your URL:**

1. Click on your vast.ai instance
2. Find the "Open Ports" section
3. Look for the line: `[IP]:[PORT] -> 8000/tcp`
4. Your URL is: `http://[IP]:[PORT]/transcribe`

**Example:**

- Open Ports: `74.48.78.46:25264 -> 8000/tcp`
- SALAD_API_URL: `http://74.48.78.46:25264/transcribe`

**Security Warning:**

- Vast.ai instances use HTTP by default (no encryption)
- Your API key provides authentication
- For sensitive data, consider setting up an SSH tunnel or VPN
- Alternatively, deploy a reverse proxy with SSL on the instance

### Step 10: Test Transcription

Run your transcription pipeline:

```bash
python src/main.py
```

Monitor the logs for successful cloud GPU transcription.

### Step 11: (Optional) Set Up SSH Tunnel for Security

For better security, you can tunnel the API through SSH:

```bash
# Get SSH connection from Vast.ai console
ssh -L 8000:localhost:8000 root@123.45.67.89 -p 12345

# Keep this terminal open
```

Then update `.env` to use localhost:

```bash
SALAD_API_URL=http://localhost:8000/transcribe
```

Now all traffic goes through the encrypted SSH tunnel.

### Vast.ai Instance Management

**Viewing Logs:**

1. Go to "Instances" tab on Vast.ai
2. Click your instance
3. Click "Logs" to see Docker container output
4. Or SSH in: `docker logs -f $(docker ps -q)`

**Stopping Instance (to save money):**

1. Go to "Instances" tab
2. Click "Destroy" on your instance
3. You can rent a new one later (will need to reconfigure)

**Restarting After Interruption:**

If your instance gets interrupted (interruptible instances):

1. Rent a new instance following Step 4-5
2. Update the IP address in your `.env` file
3. Resume transcriptions

**Pro Tip:** Use on-demand instances for important work, interruptible for batch processing overnight.

### Cost Comparison: Vast.ai vs Salad

| Provider                    | RTX 3090 24GB    | Billing    | Reliability             |
| --------------------------- | ---------------- | ---------- | ----------------------- |
| **Vast.ai (on-demand)**     | ~$0.25-0.35/hour | Per-second | High (99%+)             |
| **Vast.ai (interruptible)** | ~$0.18-0.25/hour | Per-second | Medium (can be stopped) |
| **Salad**                   | ~$0.35-0.45/hour | Per-minute | High (99%+)             |

**Monthly cost estimate (8 hours audio/week = 1.2 hours processing/week):**

- Vast.ai on-demand: ~$1.25-1.75/month
- Vast.ai interruptible: ~$0.90-1.25/month
- Salad: ~$1.75-2.25/month

**Recommendation:**

- **Vast.ai on-demand**: Best balance of cost and reliability
- **Vast.ai interruptible**: Cheapest, but may need to restart occasionally
- **Salad**: Easiest setup, most reliable, slightly higher cost

### Vast.ai-Specific Troubleshooting

**"Connection refused" when testing health endpoint:**

- Instance may still be starting (wait 2-3 minutes)
- Check that port 8000 is exposed in instance settings
- Verify firewall isn't blocking the port
- SSH into instance and run: `docker ps` to verify container is running

**Instance keeps getting interrupted:**

- Switch from "interruptible" to "on-demand" instances
- Look for hosts with higher reliability scores (≥ 98%)
- Check "Verified" hosts only

**Model download is very slow:**

- Some hosts have slower internet
- Look for instances with higher "Download" and "Upload" speeds
- Consider destroying and renting from a different host

**Port 8000 not accessible:**

- Verify port mapping in instance configuration: `8000:8000`
- Check instance firewall settings
- Try accessing from different network (some ISPs block certain ports)

**"CUDA out of memory" errors:**

- Ensure you're using RTX 3090 with 24GB VRAM minimum
- Don't run multiple transcriptions simultaneously
- Check that only one Docker container is running: `docker ps`

**Lost instance IP after restart:**

- Vast.ai doesn't provide stable IPs
- After any restart, get new IP from "Instances" tab
- Update `.env` file with new IP
- Consider using a dynamic DNS service or SSH tunnel to localhost

**Cost is higher than expected:**

- Check if instance is left running when not in use
- Destroy instances when done (unlike Salad, Vast doesn't auto-scale to 0)
- Use interruptible instances for non-urgent batch processing

### Creating a Reusable Vast.ai Template (Optional)

If you plan to use vast.ai regularly, creating a template saves time by pre-configuring your Docker image, environment variables, and settings. You can then launch instances with one click.

**When to Create a Template:**

- You've deployed manually once and everything works
- You want to quickly restart instances without reconfiguring
- You plan to use vast.ai for multiple projects with similar setups

**Step-by-Step: Create Template**

1. **Go to Vast.ai Templates Page**

   Navigate to: https://console.vast.ai/templates/

2. **Click "Create Template"**

3. **Fill in Template Fields:**

   **Identification Section:**
   - **Template Name**: `faster-whisper-transcription`
     - Short, descriptive name for your template

   - **Template Description**: `GPU-accelerated transcription API with faster-whisper large-v3 and speaker diarization`
     - Brief description of what this template does

   **Docker Repository And Environment:**
   - **Image Path:Tag**: `yourusername/faster-whisper-api:latest`
     - Replace `yourusername` with your Docker Hub username
     - This is the same image you built and pushed in Step 1
     - Format: `username/image:tag` or `registry.com/username/image:tag`

   - **Version Tag**: Leave blank (uses `:latest` from Image Path)
     - Only fill this if you want to override the tag specified in Image Path

   **Docker Options:**
   - **Docker create/run options**: Leave blank
     - Advanced users can add flags like `-e TZ=UTC -h hostname`
     - Not needed for our use case

   - **Ports**: Leave blank (we'll configure this below)
     - Port mapping is configured separately in the "Launch Mode" section

   **Environment Variables:**

   Click "+ Add Environment Variable" for each of these:

   | Key                    | Value                         | Notes                                             |
   | ---------------------- | ----------------------------- | ------------------------------------------------- |
   | `MODEL_NAME`           | `large-v3`                    | Whisper model version                             |
   | `COMPUTE_TYPE`         | `float16`                     | GPU precision (float16 for RTX 3090)              |
   | `CUDA_VISIBLE_DEVICES` | `0`                           | Use first GPU                                     |
   | `SALAD_API_KEY`        | `your-api-key-here`           | Replace with your generated API key (from Step 3) |
   | `HF_TOKEN`             | `your-huggingface-token-here` | Only needed if using speaker diarization          |

   **IMPORTANT**: Replace the placeholder values with your actual keys before saving the template.

   **Select Launch Mode:**
   - Select: **"Interactive shell server, SSH"**
     - This launches the Docker container with our API server
     - Our Dockerfile's `CMD` automatically starts the FastAPI server

   - Do NOT select "Jupyter-python notebook + SSH" (we're not using Jupyter)
   - Do NOT select "Docker ENTRYPOINT" (we use CMD in Dockerfile)

   **Args to pass to docker ENTRYPOINT:**
   - Leave blank
     - Our Docker image handles startup automatically via `CMD`

   **On-start Script:**
   - Leave blank
     - No additional bash commands needed
     - The Docker container starts the API server automatically

   **Extra Filters (CLI Format):**

   Optional filters to auto-select instances. Example:

   ```
   verified=true gpu_name=RTX_3090 num_gpus=1 disk_space>=20
   ```

   This restricts instances to:
   - `verified=true`: Only verified hosts (more reliable)
   - `gpu_name=RTX_3090`: Only RTX 3090 GPUs
   - `num_gpus=1`: Exactly 1 GPU
   - `disk_space>=20`: At least 20 GB disk

   **Recommended**: `verified=true num_gpus=1 disk_space>=20`

   **Docker Repository Authentication:**

   Only fill this if you're using a private Docker registry (Docker Hub private repo, GitHub Container Registry with authentication, etc.).

   **For public Docker Hub images, leave this section blank.**

   If using private registry:
   - **Server**: `docker.io` (for Docker Hub) or `ghcr.io` (for GitHub Container Registry)
   - **Docker Username**: Your Docker Hub or registry username
   - **Docker Access Token**: Docker Hub access token or registry token (NOT your password)

   **Disk Space (Container + Volume):**
   - **Container disk size**: `20` GB
     - Minimum: 20 GB (model + dependencies + workspace)
     - Recommended: 30-40 GB if you want more buffer

   - **Add recommended volume settings**: Leave unchecked
     - Not needed for our use case (no persistent data)

4. **Click "Save Template"**

   Your template is now saved and ready to use.

**Using Your Template to Launch Instances:**

1. Go to https://console.vast.ai/
2. Click "Search" to browse available instances
3. Apply filters (RTX 3090, North America, etc.)
4. Click "Rent" on a suitable instance
5. In the configuration screen:
   - Click the "Template" dropdown at the top
   - Select your template: `faster-whisper-transcription`
   - All fields auto-populate from your template
6. **Add port mapping** (templates don't save this):
   - In the "Expose TCP Port" section, add: `8000:8000`
7. Click "Rent" to launch

**Note**: Port mappings are NOT saved in templates (vast.ai limitation). You must add the port mapping (`8000:8000`) each time you launch an instance.

**Updating Your Template:**

If you update your Docker image or environment variables:

1. Go to https://console.vast.ai/templates/
2. Click "Edit" on your template
3. Update the fields (e.g., new `HF_TOKEN`, different image tag)
4. Click "Save Template"

All future instances will use the updated configuration.

**CLI Alternative (Advanced):**

You can also create templates via the vast.ai CLI:

```bash
# Install vast CLI
pip install vastai

# Create template from JSON
vastai create template \
  --name "faster-whisper-transcription" \
  --image "yourusername/faster-whisper-api:latest" \
  --env MODEL_NAME=large-v3 \
  --env COMPUTE_TYPE=float16 \
  --env CUDA_VISIBLE_DEVICES=0 \
  --env SALAD_API_KEY=your-api-key-here \
  --env HF_TOKEN=your-token-here \
  --disk 20

# Launch instance from template
vastai search offers 'reliability>0.95 num_gpus=1 gpu_name=RTX_3090' \
  --order 'dph_total+' \
  | head -n 1 \
  | vastai create instance --template faster-whisper-transcription
```

See vast.ai CLI docs: https://vast.ai/docs/cli/commands

### Switching Between Providers

Your code works with both Salad and Vast.ai. Just update the `.env` file:

**For Salad:**

```bash
SALAD_API_URL=https://xyz123.salad.cloud/transcribe
```

**For Vast.ai:**

```bash
SALAD_API_URL=http://123.45.67.89:8000/transcribe
```

The rest of the configuration remains the same.

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
  - Fits easily in RTX 3090 24GB (12GB+ headroom)
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

- Both models should fit comfortably in 24GB VRAM:
  - faster-whisper large-v3: ~3.5GB
  - pyannote.audio 3.1: ~6-8GB
  - Total: ~10-12GB (leaves 12GB+ headroom on RTX 3090)
- If you still get OOM, check Salad/Vast logs for actual memory usage

## Expected Performance

**Before (Local CPU):**

- 1 hour lecture = ~18 minutes transcription
- Uses laptop CPU (int8, 4 threads)

**After (Cloud GPU - RTX 3090):**

- 1 hour lecture = ~6 minutes total
  - Upload: ~3-5 minutes (depends on internet speed)
  - GPU transcription: ~1-2 minutes (20-30x real-time)
  - Download: ~5 seconds
- 3x faster overall

## Cost

- **Salad RTX 3090**: ~$0.35-0.45/hour
- **Vast.ai RTX 3090**: ~$0.20-0.35/hour
- **Typical usage**: 8 hours audio/week = 0.8 hours processing/week (faster with RTX 3090)
- **Monthly cost**: ~$1-2

Both providers only charge when instances are running. You can stop/start as needed.

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

1. **Choose a provider**: Salad (easier) or Vast.ai (cheaper)
2. **Deploy to your chosen provider** following steps above
3. **Test with one short file** (5-10 min audio) without diarization
4. **Verify transcription quality** matches local CPU output
5. **(Optional) Enable speaker diarization** if you want speaker labels
6. **Test diarization** with a lecture that has 2+ speakers
7. **Process all your classes** with cloud GPU
8. **Monitor costs** in your provider's billing dashboard

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
- Vast.ai documentation - https://vast.ai/docs
- FastAPI documentation - https://fastapi.tiangolo.com
