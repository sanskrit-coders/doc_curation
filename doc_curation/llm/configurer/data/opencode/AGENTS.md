# Global instructions

## Subagents

- Delegate to subagents whenever possible — exploration, research, multi-step work, or anything matching a listed agent's description — to keep the main context small.
- When running in JetBrains Air (which does not render background wakeups after a turn ends), poll active subagents periodically within the turn (using synchronous waits and `manage_subagents` checks) rather than ending the turn, and resume polling after handling any new user messages while subagents remain active.

### Model selection

- Be careful to use a free/lightweight model whenever possible.
- For bulk, mechanical, or low-risk work (formatting, repetitive edits, simple searches, large-file scanning), prefer a zero-cost model (eg. `opencode/Iceman`, "kilo/nvidia/ nemotron-3-ultra-550b-a55b:free high",) or low-cost model (eg. "flash_lite"). You can even use *-tui subagents for accessing such models.
- When delegating to a subagent, pass the model explicitly via the `model` parameter, e.g. `opencode-go/beam-free#xhigh`.
- Reserve stronger/paid models for judgment calls, verification of free/lighter-model output, and tasks where the lighter model is unsuitable.


## Compute

- Do NOT run CPU-heavy tasks on the local machine; offload them to Kaggle or Google Colab instead. Avoid grinding the local CPU.

## Asking the user

- The chat client may not be able to render interactive prompts: the `question` tool can fail with "The question couldn't be shown to the user in this client" (seen with OpenCode over ACP inside IntelliJ Air). Do not treat that as a hard stop — fall back in this order:
  1. `~/.local/bin/ask-gui "Question?"` — free-text answer on stdout.
  2. `~/.local/bin/ask-gui -c "Pick one" "A" "B" ...` (or `-m` for multi-select) — chosen option(s) on stdout.
  3. Ask in the reply text and end the turn.
  The scripts pop a zenity (falling back to kdialog/yad) dialog on `DISPLAY` (default `:1`), time out after 300 s (`ASK_GUI_TIMEOUT`), and exit 1 if the user cancels. Only use them for genuine blocking decisions; otherwise make a stated assumption and continue.

## Privileged commands (sudo)

- `sudo` requires a password on this machine. Prompt for it in a GUI dialog rather than failing or asking for the password in chat: `SUDO_ASKPASS=~/.local/bin/sudo-askpass sudo -A <command>`. `sudo -A -v` primes the sudo timestamp, after which plain `sudo` keeps working for `timestamp_timeout`. `pkexec <command>` also works (the polkit-gnome agent is running).
- Never request, echo, or store the password in plain text or in files. Prefer doing the unprivileged part (download, extract, verify) first and then running a single, clearly-explained privileged command.

## Existing code

Use and maintain existing code where possible — it is installed in the venv at `~/gitland/python_venv`, so invoke `~/gitland/python_venv/bin/python` (**not** the default `python3`).
- **Suggest retaining useful tooling:** When work produces a reusable utility, validator, parser, or workflow (even if prototyped as a scratch script), suggest promoting it into the appropriate shared repository (such as `doc_curation`) with tests rather than leaving it ephemeral.

### doc_curation
Before writing text-processing code, check these in `~/gitland/sanskrit-coders/doc_curation`:

- `doc_curation.md.library` has `apply_function` which is especially useful for bulk processing Markdown files within a path. Use it in combination with other functions as needed.
- `doc_curation.sanskrit` includes `accent` `sandhi_check` (forward-sandhi verification), `reconciler` for `[[OLD|NEW]]` suggestions, `validator` (for block integrity), `fixer`.

For files with Sanskrit names you output, use something like `curation_utils.file_helper.get_storage_name(SANSKRIT_TEXT, source_script=sanscript.IAST)`.


### Other libraries

For meters, there is `chandas`. For archive.org work and "source to site-page" catalog updates, use the `archival-cataloging` skill.
