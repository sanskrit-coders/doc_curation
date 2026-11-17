import logging
import os
import textwrap

import regex
from doc_curation.md import library
from doc_curation.md.content_processor import get_quasi_section_int_map
from doc_curation.md.content_processor.details.common import (
  _normalize_spaces,
  _remap_source_matches,
  get_top_level_detail_spans,
  parse_top_level_details,
)
from doc_curation.md.content_processor.details.model import Detail
from doc_curation.md.content_processor.details.transformer import merge_successive
from doc_curation.md.file import MdFile
from doc_curation.utils import patterns
from indic_transliteration import sanscript


def interleave_from_file(md_files, source_file, dest_pattern=r"[^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)", source_pattern=r"(?<=\n|^)([\d०-९೦-೯]+).+\n", detail_title="English", use_dest_number=False, overwrite=False, dry_run=False):
  r"""
  
  :param md_file: 
  :param source_file: Can be a function returning a string or a string.
  :param dest_pattern: Common patterns: 
        [^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)
        <details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n
  :param source_pattern: Pattern to find in the source. Common patterns:
      (?<=\n|^)([\d०-९೦-೯]+).+\n
  :param detail_title: If None, no new detail is inserted.
  :param dry_run: Boolean
  :return: 
  """
  if isinstance(md_files, str):
    md_files = library.get_md_files_from_path(dir_path=md_files, file_pattern="**/*.md")
  elif isinstance(md_files, MdFile):
    md_files = [md_files]
  def _get_source_matches(source_file):
    if not os.path.exists(source_file):
      logging.warning("Source %s does not exist!", source_file)
      return (None, None, None)
    logging.info("Sourcing content from %s", source_file)
    source_md = MdFile(file_path=source_file)
    (_, source_content) = source_md.read()
    source_match_map = get_quasi_section_int_map(source_content, source_pattern, use_ordinal=use_dest_number)
    logging.info(f"Got {len(source_match_map)} source matches ")
    return (source_md, source_content, source_match_map)

  missing_dest_indices = {}
  source_is_callable = callable(source_file)
  if not source_is_callable:
    cur_source_file = source_file
    source_md, source_content, source_match_map = _get_source_matches(source_file=cur_source_file)
  for md_file in md_files:
    logging.info("Interleaving into %s", md_file.file_path)
    if source_is_callable:
      cur_source_file = source_file(md_file.file_path)
      source_md, source_content, source_match_map = _get_source_matches(source_file=cur_source_file)
      if source_match_map is None:
        continue
    (_, dest_content) = md_file.read()
    dest_matches = list(regex.finditer(dest_pattern, dest_content))
    if use_dest_number: 
      source_match_map = _remap_source_matches(source_map=source_match_map, dest_matches=dest_matches)
  
    for dest_match in dest_matches:
      index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)
      if not index_str.isnumeric():
        logging.warning("Could not get index for: %s", dest_match.group())
        continue
      index = int(index_str)
      if index not in source_match_map:
        missing_dest_indices[index] = dest_match.group()
        continue
      if detail_title is not None:
        if detail_title == "विश्वास-प्रसुतिः":
          detail_params = " open"
        else:
          detail_params = ""
        inserted_html = textwrap.dedent(
          f"""
          <details{detail_params}><summary>{detail_title} - {dest_match.group(1)}</summary>
    
          {source_match_map[index].group()}
          </details>
          """
        )
        # textwrap.dedent seems to fail with in-place  formatted string
        inserted_html = regex.sub("(?<=\n|^) +", "", inserted_html)
      else:
        inserted_html = source_match_map[index].group().strip()
      if not overwrite:
        dest_content = dest_content.replace(dest_match.group(), "%s\n\n%s" % (dest_match.group(), inserted_html))
      else:
        dest_content = dest_content.replace(dest_match.group(), inserted_html)
      dest_content = _normalize_spaces(dest_content)
      source_content = source_content.replace(source_match_map[index].group(), "")
      source_content = _normalize_spaces(source_content)
    md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
    if source_content.strip() == "" and dest_content.strip() != "":
      logging.info(f"Removing {cur_source_file}")
      if not dry_run:
        os.remove(cur_source_file)
    else:
      source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)

  if len(missing_dest_indices) > 0:
    logging.warning(f"Could not get indices in source: {missing_dest_indices}")

