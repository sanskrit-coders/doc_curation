"""Create and refresh the per-harness symlinks that point into ``data/``.

Every coding-agent CLI reads user-level rules, agents and skills from its own fixed
location. Linking those locations to the canonical files here means one edit updates
every harness at once, and running this script after a move or a new harness keeps
them all in step.

Muse Code's agent definitions are the exception: Muse rejects a symlinked Agent
Definition source root, so ``sync`` copies real files into ``~/.config/muse/agents/``
and that path is not managed here. Muse's rules and skills are symlinked normally.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from doc_curation.llm.configurer.common import (
  CANONICAL_AGENTS,
  CANONICAL_AGENTS_DIR,
  CANONICAL_SKILLS,
  CANONICAL_COMMANDS,
  DATA_DIR,
)

Manager = tuple[str, Path]

# (link path, canonical target)
MANAGED_LINKS: list[Manager] = [
  # OpenCode
  ("~/.config/opencode/AGENTS.md", CANONICAL_AGENTS),
  ("~/.config/opencode/agents", CANONICAL_AGENTS_DIR),
  ("~/.config/opencode/skills", CANONICAL_SKILLS),
  ("~/.config/opencode/commands", CANONICAL_COMMANDS),
  # Muse Code (rules and skills; agents are copied by `sync`, see module docstring)
  ("~/.config/muse/AGENTS.md", CANONICAL_AGENTS),
  ("~/.config/muse/skills", CANONICAL_SKILLS),
  # Kilo
  ("~/.config/kilo/AGENTS.md", CANONICAL_AGENTS),
  ("~/.config/kilo/agents", CANONICAL_AGENTS_DIR),
  ("~/.config/kilo/commands", CANONICAL_COMMANDS),
  ("~/.kilo/skills", CANONICAL_SKILLS),
  ("~/.kilo/commands", CANONICAL_COMMANDS),
  # Legacy .kilocode (Kilo also reads from here)
  ("~/.kilocode/AGENTS.md", CANONICAL_AGENTS),
  ("~/.kilocode/agents", CANONICAL_AGENTS_DIR),
  ("~/.kilocode/commands", CANONICAL_COMMANDS),
  ("~/.kilocode/skills", CANONICAL_SKILLS),
  # Mistral Vibe
  ("~/.vibe/AGENTS.md", CANONICAL_AGENTS),
  ("~/.vibe/agents", DATA_DIR / "vibe" / "agents"),
  ("~/.vibe/skills", CANONICAL_SKILLS),
  # GitHub Copilot
  ("~/.copilot/copilot-instructions.md", CANONICAL_AGENTS),
  ("~/.copilot/agents", DATA_DIR / "copilot" / "agents"),
  # Antigravity
  ("~/.gemini/config/AGENTS.md", CANONICAL_AGENTS),
  ("~/.gemini/config/agents", DATA_DIR / "antigravity" / "agents"),
  ("~/.gemini/config/skills", CANONICAL_SKILLS),
  ("~/.gemini/commands", DATA_DIR / "antigravity" / "commands"),
  ("~/.agents/skills", CANONICAL_SKILLS),
]

WATCHED_DIRS = sorted({Path(link).expanduser().parent for link, _ in MANAGED_LINKS})


def _managed_paths() -> set[Path]:
  return {Path(link).expanduser() for link, _ in MANAGED_LINKS}


def _points_into_data(path: Path) -> bool:
  if not path.is_symlink():
    return False
  resolved = (path.parent / path.readlink()).resolve()
  return resolved == DATA_DIR or DATA_DIR in resolved.parents


def _update(link: Path, target: Path, dry_run: bool) -> str:
  """Create or repair one symlink. Returns created/updated/unchanged/conflict."""
  if not target.exists():
    print(f"  warning: target is missing: {target}")

  if link.is_symlink():
    if link.readlink() == target:
      return "unchanged"
    if not dry_run:
      link.unlink()
      link.symlink_to(target)
    return "updated"

  if link.exists():
    print(f"  conflict: {link} exists and is not a symlink; leaving it alone")
    return "conflict"

  if not dry_run:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
  return "created"


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    prog="python -m doc_curation.llm.configurer symlinks",
    description="Create/repair the harness config symlinks pointing into data/.",
  )
  parser.add_argument("--dry-run", action="store_true", help="report without changing anything")
  parser.add_argument(
    "--prune", action="store_true", help="remove unmanaged repo-pointing links in the harness dirs"
  )
  args = parser.parse_args(argv)

  counts = {"created": 0, "updated": 0, "unchanged": 0, "conflict": 0, "pruned": 0}
  for link_str, target in MANAGED_LINKS:
    link = Path(link_str).expanduser()
    status = _update(link, target, args.dry_run)
    counts[status] += 1
    if status != "unchanged":
      prefix = "would " if args.dry_run else ""
      print(f"  {prefix}{status}: {link} -> {target}")

  if args.prune:
    managed = _managed_paths()
    for watched in WATCHED_DIRS:
      if not watched.is_dir():
        continue
      for entry in sorted(watched.iterdir()):
        if entry in managed or not _points_into_data(entry):
          continue
        counts["pruned"] += 1
        prefix = "would prune" if args.dry_run else "pruned"
        print(f"  {prefix}: {entry} -> {entry.readlink()}")
        if not args.dry_run:
          entry.unlink()

  missing = [target for _, target in MANAGED_LINKS if not target.exists()]
  for target in missing:
    print(f"  note: missing canonical target: {target}")

  print(
    "Summary: {created} created, {updated} updated, {unchanged} unchanged, "
    "{conflict} conflicts, {pruned} pruned".format(**counts)
  )
  return 1 if counts["conflict"] or missing else 0


if __name__ == "__main__":
  raise SystemExit(main())
