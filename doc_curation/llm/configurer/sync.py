"""Regenerate the per-harness agent files from the canonical OpenCode definitions."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path
from typing import Callable

from doc_curation.llm.configurer import adapters
from doc_curation.llm.configurer.common import (
  DATA_DIR,
  ConfigurerError,
  mirror_files,
  sync_agents,
  user_config_dir,
)


def _sync_antigravity(dry_run: bool = False) -> list[str]:
  return sync_agents(
    DATA_DIR / "antigravity" / "agents",
    partial(adapters.to_antigravity, home=Path.home()),
    dry_run=dry_run,
  )


def _sync_copilot(dry_run: bool = False) -> list[str]:
  return sync_agents(
    DATA_DIR / "copilot" / "agents", adapters.to_copilot, suffix=".agent.md", dry_run=dry_run
  )


def _sync_kilo(dry_run: bool = False) -> list[str]:
  return sync_agents(DATA_DIR / "kilo" / "agents", adapters.to_kilo, dry_run=dry_run)


def _sync_vibe(dry_run: bool = False) -> list[str]:
  return sync_agents(
    DATA_DIR / "vibe" / "agents", adapters.to_vibe, suffix=".toml", dry_run=dry_run
  )


def _sync_muse(dry_run: bool = False) -> list[str]:
  """Convert for Muse, then copy into ``~/.config/muse/agents/`` as real files.

  Muse rejects a symlinked Agent Definition source root ("Agent Definition source
  root is a symlink or reparse point") and then silently offers only its built-in
  agents, so this one destination cannot be a symlink.
  """
  written = sync_agents(DATA_DIR / "muse" / "agents", adapters.to_muse, dry_run=dry_run)

  destination = user_config_dir() / "muse" / "agents"
  if destination.is_symlink():
    raise ConfigurerError(
      f"{destination} is a symlink; Muse ignores symlinked agent sources. "
      "Remove the link and run `sync` again."
    )
  mirror_files(DATA_DIR / "muse" / "agents", destination, dry_run=dry_run)
  return written


MUSE_AGENTS = user_config_dir() / "muse" / "agents"

# harness: (syncer, generated directory in data/, extra directory to mirror into)
SYNCERS: dict[str, tuple[Callable[..., list[str]], Path, Path | None]] = {
  "antigravity": (_sync_antigravity, DATA_DIR / "antigravity" / "agents", None),
  "copilot": (_sync_copilot, DATA_DIR / "copilot" / "agents", None),
  "kilo": (_sync_kilo, DATA_DIR / "kilo" / "agents", None),
  "muse": (_sync_muse, DATA_DIR / "muse" / "agents", MUSE_AGENTS),
  "vibe": (_sync_vibe, DATA_DIR / "vibe" / "agents", None),
}


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    prog="python -m doc_curation.llm.configurer sync",
    description="Convert data/opencode/agents/*.md into each harness's agent files.",
  )
  parser.add_argument(
    "--harness",
    action="append",
    choices=sorted(SYNCERS),
    help="harness to sync (repeatable; default: all)",
  )
  parser.add_argument("--dry-run", action="store_true", help="report without writing")
  args = parser.parse_args(argv)

  harnesses = args.harness or sorted(SYNCERS)
  for harness in harnesses:
    sync_harness, destination, mirror = SYNCERS[harness]
    try:
      written = sync_harness(dry_run=args.dry_run)
    except ConfigurerError as error:
      print(f"{harness}: {error}")
      return 1
    verb = "would sync" if args.dry_run else "synced"
    print(f"{harness}: {verb} {len(written)} agents -> {destination}")
    if mirror:
      mirror_verb = "would copy" if args.dry_run else "copied"
      print(f"{harness}: {mirror_verb} {len(written)} agents -> {mirror}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
