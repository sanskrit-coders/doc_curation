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

## Interactive pages and theme JS/CSS rules

- **DOM stability & event delegation**: `uiLib-bundle.js` no longer rewrites `document.body.innerHTML` on normal loads (`applyInlineComments` only updates leaf blocks containing `+++`), **but** `replaceWithQueryParam(...)` still rewrites `document.body.innerHTML` and `collapsibleSections()` wraps headings in `<details>`. Still prefer:
  - Delegating from `document` (`click`/`input` with id checks) rather than caching element refs or binding before `sdThemeDone`.
  - Hydrating interactive widgets on `sdThemeDone` (plus `DOMContentLoaded` if needed).
  - Guarding inline `<script>` DOM wiring with `typeof document !== "undefined"` so Node can unit-test pure functions.
- **Deferred vs sync `uiLib-bundle.js`**: `head_js.html` loads `uiLib-bundle.js` with `defer` unless `.RawContent` contains `<script` (in which case it loads synchronously so inline scripts calling `module_uiLib` or `module_dir_tree` still work at parse time).
- **Code-splitting & Bootstrap-lite**: `uiLib-bundle.js` (~58 KB) excludes jQuery/Popper/Bootstrap JS (replaced by delegated `setupBootstrapLite()` supporting only `data-toggle="collapse"` and `data-toggle="dropdown"`) and lazy-loads heavy chunks on demand (`spreadsheets` for `.spreadsheet`, `mdInclude` for `.md` `js_include`s, `sanscript` when transliteration/TTS is active, `mathjaxMacros`). Do not introduce dependencies on jQuery `$`, other Bootstrap JS widgets, or eager imports of heavy parsers into the entry bundle.
- **Fast startup & `index.json`**: Hugo emits `pageVars.pageParams` directly (`hugo-page-vars-to-js.html`), so content prep, includes, TOC, and `sdThemeDone` run immediately without awaiting `index.json`. `index.json` (slimmed to `title`, `relUrl`, `_index.md` `logicalName`, `lastmod`, `practice_weight`) prefetches in `<head>`, caches in Cache API (`sd-theme-index-v1`), and concurrently populates the lazy sidebar (`data-recdir` folders expand on `toggle`) and lazy `#pageDataList` (`#searchInput` focus). Keep `file://` (offline Android) working via XHR fallback (`utils.fetchText`/`fetchJson`).
- **MathJax & fonts**: Site-wide `js_extras = ["mathjax"]` only loads `tex-svg.js` eagerly if `.RawContent` has `@#`, `$$`, `\(`, or `\[` (or page frontmatter sets `js_extras = ["mathjax"]`), with dynamic load fallback after `js_include`. `static/css/fonts.css` serves `.woff2` (`.ttf` fallback) with `font-display: swap` and per-script `unicode-range`.
- **Rebuilding theme bundles**: After editing `webpack_src/`, run `npm run build` (`webpack --env production`) inside `webpack_src/` and commit updated `static/webpack_dist/` assets.

## Includes (`js_include`) and prefilling

Full attribute docs for `<div class="js_include">`, `<div class="spreadsheet">`, `<div class="audioEmbed">`, and `<div class="videoEmbed">` live in `themes/sanskrit-documentation-theme-hugo/README.md`.

- **Source of truth lives in `static/` (or another `content/` repo):** A `<div class="js_include" ... url="...">...</div>` block in a host `.md` file holds a prefilled inline snapshot (typically wrapped in `<details open><summary><hN>... …{Loading}…</hN></summary>`) that is dynamically replaced at page load.
  - Resolve target files via `doc_curation.md.content_processor.include.resolve_include_file_path(url, hugo_base_dir="/home/vvasuki/gitland/vishvAsa", current_file_path=...)` (wraps `file_path_from_url` with directory `_index.md` fallback and raw `static/*.md` relative-path handling):
    - Root-relative URLs ending in `.md` map to `<hugo_base_dir>/<repo>/static/<rest>.md`.
    - Root-relative URLs without `.md` map to `<hugo_base_dir>/<repo>/content/<rest>.md` (or `_index.md`).
  - `js_include` behavior & prefill parity:
    - `detailsPattern` (default `".*"`): when set to something other than `".*"`, only `<details>` blocks whose trimmed `<summary>` matches the regex are included (matching outer `<details>` keep their children; non-matching `<details>` recurse into child `<details>`).
    - `newLevelForH1` (`"1"`–`"6"` or `"b[]"`; nested shifts use `min(6, (child - 1) + parent)`), `includeTitle` (`"true"`, `"plain"`, or `"false"`, overriding `title`), `title`, and `class="js_include collapsed"` control title/collapse output.
    - For `.md` URLs, `fieldNames` prepends selected frontmatter keys and `metadataDetailName` (unless omitted or `"false"`) prepends a frontmatter `<details>` block.