def pattern_to_details(content, title="टीका", pattern=patterns.TAMIL_BLOCK, content_group=1, title_suffix_group=None, attributes_str=None):
  def _detail_maker(match):
    local_title = title
    if title_suffix_group is not None:
      local_title = f"{title} - {match.group(title_suffix_group)}"
    detail = Detail(title=local_title, content=match.group(content_group).strip())
    return detail.to_md_html(attributes_str=attributes_str) + "\n\n"
  content = regex.sub(pattern, _detail_maker, content)
  content = merge_successive(content)
  return content

def sections_to_details(content, pattern=r"(?<=\n|^)\###+ +(\S.+)\s+(\S[^\#<]+?)(?=[\#<]|$)"):
  def _detail_maker(match):
    detail = Detail(title=match.group(1), content=match.group(2).strip())
    return detail.to_md_html() + "\n\n"
  content = regex.sub(pattern, _detail_maker, content)
  return content

def shlokas_to_details(content, pattern=None, title_base="टीका"):
  from doc_curation import sanskrit as sanskrit_helper
  from doc_curation.utils import patterns
  if f">{title_base}" in content:
    return content
  content = sanskrit_helper.seperate_uvaacha(text=content)
  if pattern is None:
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    if pattern == patterns.PATTERN_BOLDED_QUOTED_SHLOKA:
      shloka = shloka.replace("**", "")
      shloka = regex.sub("\n> *", "\n", shloka)
    if "shloka_id" in pattern:
      shloka_id = match.group('shloka_id')
      shloka_id = regex.sub(r"[\.,]$", "", shloka_id)
      shloka_id = f" - {shloka_id}"
    elif pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
      shloka_id = f" - {match.groups()[-1].strip()}"
    else:
      shloka_id = ""
    detail = Detail(title=f"{title_base}{shloka_id}", content=shloka)
    return f"\n{detail.to_md_html()}\n"
  try:
    content = regex.sub(pattern, detail_maker, content)
  except TimeoutError as x:
    print(x)
    logging.fatal(f"pattern: {pattern}")
  content = _normalize_spaces(content)
  return content

def shlokas_to_muula_viprastuti_details(content, shloka_processor=lambda x:x, pattern=None, id_position=-1):
  if "विश्वास-प्रस्तुतिः" in content:
    logging.warning("विश्वास-प्रस्तुतिः found. Returning")
    content = regex.sub(r"(?<=/details>|^)\s*([^<]+?)\s*(?=<details|$)", lambda x: shlokas_to_muula_viprastuti_details(content=x.group(0), pattern=pattern, id_position=id_position), content)
    return content
  from doc_curation import sanskrit as sanskrit_helper
  from doc_curation.utils import patterns
  content = sanskrit_helper.seperate_uvaacha(text=content)
  if pattern is None:
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    if pattern == patterns.PATTERN_BOLDED_QUOTED_SHLOKA:
      shloka = shloka.replace("**", "")
      shloka = regex.sub("\n> *", "\n", shloka)
    if "shloka_id" in pattern:
      shloka_id = match.group('shloka_id')
      shloka_id = regex.sub(r"[\.,]$", "", shloka_id)
      shloka_id = f" - {shloka_id}"
    elif pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
      shloka_id = match.groups()[id_position].strip()
      if shloka_id != "":
        shloka_id = f" - {shloka_id}"
    else:
      shloka_id = ""
    shloka = shloka.replace("**", "")
    shloka = shloka_processor(shloka)
    detail_vishvaasa = Detail(title=f"विश्वास-प्रस्तुतिः{shloka_id}", content=shloka)
    detail_muula = Detail(title=f"मूलम्{shloka_id}", content=shloka)
    return f"\n{detail_vishvaasa.to_md_html()}\n\n{detail_muula.to_md_html()}" 
  try:
    content = regex.sub(pattern, detail_maker, content)
  except TimeoutError as x:
    print(x)
    logging.fatal(f"pattern: {pattern}")
  return content

