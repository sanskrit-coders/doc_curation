---
description: Edit canonical OpenCode agents, commands, skills, or AGENTS.md under doc_curation/llm/configurer/data/opencode/, then sync to all harnesses.
---
Load the llm-config skill and follow its workflow:

1. Make your edits **only** in `doc_curation/llm/configurer/data/opencode/`:
   - `AGENTS.md` — global rules
   - `agents/*.md` — subagent definitions (frontmatter: `name`, `description`)
   - `commands/*.md` — slash commands (filename stem = command name, frontmatter: `description`)
   - `skills/<name>/SKILL.md` — skills (frontmatter `name` matches directory)

2. After editing, run the sync to propagate to antigravity, copilot, kilo, muse, vibe:
   ```
   ~/gitland/python_venv/bin/python -m doc_curation.llm.configurer sync --dry-run
   ~/gitland/python_venv/bin/python -m doc_curation.llm.configurer sync
   ```

3. Verify the generated files, e.g. `data/antigravity/commands/<name>.toml` or `~/.config/opencode/commands/<name>.md`.

$ARGUMENTS