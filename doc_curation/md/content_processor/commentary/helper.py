import logging

import doc_curation.md.library

import regex

from indic_transliteration import sanscript

from doc_curation.md import content_processor
from doc_curation.md.content_processor.details.common import (
  get_js_include_spans,
  get_top_level_detail_spans,
  parse_top_level_details,
)
from doc_curation.md.content_processor.details.model import Detail
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.utils import patterns

DEFAULT_AVATARIKA_PATTERNS = (
  r"अवतारिका",
  r"विनियोग(?!सङ्ग्रह|संग्रह)",
  r"प्रस्तावः",
  r"भूमिका",
  r"^विषयः$",
  r"^त्रिभुवनः\s*-\s*Note$",
)

DEFAULT_LEADING_COMPATIBLE_PATTERNS = (
  r"^मूलम्\s*[\(\-]\s*संयुक्तम्",
  r"^संयुक्त-मूलम्$",
  r"विस्तारः",
  r"^विश्वास-टिप्पनी(?:\s*-\s*.*)?$",
)

_MULA_OR_PADA_RE = regex.compile(r"^(?:मूलम्(?:\s*$|\s*-\s*(?!संयुक्तम्))|पद-?पाठः)")
_OPEN_DETAILS_RE = regex.compile(r"^<details\b[^>]*\bopen\b", flags=regex.IGNORECASE)
_FRONTMATTER_RE = regex.compile(r"\A(?:\+\+\+.*?^\+\+\+|---.*?^---)\s*", flags=regex.DOTALL | regex.MULTILINE)
_NESTED_VP_BLOCK_RE = regex.compile(r"<summary>[^<]*विश्वास-प्रस्तुति|title=[\"'][^\"']*विश्वास-प्रस्तुति")


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


def _compile_patterns(patterns_seq):
  compiled = []
  for p in (patterns_seq or ()):
    compiled.append(p if hasattr(p, "search") else regex.compile(str(p)))
  return compiled


def _classify_run_for_wrappers(
  run_items,
  left_kind,
  right_kind,
  block_name,
  avatarika_block_name,
  avatarika_res,
  leading_res,
):
  """Assign each item in a contiguous wrappable run to ``avatarika_block_name`` or ``block_name``.

  ``run_items`` is a list of ``(start, end, title)`` tuples.
  """
  if not avatarika_block_name:
    return [block_name] * len(run_items)

  k = len(run_items)
  raw_kinds = []
  for _, _, title in run_items:
    if any(p.search(title) for p in avatarika_res):
      raw_kinds.append("AV")
    elif any(p.search(title) for p in leading_res):
      raw_kinds.append("LEAD")
    else:
      raw_kinds.append("TIKA")

  # Rule A: file-top introductory bhūmikā block(s) sitting alongside an explicit
  # avatārikā/viniyoga immediately before the first VP (provided the run doesn't
  # contain a standalone मूलम् / पद-पाठः pratīka unit).
  if (
    left_kind == "START"
    and right_kind in ("VP", "INC_VP")
    and "AV" in raw_kinds
    and not any(_MULA_OR_PADA_RE.search(t) for _, _, t in run_items)
  ):
    return [avatarika_block_name] * k

  labels = [
    avatarika_block_name if rk == "AV" else (block_name if rk == "TIKA" else None)
    for rk in raw_kinds
  ]

  # Trailing AV/LEAD suffix directly before VP/INC_VP belongs to the upcoming VP.
  if right_kind in ("VP", "INC_VP"):
    idx = k - 1
    while idx >= 0 and raw_kinds[idx] in ("AV", "LEAD"):
      labels[idx] = avatarika_block_name
      idx -= 1

  # Leading AV/LEAD prefix at the very start of the file belongs to avatārikā.
  if left_kind == "START":
    idx = 0
    while idx < k and raw_kinds[idx] in ("AV", "LEAD"):
      labels[idx] = avatarika_block_name
      idx += 1

  # Any remaining LEAD block immediately followed by an AV block joins it (right-to-left).
  for idx in range(k - 2, -1, -1):
    if labels[idx] is None and labels[idx + 1] == avatarika_block_name:
      labels[idx] = avatarika_block_name

  # Default any remaining undecided LEAD block to block_name (सर्वाष् टीकाः).
  return [lbl if lbl is not None else block_name for lbl in labels]


