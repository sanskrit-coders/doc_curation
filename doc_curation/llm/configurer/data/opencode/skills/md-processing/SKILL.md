---
name: md-processing
description: Processes Markdown (md) files — bulk transforms, details blocks, footnotes, commentary, include directives, and file splitting — using doc_curation's md/ toolkit. Use when Markdown files need structured content edits beyond simple text replacement.
---
Where appropriate, process Markdown with the `doc_curation.md` toolkit (venv: `~/gitland/python_venv`).

## Editing content

### Handling `js_include` directives (`<div class="js_include" ...>`)

- **Source of truth lives in `static/` (or another `content/` repo):** A `<div class="js_include" ... url="...">...</div>` block in a host `.md` file holds a prefilled inline snapshot (typically wrapped in `<details open><summary><hN>... …{Loading}…</hN></summary>`) that is dynamically replaced at page load.
  - Resolve the target file with `include.file_path_from_url(url, hugo_base_dir="/home/vvasuki/gitland/vishvAsa", current_file_path=...)`:
    - Root-relative URLs ending in `.md` (e.g. `/vedAH_yajuH/taittirIyam/.../foo.md` or `/vedAH_Rk/shAkalam/.../bar.md`) map to `/home/vvasuki/gitland/vishvAsa/<repo>/static/<rest>.md`.
    - Root-relative URLs without `.md` map to `/home/vvasuki/gitland/vishvAsa/<repo>/content/<rest>.md` (or `_index.md`).
  - When a task applies to included content as well, edit the underlying `static/` (or cross-repo `content/`) source files and refresh the host files' inline snapshots via `include.prefill_includes(dir_path=...)` (or apply the transform to both so they stay in sync).
- **Treat `js_include` divs as atomic boundaries when transforming host files:**
  - Match `<div\s+[^>]*js_include[^>]*>.*?</div>` (note: `class` may be `"js_include"` or `"js_include collapsed"`, and attributes like `unfilled` may precede `url`) **before** matching headings (`\n#+\s+`) or `<details>` blocks.
  - Never let a host-file `<details>` parser reach inside a `js_include` wrapper unless intentionally syncing an inline prose include (`includetitle="false"`), or inner `<details><summary>मूलम्</summary>` / `###` headings inside prefilled `सर्वाष् टीकाः` includes will be misparsed or split across `</div>` tags.

For various python utilities, see `doc_curation.md.content_processor.include` and `doc_curation_projects/general_tasks/content/include_fix.py`.


### Details blocks
`doc_curation.md.content_processor.details` has several nifty utilties. See `maker`, `transformer`, `seeker` subpackages.

#### Preserving `<details>` block structure & invariants

- **Cluster anatomy:** A standard unit in case of vedic text consists of optional `<details><summary>*विनियोगः</summary>` (`भास्करोक्त-विनियोगः`, `सायणोक्त-विनियोगः`, etc.), followed by `<details open><summary>विश्वास-प्रस्तुतिः...</summary>`, `<details><summary>मूलम्</summary>`, and commentary blocks (`भट्टभास्कर-टीका`, `सायण-टीका`, etc.). Section-intro blocks (`विस्तारः (द्रष्टुं नोद्यम्)`) and trailing summaries (`विनियोगसङ्ग्रहः`) sit outside individual unit clusters.
- **Frontmatter vs. horizontal rules:** Anchor frontmatter regexes to the start of the file (`\A(?:\+\+\+.*?^\+\+\+|---.*?^---)`). An unanchored `^---.*?^---` with `MULTILINE`/`DOTALL` will swallow content between mid-file `---` horizontal rules. Preserve mid-file separators (`____________`, `---`) and headings in place.
- **Editorial glosses & layer alignment:** `विश्वास-प्रस्तुतिः` often adds `+++(...)+++` glosses, supplied elliptical verbs, hyphens, and punctuation not present in `मूलम्`. Mask or strip `+++(...)+++` glosses and svaras (`[\u0951-\u0954\u1cd0-\u1cff]`) when aligning sentence segments or commentary pratīkas across layers, and never split on daṇḍas inside `+++(...)+++`, quotes, or parentheses.
- **Verify invariants before writing:** For any block splitting, merging, or commentary/viniyoga separation, assert that:
  1. The whitespace-stripped character stream of each layer (`विश्वास-प्रस्तुतिः`, `मूलम्`, `*टीका`, `*विनियोगः`) is unchanged before and after (except where text is intentionally moved between `*टीका` and `*विनियोगः`).
  2. `<details>` / `</details>` and `<div` / `</div>` tag counts are balanced.

