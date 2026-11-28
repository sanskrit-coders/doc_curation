---
name: comm
description: Handles external communication — Gmail API OAuth 2.0 (curation_utils.google.gmail), LinkedIn Posts API (curation_utils.social.linkedin), X API v2 (curation_utils.social.x_post), Instagram Login Publishing API (curation_utils.social.instagram), and drafts/statuses for WhatsApp and Telegram. Use when looking up a mailing-list thread, authenticating social/email OAuth, or drafting/posting announcements.
---

Inspect and publish external communications cleanly in `~/gitland/python_venv`.

## Channel Support Matrix

| Channel | Tooling | Credentials / Notes |
|---|---|---|
| **Gmail** | `curation_utils.google.gmail` | OAuth client `~/gitland/vvasuki-git/sysconf/kunchikA/google/proofing/ocr_app_oauth.json`, token `gmail_tokens.json` |
| **LinkedIn** | `curation_utils.social.linkedin` | `[linkedin]` (`client_id`, `client_secret`/`gen`, `redirect_uri="http://localhost:18765/callback"`) in `tokens.toml`, token `kunchikA/social/linkedin_tokens.json` |
| **X (`x.com`)** | Draft-only by default (`curation_utils.social.x_post`) | **X API posting requires payment** — draft to fit X's 280-char limit (doubles as WhatsApp Status). Only use `[x]` OAuth (`http://localhost:18766/callback`, `kunchikA/social/x_tokens.json`) if paid API credits are confirmed |
| **Instagram** | `curation_utils.social.instagram` | `[instagram]` (`app_id`, `app_secret`, `redirect_uri`) in `tokens.toml`, token `kunchikA/social/instagram_tokens.json`; Business/Creator account + public `https://` media URL required |
| **WhatsApp / Telegram Status** | Draft-only | Personal WhatsApp Status and Telegram User Stories lack an official personal-account API here (`jyotir_bot` has `can_connect_to_business: False`, no MTProto session) — prepare concise status text/links (`<= 280`-char X drafts double cleanly as WA Status) |

Never print, log, or commit `tokens.toml` values or cached OAuth token JSON contents.

## Workflows (invoke with `~/gitland/python_venv/bin/python`)

### Gmail (`curation_utils.google.gmail`)

1. Authorize: `python -m curation_utils.google.gmail auth`
2. Inspect latest thread: `python -m curation_utils.google.gmail latest --q "to:sanskrit-programmers@googlegroups.com OR list:sanskrit-programmers.googlegroups.com" --limit 5`
3. Preview draft: `python -m curation_utils.google.gmail send --to ... --reply-query ... --body-file /path/to/msg.txt --llm-name "<ACTUAL LLM NAME>" --prompt "<PROMPT>" --dry-run`
4. Send (only after user approval): drop `--dry-run`.

### LinkedIn (`curation_utils.social.linkedin`)

1. Enable **Share on LinkedIn** (`w_member_social`) and **Sign In with LinkedIn using OpenID Connect** (`openid`, `profile`) and register `http://localhost:18765/callback` in the app's **Auth** tab. Ensure `[linkedin]` in `tokens.toml` has both `client_id` and `client_secret` (or `gen`).
2. Authorize: `python -m curation_utils.social.linkedin auth` (or `exchange --code <CODE_OR_URL>`)
3. Preview: `python -m curation_utils.social.linkedin post --body-file msg.txt --llm-name ... --prompt ... --dry-run`
4. Post (after user approval): drop `--dry-run`.

### X (`x.com`, draft-only unless paid API credits exist)

> **X API posting requires payment:** By default, do **not** run live `x_post post` — prepare a draft fitting `x.com`'s **280-character** limit (which also doubles as a WhatsApp Status; skip the `Sent by ...` attribution header on short messages, or preview via `--dry-run` without `--llm-name`/`--prompt`). Only run steps 1–3 below if the user explicitly confirms paid X API credits:

1. In X Developer Portal (**User authentication settings**), enable **Read and write** and register callback `http://localhost:18766/callback`; set `[x].client_id` in `tokens.toml` (or pass `--oauth1-json` with fresh OAuth 1.0a keys).
2. Authorize: `python -m curation_utils.social.x_post auth`
3. Preview & post: `python -m curation_utils.social.x_post post --body-file msg.txt --dry-run` (omit `--llm-name`/`--prompt` for short posts; drop `--dry-run` after user approval).

### Instagram (`curation_utils.social.instagram`)

1. Use a Business/Creator Instagram account with a Meta app (**Instagram API with Instagram Login**, scopes `instagram_business_basic,instagram_business_content_publish`) and set `[instagram].app_id` + `[instagram].app_secret` in `tokens.toml`.
2. Authorize: `python -m curation_utils.social.instagram auth` (or `exchange --code <CODE>` if Meta uses an HTTPS callback).
3. Preview & post (requires public `https://` image URL): `python -m curation_utils.social.instagram post --image-url https://... --body-file caption.txt --dry-run`

## Safety & Attribution Rules

- **Mandatory draft approval before publishing/sending:** Always run `--dry-run`, show the exact recipient/platform, thread/target, and full text to the user, and wait for explicit approval before sending/posting.
- **Always prepend attribution with the actual LLM name (except short messages):** Every non-short message (emails, LinkedIn posts, long Instagram captions, etc.) sent or drafted on the user's behalf must begin with:
  ```text
  Sent by <LLM name> on behest of vishvAsa's prompt - {<PROMPT>}
  ```
  followed by a blank line before the body (`gmail.prepend_agent_attribution(...)` / `--llm-name` + `--prompt`). Skip this attribution line for short messages (e.g., `<= 280`-character X posts and WhatsApp/Telegram Statuses).
  `<LLM name>` must be the **underlying LLM model name** (e.g., `Gemini 4 Hydrogen`, `Gemini 4 Argon`, `Claude Opus 4.6`, `GPT-5.4`) — **never** a harness, CLI, or IDE name (`Antigravity`, `OpenCode`, `Copilot`, `Kilo`, `Muse`, `Vibe`, `Junie`, `IntelliJ Air`, `Claude Code`). If the active model name is not already explicit in context, check the harness session log or settings (e.g., `~/.gemini/antigravity-cli/log/acp-server-*.log` or `~/.gemini/antigravity-cli/settings.json`) before drafting.
- Never bypass expired/missing OAuth consent or scrape browser cookies/sessions; run the official OAuth consent flow or report the missing credential cleanly.
