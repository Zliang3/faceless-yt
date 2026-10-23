import json
import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent

ELEVENLABS_MODEL_ID = "eleven_turbo_v2_5"
# Maya: friendly female voice — best fit for kids content.
# Other options: Alice (woman), Carter (man), Frank (man), Mary (woman + bg music)
VIBEVOICE_DEFAULT_SPEAKER = "Maya"
VIBEVOICE_DEFAULT_MODEL = "microsoft/VibeVoice-1.5B"


def _pick_elevenlabs_voice(api_key: str) -> str:
    if voice_id := os.environ.get("ELEVENLABS_VOICE_ID"):
        return voice_id
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
    )
    with urllib.request.urlopen(req) as r:
        voices = json.loads(r.read())["voices"]
    voice = voices[0]
    log.info("Using voice: %s (%s)", voice["name"], voice["voice_id"])
    return voice["voice_id"]


def _generate_elevenlabs(full_text: str) -> str:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = _pick_elevenlabs_voice(api_key)

    payload = json.dumps(
        {
            "text": full_text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
    ).encode()

    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )

    out_path = ROOT / "tmp" / "voiceover.mp3"
    with urllib.request.urlopen(req) as r:
        out_path.write_bytes(r.read())

    log.info("Voiceover saved to %s", out_path)
    return str(out_path)


def _generate_vibevoice(full_text: str) -> str:
    """Generate voiceover using local VibeVoice-1.5B. Returns path to MP3.

    Requires the community fork cloned and installed:
      git clone https://github.com/vibevoice-community/VibeVoice ~/.vibevoice/VibeVoice
      pip install -e ~/.vibevoice/VibeVoice

    Set VIBEVOICE_REPO to override the default clone location.
    Set VIBEVOICE_SPEAKER to override the voice (default: Maya).
    """
    repo = Path(os.environ.get("VIBEVOICE_REPO", Path.home() / ".vibevoice" / "VibeVoice"))
    if not repo.exists():
        raise RuntimeError(
            f"VibeVoice repo not found at {repo}. "
            "Clone https://github.com/vibevoice-community/VibeVoice and set VIBEVOICE_REPO."
        )

    speaker = os.environ.get("VIBEVOICE_SPEAKER", VIBEVOICE_DEFAULT_SPEAKER)
    model = os.environ.get("VIBEVOICE_MODEL", VIBEVOICE_DEFAULT_MODEL)

    tmp_dir = ROOT / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # VibeVoice requires "Speaker N: text" format per paragraph.
    labeled = "\n\n".join(f"Speaker 1: {p.strip()}" for p in full_text.split("\n\n") if p.strip())
    txt_path = tmp_dir / "narration.txt"
    txt_path.write_text(labeled)

    out_dir = repo / "outputs"
    out_dir.mkdir(exist_ok=True)

    log.info("Running VibeVoice (model=%s, speaker=%s)...", model, speaker)

    result = subprocess.run(
        [
            sys.executable, "demo/inference_from_file.py",
            "--model_path", model,
            "--txt_path", str(txt_path),
            "--speaker_names", speaker,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"VibeVoice inference failed:\n{result.stderr}")

    # Inference script names output after the input txt stem.
    wav_path = out_dir / "narration_generated.wav"
    if not wav_path.exists():
        wavs = sorted(out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not wavs:
            raise RuntimeError("VibeVoice produced no output WAV in outputs/")
        wav_path = wavs[0]

    mp3_path = tmp_dir / "voiceover.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-q:a", "2", str(mp3_path)],
        check=True,
        capture_output=True,
    )

    log.info("VibeVoice voiceover saved to %s", mp3_path)
    return str(mp3_path)


def generate_voiceover(script_path: str, backend: str = "vibevoice") -> str:
    """Generate voiceover MP3 from script JSON. Returns path to MP3."""
    script = json.loads(Path(script_path).read_text())
    full_text = "\n\n".join(scene["narration"] for scene in script["scenes"])
    log.info("Generating voiceover (%d chars) via %s...", len(full_text), backend)

    if backend == "vibevoice":
        return _generate_vibevoice(full_text)
    return _generate_elevenlabs(full_text)
