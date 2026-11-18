"""Composable system prompts loaded from ``data/prompts.toml``."""
from __future__ import annotations

import os
import tomllib

_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "data", "prompts.toml")
with open(_PROMPTS_PATH, "rb") as _f:
  _CFG = tomllib.load(_f)

INTERLEAVER_SYSTEM_PROMPT: str = _CFG["interleaver_system_prompt"]
PADAPATHA_ACCENT_SYSTEM_PROMPT: str = _CFG["padapatha_accent_system_prompt"]


def build_system_prompt(
  *,
  clause_newlines: bool = True,
  suggest_corrections: bool = True,
  markdown_cleanup: bool = True,
  extra_instructions: str = "",
  variant: int = 0,
) -> str:
  """Construct a modular system prompt for training or inference."""
  openers = _CFG["openers"]
  opener = openers[variant % len(openers)]
  sug_block = _CFG["suggestion_rules_on"] if suggest_corrections else _CFG["suggestion_rules_off"]
  if clause_newlines:
    variants = _CFG["clause_newlines_variants"]
    flow_block = variants[variant % len(variants)]
  else:
    flow_block = _CFG["clause_newlines_off"]
  md_block = _CFG["markdown_cleanup_on"] if markdown_cleanup else _CFG["markdown_cleanup_minimal"]

  sections = [opener, _CFG["core_separation_rules"], sug_block, flow_block, md_block]
  if extra_instructions and extra_instructions.strip():
    sections.append(f"### Additional Instructions\n{extra_instructions.strip()}")
  return "\n\n".join(sections)
