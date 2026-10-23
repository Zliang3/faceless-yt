"""Batch script generator — 100 episodes across 5 biomes, 20 animals each.

Saves each script to output/scripts/ep{N:03d}_{biome}_{animal}.json.
Skips episodes that already exist so it can resume safely.

Option B problem rotation (6 types, cycling through remaining episodes):
  1 - SCARF RESCUE: Daisy's scarf blows away or gets snagged — animal retrieves it using its special trait
  2 - LOST: Daisy gets turned around in the biome — animal uses navigation/sensing to guide her back
  3 - BABY RESCUE: A baby animal is gently stuck or separated — Daisy and guest work together to help
  4 - WEATHER SURVIVAL: Sudden weather threatens Daisy — animal shares its survival trick to keep her safe
  5 - CAN'T REACH: Daisy can't reach or see something important — animal's size, speed, or senses save the day
  6 - SHY FRIEND: A timid background animal is scared of Daisy — guest helps make a warm introduction
"""
import json, shutil, time, logging
from pathlib import Path

from steps.script import generate_script

PROBLEM_TYPES = {
    1: "LITTLE PROBLEM TYPE — Scarf rescue: Daisy's scarf blows away or gets snagged somewhere; the guest animal uses its unique trait to retrieve it.",
    2: "LITTLE PROBLEM TYPE — Lost: Daisy gets turned around and can't find her way; the guest animal uses its navigation or sensing ability to guide her back safely.",
    3: "LITTLE PROBLEM TYPE — Baby rescue: A baby animal nearby is gently stuck or has wandered off; Daisy and the guest animal work together to help it.",
    4: "LITTLE PROBLEM TYPE — Weather survival: A sudden weather change (sandstorm, rain, cold snap) threatens Daisy; the guest animal teaches her its survival trick and keeps her safe.",
    5: "LITTLE PROBLEM TYPE — Can't reach: Daisy spots something important (a lost item, a pretty flower, a message) she can't reach or see; the animal's special size, speed, or senses save the day.",
    6: "LITTLE PROBLEM TYPE — Shy friend: A timid background animal is hiding because it's scared of Daisy; the guest animal uses its personality or traits to help make a warm, gentle introduction.",
}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent
SCRIPTS_DIR = ROOT / "output" / "scripts"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

EPISODES = [
    # ── Rainforest (1–20) ──────────────────────────────────────────────────
    (1,  "Rainforest - Toucan"),
    (2,  "Rainforest - Sloth"),
    (3,  "Rainforest - Poison Dart Frog"),
    (4,  "Rainforest - Macaw"),
    (5,  "Rainforest - Capybara"),
    (6,  "Rainforest - Giant Anteater"),
    (7,  "Rainforest - Morpho Butterfly"),
    (8,  "Rainforest - Howler Monkey"),
    (9,  "Rainforest - Jaguar"),
    (10, "Rainforest - Tapir"),
    (11, "Rainforest - Leafcutter Ant"),
    (12, "Rainforest - Red-Eyed Tree Frog"),
    (13, "Rainforest - Armadillo"),
    (14, "Rainforest - Chameleon"),
    (15, "Rainforest - Harpy Eagle"),
    (16, "Rainforest - Green Anaconda"),
    (17, "Rainforest - Spider Monkey"),
    (18, "Rainforest - Piranha"),
    (19, "Rainforest - Ocelot"),
    (20, "Rainforest - Electric Eel"),
    # ── Arctic / Tundra (21–40) ────────────────────────────────────────────
    (21, "Arctic - Polar Bear"),
    (22, "Arctic - Arctic Fox"),
    (23, "Arctic - Snowy Owl"),
    (24, "Arctic - Walrus"),
    (25, "Arctic - Narwhal"),
    (26, "Arctic - Arctic Hare"),
    (27, "Arctic - Musk Ox"),
    (28, "Arctic - Puffin"),
    (29, "Arctic - Caribou"),
    (30, "Arctic - Lemming"),
    (31, "Arctic - Beluga Whale"),
    (32, "Arctic - Arctic Wolf"),
    (33, "Arctic - Ermine"),
    (34, "Arctic - Ptarmigan"),
    (35, "Arctic - Arctic Tern"),
    (36, "Arctic - Harbor Seal"),
    (37, "Arctic - Wolverine"),
    (38, "Arctic - Bearded Seal"),
    (39, "Arctic - Snow Bunting"),
    (40, "Arctic - Musk Deer"),
    # ── Savanna (41–60) ───────────────────────────────────────────────────
    (41, "Savanna - Giraffe"),
    (42, "Savanna - African Elephant"),
    (43, "Savanna - Lion"),
    (44, "Savanna - Zebra"),
    (45, "Savanna - Cheetah"),
    (46, "Savanna - Hippopotamus"),
    (47, "Savanna - White Rhinoceros"),
    (48, "Savanna - Meerkat"),
    (49, "Savanna - Warthog"),
    (50, "Savanna - Ostrich"),
    (51, "Savanna - Flamingo"),
    (52, "Savanna - Hyena"),
    (53, "Savanna - Aardvark"),
    (54, "Savanna - Secretary Bird"),
    (55, "Savanna - Dung Beetle"),
    (56, "Savanna - Mongoose"),
    (57, "Savanna - Serval"),
    (58, "Savanna - African Wild Dog"),
    (59, "Savanna - Gerenuk"),
    (60, "Savanna - Marabou Stork"),
    # ── Ocean / Coral Reef (61–80) ────────────────────────────────────────
    (61, "Ocean - Clownfish"),
    (62, "Ocean - Sea Turtle"),
    (63, "Ocean - Dolphin"),
    (64, "Ocean - Whale Shark"),
    (65, "Ocean - Octopus"),
    (66, "Ocean - Seahorse"),
    (67, "Ocean - Manta Ray"),
    (68, "Ocean - Starfish"),
    (69, "Ocean - Blue Whale"),
    (70, "Ocean - Cuttlefish"),
    (71, "Ocean - Sea Otter"),
    (72, "Ocean - Manatee"),
    (73, "Ocean - Parrotfish"),
    (74, "Ocean - Moray Eel"),
    (75, "Ocean - Nautilus"),
    (76, "Ocean - Flying Fish"),
    (77, "Ocean - Hammerhead Shark"),
    (78, "Ocean - Jellyfish"),
    (79, "Ocean - Sea Lion"),
    (80, "Ocean - Anglerfish"),
    # ── Desert (81–100) ───────────────────────────────────────────────────
    (81,  "Desert - Camel"),
    (82,  "Desert - Fennec Fox"),
    (83,  "Desert - Roadrunner"),
    (84,  "Desert - Gila Monster"),
    (85,  "Desert - Scorpion"),
    (86,  "Desert - Desert Tortoise"),
    (87,  "Desert - Coyote"),
    (88,  "Desert - Horned Lizard"),
    (89,  "Desert - Elf Owl"),
    (90,  "Desert - Kangaroo Rat"),
    (91,  "Desert - Sand Cat"),
    (92,  "Desert - Jerboa"),
    (93,  "Desert - Arabian Oryx"),
    (94,  "Desert - Sidewinder Rattlesnake"),
    (95,  "Desert - Addax"),
    (96,  "Desert - Desert Hedgehog"),
    (97,  "Desert - Burrowing Owl"),
    (98,  "Desert - Gila Woodpecker"),
    (99,  "Desert - Thorny Devil"),
    (100, "Desert - Saharan Cheetah"),
]

