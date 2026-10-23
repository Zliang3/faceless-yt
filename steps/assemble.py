import json
import logging
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

CAPTION_CHUNK = 5  # words per caption card
FONT_SIZE = 18


def _ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _concat_clips(clip_paths: list[str], total_duration: float, out_path: Path) -> None:
    # Loop clips until they cover total_duration
    looped, accumulated = [], 0.0
    while accumulated < total_duration:
        for p in clip_paths:
            looped.append(p)
            accumulated += _ffprobe_duration(p)
            if accumulated >= total_duration:
                break

    concat_file = ROOT / "tmp" / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{Path(p).resolve()}'" for p in looped)
    )
    # Concat then trim to exact audio duration
    subprocess.run(
        [
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-t", str(total_duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out_path),
        ],
        capture_output=True, check=True,
    )


def _transcribe(audio_path: str) -> list[dict]:
    import whisper
    log.info("Transcribing audio with Whisper (base model)...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for segment in result["segments"]:
        for w in segment.get("words", []):
            words.append({"word": w["word"], "start": w["start"], "end": w["end"]})
    log.info("Transcribed %d words", len(words))
    return words


def _seconds_to_srt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")


def _make_srt(words: list[dict], out_path: Path) -> None:
    chunks, i = [], 0
    while i < len(words):
        chunk = words[i : i + CAPTION_CHUNK]
        text = " ".join(w["word"].strip() for w in chunk)
        chunks.append({"start": chunk[0]["start"], "end": chunk[-1]["end"], "text": text})
        i += CAPTION_CHUNK

    lines = []
    for idx, chunk in enumerate(chunks, 1):
        lines.append(str(idx))
        lines.append(f"{_seconds_to_srt_time(chunk['start'])} --> {_seconds_to_srt_time(chunk['end'])}")
        lines.append(chunk["text"])
        lines.append("")

    out_path.write_text("\n".join(lines))
    log.info("SRT written to %s (%d entries)", out_path, len(chunks))


def assemble(script_path: str, audio_path: str, footage_paths: list[str]) -> str:
    """Assemble final video. Returns path to output MP4."""
    script = json.loads(Path(script_path).read_text())
    slug = re.sub(r"[^\w]+", "_", script["title"].lower()).strip("_")
    out_path = ROOT / "output" / f"{slug}.mp4"
    (ROOT / "output").mkdir(exist_ok=True)

    audio_duration = _ffprobe_duration(audio_path)
    log.info("Audio duration: %.1fs", audio_duration)

    # 1. Concatenate footage
    log.info("Concatenating %d footage clips...", len(footage_paths))
    raw_video = ROOT / "tmp" / "raw_video.mp4"
    _concat_clips(footage_paths, audio_duration, raw_video)

    # 2. Transcribe for captions
    words = _transcribe(audio_path)
    srt_path = ROOT / "tmp" / "captions.srt"
    _make_srt(words, srt_path)

    # 3. Final assembly: video + audio + burned-in captions
    # Commas inside force_style must be escaped as \, for FFmpeg's filter parser
    log.info("Rendering final video...")
    style = (
        f"FontSize={FONT_SIZE}\\,PrimaryColour=&HFFFFFF\\,OutlineColour=&H000000"
        f"\\,Outline=2\\,Bold=1\\,Alignment=2"
    )
    subtitle_filter = f"subtitles={srt_path}:force_style={style}"
    subprocess.run(
        [
            FFMPEG, "-y",
            "-i", str(raw_video),
            "-i", audio_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ],
        capture_output=True, check=True,
    )

    log.info("Final video saved to %s", out_path)
    return str(out_path)