def translation_details(translation, notes=None,
                        translation_title="Translation",
                        notes_title="Translation - Notes"):
  """Translation [+ Notes] detail blocks for one already-placed sentence.

  Companion to :func:`generic_sanskrit_vipra_mUla`: the caller inserts the
  returned blocks directly above the sentence's ``मूलम्`` block.
  """
  translation = (translation or "").strip()
  parts = [Detail(title=translation_title, content=translation).to_md_html()]
  if (notes or "").strip():
    parts.append(Detail(title=notes_title, content=notes.strip()).to_md_html())
  return "\n\n".join(parts)


def generic_sanskrit_vipra_mUla(content, start_text=None,
                               vishvaasa_title="विश्वास-प्रस्तुतिः",
                               muula_title="मूलम्",
                               split_sentences=True,
                               to_us_accents=False,
                               unaccented_vishvaasa_title=None,
                               vishvaasa_preprocessor=None):
  """Wrap each sentence or paragraph of bare Sanskrit text in विश्वास + मूलम् blocks.

  Takes ``content`` (a full file body or section), and for every
  non-detail paragraph after ``start_text`` splits it (when ``split_sentences``
  is True) with :func:`doc_curation.sanskrit.split_to_sentences` and
  replaces each unit with an (open) विश्वास-प्रस्तुतिः block plus a
  मूलम् block — no translations involved (those are inserted later,
  above each मूलम् block, once mapped).

  :param content: markdown text.
  :param start_text: only text after this marker's line is processed;
    ``None`` processes from the top (leading frontmatter and markdown headings
    are always skipped).
  :param split_sentences: split each paragraph into sentences when True; keep
    each paragraph together as a single unit when False.
  :param to_us_accents: convert Vedic dependent accents in विश्वास-प्रस्तुतिः
    blocks to US (Udatta-Svarita) accents when True.
  :param unaccented_vishvaasa_title: optional summary title (still opened) when
    a unit lacks Vedic accent marks.
  :param vishvaasa_preprocessor: optional callable transforming the text placed
    inside विश्वास-प्रस्तुतिः without altering मूलम्.
  :return: new markdown text (input untouched where there is nothing to
    wrap: details blocks, headings, non-Devanagari paragraphs).
  """
  from doc_curation.sanskrit import split_to_sentences

  if start_text:
    idxs = [m.start() for m in regex.finditer(regex.escape(start_text),
                                              content)]
    if not idxs:
      raise ValueError(f"start_text {start_text!r} not found in content.")
    line_end = content.find("\n", idxs[-1])
    cut = len(content) if line_end == -1 else line_end + 1
    head, rest = content[:cut], content[cut:]
  else:
    m = regex.match(
      r"\A(?:\+\+\+.*?^\+\+\+|---.*?^---)[ \t]*\n?",
      content,
      flags=regex.DOTALL | regex.MULTILINE,
    )
    head = m.group(0) if m else ""
    rest = content[len(head):]

  segments = []
  pos = 0
  for s, e in get_top_level_detail_spans(rest):
    if s > pos:
      segments.append((False, rest[pos:s]))
    segments.append((True, rest[s:e]))
    pos = e
  if pos < len(rest):
    segments.append((False, rest[pos:]))

  out = []
  for is_detail, seg in segments:
    if is_detail:
      out.append(seg)
      continue
    chunks = []
    for tok in regex.split(r"(\n\s*\n)", seg):
      if not tok.strip() or regex.fullmatch(r"\n\s*\n", tok):
        chunks.append(tok)
        continue
      if all(not line.strip() or line.strip().startswith("#")
             for line in tok.split("\n")) \
          or not regex.search(r"[\u0900-\u097F]", tok):
        chunks.append(tok)  # headings / non-Sanskrit: as-is
        continue
      # Line-level pass: `--` attribution lines (e.g.
      # --वैयासिकन्यायमाला, often glued to a para by single newlines)
      # and `#` headings pass through verbatim; other runs are wrapped.
      runs, cur = [], []
      for line in tok.split("\n"):
        if line.strip().startswith(("--", "#")):
          if cur:
            runs.append(("txt", "\n".join(cur)))
            cur = []
          runs.append(("raw", line))
        else:
          cur.append(line)
      if cur:
        runs.append(("txt", "\n".join(cur)))
      parts = []
      for kind, chunk in runs:
        if kind == "raw" or not regex.search(r"[\u0900-\u097F]", chunk):
          parts.append(chunk)
        else:
          units = (
            [x for x in split_to_sentences(chunk) if x.strip()]
            if split_sentences
            else [chunk.strip()]
          )
          groups = []
          for muula_text in units:
            vishvaasa_text = (
              vishvaasa_preprocessor(muula_text)
              if vishvaasa_preprocessor
              else muula_text
            )
            has_accents = bool(
              regex.search(r"[\u0951-\u0954\u1CD0-\u1CFF]", vishvaasa_text)
            )
            if not has_accents and unaccented_vishvaasa_title:
              vishvaasa_detail = Detail(
                title=unaccented_vishvaasa_title,
                content=vishvaasa_text,
              ).to_md_html(attributes_str="open")
            else:
              if to_us_accents and has_accents:
                from indic_transliteration.sanscript.schemes.brahmic import accent
                vishvaasa_text = accent.to_US_accents(
                  vishvaasa_text, pauses=r"[।॥,;]+"
                )
              vishvaasa_detail = Detail(
                title=vishvaasa_title,
                content=vishvaasa_text,
              ).to_md_html()
            muula_detail = Detail(
              title=muula_title,
              content=muula_text,
            ).to_md_html()
            groups.append(f"{vishvaasa_detail}\n\n{muula_detail}")
          parts.append("\n\n".join(groups) if groups else chunk)
      chunks.append("\n".join(parts))
    out.append("".join(chunks))
  return head + "".join(out)