# Problem type assignment for remaining episodes (Option B rotation).
# Episodes 1-77 are already generated; these guide the new ones only.
PROBLEM_HINT: dict[int, int] = {
    78: 2,   # Jellyfish        — Lost
    79: 3,   # Sea Lion         — Baby rescue
    80: 4,   # Anglerfish       — Weather survival
    81: 5,   # Camel            — Can't reach
    82: 6,   # Fennec Fox       — Shy friend
    83: 1,   # Roadrunner       — Scarf rescue
    84: 2,   # Gila Monster     — Lost
    85: 3,   # Scorpion         — Baby rescue
    86: 4,   # Desert Tortoise  — Weather survival
    87: 5,   # Coyote           — Can't reach
    88: 6,   # Horned Lizard    — Shy friend
    89: 1,   # Elf Owl          — Scarf rescue
    90: 2,   # Kangaroo Rat     — Lost
    91: 3,   # Sand Cat         — Baby rescue
    92: 4,   # Jerboa           — Weather survival
    93: 5,   # Arabian Oryx     — Can't reach
    94: 6,   # Sidewinder       — Shy friend
    95: 1,   # Addax            — Scarf rescue
    96: 2,   # Desert Hedgehog  — Lost
    97: 3,   # Burrowing Owl    — Baby rescue
    98: 4,   # Gila Woodpecker  — Weather survival
    99: 5,   # Thorny Devil     — Can't reach
    100: 6,  # Saharan Cheetah  — Shy friend
}


def slug(text: str) -> str:
    return text.lower().replace(" ", "_").replace("/", "_").replace("-", "_")


def main():
    total = len(EPISODES)
    done = 0
    skipped = 0
    errors = 0

    for ep_num, topic in EPISODES:
        biome, animal = topic.split(" - ", 1)
        out_file = SCRIPTS_DIR / f"ep{ep_num:03d}_{slug(biome)}_{slug(animal)}.json"

        if out_file.exists():
            log.info("[%d/%d] SKIP — %s already exists", ep_num, total, out_file.name)
            skipped += 1
            continue

        problem_type = PROBLEM_HINT.get(ep_num)
        prompt = topic
        if problem_type:
            prompt = f"{topic}. {PROBLEM_TYPES[problem_type]}"
            log.info("  Problem type %d assigned", problem_type)

        log.info("[%d/%d] Generating: %s", ep_num, total, topic)
        try:
            generate_script(prompt, ep_num)
            shutil.copy(ROOT / "tmp" / "script.json", out_file)
            log.info("  Saved → %s", out_file.name)
            done += 1
            time.sleep(0.5)  # avoid hammering the API
        except Exception as e:
            log.error("  FAILED ep %d (%s): %s", ep_num, topic, e)
            errors += 1

    log.info("Done. Generated: %d | Skipped: %d | Errors: %d", done, skipped, errors)


if __name__ == "__main__":
    main()
