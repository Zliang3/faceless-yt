import json
import logging
import math
import os
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

KLING_BASE = "https://api.klingai.com"
LEONARDO_BASE = "https://cloud.leonardo.ai/api/rest/v1"
LEONARDO_IMAGE_MODEL = "b24e16ff-06e3-43eb-8d33-4416c2d75876"  # Phoenix

BG_COLORS = ["0x1a1a2e", "0x16213e", "0x0f3460", "0x1b262c", "0x2c003e", "0x162447"]


def _ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _parse_time(t: str) -> int:
    """'M:SS' or 'MM:SS' → seconds."""
    m, s = t.split(":")
    return int(m) * 60 + int(s)


# ── Kling API helpers ─────────────────────────────────────────────────────────

def _kling_token(ak: str, sk: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iss": ak, "exp": now + 1800, "nbf": now - 5},
        sk,
        headers={"alg": "HS256", "typ": "JWT"},
    )


def _kling_headers(ak: str, sk: str) -> dict:
    return {"Authorization": f"Bearer {_kling_token(ak, sk)}", "Content-Type": "application/json"}


def _submit_job(ak: str, sk: str, prompt: str, duration: int, mode: str) -> str:
    """Submit a text-to-video job. Returns task_id. Retries on 429."""
    body = {
        "model_name": "kling-v1",
        "prompt": prompt,
        "mode": mode,
        "aspect_ratio": "16:9",
        "duration": str(duration),
    }
    for attempt in range(5):
        resp = requests.post(f"{KLING_BASE}/v1/videos/text2video", headers=_kling_headers(ak, sk), json=body)
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            log.info("  Rate limited — waiting %ds before retry %d/5", wait, attempt + 1)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Kling submit error: {data}")
        return data["data"]["task_id"]
    raise RuntimeError("Kling submit failed after 5 retries (rate limit)")


