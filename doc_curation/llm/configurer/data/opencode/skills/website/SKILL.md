---
name: website
description: Build and maintain the vishvAsa/sanskrit Hugo sites (repo layout, sidebars, URLs, uiLib JS rules, verification).
---

# Website

Use for work on the Hugo sites under `~/gitland/vishvAsa/` and
`~/gitland/sanskrit/` (content moves, new repos, sidebars, link fixes,
interactive pages, deploys).

## Repo layout (every site follows it)

- `master` branch: scaffold only — `config.toml`, `config_offline_android.toml`,
  `data/`, `themes/` + `content/` submodules, `.github/workflows/build.yml`,
  `.gitignore`, `<repo>.iml`.
- `content` branch (the GitHub **default** branch): site content at root plus
  `.github/workflows/{build.yml,index_pages.yml}`. No `.gitignore` (only
  `sanskrit` has one, repo-specific — do not copy it).
- `content/` submodule on master tracks the same repo's `content` branch;
  `themes/sanskrit-documentation-theme-hugo` tracks sanskrit-coders.
- `gh-pages` branch is the deployed build; enable Pages from it via
  `gh api repos/<org>/<repo>/pages -X POST -f 'source[branch]=gh-pages'`.
- New repo order: `gh repo create` → push `content` → push `master` →
  default-branch `content` → `git submodule add` (never hand-write
  `.gitmodules` first) → commit gitlinks → enable Pages.
- First CI runs fail until the gitlink commit lands (theme/content missing);
  this bootstrap failure is expected, not a bug.

## Interactive pages: the uiLib rule

`uiLib-bundle.js` rewrites `document.body.innerHTML` after load, silently
dropping listeners attached during parsing (proven by MutationObserver probe;
no console errors). For any in-page JS:

- Delegate from `document` (`click`/`input` with id checks), never
  `getElementById(...).addEventListener` at parse time.
- Re-query elements inside every handler; never cache refs.
- Inline `<script>` in `.md` files renders fine (`unsafe=true`); guard
  DOM wiring with `typeof document !== "undefined"` so node can test the
  pure logic by extracting the script block.

## Sidebars

- Sibling list lives in `data/sidebars/*_sidebar.yml` under `सङ्ग्रहान्तरम्`
  (names vary: `home_sidebar`, `kAvya_sidebar`, `kannada_sidebar`,
  `bhAShAntara_sidebar`). Insert new-repo entries after `Book pub`.
- Outliers: `english` (anchor `भाषान्तरम्`, home link inside the list),
  `pALi`/`tipiTaka` (anchor `English Lit`), `rahaShTippanyaH` (no sibling
  list — skip), `top_bar.yml` files (topnav, not sidebars — skip),
  `vishvAsa.github.io/conversations_sidebar.yml` (skip),
  `agnirahas.bitbucket.org` and `image-pub` (no sidebars — skip).
- Commit exactly one file per repo (`git add <sidebar file>`); never sweep
  pre-existing dirty submodule pointers into the commit.
- A repo may be deliberately unlisted (e.g. `dyumatsyAH`): never add such
  links anywhere, including its own sidebar.

## URLs and moves

- Internal links use absolute paths (`/dyugangaa/...`) and full
  `https://vishvAsa.github.io/...` URLs; query placeholders
  `?githubUserId=XYZ&repo=REPO` are rewritten client-side by
  `contribution-page-customizer.js` — preserve them verbatim.
- `js_include` divs accept cross-site absolute paths (precedent:
  `url="/rAmAnujIyam/..."`).
- When moving content: enumerate every stale URL, verify each target exists
  at its new location (a move may split targets across repos — e.g.
  `searchable-text/` stayed on `dyugangaa`), then rewrite specific prefixes
  before general ones. Fix inbound links in the same commit.
- Functional identifiers (localStorage keys, branding names, mailing-list
  and short links) stay untouched; only site URLs move.

## Verification

- `hugo` in the master checkout must build cleanly.
- `gh run list --repo <org>/<repo>` for CI; `curl` the live URL and check
  the `<title>` after Pages deploys (takes ~1 min).
- Browser testing: Playwright lives in `~/gitland/python_venv`;
  serve a local build under its subpath (`/tmp/serve/<repo>/`) so absolute
  asset paths resolve.
- Check `git status` before every commit in repos the user edits; staged
  work of theirs must never be swept into your commit message.

## Shell notes

- Never `&`-background; use `setsid -f` for servers, then kill precisely.
- `pkill -f` matches your own command line — use the `[.]` trick
  (e.g. `pkill -f "http[.]server 8321"`).
- `$?` after `cmd | head` is head's status, not cmd's — assert `grep`
  emptiness without a pipe.
