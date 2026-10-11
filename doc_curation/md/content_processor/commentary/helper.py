import logging

import doc_curation.md.library

import regex

from indic_transliteration import sanscript

from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.utils import patterns


def separate_parts(content, exclusion_pattern, inclusion_pattern=f"[{patterns.DEVANAGARI}]", replacement=r"\1\n\n<details><summary>मूलम्</summary>\n\n\2\n</details>\n\n"):
  content = regex.sub(rf"({exclusion_pattern})\s*({inclusion_pattern}[\s\S]+?)\s*(?={exclusion_pattern})", replacement, content)
  return content


def transliterate_init_ids(content, id_pattern=r"॥ *([०-९]+) *॥", source_script=sanscript.DEVANAGARI, dest_script=sanscript.IAST):
  """
  
  Sometimes, content may contain different but related identically numbered sections (eg. shloka and commentary). For fu
  rther processing, it may be convenient to distinguish them based on which appears first.
  
  :param content: 
  :param id_pattern: 
  :param source_script: 
  :param dest_script: 
  :return: 
  """
  matches = list(regex.finditer(id_pattern, content))
  ids = [x.group(1) for x in matches]
  id_counts = {}
  for id in ids:
    id_counts[id] = id_counts.get(id, 0) + 1

  for id, count in id_counts.items():
    if count != 2:
      logging.warning(f"{id} count is {count}. Skipping.")
    else:
      particular_id_pattern = regex.sub(r"\(.+?\)", id, id_pattern)
      replacement = regex.sub(r"\(.+?\)", sanscript.transliterate(id, source_script, dest_script), id_pattern).replace(" *", "")
      content = regex.sub(particular_id_pattern, replacement, content, count=1)
  
  return content


def wrap_commentaries_in_details(content, block_name="सर्वाष् टीकाः", exclude=["विश्वास-प्रस्तुतिः"]):
  """Wrap runs of non-excluded top-level <details> blocks in a named wrapper block.

  Consecutive top-level <details> blocks (separated only by whitespace) whose
  summary title matches none of the `exclude` regexes nor `block_name` itself
  are grouped, and each maximal group is wrapped as::

    <details><summary>{block_name}</summary>

    <original blocks joined by blank lines>
    </details>

  :param exclude: regexes (strings, compiled on the fly, or pre-compiled
    patterns with a ``search`` method) matched with ``search`` against the
    stripped summary title. A block is excluded when any regex matches, eg.
    ``exclude=[r"^विश्वास-प्रस्तुतिः"]`` skips ``विश्वास-प्रस्तुतिः`` as well
    as suffixed variants like ``विश्वास-प्रस्तुतिः - DP_१ - ०१``. Anchor with
    ``^...$`` for exact-title matching.

  Excluded blocks (eg. विश्वास-प्रस्तुतिः), pre-existing wrapper blocks and any
  non-whitespace content (headings, audio embeds, bare text) break groups and
  are left in place. Inner block text is preserved byte-for-byte. Idempotent:
  re-running leaves already-wrapped content untouched.
  """
  exclude_res = []
  for e in (exclude or []):
    exclude_res.append(e if hasattr(e, "search") else regex.compile(str(e)))
  open_re = regex.compile(r"<details[^>]*>")
  tag_re = regex.compile(r"</details>|<details[^>]*>")
  summary_re = regex.compile(r"<summary>(.*?)</summary>", flags=regex.DOTALL)
  # Top-level spans via depth tracking (handles pre-wrapped nested blocks).
  spans = []
  depth = 0
  start = None
  for m in tag_re.finditer(content or ""):
    if m.group().startswith("</"):
      if depth > 0:
        depth -= 1
        if depth == 0 and start is not None:
          spans.append((start, m.end()))
          start = None
    else:
      if depth == 0:
        start = m.start()
      depth += 1
  if not spans:
    return content

  def title_of(span_text):
    m = summary_re.search(span_text)
    return (m.group(1) or "").strip() if m else ""

  titles = [title_of(content[s:e]) for (s, e) in spans]
  wrappable = [(not any(p.search(t) for p in exclude_res) and t != block_name) for t in titles]

  parts = []
  pos = 0
  i = 0
  n = len(spans)
  while i < n:
    if not wrappable[i]:
      parts.append(content[pos:spans[i][1]])
      pos = spans[i][1]
      i += 1
      continue
    j = i
    while (j + 1 < n and wrappable[j + 1]
           and not content[spans[j][1]:spans[j + 1][0]].strip()):
      j += 1
    inner = "\n\n".join(content[spans[k][0]:spans[k][1]] for k in range(i, j + 1))
    parts.append(content[pos:spans[i][0]])
    parts.append(f"<details><summary>{block_name}</summary>\n\n{inner}\n</details>")
    pos = spans[j][1]
    i = j + 1
  parts.append(content[pos:])
  return "".join(parts)


def move_detail_to_matching_file(dest_dir, source_file, dest_id_maker=None, dest_pattern="<details.+?summary>मूलम्</summary>[\s\S]+?॥ *([०-९]+) *॥\s*</details>\n*", source_pattern="(?<=\n|^)([\d०-९೦-೯]+).+\n", overwrite_pattern=None, overwrite_mode=None, dry_run=False):
  source_md = MdFile(file_path=source_file)
  (_, source_content) = source_md.read()
  source_match_map = content_processor.get_quasi_section_int_map(source_content, source_pattern)

  dest_md_files = doc_curation.md.library.get_md_files_from_path(dir_path=dest_dir)  
  if dest_id_maker is None:
    def dest_id_maker(x): 
      return arrangement.get_sub_path_id(x.file_path.replace(dest_dir, ""))
  for md_file in dest_md_files:
    index_str = dest_id_maker(md_file)
    if not index_str.isnumeric():
      logging.warning(f"Could not get index for: {index_str} in file {md_file.file_path}")
      continue
    index = int(index_str)
    if index not in source_match_map:
      logging.warning(f"Could not get commentary for: {index} in file {md_file.file_path}")
      continue
    inserted_html = source_match_map[index].group()
    (dest_metadata, dest_content) = md_file.read()
    if overwrite_pattern is not None:
      overwrite_matches = list(regex.finditer(overwrite_pattern, dest_content))
      if len(overwrite_matches) > 0:
        logging.warning(f"detail already exists: {index} in file {md_file.file_path}")
        overwrite_match = overwrite_matches[0]
        if overwrite_mode is None:
          continue
        elif overwrite_mode == "overwrite":
          dest_content = dest_content.replace(overwrite_match.group(), inserted_html)
        elif overwrite_mode == "append":
          dest_content = dest_content.replace(overwrite_match.group(), "%s\n\n%s" % (overwrite_match.group(), inserted_html))
    else:
      dest_matches = list(regex.finditer(dest_pattern, dest_content))
      if len(dest_matches) == 0:
        logging.warning(f"Could not get insertion point for: {index} in file {md_file.file_path}")
        continue
      dest_match = dest_matches[-1]
      dest_content = dest_content.replace(dest_match.group(), "%s\n\n%s" % (dest_match.group(), inserted_html))
    md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
    source_content = source_content.replace(source_match_map[index].group(), "")
  source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)

  pass