def wrap_into_detail(content, title, attributes_str=None):
  content_out = content.strip()
  if content_out == "":
    return content
  return Detail(title=title, content=content.strip()).to_md_html(attributes_str=attributes_str)

def non_detail_parts_to_detail(content, title, attributes_str=""):

  if title in ["विश्वास-प्रस्तुतिः", "मूलम् (वचनम्)"] and not "open" in attributes_str:
    attributes_str = " open"
  content = regex.sub(r"(/details>|\n##+ .*)\s*([^<#]+?)\s*(?=<details|\n#|$)", rf"\1\n\n<details{attributes_str}><summary>{title}</summary>\n\n\2\n</details>\n\n", content)
  content = regex.sub(r"(?<=/details>|^)\s*([^<#]+?)\s*(?=<details|\n#|$)", rf"\n\n<details{attributes_str}><summary>{title}</summary>\n\n\1\n</details>\n\n", content)
  content = regex.sub(rf"<details{attributes_str}><summary>{title}</summary>\n\n*</details>", "", content)
  content = _normalize_spaces(content)
  
  return content


def _check_details_balanced(text, label="content"):
  """Raise ValueError if `<details` and `</details>` counts disagree."""
  opens = len(regex.findall(r"<details\b", text))
  closes = len(regex.findall(r"</details>", text))
  if opens != closes:
    raise ValueError(
      f"Unbalanced <details> tags in {label}: {opens} open vs {closes} close."
    )


def _find_empty_leaf_heading_ends(content, detail_spans):
  """Return end offsets of headings with no content or subheadings before the next <=-level heading."""
  def _in_details(pos):
    return any(s <= pos < e for s, e in detail_spans)

  headings = [
    (m.start(), m.end(), len(m.group(1)))
    for m in regex.finditer(r"(?m)^[ \t]*(#{1,6})[ \t]+[^\n]*?(?=[ \t]*\r?$)", content)
    if not _in_details(m.start())
  ]
  empty_ends = []
  for idx, (_, h_end, level) in enumerate(headings):
    limit = len(content)
    for j in range(idx + 1, len(headings)):
      if headings[j][2] <= level:
        limit = headings[j][0]
        break
    if any(not (e <= h_end or s >= limit) for s, e in detail_spans):
      continue
    if not content[h_end:limit].strip():
      empty_ends.append(h_end)
  return empty_ends


