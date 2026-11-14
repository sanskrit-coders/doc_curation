---
name: md-processing
description: Processes Markdown (md) files — bulk transforms, details blocks, footnotes, commentary, include directives, and file splitting — using doc_curation's md/ toolkit. Use when Markdown files need structured content edits beyond simple text replacement.
---
Where appropriate, process Markdown with the `doc_curation.md` toolkit (venv: `~/gitland/python_venv`).

## Editing content
...


### Content processors

`doc_curation.md.content_processor` subpackages:

- `details` — `<details><summary>मूलम्</summary>` blocks. `maker`, `transformer`, `seeker`.
- `footnote` — footnotes. `footnote_helper.define_footnotes_near_use` is the usual entry point; other fixers (`fix_plain_footnotes`, `fix_sup_footnotes`, `add_page_id_to_ref_ids`, `comments_to_footnotes`) are shown in `doc_curation_projects/general_tasks/content/footnote_fix.py`.
- `commentary` — commentary blocks. For *interleaving* a translation or ṭīkā alongside the mUlam, use the `interleaver` skill.
- `include` — include directives, where one md file's content is included in another. See `doc_curation_projects/general_tasks/content/include_fix.py`.
- `section_helper` — sections: `autonumber`, `fix_headers`, `denumerify_section_titles`, `drop_sections`. See `doc_curation_projects/general_tasks/content/section_fix.py`.



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
