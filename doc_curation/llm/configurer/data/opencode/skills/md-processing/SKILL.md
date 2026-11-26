---
name: md-processing
description: Processes Markdown (md) files — bulk transforms, details blocks, footnotes, commentary, include directives, and file splitting — using doc_curation's md/ toolkit. Use when Markdown files need structured content edits beyond simple text replacement.
---
Where appropriate, process Markdown with the `doc_curation.md` toolkit (venv: `~/gitland/python_venv`).

**Fix toolkit shortcomings; don't work around them.** When a toolkit function mishandles the case at hand (wrong output, dropped content, mangled formatting), fix the function in `doc_curation` source with a regression test in `tests/` and run the suite — never paper over it with a one-off bypass script while leaving the bug for the next user.

## Editing content

### Handling `js_include` directives (`<div class="js_include" ...>`)

For `js_include` parameters (`detailsPattern`, `newLevelForH1`, `includeTitle`, etc.), Hugo path resolution (`include.resolve_include_file_path`), refreshing prefills (`surgical_prefill_transitive` / `prefill_includes`), and `include.deinclude`, see the `website` skill. When running Markdown structure transforms on files that contain `js_include` directives:

- **Treat `js_include` divs as atomic boundaries when transforming host files:**
  - Match `<div\s+[^>]*js_include[^>]*>` and track balanced `<div` / `</div>` tags (since a prefilled file-level `js_include` may itself contain nested `<div class="js_include">` blocks) **before** matching headings (`\n#+\s+`) or `<details>` blocks.
  - Never let a host-file `<details>` parser reach inside a `js_include` wrapper unless intentionally syncing an inline prose include (`includetitle="false"`), or inner `<details><summary>मूलम्</summary>` / `###` headings inside prefilled `सर्वाष् टीकाः` includes will be misparsed or split across `</div>` tags.
  - **Nested `js_include` inside `<details>`:** A top-level `<details>` (e.g. `भट्टभास्कर-टीका`, `विश्वास-प्रस्तुतिः`, or a recension-variant section like `आन्ध्रपाठे ऽधिकाः`) may itself contain inline `<div class="js_include">` quotes. Use `details.common.get_js_include_spans(content)` and `details.common.get_top_level_detail_spans(content, skip_js_includes=True)`, and discard any `js_include` span enclosed inside a top-level `<details>` span so combined top-level spans remain strictly disjoint (otherwise emitting both duplicates the include and unbalances `</details>`).

For cross-recension reuse, two-part static layout (`vishvAsa-prastutiH/` + `sarvASh_TIkAH/`), and deduplication rules, see the `commentary_translation` skill (and the `vedic` skill for cross-śākhā Vedic specifics).


### Details blocks
`doc_curation.md.content_processor.details` has several nifty utilities. See `maker`, `transformer`, `seeker` subpackages. For wrapping bare Sanskrit text into `विश्वास-प्रस्तुतिः` / `मूलम्` details blocks or splitting existing coarse blocks into fine sense-unit blocks, use the `text_to_blocks` skill. For cluster anatomy, commentary/translation interleaving, and wrapping non-`विश्वास-प्रस्तुतिः` clusters into `सर्वा अवतारिकाः` / `सर्वाष् टीकाः`, see the `commentary_translation` skill.

#### Preserving `<details>` block structure & invariants

- **Frontmatter vs. horizontal rules:** Anchor frontmatter regexes to the start of the file (`\A(?:\+\+\+.*?^\+\+\+|---.*?^---)`). An unanchored `^---.*?^---` with `MULTILINE`/`DOTALL` will swallow content between mid-file `---` horizontal rules. Preserve mid-file separators (`____________`, `---`) and headings in place.
- **Verify invariants before writing:** For any block splitting, merging, or commentary/avatārikā separation, assert that:
  1. The whitespace-stripped character stream of each layer (`विश्वास-प्रस्तुतिः`, translations, `मूलम्`, `*टीका`, `*अवतारिका`/`*विनियोगः`) is unchanged before and after (except where text is intentionally moved between layers).
  2. `<details>` / `</details>` and `<div` / `</div>` tag counts are balanced.
- **Nested-`<details>` leaf-regex hazard:** Whenever inner `<details>` blocks (e.g. commentaries, translations, `मूलम्`, `पद-पाठः`) live inside outer wrapper blocks (`सर्वाष् टीकाः`, `सर्वा अवतारिकाः` — see the `commentary_translation` skill), naive non-nested `<details[^>]*><summary>([^<]*)</summary>(.*?)</details>` regexes swallow the first inner child `<details>` into the wrapper. Parse hierarchically with `details.common.parse_top_level_details` or forbid nested opens (`(?:(?!<details\b).)*?`) when matching leaf `<details>` blocks.

### Footnotes
`doc_curation.md.content_processor.footnote` — has useful code. `footnote_helper.define_footnotes_near_use` is the usual entry point; other fixers (`fix_plain_footnotes`, `fix_sup_footnotes`, `add_page_id_to_ref_ids`, `comments_to_footnotes`) are shown in `doc_curation_projects/general_tasks/content/footnote_fix.py`.

### Sections
`doc_curation.md.content_processor.section_helper` has useful code — sections: `autonumber`, `fix_headers`, `denumerify_section_titles`, `drop_sections`, `deromanize_section_numbers` . See `doc_curation_projects/general_tasks/content/section_fix.py`.

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