### Footnotes
`doc_curation.md.content_processor.footnote` — has useful code. `footnote_helper.define_footnotes_near_use` is the usual entry point; other fixers (`fix_plain_footnotes`, `fix_sup_footnotes`, `add_page_id_to_ref_ids`, `comments_to_footnotes`) are shown in `doc_curation_projects/general_tasks/content/footnote_fix.py`.

### Sections
`doc_curation.md.content_processor.section_helper` has useful code — sections: `autonumber`, `fix_headers`, `denumerify_section_titles`, `drop_sections`. See `doc_curation_projects/general_tasks/content/section_fix.py`.

### Other Content processors

`doc_curation.md.content_processor` subpackages:

- `commentary` — commentary blocks. For *interleaving* a translation or ṭīkā alongside the mUlam, use the `interleaver` skill.



## Editing Metadata

Files should have proper TOML metadata (preferred over YAML). Useful functions in `doc_curation.md.library.metadata_helper`:

- `set_title_from_filename` — title from the file name.
- `set_filename_from_title` — file name from the title.
- Others: `transliterate_title`, `set_index_from_filename`, `ensure_ordinal_in_title`, `prepend_file_index_to_title`.

See `doc_curation_projects/general_tasks/metadata_fix.py` for usage.

## Bulk transforms

`doc_curation.md.library.apply_function` runs a transform over every Markdown file under a path:

```python
from doc_curation.md import library
from doc_curation.md.file import MdFile

library.apply_function(fn=MdFile.transform, dir_path=dir_path,
                       content_transformer=my_transformer, dry_run=False)
```

Signature: `apply_function(fn, dir_path, file_pattern="**/*.md", file_name_filter=None, start_file=None, end_file=None, silent_iteration=True, *args, **kwargs)`.

Gotchas —

- **`dry_run` is not an `apply_function` parameter** — it is forwarded through `**kwargs` to the callback, so the callback must accept it. `MdFile.transform` does; a bare `lambda c: ...` will raise `TypeError`.
- **`content_transformer` is called as `content_transformer(content, metadata=metadata, **kwargs)`.** Use `lambda c, *args, **kwargs: ...` or a named function; `metadata` also carries a `_file_path` key. Returning `None` skips the file.
- Scope large trees with `file_pattern`, `file_name_filter`, `start_file`, `end_file` rather than pointing at a whole `content` directory. `file_name_filter` receives a `pathlib.Path`, so use `lambda p: str(p).endswith(".md")`.

Workflow: run with `dry_run=True`, inspect `git diff --stat`, then run for real and re-check the diff.


## Splitting and placing Markdown files

```python
from indic_transliteration import sanscript

library.apply_function(fn=MdFile.split_to_bits, dir_path=path_to_md,
                       source_script=sanscript.DEVANAGARI, start_index=None,
                       target_frontmantter_type=MdFile.TOML, dry_run=False)
```

`MdFile.split_to_bits(source_script, mixed_languages_in_titles, bits_dir_url, maybe_use_dravidian_variant, target_frontmantter_type, add_short_title, deromanize, start_index, dry_run, max_length)` writes one file per section into a sibling directory named after the source file (in place for `_index.md`). Worked invocations for Devanagari, Kannada and IAST sources are in `doc_curation_projects/general_tasks/splitter.py`.

Whenever you create markdown files in a directory within a `vishvAsa/*/content` path, fix the index files there:

```python
from doc_curation.md.library import arrangement
arrangement.fix_index_files(dir_path=dir_path, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
```

## Conversion to epub/pdf

Use `doc_curation.ebook.make_all`:

```python
from doc_curation import ebook
ebook.make_all(source_dir=book_dir, out_path=out_dir, metadata={"author": "..."},
               css_path=CSS_PATH, appendix=appendix_md, file_split_level=1,
               detail_pattern_to_remove=r"मूलम्.*", booklets=["a4"])
```

`doc_curation_projects/general_tasks/ebooks.py` holds the CSS path and worked examples, including booklet page sizes and `split_locus`.