def _remove_spans_preserving_spacing(text, spans):
  """Remove non-overlapping character spans and collapse extra blank lines."""
  if not spans:
    return text
  out = []
  pos = 0
  for s, e in sorted(spans):
    if s > pos:
      out.append(text[pos:s])
    pos = max(pos, e)
  if pos < len(text):
    out.append(text[pos:])
  cleaned = regex.sub(r"\n{3,}", "\n\n", "".join(out)).strip()
  return f"{cleaned}\n" if cleaned else ""


def extract_paired_details(
  source_content,
  mUla_title="मूलम्",
  commentary_title="व्याख्या",
  require_commentary=True,
):
  """Extract sequential `(mUla_detail, commentary_detail)` top-level detail pairs.

  When `require_commentary` is True (default), standalone `mUla_title` blocks
  without an immediately following `commentary_title` block (such as trailing
  editorial notes) are skipped so they remain untouched in source.
  """
  _check_details_balanced(source_content, label="source_content")
  details = parse_top_level_details(source_content)
  pairs = []
  i = 0
  while i < len(details):
    cur = details[i]
    title = cur[2]
    if title == mUla_title:
      if i + 1 < len(details) and details[i + 1][2] == commentary_title:
        pairs.append((cur, details[i + 1]))
        i += 2
      else:
        if not require_commentary:
          pairs.append((cur, None))
        i += 1
    elif title == commentary_title:
      raise ValueError(
        f"Unexpected commentary block {commentary_title!r} without preceding {mUla_title!r}."
      )
    else:
      i += 1
  return pairs


def interleave_paired_mUla_commentary(
  target_content,
  source_content,
  commentary_title,
  variant_mUla_title=None,
  source_mUla_title="मूलम्",
  source_commentary_title="व्याख्या",
  target_mUla_title="मूलम्",
  mUla_clean_fn=None,
  commentary_clean_fn=None,
  pair_transform_fn=None,
  mUla_same_fn=None,
  insert_into_empty_headings=True,
  commentary_attributes_str=None,
):
  """Interleave paired `(mUla, commentary)` blocks from source into target slots.

  Matches each sequential pair against target `<details><summary>{target_mUla_title}</summary>`
  blocks (and optionally empty leaf headings). When `variant_mUla_title` is set,
  adds a variant mUla block when target differs (or has an empty heading slot).
  Returns `(new_target_content, new_source_content)` where `new_source_content`
  retains any source blocks that were not inserted.
  """
  _check_details_balanced(target_content, label="target_content")
  pairs = extract_paired_details(
    source_content,
    mUla_title=source_mUla_title,
    commentary_title=source_commentary_title,
  )
  target_details = parse_top_level_details(target_content)
  detail_spans = [(s, e) for s, e, _, _ in target_details]

  slots = [
    (e, "details", body)
    for _, e, title, body in target_details
    if title == target_mUla_title
  ]
  if insert_into_empty_headings:
    for h_end in _find_empty_leaf_heading_ends(target_content, detail_spans):
      slots.append((h_end, "empty_heading", None))
  slots.sort(key=lambda item: item[0])

  if len(slots) < len(pairs):
    raise ValueError(
      f"Target has {len(slots)} slots but source has {len(pairs)} pairs."
    )

  insertions = []
  source_spans_to_remove = []
  for (m_item, c_item), (ins_pos, kind, target_body) in zip(pairs, slots):
    m_start, m_end, _, raw_m_body = m_item
    raw_c_body = c_item[3] if c_item is not None else None
    if pair_transform_fn is not None:
      clean_m, clean_c = pair_transform_fn(raw_m_body, raw_c_body)
    else:
      clean_m = mUla_clean_fn(raw_m_body) if mUla_clean_fn else raw_m_body
      clean_c = (
        commentary_clean_fn(raw_c_body)
        if commentary_clean_fn and raw_c_body is not None
        else raw_c_body
      )

    blocks_to_insert = []
    if kind == "empty_heading":
      m_title = variant_mUla_title or target_mUla_title
      blocks_to_insert.append(Detail(title=m_title, content=clean_m).to_md_html())
      source_spans_to_remove.append((m_start, m_end))
    else:
      if variant_mUla_title:
        is_same = (
          mUla_same_fn(target_body, clean_m)
          if mUla_same_fn is not None
          else regex.sub(r"\s+", " ", target_body.strip())
          == regex.sub(r"\s+", " ", clean_m.strip())
        )
        if not is_same:
          blocks_to_insert.append(
            Detail(title=variant_mUla_title, content=clean_m).to_md_html()
          )
          source_spans_to_remove.append((m_start, m_end))

    if c_item is not None and clean_c is not None:
      blocks_to_insert.append(
        Detail(title=commentary_title, content=clean_c).to_md_html(
          attributes_str=commentary_attributes_str
        )
      )
      source_spans_to_remove.append((c_item[0], c_item[1]))

    if blocks_to_insert:
      insertions.append((ins_pos, "\n\n".join(blocks_to_insert)))

  new_target = target_content
  for ins_pos, block_text in reversed(insertions):
    before = new_target[:ins_pos]
    after = new_target[ins_pos:]
    if after.startswith("\n\n"):
      new_target = f"{before}\n\n{block_text}{after}"
    elif after.startswith("\n"):
      new_target = f"{before}\n\n{block_text}\n{after}"
    elif after == "":
      new_target = f"{before}\n\n{block_text}\n"
    else:
      new_target = f"{before}\n\n{block_text}\n\n{after}"

  new_source = _remove_spans_preserving_spacing(source_content, source_spans_to_remove)
  return new_target, new_source


