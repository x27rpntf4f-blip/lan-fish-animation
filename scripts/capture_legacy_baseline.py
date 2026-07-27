from __future__ import annotations

import argparse
import json
import platform
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SPRITES = ROOT / "assets" / "fish_sprites"
PERSONAL_PATH = re.compile(r"(?:[A-Za-z]:)?[/\\](?:Users|home)[/\\][^\s\"']+", re.IGNORECASE)

sys.path.insert(0, str(SRC))
import message  # noqa: E402


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as source:
        return sum(1 for _ in source)


def tracked_personal_paths() -> list[str]:
    config = ROOT / "config.ini"
    return PERSONAL_PATH.findall(config.read_text(encoding="utf-8"))


def capture() -> dict[str, object]:
    source_files = sorted(SRC.rglob("*.py"))
    sprite_directories = sorted(path for path in SPRITES.iterdir() if path.is_dir())
    return {
        "schema_version": 1,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_lines": {
            path.relative_to(ROOT).as_posix(): count_lines(path) for path in source_files
        },
        "message_header_bytes": message.HEADER_SIZE,
        "message_type_count": len(message.MSG_NAMES),
        "sprite_type_count": len(sprite_directories),
        "tracked_personal_paths": tracked_personal_paths(),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the FishMesh M0 legacy baseline.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/baseline/legacy-m0.json"),
        help="JSON output path (default: artifacts/baseline/legacy-m0.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(capture(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
