#!/usr/bin/env python3
"""Sync the canonical Python module into every skill folder.

Repo layout:
    canonical/
        bonsai_bim_helpers.py        ← ONE source of truth
    skills/
        bonsai-walls/
            bonsai_bim_helpers.py    ← copy
            bonsai_room_with_miters.py   ← backward-compat shim
            SKILL.md
        bonsai-openings/             (same)
        bonsai-roofs/                (same)
        bonsai-stairs/               (same)
        bonsai-spaces-grid/          (same)
        bonsai-project-setup/        (same)
        bonsai-drawings/             (different module: bonsai_drawings.py)

After editing canonical/bonsai_bim_helpers.py, run this script to
propagate the change into every element-related skill folder. The
drawings skill has its own module (bonsai_drawings.py) and is NOT
touched by this sync.

Usage:
    python tools/sync_modules.py
    python tools/sync_modules.py --check    # exit non-zero if drift detected (for CI)
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

# Skill folders that share canonical/bonsai_bim_helpers.py
ELEMENT_SKILLS = (
    "bonsai-walls",
    "bonsai-openings",
    "bonsai-roofs",
    "bonsai-stairs",
    "bonsai-spaces-grid",
    "bonsai-project-setup",
)

# Files copied verbatim from canonical/ into each ELEMENT_SKILLS folder
SYNCED_FILES = ("bonsai_bim_helpers.py",)

# Repo root = parent of this script's folder
REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Don't copy; exit non-zero if any skill copy differs from canonical.",
    )
    args = parser.parse_args(argv)

    canonical = REPO_ROOT / "canonical"
    if not canonical.is_dir():
        print(f"ERROR: canonical folder not found at {canonical}", file=sys.stderr)
        return 2

    drift = []
    for filename in SYNCED_FILES:
        src = canonical / filename
        if not src.is_file():
            print(f"ERROR: canonical/{filename} missing", file=sys.stderr)
            return 2

        for skill in ELEMENT_SKILLS:
            dst = REPO_ROOT / "skills" / skill / filename
            if args.check:
                if not dst.is_file() or not filecmp.cmp(src, dst, shallow=False):
                    drift.append(str(dst.relative_to(REPO_ROOT)))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  → {dst.relative_to(REPO_ROOT)}")

    if args.check:
        if drift:
            print("DRIFT — these copies differ from canonical:", file=sys.stderr)
            for d in drift:
                print(f"  - {d}", file=sys.stderr)
            print("\nRun `python tools/sync_modules.py` to re-sync.",
                  file=sys.stderr)
            return 1
        print("OK — all skill copies match canonical/.")
        return 0

    print(f"\nSynced {len(SYNCED_FILES)} file(s) × {len(ELEMENT_SKILLS)} skill(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