def wrap_commentaries_in_details(
  content,
  block_name="सर्वाष् टीकाः",
  exclude=("विश्वास-प्रस्तुतिः",),
  avatarika_block_name=None,
  avatarika_patterns=DEFAULT_AVATARIKA_PATTERNS,
  leading_compatible_patterns=DEFAULT_LEADING_COMPATIBLE_PATTERNS,
  skip_js_includes=True,
  exclude_open_patterns=(),
  vp_pattern=r"विश्वास-प्रस्तुति",
):
  """Wrap runs of non-excluded top-level <details> blocks in named wrapper block(s).

  Consecutive top-level <details> blocks (separated only by whitespace) whose
  summary title matches none of the ``exclude`` regexes nor wrapper names
  themselves are grouped, and each maximal group is wrapped as::

    <details><summary>{block_name}</summary>

    <original blocks joined by blank lines>
    </details>

  When ``avatarika_block_name`` (eg. ``"सर्वा अवतारिकाः"``) is supplied, each
  contiguous run is further partitioned into avatārikā/viniyoga sub-runs
  (wrapped in ``avatarika_block_name``) and commentary/mūlam/padapāṭha/translation
  sub-runs (wrapped in ``block_name``), with context-sensitive handling of
  leading-compatible blocks such as ``मूलम् (संयुक्तम्)`` and ``विस्तारः``.

  :param exclude: regexes (strings, compiled on the fly, or pre-compiled
    patterns with a ``search`` method) matched with ``search`` against the
    stripped summary title. A block is excluded when any regex matches, eg.
    ``exclude=[r"^विश्वास-प्रस्तुतिः"]`` skips ``विश्वास-प्रस्तुतिः`` as well
    as suffixed variants like ``विश्वास-प्रस्तुतिः - DP_१ - ०१``. Anchor with
    ``^...$`` for exact-title matching.
  :param skip_js_includes: When True (default), balanced
    ``<div class="js_include"...>...</div>`` blocks are treated as atomic
    boundaries and never mutated or parsed internally.
  :param exclude_open_patterns: optional regexes matching titles that should be
    left unwrapped only when their opening tag has the ``open`` attribute (eg.
    ``<details open><summary>विश्वास-टिप्पनी</summary>``).

  Excluded blocks (eg. विश्वास-प्रस्तुतिः), ``js_include`` divs, pre-existing
  wrapper blocks and any non-whitespace content (headings, audio embeds, bare
  text) break groups and are left in place. Inner block text is preserved
  byte-for-byte. Idempotent: re-running leaves already-wrapped content untouched.
  """
  if not content or "<details" not in content:
    return content

  exclude_res = _compile_patterns(exclude)
  exclude_open_res = _compile_patterns(exclude_open_patterns)
  avatarika_res = _compile_patterns(avatarika_patterns) if avatarika_block_name else []
  leading_res = _compile_patterns(leading_compatible_patterns) if avatarika_block_name else []
  vp_re = vp_pattern if hasattr(vp_pattern, "search") else regex.compile(str(vp_pattern))
  summary_re = regex.compile(r"<summary>(.*?)</summary>", flags=regex.DOTALL)

  inc_spans = get_js_include_spans(content) if skip_js_includes else []
  det_spans = get_top_level_detail_spans(content, skip_js_includes=skip_js_includes)
  if not det_spans:
    return content

  fm_match = _FRONTMATTER_RE.match(content)
  body_start = fm_match.end() if fm_match else 0

  wrapper_names = {block_name}
  if avatarika_block_name:
    wrapper_names.add(avatarika_block_name)

  # Build a unified sorted list of strictly disjoint top-level items:
  # (start, end, kind, title) where kind in {"DET", "VP", "EXCL", "INC_VP", "INC_OTHER"}.
  # Ignore js_include spans nested inside a top-level <details> block (the outer
  # <details> owns that byte range and preserves it verbatim).
  top_inc_spans = [
    (s, e) for s, e in inc_spans
    if not any(ds <= s and e <= de for ds, de in det_spans)
  ]

  items = []
  for s, e in top_inc_spans:
    gt = content.find(">", s, e)
    open_tag = content[s:gt + 1] if gt != -1 else content[s:e]
    is_vp_inc = (
      bool(vp_re.search(open_tag))
      or "vishvAsa-prastutiH/" in open_tag
      or "sarva-prastutiH/" in open_tag
    )
    items.append((s, e, "INC_VP" if is_vp_inc else "INC_OTHER", ""))

  for s, e in det_spans:
    span_text = content[s:e]
    m = summary_re.search(span_text)
    title = (m.group(1) or "").strip() if m else ""
    is_open = bool(_OPEN_DETAILS_RE.match(span_text))
    contains_vp = bool(avatarika_block_name and _NESTED_VP_BLOCK_RE.search(span_text))
    is_excluded = (
      title in wrapper_names
      or any(p.search(title) for p in exclude_res)
      or (is_open and any(p.search(title) for p in exclude_open_res))
      or contains_vp
    )
    if is_excluded:
      kind = "VP" if (vp_re.search(title) or contains_vp) else "EXCL"
    else:
      kind = "DET"
    items.append((s, e, kind, title))

  items.sort(key=lambda x: x[0])

  parts = []
  pos = 0
  i = 0
  n = len(items)
  while i < n:
    if items[i][2] != "DET":
      parts.append(content[pos:items[i][1]])
      pos = items[i][1]
      i += 1
      continue

    j = i
    while (
      j + 1 < n
      and items[j + 1][2] == "DET"
      and not content[items[j][1]:items[j + 1][0]].strip()
    ):
      j += 1

    if i == 0:
      left_kind = "START" if not content[body_start:items[i][0]].strip() else "SEP"
    else:
      left_kind = "SEP" if content[items[i - 1][1]:items[i][0]].strip() else items[i - 1][2]

    if j + 1 == n:
      right_kind = "END" if not content[items[j][1]:].strip() else "SEP"
    else:
      right_kind = "SEP" if content[items[j][1]:items[j + 1][0]].strip() else items[j + 1][2]

    run_items = [(items[k][0], items[k][1], items[k][3]) for k in range(i, j + 1)]
    labels = _classify_run_for_wrappers(
      run_items=run_items,
      left_kind=left_kind,
      right_kind=right_kind,
      block_name=block_name,
      avatarika_block_name=avatarika_block_name,
      avatarika_res=avatarika_res,
      leading_res=leading_res,
    )

    # Emit consecutive sub-runs sharing the same wrapper label.
    wrapped_chunks = []
    sub_start = 0
    while sub_start < len(run_items):
      sub_label = labels[sub_start]
      sub_end = sub_start
      while sub_end + 1 < len(run_items) and labels[sub_end + 1] == sub_label:
        sub_end += 1
      inner = "\n\n".join(
        content[run_items[k][0]:run_items[k][1]] for k in range(sub_start, sub_end + 1)
      )
      wrapped_chunks.append(f"<details><summary>{sub_label}</summary>\n\n{inner}\n</details>")
      sub_start = sub_end + 1

    parts.append(content[pos:items[i][0]])
    parts.append("\n\n".join(wrapped_chunks))
    pos = items[j][1]
    i = j + 1

  parts.append(content[pos:])
  return "".join(parts)


