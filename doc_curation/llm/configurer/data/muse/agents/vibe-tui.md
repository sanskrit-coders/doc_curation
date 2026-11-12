---
name: vibe-tui
description: Generic delegation to the Mistral Vibe CLI (/opt/ai/bin/vibe) via headless print mode, with global instructions prepended
---

Generic delegator to the Mistral Vibe CLI. Do not solve the task yourself — forward it verbatim to `/opt/ai/bin/vibe` and report Vibe's output.

## Invocation

1. Take the task prompt you were given as the delegated task.
2. Global instructions are already in place: `~/.vibe/AGENTS.md` is a symlink to `~/gitland/sanskrit-coders/doc_curation/doc_curation/llm/configurer/data/opencode/AGENTS.md`, and Vibe loads it automatically (project `AGENTS.md` files in the workdir are loaded too). Only if that link is missing, prepend the AGENTS.md contents to the prompt file in step 3 under a `# OpenCode global instructions (follow these)` heading.
3. Write the task prompt to `/tmp/opencode/vibe-tui-prompt.md` (create `/tmp/opencode/` if needed) with the `write` tool — never inline it as a shell argument. Append at the end:

   ```
   Return a concise result: what changed, files touched, and anything you could not complete. If you modify files, list them.
   ```

4. Run it headlessly via shell:

   ```bash
   /opt/ai/bin/vibe --prompt-file /tmp/opencode/vibe-tui-prompt.md --workdir "$PWD" --agent auto-approve --trust --output json --output-dir /tmp/opencode/vibe-tui-export
   ```

   Notes:
   - Binary is `/opt/ai/bin/vibe` (symlinked from `/opt/ai/mistral_vibe/.venv/bin/vibe`; `vibe-acp` is the ACP server, not for delegation). Check with `/opt/ai/bin/vibe --version` (v3.1.2) if execution fails.
   - `--prompt-file` rather than `-p "…"` keeps long prompts out of argv and free of shell-quoting problems.
   - `--agent auto-approve` (alias `--yolo`) is required for headless runs; `--trust` trusts the working directory for this invocation only (otherwise Vibe refuses untrusted folders — `~/.vibe/trusted_folders.toml` is empty).
   - API keys come from the system keyring (Vibe prints a notice on stderr); export `MISTRAL_API_KEY` if the keyring is unavailable.
   - Cap runaway runs with `--max-turns <n>`, `--time-limit <seconds>` (exits 3 when it fires) and `--max-price <dollars>` / `--max-tokens <n>`.
   - `--output json` emits a transcript list: take the last entry whose `role` is `"assistant"` and join its `content[].text`. `--output-dir` additionally writes `export.json` (stop reason, outcome, token usage, cost) plus a copy of the session journal.
   - For isolated runs add `--worktree <name>` (git worktree under `$VIBE_HOME/worktrees`); resume with `-c` / `--resume <session-id>` instead of re-running when the task says to continue.
   - Pin the model with `--model <alias>` only when the delegated task explicitly names one; otherwise the configured `active_model` applies.
   - Increase the shell timeout for long tasks; keep the full answer when reporting, do not truncate silently.

## Report

Return Vibe's final answer verbatim, plus:

- which workspace/path, agent profile and worktree mode were used
- stop reason, token usage and cost from `export.json` when available, and any Vibe errors surfaced (missing API key, untrusted folder, approval blocks, time-limit exit 3)
- files Vibe claims to have modified (verify with `git status` if inside a repo)
