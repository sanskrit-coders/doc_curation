---
name: llm-config
description: Maintains this repo's coding-agent configuration — the canonical OpenCode agents, commands, skills and AGENTS.md under doc_curation/llm/configurer/data, and their generated forms for antigravity, copilot, kilo, muse and vibe. Use when editing agents, commands, skills or AGENTS.md, or when another harness's config must be regenerated.
---

Maintain the coding-agent config in `doc_curation/llm/configurer/`.

## Edit only the canonical files

Everything under `data/opencode/` is canonical:

- `AGENTS.md` — global rules.
- `agents/*.md` — subagent definitions; frontmatter needs `name` and `description`.
- `commands/*.md` — slash commands; the **filename stem is the command name** and frontmatter needs `description`.
- `skills/<name>/SKILL.md` — skills; the frontmatter `name` must match the directory.

Everything under `data/antigravity/`, `data/copilot/`, `data/kilo/`, `data/muse/`, `data/vibe/` is **generated**. Never edit those by hand — `sync` overwrites them and prunes stale files.

## After editing agents or commands

```bash
~/gitland/python_venv/bin/python -m doc_curation.llm.configurer sync --dry-run
~/gitland/python_venv/bin/python -m doc_curation.llm.configurer sync
```

`sync` converts agents for antigravity, copilot, kilo, muse and vibe, converts commands to Gemini-CLI-style TOML for antigravity, prunes stale output, and copies Muse agents to `~/.config/muse/agents` (Muse rejects a symlinked agent source and silently falls back to its built-ins).

`symlinks` creates or repairs the per-harness links into `data/` (run it after adding a skill or a harness, or with `--prune` to drop unmanaged links). `python -m doc_curation.llm.configurer all` runs both. Both accept `--dry-run`.

**Skills need no sync**: every harness symlinks the whole `data/opencode/skills` directory, so a new skill directory is live immediately.

## Gotchas

- Renaming a command file renames the generated TOML too; the stale one is pruned. After a rename, run `sync` rather than editing the generated file.
- Command names must match `[a-z0-9]+([-_][a-z0-9]+)*`; agent names allow only single hyphens.
- Prompts in the generated TOML use `{{args}}` for the user's arguments, where Markdown commands use `$ARGUMENTS`.
- A new harness needs an entry in `SYNCERS` (`sync.py`) and in `MANAGED_LINKS` (`symlinks.py`).
- `sync` only propagates *frontmatter description and body*; check the generated file after a large rewrite.

## Verify

- Re-read the generated file (e.g. `data/antigravity/commands/<name>.toml`) to confirm the content landed.
- Confirm a command or skill resolves at its harness path, e.g. `~/.config/opencode/commands/<name>.md` and `~/.config/opencode/skills/<name>/SKILL.md`.
