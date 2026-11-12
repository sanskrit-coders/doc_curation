---
name: markdown-processing
description: Processes Sanskrit Markdown files — bulk transforms, details blocks, footnotes, commentary, include directives, and file splitting — using doc_curation's md/ toolkit. Use when Markdown files need structured content edits beyond simple text replacement.
---

Process Sanskrit Markdown with the `doc_curation.md` toolkit (venv: `~/gitland/python_venv`).

## Bulk transforms

`doc_curation.md.library.apply_function` processes every Markdown file under a path:

```python
library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=content_transformer, dry_run=False, silent_iteration=False)
```

Prefer `dry_run=True` on a first pass when the transform is new.

## Content processors (`doc_curation.md.content_processor`)

- `details` — `<details><summary>मूलम्</summary>` blocks.
- `footnote` — footnotes.
- `commentary` — commentary blocks.
- `indlude` — include directives, where one md file's content is included in another.

## Splitting Markdown files

`/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation_projects/general_tasks/splitter.py`