def interleave_paired_mUla_commentary_file(
  target_md_file,
  source_file,
  commentary_title,
  variant_mUla_title=None,
  source_mUla_title="मूलम्",
  source_commentary_title="व्याख्या",
  target_mUla_title="मूलम्",
  mUla_clean_fn=None,
  commentary_clean_fn=None,
  pair_transform_fn=None,
  mUla_same_fn=None,
  insert_into_empty_headings=True,
  commentary_attributes_str=None,
  remove_from_source=True,
  delete_empty_source=True,
  dry_run=False,
):
  """Interleave paired source details into `target_md_file` and update `source_file`."""
  import os
  from doc_curation.md.file import MdFile

  if isinstance(target_md_file, (str, os.PathLike)):
    target_md_file = MdFile(file_path=str(target_md_file))
  cur_source_file = (
    source_file(target_md_file.file_path) if callable(source_file) else source_file
  )
  if cur_source_file is None or not os.path.exists(cur_source_file):
    return None

  source_md_file = MdFile(file_path=str(cur_source_file))
  _, target_content = target_md_file.read()
  _, source_content = source_md_file.read()

  new_target, new_source = interleave_paired_mUla_commentary(
    target_content=target_content,
    source_content=source_content,
    commentary_title=commentary_title,
    variant_mUla_title=variant_mUla_title,
    source_mUla_title=source_mUla_title,
    source_commentary_title=source_commentary_title,
    target_mUla_title=target_mUla_title,
    mUla_clean_fn=mUla_clean_fn,
    commentary_clean_fn=commentary_clean_fn,
    pair_transform_fn=pair_transform_fn,
    mUla_same_fn=mUla_same_fn,
    insert_into_empty_headings=insert_into_empty_headings,
    commentary_attributes_str=commentary_attributes_str,
  )

  target_md_file.replace_content_metadata(new_content=new_target, dry_run=dry_run)
  if remove_from_source and not dry_run:
    if not new_source.strip() and delete_empty_source:
      os.remove(str(cur_source_file))
    else:
      source_md_file.replace_content_metadata(new_content=new_source, dry_run=False)
  return new_target, new_source


if __name__ == '__main__':
  pass
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/07_antaradhikaraNam.md", content_transformer=lambda c, *args, **kwargs: generic_sanskrit_vipra_mUla(c))
