"""Per-harness conversions of the canonical OpenCode agent definitions.

OpenCode's frontmatter (``name``/``title``/``mode``/``subagent`` plus a list-of-mappings
``permissions:`` block) is richer than the other harnesses accept, so each converter
keeps only the fields its harness understands and leaves the prompt body intact.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc_curation.llm.configurer.common import Agent, frontmatter_value

ANTIGRAVITY_TOOLS = [
  "send_message",
  "view_file",
  "search_web",
  "schedule",
  "generate_image",
  "write_file",
  "edit_file",
  "run_command",
  "manage_task",
  "define_subagent",
  "invoke_subagent",
  "manage_subagents",
]

# Muse Code frontmatter keys, in output order. Muse rejects unknown keys.
MUSE_PASSTHROUGH_KEYS = ["model", "effort", "tools", "disallowedTools"]


def to_copilot(agent: Agent) -> str:
  """Copilot profile: only ``name`` and ``description``, plus the body."""
  return (
    "---\n"
    f"name: {agent.name}\n"
    "description: >-\n"
    f"  {agent.description}\n"
    "---\n"
    f"{agent.body}"
  )


def to_antigravity(agent: Agent, home: Path | None = None) -> str:
  """Antigravity agent: OpenCode frontmatter plus an explicit ``tools:`` list.

  Antigravity resolves Markdown links strictly, so leading ``~/`` in links is
  expanded to the absolute home path.
  """
  frontmatter = agent.frontmatter
  if not re.search(r"^tools\s*:", frontmatter, flags=re.MULTILINE):
    tools_yaml = "tools:\n" + "".join(f"  - {tool}\n" for tool in ANTIGRAVITY_TOOLS)
    frontmatter = frontmatter.rstrip("\n") + "\n" + tools_yaml

  body = agent.body.replace("](~/", f"]({home or Path.home()}/")
  return f"---\n{frontmatter}---\n{body}"


def to_kilo(agent: Agent) -> str:
  """Kilo agent: ``description`` + ``mode`` frontmatter; the filename is the name."""
  mode = frontmatter_value(agent.frontmatter, "mode") or "subagent"
  if mode not in ("primary", "subagent", "all"):
    mode = "subagent"
  return f"---\ndescription: {agent.description}\nmode: {mode}\n---\n\n{agent.body}"


def to_vibe(agent: Agent) -> str:
  """Vibe subagent: a TOML file whose filename is the agent name."""
  return (
    f'description = """{agent.description}"""\n'
    "agent_type = 'subagent'\n"
    "instructions = '''\n"
    f"{agent.body.strip()}\n"
    "'''\n"
  )


def to_muse(agent: Agent) -> str:
  """Muse Code agent definition: Markdown frontmatter + prompt body.

  Muse rejects any frontmatter key it does not know, so the OpenCode-only keys
  (``title``, ``mode``, ``subagent``, ``permissions``) are dropped. The optional
  ``model``/``effort``/``tools``/``disallowedTools`` keys pass through.
  """
  lines = [f"name: {agent.name}", f"description: {agent.description}"]
  for key in MUSE_PASSTHROUGH_KEYS:
    value = frontmatter_value(agent.frontmatter, key)
    if value:
      lines.append(f"{key}: {value}")
  return "---\n" + "\n".join(lines) + "\n---\n\n" + agent.body.strip() + "\n"


def command_to_toml(name: str, description: str, body: str) -> str:
  """Convert a command to TOML format for Gemini."""
  # Convert $ARGUMENTS to {{args}} for Gemini
  gemini_body = body.strip().replace("$ARGUMENTS", "{{args}}")
  return (
    f'name = "{name}"\n'
    f'description = """{description}"""\n'
    f'prompt = """\n'
    f"{gemini_body}\n"
    '"""\n'
  )