def wrap_vedic_details(content, *args, **kwargs):
  """Wrap non-``विश्वास-प्रस्तुतिः`` Vedic details into ``सर्वा अवतारिकाः`` and ``सर्वाष् टीकाः``.

  Compatible with ``MdFile.transform`` (accepts extra ``metadata``/keyword args).
  Leaves ``विश्वास-प्रस्तुतिः*``, ``विनियोगसङ्ग्रहः``, explicitly-open
  ``विश्वास-टिप्पनी``, pre-existing wrapper blocks, and all ``js_include`` divs
  untouched.
  """
  return wrap_commentaries_in_details(
    content,
    block_name="सर्वाष् टीकाः",
    exclude=(r"विश्वास-प्रस्तुति", r"^विनियोगसङ्ग्रहः$"),
    avatarika_block_name="सर्वा अवतारिकाः",
    skip_js_includes=True,
    exclude_open_patterns=(r"^विश्वास-टिप्पनी",),
  )


def collapse_details_to_end(content, title="द्राविडी", title_pattern=None, separator="\n\n"):
  """Merge all matching top-level detail blocks into one block at the end.

  Details whose summary fully matches ``title_pattern`` (default: the literal
  ``title``) are removed and their bodies are joined, in document order, into a
  single ``title`` detail appended at the end of the content. Surrounding blank
  lines are normalized; text inside other details and elsewhere is untouched.
  Idempotent when a single matching block already sits at the end.
  """
  if "<details" not in (content or ""):
    return content
  if title_pattern is None:
    title_pattern = regex.escape(title)
  if isinstance(title_pattern, str):
    title_pattern = regex.compile(title_pattern)

  matched_spans = []
  bodies = []
  for (start, end, detail_title, body) in parse_top_level_details(content):
    if not title_pattern.fullmatch(detail_title):
      continue
    bodies.append(body)
    matched_spans.append((start, end))

  if not matched_spans:
    return content
  if len(matched_spans) == 1 and not content[matched_spans[0][1]:].strip():
    return content

  segments = []
  pos = 0
  for (start, end) in matched_spans:
    segments.append(content[pos:start])
    pos = end
  segments.append(content[pos:])
  segments = [segment.strip("\n") for segment in segments]
  segments = [segment for segment in segments if segment.strip()]

  merged = Detail(title=title, content=separator.join(body for body in bodies if body)).to_md_html()
  new_content = separator.join(segments)
  if new_content.strip():
    return f"{new_content}{separator}{merged}\n"
  return f"{merged}\n"


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