- **Refreshing prefilled includes:**
  - When editing included `static/` or cross-repo `content/` sources, propagate changes across all transitive host containers via `include.surgical_prefill_transitive([static_dir, content_dir], changed_file_paths, hugo_base_dir="/home/vvasuki/gitland/vishvAsa")` (preserves `{Loading}` headers, Hugo `{{< ... >}}` shortcodes, and multi-hop nested `js_include`s without BeautifulSoup re-serialization; `include.surgical_prefill_includes` refreshes a single directory, and `include.prefill_includes` / `prefill_include` is the BeautifulSoup prefiller).
  - To inline matching `js_include` directives directly into host files and safely delete unreferenced included source files, use `include.deinclude(dir_path, url_filter=..., prefill=True, delete_included_files=True, reference_check_roots=..., dry_run=...)` (or `include.deinclude_content`). It uses balanced div slicing, applies `detailsPattern`/`fieldNames`/`metadataDetailName`, strips `{Loading}` and `<hN>` summary tags, and preserves open vs. collapsed `<details>` state.
  - See `doc_curation.md.content_processor.include` and `doc_curation_projects/general_tasks/content/include_fix.py`.

## Updating theme submodules across all Hugo sites

Whenever `sanskrit-documentation-theme-hugo` changes must roll out everywhere:

1. **Discover all checkouts**: Look across `~/gitland/vishvAsa/*` (31 repos) plus the standalone org repos (`~/gitland/sanskrit-coders/sanskrit-coders.github.io`, `~/gitland/sanskrit/sanskrit.github.io`, `~/gitland/hindutva/hindutva.github.io`, `~/gitland/become-hindu/become-hindu.github.io`, `~/gitland/jyotisham/jyotisham.github.io`, `~/gitland/subhashita/subhAShita.github.io`, `~/gitland/xetram/xetram.github.io`) — verify with a directory scan for `themes/sanskrit-documentation-theme-hugo`.
2. **Pre-flight checks before editing**:
   - Ensure the canonical theme checkout (`notes/themes/sanskrit-documentation-theme-hugo`) is clean, tested (`verify_theme.py`), and pushed to `origin/master`.
   - Fetch `origin` in each site repo and verify `0 0` sync, confirm `git diff --cached --name-only` is empty (do not sweep user-staged work), check each submodule checkout is clean, and inspect `.github/workflows/build*.yml` (both `master` and `content` branches when applicable, watching `hugo-version` compatibility and branch name, e.g. `jyotisham` uses `hugo-source`).
3. **Update, verify, commit, and push**:
   - Inside each site's `themes/sanskrit-documentation-theme-hugo`, fetch `origin master`, switch to `master` if detached, and fast-forward (`git merge --ff-only <target_sha>`).
   - Spot-check `hugo --destination <tmpdir>` builds (especially sites with custom `layouts/` like `rahaShTippanyaH` or special `config*.toml` like `mImAMsA`, `mahAbhAratam`) without clobbering `build_github/`.
   - Commit **only** the submodule (`git commit --only themes/sanskrit-documentation-theme-hugo -m "Update theme submodule: ..."`), never sweeping dirty `content/` or `static/` submodule pointers.
   - Push each site's branch (`git push origin <branch>`) and verify CI with `gh run list -R <org>/<repo>`.

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
- Theme verification & 4G performance regression suite (Playwright + Hugo):
  - Fixture suite + offline `file://` check + bundle/4G budgets:
    `~/gitland/python_venv/bin/python themes/sanskrit-documentation-theme-hugo/tests/verify_theme.py`
  - Benchmark any site or built directory:
    `~/gitland/python_venv/bin/python themes/sanskrit-documentation-theme-hugo/tests/verify_theme.py --site <site_dir> --base-path /<repo>/` (or `--built-dir <dir> --no-perf-assert`).
- `gh run list --repo <org>/<repo>` for CI; `curl` the live URL and check
  the `<title>` after Pages deploys (takes ~1 min).
- Check `git status` before every commit in repos the user edits; staged
  work of theirs must never be swept into your commit message.

## Shell notes

- Never `&`-background; use `setsid -f` for servers, then kill precisely.
- `pkill -f` matches your own command line — use the `[.]` trick
  (e.g. `pkill -f "http[.]server 8321"`).
- `$?` after `cmd | head` is head's status, not cmd's — assert `grep`
  emptiness without a pipe.
