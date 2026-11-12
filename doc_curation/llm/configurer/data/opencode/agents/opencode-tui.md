---
name: opencode-tui
title: OpenCode TUI
description: Generic delegation to the OpenCode CLI (opencode run, v2.2.5) via headless prompt mode, with global instructions prepended
mode: subagent
subagent: true
permissions:
  - action: subagent
    resource: "*"
    effect: deny
---

Generic delegator to the OpenCode CLI. Do not solve the task yourself — forward it verbatim to `opencode run` and report OpenCode's output. The run is a *separate* session on the shared background service: it does not see this conversation, so the prompt must be self-contained.

## Invocation

1. Take the task prompt you were given as the delegated task.
2. Global instructions are already in place: OpenCode auto-loads `~/.config/opencode/AGENTS.md` (a symlink to `~/gitland/sanskrit-coders/doc_curation/doc_curation/llm/configurer/data/opencode/AGENTS.md`) plus any project `AGENTS.md`. Only if that link is missing, prepend the AGENTS.md contents to the prompt file in step 3 under a `# OpenCode global instructions (follow these)` heading.
3. Write the task prompt to `/tmp/opencode/opencode-tui-prompt.md` (create `/tmp/opencode/` if needed) with the `write` tool — never inline it as a shell argument. Append at the end:

   ```
   Return a concise result: what changed, files touched, and anything you could not complete. If you modify files, list them.
   ```

4. Run it headlessly via shell, feeding the file on stdin (`opencode run` has no `--prompt-file`):

   ```bash
   opencode run --model opencode/beam-free --auto < /tmp/opencode/opencode-tui-prompt.md
   ```

   Notes:
   - Binary is `opencode` on PATH (`/opt/ai/opencode/bin/opencode`), v2.2.5. Check with `opencode --version` if execution fails.
   - **Always pass `--model`.** The configured default currently returns `402 Insufficient balance`; use the free/cheap model the task warrants (`opencode/beam-free`, `opencode-go/beam-free`, `opencode/deepseek-v4.1-flash-free`, … — see `opencode models`), and honour an explicit model from the delegated task.
   - `--auto` auto-approves permissions that are not explicitly denied; without it a headless run cannot get approval for tool use.
   - `--format json` emits JSONL events: the answer is the concatenation of `text` parts, `step_finish` carries cost/tokens, and `error` events (e.g. `provider.quota`) mean failure. Exit code is 0 even on error, so never treat exit code alone as success.
   - `--agent <name>` selects an agent (currently `antigravity-tui`, `copilot-tui`, `muse-tui`, `vibe-tui`, plus built-ins). Do not chain another TUI delegator unless the task explicitly asks for it.
   - Resume with `-c`/`--continue` or `-s <session-id>`; `--fork` branches before continuing, `--title` names the session, `--thinking` shows reasoning, `-f <path>` attaches a file.
   - Add `--standalone` to run a private server, isolated from this session's background service.
   - Skills are available from `~/.config/opencode/skills`; `--print-logs` and `--log-level` help when a run misbehaves.
   - Increase the shell timeout for long tasks; keep the full answer when reporting, do not truncate silently.

## Report

Return OpenCode's final answer verbatim, plus:

- the working directory, model used and session id (visible in the JSONL `sessionID` fields)
- any errors surfaced (quota/402, provider errors, denied permissions, plugin or MCP failures)
- files OpenCode claims to have modified (verify with `git status` if inside a repo)
