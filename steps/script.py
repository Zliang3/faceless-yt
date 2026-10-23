import json
import logging
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent

# Series character config — edit here to change the show's identity
BIRD_NAME = "Daisy"
BIRD_SPECIES = "small bluebird"
BIRD_SIGNATURE_ITEM = "tiny red scarf"
BIRD_CATCHPHRASE = "Wings up, friends!"

_SYSTEM_PROMPT_TEMPLATE = (ROOT / "script_system.md").read_text()
SYSTEM_PROMPT = (
    _SYSTEM_PROMPT_TEMPLATE
    .replace("[FILL IN: e.g. \"Pip\", \"Skye\", \"Echo\"]", f'"{BIRD_NAME}"')
    .replace("[FILL IN: e.g. small bluebird, hummingbird, parrot]", BIRD_SPECIES)
    .replace(
        "[FILL IN: e.g. tiny red scarf, explorer's hat, leaf backpack] — must appear every episode for visual recognition",
        f"{BIRD_SIGNATURE_ITEM} — must appear every episode for visual recognition",
    )
    .replace(
        "[FILL IN: e.g. \"Wings up, friends!\"] — say at start AND end of every episode",
        f'"{BIRD_CATCHPHRASE}" — say at start AND end of every episode',
    )
)


class Scene(BaseModel):
    beat: str
    start_time: str
    end_time: str
    narration: str
    visual_description: str
    sound_effects: list[str]


class EpisodeScript(BaseModel):
    episode_number: int
    biome: str
    guest_animal: str
    title: str
    description: str
    tags: list[str]
    thumbnail_prompt: str
    scenes: list[Scene]
    facts_taught: list[str]
    moral: str
    next_episode_tease: str
    total_duration_seconds: int


def generate_script(topic: str, episode_number: int = 1) -> str:
    """Generate an episode script for topic (biome/animal hint). Returns path to saved JSON."""
    (ROOT / "tmp").mkdir(exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    log.info("Starting script generation for topic: %s", topic)

    client = anthropic.Anthropic()

    log.info("Calling Claude API (claude-sonnet-4-6)...")
    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write episode {episode_number} of the series. "
                    f"Topic / biome+animal hint: {topic}"
                ),
            }
        ],
        output_format=EpisodeScript,
    )

    script: EpisodeScript = response.parsed_output
    log.info(
        "Script generated: '%s' — %s / %s, %d scenes, %ds",
        script.title,
        script.biome,
        script.guest_animal,
        len(script.scenes),
        script.total_duration_seconds,
    )
    log.info(
        "Usage — input: %d, cache_write: %d, cache_read: %d, output: %d",
        response.usage.input_tokens,
        response.usage.cache_creation_input_tokens or 0,
        response.usage.cache_read_input_tokens or 0,
        response.usage.output_tokens,
    )

    out_path = ROOT / "tmp" / "script.json"
    out_path.write_text(json.dumps(script.model_dump(), indent=2))
    log.info("Script saved to %s", out_path)

    return str(out_path)