def _poll_job(ak: str, sk: str, task_id: str, timeout: int = 600) -> str:
    """Poll until job succeeds. Returns video URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{KLING_BASE}/v1/videos/text2video/{task_id}",
            headers=_kling_headers(ak, sk),
        )
        resp.raise_for_status()
        data = resp.json()
        status = data["data"]["task_status"]
        if status == "succeed":
            return data["data"]["task_result"]["videos"][0]["url"]
        if status == "failed":
            raise RuntimeError(f"Kling job {task_id} failed: {data}")
        log.info("  [%s] status=%s — sleeping 15s", task_id[:8], status)
        time.sleep(15)
    raise TimeoutError(f"Kling job {task_id} timed out after {timeout}s")


def _download(url: str, out_path: Path) -> str:
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(65536):
            f.write(chunk)
    return str(out_path)


# ── Main Kling footage generator ──────────────────────────────────────────────

def _kling_footage(script: dict, ak: str, sk: str, mode: str) -> list[str]:
    """Generate one or more Kling clips per scene. Returns ordered clip paths."""
    tmp_dir = ROOT / "tmp"
    scenes = script["scenes"]
    total_script_s = script.get("total_duration_seconds", 240)

    # Build job list: for each scene, generate ceil(scene_dur / 10) × 10s clips
    jobs: list[tuple[str, int, int]] = []  # (prompt, clip_idx, clip_dur)
    for scene in scenes:
        start = _parse_time(scene["start_time"])
        end = _parse_time(scene["end_time"])
        scene_dur = max(end - start, 1)
        n_clips = math.ceil(scene_dur / 10)
        clip_dur = 10 if scene_dur > 5 else 5
        for _ in range(n_clips):
            jobs.append((scene["visual_description"], clip_dur))

    log.info("Submitting %d Kling jobs (mode=%s)...", len(jobs), mode)
    task_ids: list[tuple[str, int]] = []
    for i, (prompt, clip_dur) in enumerate(jobs):
        task_id = _submit_job(ak, sk, prompt, clip_dur, mode)
        task_ids.append((task_id, clip_dur))
        log.info("  Job %d/%d submitted: %s (%ds)", i + 1, len(jobs), task_id[:8], clip_dur)
        time.sleep(3)

    log.info("All jobs submitted — polling for completion...")
    clip_paths: list[str] = []
    for i, (task_id, clip_dur) in enumerate(task_ids):
        log.info("Waiting for job %d/%d (%s)...", i + 1, len(task_ids), task_id[:8])
        video_url = _poll_job(ak, sk, task_id)
        out_path = tmp_dir / f"kling_{i:03d}.mp4"
        _download(video_url, out_path)
        clip_paths.append(str(out_path))
        log.info("  Downloaded clip %d/%d", i + 1, len(task_ids))

    return clip_paths


# ── Leonardo AI helpers ───────────────────────────────────────────────────────

def _leonardo_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _leonardo_generate_image(api_key: str, prompt: str) -> str:
    """Submit image generation job. Returns image_id (not generation_id)."""
    resp = requests.post(
        f"{LEONARDO_BASE}/generations",
        headers=_leonardo_headers(api_key),
        json={
            "prompt": prompt,
            "modelId": LEONARDO_IMAGE_MODEL,
            "width": 1280,
            "height": 720,
            "num_images": 1,
        },
    )
    resp.raise_for_status()
    generation_id = resp.json()["sdGenerationJob"]["generationId"]
    log.info("  Image job submitted: %s", generation_id[:8])

    for _ in range(60):
        time.sleep(5)
        r = requests.get(f"{LEONARDO_BASE}/generations/{generation_id}", headers=_leonardo_headers(api_key))
        r.raise_for_status()
        data = r.json()["generations_by_pk"]
        if data["status"] == "COMPLETE":
            image_id = data["generated_images"][0]["id"]
            log.info("  Image complete: %s", image_id[:8])
            return image_id
    raise TimeoutError(f"Leonardo image generation timed out: {generation_id}")


def _leonardo_generate_motion(api_key: str, image_id: str, prompt: str) -> str:
    """Animate an image into a motion clip. Returns video URL."""
    resp = requests.post(
        f"{LEONARDO_BASE}/generations-image-to-video",
        headers=_leonardo_headers(api_key),
        json={"imageId": image_id, "imageType": "GENERATED", "prompt": prompt, "model": "MOTION2"},
    )
    resp.raise_for_status()
    generation_id = resp.json()["motionVideoGenerationJob"]["generationId"]
    log.info("  Motion job submitted: %s", generation_id[:8])

    for _ in range(60):
        time.sleep(10)
        r = requests.get(f"{LEONARDO_BASE}/generations/{generation_id}", headers=_leonardo_headers(api_key))
        r.raise_for_status()
        data = r.json()["generations_by_pk"]
        if data["status"] == "COMPLETE":
            url = data["generated_images"][0]["motionMP4URL"]
            log.info("  Motion complete: %s", generation_id[:8])
            return url
    raise TimeoutError(f"Leonardo motion generation timed out: {generation_id}")


def _leonardo_footage(script: dict, api_key: str) -> list[str]:
    """Generate one motion clip per scene via Leonardo. Returns ordered clip paths."""
    tmp_dir = ROOT / "tmp"
    scenes = script["scenes"]
    clip_paths = []

    for i, scene in enumerate(scenes):
        log.info("Scene %d/%d: generating image...", i + 1, len(scenes))
        image_id = _leonardo_generate_image(api_key, scene["visual_description"])

        log.info("Scene %d/%d: generating motion...", i + 1, len(scenes))
        video_url = _leonardo_generate_motion(api_key, image_id, scene["visual_description"])

        out_path = tmp_dir / f"leonardo_{i:03d}.mp4"
        _download(video_url, out_path)
        clip_paths.append(str(out_path))
        log.info("Scene %d/%d: clip saved to %s", i + 1, len(scenes), out_path.name)
        time.sleep(2)

    return clip_paths


# ── Color placeholder fallback ────────────────────────────────────────────────

def _generate_color_clip(color: str, duration: float, out_path: Path) -> str:
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "lavfi",
            "-i", f"color=c={color}:size=1920x1080:rate=30",
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out_path),
        ],
        capture_output=True, check=True,
    )
    return str(out_path)


# ── Public entry point ────────────────────────────────────────────────────────

def get_footage(script_path: str, total_duration: float) -> list[str]:
    """Return list of footage clip paths covering total_duration seconds.

    Priority:
      1. Kling AI generation (if KLING_AK + KLING_SK are set)
      2. Local footage/ folder mp4s (looped to cover duration)
      3. Solid-color placeholder clips (one per scene)
    """
    script = json.loads(Path(script_path).read_text())
    footage_dir = ROOT / "footage"
    footage_dir.mkdir(exist_ok=True)
    tmp_dir = ROOT / "tmp"

    # 1. Leonardo AI
    leo_key = os.getenv("LEONARDO_API_KEY")
    if leo_key:
        log.info("Leonardo API key found — generating AI clips")
        return _leonardo_footage(script, leo_key)

    # 2. Kling AI
    ak = os.getenv("KLING_AK")
    sk = os.getenv("KLING_SK")
    if ak and sk:
        mode = os.getenv("KLING_MODE", "std")
        log.info("Kling credentials found — generating AI clips (mode=%s)", mode)
        return _kling_footage(script, ak, sk, mode)

    # 3. Local footage
    clips = sorted(footage_dir.glob("*.mp4"))
    if clips:
        log.info("Found %d local footage clips — looping to fill %ds", len(clips), total_duration)
        result, accumulated = [], 0.0
        while accumulated < total_duration:
            for clip in clips:
                result.append(str(clip))
                accumulated += _ffprobe_duration(str(clip))
                if accumulated >= total_duration:
                    break
        return result

    # 4. Color placeholders
    scenes = script.get("scenes", [])
    num_clips = max(len(scenes), 1)
    clip_duration = total_duration / num_clips
    log.info("No footage — generating %d color placeholder clips", num_clips)
    result = []
    for i in range(num_clips):
        color = BG_COLORS[i % len(BG_COLORS)]
        out_path = tmp_dir / f"bg_{i:02d}.mp4"
        _generate_color_clip(color, clip_duration, out_path)
        result.append(str(out_path))
        log.info("Generated placeholder %d/%d", i + 1, num_clips)
    return result
