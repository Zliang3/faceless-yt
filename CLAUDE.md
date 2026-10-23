# Faceless YouTube Automation

## Project Goal
Automated pipeline that takes a topic and produces a ready-to-upload MP4 video.

## Pipeline Steps
1. Generate script (via Claude API)
2. Generate voiceover MP3 (via ElevenLabs or VibeVoice)
3. Fetch B-roll video clips (via Pexels API)
4. Assemble final video with captions (via FFmpeg)

## Stack
- Language: Python 3.11+
- TTS: VibeVoice (local, default) or ElevenLabs API
- Stock footage: Pexels API
- Video assembly: FFmpeg (via subprocess or moviepy)
- Captions: Whisper (openai-whisper) for word-level timestamps

## Project Structure
faceless-yt/
├── CLAUDE.md
├── .env                  # API keys (never commit)
├── .env.example          # Template for .env
├── requirements.txt      # Python dependencies
├── main.py               # Entry point — takes a topic, runs full pipeline
├── steps/
│   ├── script.py         # Claude API script generation
│   ├── voice.py          # TTS — VibeVoice (local) or ElevenLabs
│   ├── footage.py        # Pexels clip fetching
│   └── assemble.py       # FFmpeg assembly
├── output/               # Final videos land here
└── tmp/                  # Temp clips/audio

## Usage
```
python main.py <topic> [--episode N] [--tts elevenlabs|vibevoice]
```
VibeVoice is the default. Use `--tts elevenlabs` to switch.

## API Keys (stored in .env)
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
PEXELS_API_KEY=

## VibeVoice Setup (one-time)
VibeVoice runs locally for free. Requires ~3GB disk for the model (auto-downloaded on first run).

```bash
# 1. Clone the community fork
git clone https://github.com/vibevoice-community/VibeVoice <path>

# 2. Install (skip gradio/demo deps)
pip install -e <path> --no-deps
pip install torch transformers==4.51.3 huggingface_hub soundfile einops diffusers accelerate==1.6.0 librosa scipy peft absl-py ml-collections

# 3. Set VIBEVOICE_REPO in .env (if not using default ~/.vibevoice/VibeVoice)
VIBEVOICE_REPO=<path>
```

Default clone location (no .env config needed): `~/.vibevoice/VibeVoice`

Available voices: Alice, Carter, Frank, Mary, Maya (default — kids-friendly female)

## Conventions
- Each step saves its output to tmp/ and returns the file path
- Functions should be idempotent where possible
- Always clean up tmp/ after a successful run
- Log each step with a timestamp
