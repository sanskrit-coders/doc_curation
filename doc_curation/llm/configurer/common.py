"""Shared paths and helpers for the coding-agent configurer."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"

CANONICAL_AGENTS = DATA_DIR / "opencode" / "AGENTS.md"
CANONICAL_AGENTS_DIR = DATA_DIR / "opencode" / "agents"
CANONICAL_SKILLS = DATA_DIR / "opencode" / "skills"

_FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
_AGENT_NAME = re.compile(r"[a-z]+(?:-[a-z]+)*")


class ConfigurerError(RuntimeError):
  """A harness configuration cannot be converted or installed."""


@dataclass(frozen=True)
class Agent:
  """A canonical OpenCode agent definition, split into its parts."""

  name: str
  description: str
  frontmatter: str
  body: str
  source: Path


def user_config_dir() -> Path:
  """The per-user config root, honouring ``XDG_CONFIG_HOME``."""
  xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
  return base


def split_frontmatter(text: str, source: Path) -> tuple[str, str]:
  match = _FRONTMATTER.match(text)
  if not match:
    raise ConfigurerError(f"{source} has no YAML frontmatter")
  return match.group(1), match.group(2)


def frontmatter_value(frontmatter: str, key: str) -> str | None:
  match = re.search(rf"^{re.escape(key)}:\s*(.*?)\s*$", frontmatter, flags=re.MULTILINE)
  return match.group(1) if match else None


def load_agent(source: Path) -> Agent:
  frontmatter, body = split_frontmatter(source.read_text(encoding="utf-8"), source)
  name = frontmatter_value(frontmatter, "name")
  description = frontmatter_value(frontmatter, "description")
  if not name or not description:
    raise ConfigurerError(f"{source} must define name and description")
  if not _AGENT_NAME.fullmatch(name):
    raise ConfigurerError(
      f"{source}: name {name!r} is invalid (use lowercase words separated by single hyphens)"
    )
  return Agent(
    name=name,
    description=description,
    frontmatter=frontmatter,
    body=body,
    source=source,
  )


def write_text(path: Path, text: str, dry_run: bool = False) -> bool:
  """Write ``text`` unless the file already has it. Returns True when it changed."""
  path.parent.mkdir(parents=True, exist_ok=True)
  if path.exists() and path.read_text(encoding="utf-8") == text:
    return False
  if not dry_run:
    path.write_text(text, encoding="utf-8")
  return True


def agent_sources(source_dir: Path = CANONICAL_AGENTS_DIR) -> Iterable[Path]:
  for source in sorted(source_dir.glob("*.md")):
    if not source.name.startswith("_"):
      yield source


def sync_agents(
  dest_dir: Path,
  convert: Callable[[Agent], str],
  suffix: str = ".md",
  source_dir: Path = CANONICAL_AGENTS_DIR,
  dry_run: bool = False,
) -> list[str]:
  """Convert every canonical agent into ``dest_dir``, pruning stale files.

  Returns the destination file names, for reporting.
  """
  written: list[str] = []
  for source in agent_sources(source_dir):
    destination = dest_dir / f"{source.stem}{suffix}"
    write_text(destination, convert(load_agent(source)), dry_run=dry_run)
    written.append(destination.name)

  if dest_dir.is_dir():
    for stale in dest_dir.glob(f"*{suffix}"):
      if stale.name.startswith("_") or stale.name in written or not stale.is_file():
        continue
      if not dry_run:
        stale.unlink()

  return written


def mirror_files(
  source_dir: Path, dest_dir: Path, pattern: str = "*.md", dry_run: bool = False
) -> list[str]:
  """Copy ``pattern`` files verbatim from ``source_dir`` to ``dest_dir``, pruning stale ones."""
  written: list[str] = []
  for source in sorted(source_dir.glob(pattern)):
    if source.name.startswith("_"):
      continue
    write_text(dest_dir / source.name, source.read_text(encoding="utf-8"), dry_run=dry_run)
    written.append(source.name)

  if dest_dir.is_dir():
    for stale in dest_dir.glob(pattern):
      if stale.name.startswith("_") or stale.name in written or not stale.is_file():
        continue
      if not dry_run:
        stale.unlink()

  return written
