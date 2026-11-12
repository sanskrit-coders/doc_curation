"""Configure the coding-agent CLIs (OpenCode, Muse, Kilo, Vibe, Copilot, Antigravity).

``data/`` next to this module is the single source of truth:

- ``data/opencode/AGENTS.md`` - global instructions (rules) for every harness.
- ``data/opencode/agents/`` - agent definitions; edited here, then converted for
  the other harnesses by :mod:`doc_curation.llm.configurer.sync`.
- ``data/opencode/skills/`` - skills, shared by every harness through symlinks.
- ``data/<harness>/agents/`` - generated agent files for that harness.

Each harness reads user-level config from its own fixed location. Rather than
copying, :mod:`doc_curation.llm.configurer.symlinks` links those locations back
here, so one edit propagates everywhere. Muse agent files are the exception:
Muse rejects a symlinked Agent Definition source root, so ``sync`` copies them
into ``~/.config/muse/agents/`` as real files.

Usage::

    python -m doc_curation.llm.configurer sync       # regenerate harness agent files
    python -m doc_curation.llm.configurer symlinks   # create/repair the symlinks
    python -m doc_curation.llm.configurer all        # both
"""

from doc_curation.llm.configurer.common import (
    CANONICAL_AGENTS,
    CANONICAL_AGENTS_DIR,
    CANONICAL_SKILLS,
    DATA_DIR,
    Agent,
    ConfigurerError,
    user_config_dir,
)

__all__ = [
    "CANONICAL_AGENTS",
    "CANONICAL_AGENTS_DIR",
    "CANONICAL_SKILLS",
    "DATA_DIR",
    "Agent",
    "ConfigurerError",
    "user_config_dir",
]
