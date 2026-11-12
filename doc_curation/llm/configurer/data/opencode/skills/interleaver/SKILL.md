---
name: interleaver
description: Interleaves translations or commentaries into Markdown files containing mUlam blocks, generating mUlam blocks first when missing. Use when a translation or ṭīkā must be placed alongside the Sanskrit mUlam in a file.
---

Interleave translations or commentaries into the Markdown files you are given.

1. **Generate mUlam blocks if missing.** If the files have no `<details><summary>मूलम्</summary>` blocks, create them first:
   ```python
   library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: maker.generic_sanskrit_vipra_mUla(c))
   ```
   (`maker` is `doc_curation.md.content_processor.details.maker`.)

2. **Sanskrit commentaries (ṭīkā).** If you are interleaving a commentary, call:
   ```python
   interleaver.interleave_TIkA_below_mUla(dest_file, commentary_file)
   ```
   (`interleaver` is `doc_curation.md.content_processor.commentary.interleaver`.)

3. **Otherwise (translations above mUlam).** Follow the instructions in `~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/interleave-translation/mUla_and_En_translation/Insert_above_mUla.md` — insert each translated segment directly above its corresponding `<details><summary>मूलम्</summary>` block, preserving the original Sanskrit text verbatim.

Report which step you ran and what changed.
