import logging
import shutil
import sys
from pathlib import Path

from steps.script import generate_script
from steps.voice import generate_voiceover
from steps.footage import get_footage, _ffprobe_duration
from steps.assemble import assemble

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
ROOT = Path(__file__).parent


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <topic> [--episode N] [--tts elevenlabs|vibevoice]")
        sys.exit(1)

    args = sys.argv[1:]
    episode_number = 1
    tts_backend = "vibevoice"

    if "--episode" in args:
        idx = args.index("--episode")
        if idx + 1 >= len(args):
            print("Usage: python main.py <topic> [--episode N] [--tts elevenlabs|vibevoice]")
            sys.exit(1)
        episode_number = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if "--tts" in args:
        idx = args.index("--tts")
        if idx + 1 >= len(args) or args[idx + 1] not in ("elevenlabs", "vibevoice"):
            print("Usage: python main.py <topic> [--episode N] [--tts elevenlabs|vibevoice]")
            sys.exit(1)
        tts_backend = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    topic = " ".join(args)

    log.info("=== Starting pipeline — episode %d, topic: %s ===", episode_number, topic)

    script_cache = ROOT / "tmp" / "script.json"
    audio_cache = ROOT / "tmp" / "voiceover.mp3"

    if script_cache.exists():
        log.info("Reusing cached script: %s", script_cache)
        script_path = str(script_cache)
    else:
        script_path = generate_script(topic, episode_number=episode_number)

    if audio_cache.exists():
        log.info("Reusing cached voiceover: %s", audio_cache)
        audio_path = str(audio_cache)
    else:
        audio_path = generate_voiceover(script_path, backend=tts_backend)

    audio_duration = _ffprobe_duration(audio_path)
    footage_paths = get_footage(script_path, audio_duration)
    video_path = assemble(script_path, audio_path, footage_paths)

    log.info("=== Done! Video saved to: %s ===", video_path)
    print(f"\nOutput: {video_path}")

    # Clean up tmp/
    shutil.rmtree(ROOT / "tmp", ignore_errors=True)
    log.info("Cleaned up tmp/")


if __name__ == "__main__":
    main()
