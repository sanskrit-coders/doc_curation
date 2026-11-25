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

## Updating derived AI prompts

`data/opencode/skills/proofreader-hyphenator/SKILL.md` is the canonical main copy of the proofreading and hyphenation rules.
Two standalone prompts in `dyumatsyAH` (read by `doc_curation.llm.get_prompt(path, block_index=0)`) are derived from it and should be regenerated with an LLM coding agent whenever rules in `proofreader-hyphenator/SKILL.md` change:

- `~/gitland/vishvAsa/dyumatsyAH/content/prakriyA/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md`
- `~/gitland/vishvAsa/dyumatsyAH/content/prakriyA/proofreading/editing/AI-prompt/bare-hyphenator.md`

### Rules for regenerating those two files

1. **`Sanskrit_devanAgarI_markdown.md`:**
   - Keep the Hugo TOML frontmatter (`+++\ntitle = "Sanskrit devanAgarI markdown"\n\n+++`) and update only the **first** fenced ```` ```markdown ... ``` ```` code block (leaving any human-only notes below it untouched).
   - Phrase the rules from `proofreader-hyphenator/SKILL.md` as a self-contained single-turn prompt ("You are an expert Sanskrit proofreader and formatter...", `"Your entire output must be a single Markdown code block."`, ending with `"Are you ready?"`):
     - Include the `<details><summary>मूलम्</summary>` preservation clauses (preamble and Final Markdown formatting bullet).
     - Include Part 1 (Definitions, Separation Principle, Absolute Non-Separability Veto Rule, Boundary Types & Examples) and Part 2 (Workflow: cleanup, Core Separation Algorithm across Devanagari and non-Devanagari Sanskrit, Sentence and Phrase Line Breaks, `[[OLD|NEW]]` source error handling + `[[??]]` illegible spans, Final Markdown Formatting).
     - **Exclude** coding-agent-only sections (`Special hyphenation tools` and `Report`).

2. **`bare-hyphenator.md`:**
   - Keep the Hugo TOML frontmatter (`+++\ntitle = "Bare Hyphenator"\n+++`) and place the prompt inside the **first** fenced ```` ```markdown ... ``` ```` code block.
   - Match the regenerated `Sanskrit_devanAgarI_markdown.md` prompt block **except**:
     - **Omit** both `<details><summary>मूलम्</summary>` preservation clauses (preamble sentence and Final Markdown formatting bullet), because callers such as `process_details_with_keys` pass bare or `मूलम्` detail blocks directly to it.
     - **Omit** everything after the closing ```` ``` ```` fence (no `PROMPT ENDS ABOVE...`, `Variants`, or `उदाहरणानि`).

3. **Verify:** Run `~/gitland/python_venv/bin/python` to confirm `doc_curation.llm.get_prompt(path)` extracts the full prompt cleanly (`block_index=0`) from both files without any coding-agent tool references.

## Gotchas

- Renaming a command file renames the generated TOML too; the stale one is pruned. After a rename, run `sync` rather than editing the generated file.
- Command names must match `[a-z0-9]+([-_][a-z0-9]+)*`; agent names allow only single hyphens.
- Prompts in the generated TOML use `{{args}}` for the user's arguments, where Markdown commands use `$ARGUMENTS`.
- A new harness needs an entry in `SYNCERS` (`sync.py`) and in `MANAGED_LINKS` (`symlinks.py`).
- `sync` only propagates *frontmatter description and body*; check the generated file after a large rewrite.

## Verify

- Re-read the generated file (e.g. `data/antigravity/commands/<name>.toml`) to confirm the content landed.
- Confirm a command or skill resolves at its harness path, e.g. `~/.config/opencode/commands/<name>.md` and `~/.config/opencode/skills/<name>/SKILL.md`.
