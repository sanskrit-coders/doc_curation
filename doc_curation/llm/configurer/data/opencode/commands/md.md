---
description: Runs a doc_curation md/ transform (bulk edits, details, footnotes, includes, sections, splitting) over the given path.
---
Load the md-processing skill and process the given Markdown:

$ARGUMENTS

If no path is given, ask for one, and confirm the target path before transforming a directory. Start any new transform with `dry_run=True` and show the resulting `git diff --stat` before applying it.
