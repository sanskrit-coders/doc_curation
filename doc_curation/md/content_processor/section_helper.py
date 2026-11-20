from bs4.element import PageElement
from tqdm import tqdm
import itertools
import logging

import regex
from more_itertools import peekable
from curation_utils.list_helper import OrderedDefaultDict


from doc_curation.md import content_processor
from indic_transliteration import sanscript


def get_lines_till_section(lines_in):
  lines = list(lines_in)
  lines_till_section = itertools.takewhile(lambda line: not line.startswith("#"), lines)
  remaining = itertools.dropwhile(lambda line: not line.startswith("#"), lines)
  return (peekable(lines_till_section), peekable(remaining))


def reduce_section_depth(lines_in, hashes_to_reduce):
  for line in lines_in:
    if line.startswith("#"):
      yield line[len(hashes_to_reduce):]
    else:
      yield line


def convert_heading_style(text, dash="##", equals="###") -> str:
  """
  Convert '=====' style divider headings into Markdown ## headings.
  
  Pattern:
  - A line of text followed by a line of '=' characters (length >= 5).
  - That text line becomes a '##' heading.
  - The '=' line is removed.
  """
  text = regex.sub("\r", "\n", text)
  # Regex: capture a line of text followed by a line of '=' characters
  pattern = regex.compile(r'^(?P<title>[^\n]+)\n={5,}\s*$', regex.MULTILINE)
  # Replace with Markdown heading
  text = pattern.sub(rf'{equals} \g<title>', text)
  # Regex: capture a line of text followed by a line of '=' characters
  pattern = regex.compile(r'^(?P<title>[^\n]+)\n-{5,}\s*$', regex.MULTILINE)
  # Replace with Markdown heading
  text = pattern.sub(rf'{dash} \g<title>', text)
  text = regex.sub("^[-=]+", "________", text)
  return text


def get_sections(content):
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  return (lines_till_section, sections)


class Section(object):
  def __init__(self, title, header_prefix, lines=None):
    self.title = title
    if lines is None:
      lines = []
    self.lines = lines
    self.header_prefix = header_prefix

  def __repr__(self):
    return f"{self.header_prefix} {self.title.strip()} ({len(self.lines)})"

  def to_md(self):
    text = "\n".join(self.lines)
    return f"\n\n{self.header_prefix} {self.title.strip()}\n{text}"
    

def get_section(lines_in):
  """
  
  :param lines_in: 
  :return: (title, lines_in_section, reamining)
  """
  lines = list(lines_in)
  if len(lines) == 0:
    return (None, [])
  if not lines[0].startswith("#"):
    header_prefix = "# "
    title = None
  else:
    header_prefix = lines[0].split()[0] + " "
    title = get_section_title(lines[0])
  section = Section(title=title, header_prefix=header_prefix)
  lines_in_section = []
  remaining = []
  if len(lines) > 1:
    # Convert the iterator to a list immediately
    is_non_section_start = lambda line: not (line.strip() + " ").startswith(header_prefix)
    section.lines = list(itertools.takewhile(is_non_section_start, lines[1:]))
    remaining = list(itertools.dropwhile(lambda line: is_non_section_start(line), lines[1:]))
  return (section, remaining)


def repeat_sections_to_bold(content):
  (lines_till_section, sections) = get_sections(content=content)
  new_sections = []
  for section in sections:
    section_title = section.title.strip()
    prev_title = None
    if len(new_sections) > 0:
      prev_title = new_sections[-1].title.strip()
    if section_title != prev_title:
      new_sections.append(section)
    else:
      new_sections[-1].lines.extend(["\n", "**%s**" % section_title, "\n"])
      new_sections[-1].lines.extend(section.lines)

  new_content = "\n".join(lines_till_section)
  for section in new_sections:
    new_content += section.to_md()
  return new_content


def split_to_sections(lines_in):
  remaining = peekable(lines_in)
  sections = []
  while (remaining):
    (section, remaining) = get_section(remaining)
    if section is not None:
      sections.append(section)
  return sections


def get_section_lines(lines_in, section_title):
  sections = split_to_sections(lines_in=lines_in)
  for section in sections:
    if section == section.title:
      return section.lines
  return None


def get_section_title(title_line):
  splits = title_line.split()
  if len(splits) == 1:
    return None
  title = " ".join(splits[1:])
  title = regex.sub("[।॥. ]+", " ", title)
  title = regex.sub("\\s+", " ", title)
  return title.strip()


def get_init_content_lines(lines_in):
  lines_in = list(lines_in)
  if len(lines_in) == 0:
    return lines_in
  (lines_till_section, remaining) = get_lines_till_section(lines_in=lines_in)
  lines_till_section = [line for line in lines_till_section if line.strip() != ""]
  if len(lines_till_section) != 0:
    return lines_till_section
  else:
    sections = split_to_sections(lines_in=remaining)
    if len(sections) > 0:
      return get_init_content_lines(lines_in=sections[0].lines)
    else:
      return []


def drop_sections(md_file, title_condition):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  if len(sections) == 0:
    return
  sections = [section for section in sections if not title_condition(section.title)]

  lines_out = list(lines_till_section)
  for section_index, section in enumerate(sections):
    lines_out.append("\n## %s" % section.title)
    lines_out.extend(section.lines)
  return "\n".join(lines_out)


def deromanize_section_numbers(content):
  lines = content.splitlines(keepends=False)
  outlines = []
  def deromanize(match):
    import roman
    prefix, rom, rest = match.group(1), match.group(2), match.group(3)
    if not regex.fullmatch(r"#+\s*", prefix) and not rom.isupper():
      return match.group(0)
    try:
      number = roman.fromRoman(rom.upper())
    except Exception:
      return match.group(0)
    suffix = f" {rest}" if rest else ""
    return f"{prefix} {number:02d}{suffix}"
  for line in lines:
    outline = regex.sub(r"^(#+(?: +[^\d#\s]+)*?) +([MCDLXIVmcdlxiv]+)(?:[\.\s]+(.+)| *$)", deromanize, line)
    outlines.append(outline)
  return "\n".join(outlines)


def denumerify_section_titles(content):
  content = regex.sub(r"(?<=^|\n)(#+) *([\d०-९೦-೯]+)", r"\1", content)
  return content


def add_init_words_to_section_titles(md_file, num_words=2, title_post_processor=None, dry_run=False):
  from doc_curation.md.library import metadata_helper
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  if len(sections) == 0:
    return

  sections_out = []
  for section_index, section in enumerate(sections):
    title = section.title
    if title is None:
      title = ""
    section_lines = list(section.lines)
    init_lines = get_init_content_lines(lines_in=section_lines)
    extra_title = metadata_helper.title_from_text(text=" ".join(init_lines), num_words=num_words, target_title_length=None)
    if extra_title is not None:
      title = "%s %s" % (title.strip(), extra_title)

    sections_out.append(Section(title=title, lines=section_lines, header_prefix=section.header_prefix))

  lines_out = list(lines_till_section)
  for section_index, section in enumerate(sections_out):
    title = section.title
    if title_post_processor is not None:
      title = title_post_processor(title)
    lines_out.append("\n%s%s" % (section.header_prefix, title))
    lines_out.extend(section.lines)
  content = "\n".join(lines_out)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def autonumber_section_lines(lines, dest_script=sanscript.DEVANAGARI, recursive=True, overwrite_numbers=False, init_index=1):
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  lines_out = list(lines_till_section)
  index_pattern = "%%0%dd" % (len(str(len(sections))))
  for section_index, section in enumerate(sections):
    title = section.title
    if title is None:
      title = ""
    if overwrite_numbers:
      transliterated_index = index_pattern % (section_index + init_index)
    else:
      if regex.match("^[0-9०-९೦-೯]+", title.strip()):
        transliterated_index = regex.match("^[0-9०-९೦-೯]+", title.strip()).group()
      else:
        transliterated_index = index_pattern % (section_index + init_index)
    title = regex.sub("^[0-9०-९೦-೯]+", "", title.strip())
    if dest_script is not None:
      transliterated_index = sanscript.transliterate(data=transliterated_index, _to=dest_script, _from=sanscript.IAST)
    title = "%s %s" % (transliterated_index, title)
    lines_out.append("\n%s%s" % (section.header_prefix, title))
    if recursive:
      # Assume that numbers start with 1 at subsection level and beyond 
      section.lines = autonumber_section_lines(lines=section.lines, dest_script=dest_script, recursive=recursive, init_index=1, overwrite_numbers=overwrite_numbers) 
    lines_out.extend(section.lines)
  return lines_out


def autonumber(md_file, dest_script=sanscript.DEVANAGARI, recursive=True, start_index=1, overwrite_numbers=True, dry_run=False):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  lines = autonumber_section_lines(lines=lines, dest_script=dest_script, recursive=recursive, init_index=start_index, overwrite_numbers=overwrite_numbers)
  content = "\n".join(lines)
  content = regex.sub("\n\n+", "\n\n", content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def create_sections_from_terminal_digits(md_file, digit_pattern="([०-९]+)", section_mark="##", dry_run=False):
  def replacement_maker(match):
    return "\n%s %s\n%s\n\n" %  (section_mark, match.group(1), match.group().strip())
  content_processor.replace_texts(md_file=md_file, patterns=[r"\n[\s\S]+?%s *\n" % (digit_pattern)], replacement=replacement_maker, dry_run=dry_run)
  

def section_hash_by_index(section):
  matches = list(regex.finditer(r"\d+", section.title))
  if len(matches) > 0:
    return int(matches[0][0])
  else:
    return 999999


def merge_sections(md_file, md_files, out_path=None, section_hasher=lambda x: sanscript.transliterate(x.title, _to=sanscript.DEVANAGARI).strip(), prepend=False, dry_run=False):
  from doc_curation.md import file

  content = ""
  section_map = OrderedDefaultDict(list)
  if callable(md_files):
    md_files = md_files(md_file.file_path)
  if isinstance(md_files[0], str):
    md_files = [file.MdFile(x) for x in md_files]
  final_md_files = [md_file] + md_files
  if prepend:
    final_md_files = md_files + [md_file]
  for md_to_merge in final_md_files:
    (metadata, md_content) = md_to_merge.read()
    (lines_till_section, sections) = get_sections(content=md_content)
    para = "\n".join(lines_till_section)
    content += f"{para}\n\n"
    for section in sections:
      title = section_hasher(section)
      section_map[title].append(section)

  sections_final = []
  for id, sections in section_map.items():
    if len(sections) != len(md_files) + 1:
      logging.warning(f"{md_file.file_path} - {id} - only {len(sections)} sections vs {len(md_files)}")
    section_final = Section(title=sections[0].title, header_prefix=sections[0].header_prefix, lines=list(sections[0].lines))
    for section in sections[1:]:
      section_final.lines.extend(list(section.lines))
    sections_final.append(section_final)
  
  for section in sections_final:
    lines = "\n".join(section.lines)
    content += f"{section.header_prefix} {section.title}\n{lines}\n\n"

  (metadata_out, _) = md_file.read()
  if out_path is not None:
    out_path = md_files.file_path
    md_file = file.MdFile(file_path=out_path)
  content = regex.sub("\n\n+", "\n\n", content)
  md_file.dump_to_file(metadata=metadata_out, content=content, dry_run=dry_run)


def section_contents_to_details(content, title):
  from doc_curation.md.content_processor import details as details_helper
  (lines_till_section, sections) = get_sections(content=content)

  def _make_detail(lines):
    text = "\n".join(lines).strip()
    if text == "":
      return ""
    else:
      return details_helper.Detail(title=title, content=text).to_md_html()
  
  new_content = _make_detail(lines_till_section)
  
  for section in sections:
    section.lines = [_make_detail(section.lines)]
    new_content += section.to_md()

  return new_content


def section_headings_to_details(content, prev_detail_title="मूलम्(.*)", title="विषयः", inserter=PageElement.insert_after):
  from doc_curation.md.content_processor import details as details_helper
  (lines_till_section, sections) = get_sections(content=content)

  new_content = "\n".join(lines_till_section)

  # TODO: Consider section hierarchy
  for section in tqdm(sections):
    section_content = "\n".join(section.lines)
    
    section_content_new = details_helper.insert_adjascent_element(content=section_content, metadata=None, title=prev_detail_title, new_element=details_helper.Detail(title=title, content=section.title), inserter=inserter)
    section.lines = section_content_new.split("\n")
    new_content += section.to_md()

  return new_content


def headings_to_bold(content,suffix="॥"):
  return regex.sub(r"^(#+) *(.+)[॥ ]*", rf"**\2{suffix}**", content, flags=regex.MULTILINE)


def fix_headers(content: str, h1_level: int) -> str:
  # TODO: Hand jsinclude tags heregex.
  # h1_level is taken to mean title header level.
  if h1_level == "b[]":
    content = regex.sub(rf"(?<=\n|^)#+ ([^\n]+) *(?=\n)", rf"**\1**", content)
    return content

  if regex.search("^# ", content, flags=regex.MULTILINE):
    content = regex.sub(r"(?<=\n|^)#", f"{'#' * (h1_level+1)}", content)
  else:
    content = regex.sub(r"(?<=\n|^)#", f"{'#' * h1_level}", content)
  content = regex.sub(rf"(?<=\n|^)#######+", f"{'#' * 6}", content)
  return content


def _split_blocks_and_footnotes(text: str) -> tuple[list[dict], list[str]]:
  """Decompose Markdown into ordered body/heading blocks and verbatim footnote defs.

  Treats blank-separated indented paragraphs (4+ spaces or tab, including indented
  blockquotes) immediately following a ``[^id]:`` definition as continuations of that
  Goldmark footnote so ``p_idx`` counts only non-footnote, non-heading body blocks.
  """
  blocks = regex.split(r"\n{2,}", text.strip()) if text.strip() else []
  items = []
  fn_defs = []
  in_fn_def = False
  p_idx = 0
  for b_idx, blk in enumerate(blocks):
    stripped = blk.strip()
    if regex.match(r"^\[\^[^\]\n]+\]:", stripped):
      in_fn_def = True
      fn_defs.append(blk.rstrip())
      continue
    if in_fn_def and (blk.startswith("    ") or blk.startswith("\t")):
      fn_defs[-1] = f"{fn_defs[-1]}\n\n{blk.rstrip()}"
      continue
    in_fn_def = False
    hm = regex.match(r"^(#{1,6})\s+", stripped)
    is_h = bool(hm and "\n" not in stripped)
    items.append({
      "block_idx": b_idx,
      "p_idx": -1 if is_h else p_idx,
      "is_heading": is_h,
      "level": len(hm.group(1)) if is_h else 0,
      "text": stripped,
    })
    if not is_h:
      p_idx += 1
  return items, fn_defs


def parse_outline_blocks(text: str) -> list[dict]:
  """Return ordered heading and body blocks, skipping footnote definitions."""
  items, _ = _split_blocks_and_footnotes(text)
  return items


def prose_tokens_without_headings(text: str) -> list[str]:
  """Return ordered whitespace-delimited tokens outside headings and footnote defs."""
  return [
    tok
    for blk in parse_outline_blocks(text)
    if not blk["is_heading"]
    for tok in blk["text"].split()
  ]


def audit_headings(text: str) -> list[str]:
  """Audit Markdown heading nesting and placement against common structural bugs.

  Checks:
  - Skipped heading levels (e.g. ``##`` directly followed by ``####``).
  - Headings fused onto a preceding line without a blank line (outside fenced blocks).
  - Headings placed right before an unrelated ``[^id]:`` definition, lowercase
    mid-sentence continuation, or ``[First published: ...]`` attribution line.
  """
  issues = []
  in_fence = False
  prev_nonempty = ""
  for line_no, raw_line in enumerate(text.splitlines(), 1):
    s = raw_line.strip()
    if s.startswith("```"):
      in_fence = not in_fence
      prev_nonempty = s
      continue
    if not in_fence and regex.match(r"^#{1,6}\s+", s) and prev_nonempty and not regex.match(r"^#{1,6}\s+", prev_nonempty):
      issues.append(f"UNSPACED_HEADING at L{line_no}: {s!r} after {prev_nonempty[:40]!r}")
    prev_nonempty = s

  blocks = regex.split(r"\n{2,}", text.strip()) if text.strip() else []
  prev_level = 0
  for idx, blk in enumerate(blocks):
    s = blk.strip()
    hm = regex.match(r"^(#{1,6})\s+", s)
    if not hm or "\n" in s:
      continue
    lvl = len(hm.group(1))
    if prev_level and lvl > prev_level + 1:
      issues.append(f"LEVEL_JUMP: H{prev_level} -> H{lvl} at {s!r}")
    prev_level = lvl

    if idx + 1 >= len(blocks):
      continue
    nxt = blocks[idx + 1].strip()
    if regex.match(r"^#{1,6}\s+", nxt):
      continue
    if m_fn := regex.match(r"^\[\^([^\]\n]+)\]:", nxt):
      if f"[^{m_fn.group(1)}]" not in s:
        issues.append(f"HEADING_BEFORE_FOOTNOTE_DEF: {s!r} -> {nxt[:50]!r}")
    elif regex.match(r"^[a-zāīūṛṝḷḹēōṁḥṅñṭḍṇśṣ]", nxt):
      issues.append(f"HEADING_BEFORE_LOWERCASE: {s!r} -> {nxt[:50]!r}")
    elif nxt.lower().startswith("[first published:"):
      issues.append(f"HEADING_BEFORE_ATTRIBUTION: {s!r} -> {nxt[:50]!r}")
  return issues


def _emit_paragraph_with_headings(
  blk_text: str,
  p_idx: int,
  p_headings: list[dict],
  cur_level: int,
  allowed_levels: tuple[int, ...],
  errors: list[str],
) -> tuple[list[str], int]:
  """Insert validated stacked and inline split headings into one body paragraph."""
  out = []
  non_splits = sorted(
    [h for h in p_headings if not h.get("split_before", "").strip()],
    key=lambda h: h["level"],
  )
  splits = [h for h in p_headings if h.get("split_before", "").strip()]

  for i in range(1, len(non_splits)):
    if non_splits[i]["level"] != non_splits[i - 1]["level"] + 1:
      errors.append(f"BAD_STACK_ORDER at p{p_idx}: {non_splits}")

  for h in non_splits:
    lvl = h["level"]
    title = h["title"].strip()
    if lvl not in allowed_levels:
      errors.append(f"BAD_LEVEL at p{p_idx}: {h}")
    if "[First published:" in blk_text:
      errors.append(f"HEADING_ON_ATTRIBUTION at p{p_idx}: {title!r}")
    if cur_level and lvl > cur_level + 1:
      errors.append(f"LEVEL_JUMP at p{p_idx}: H{cur_level} -> H{lvl} ({title!r})")
    cur_level = lvl
    out.append(f"{'#' * lvl} {title}")

  if not splits:
    out.append(blk_text)
    return out, cur_level

  positioned = []
  for h in splits:
    sb = h["split_before"].strip()
    cnt = blk_text.count(sb)
    if cnt != 1:
      errors.append(f"SPLIT_NOT_UNIQUE (cnt={cnt}) at p{p_idx}: {sb!r}")
      continue
    pos = blk_text.find(sb)
    if pos == 0:
      errors.append(f"SPLIT_AT_ZERO at p{p_idx}: {sb!r}")
    positioned.append((pos, h))
  positioned.sort(key=lambda item: item[0])

  last = 0
  for pos, h in positioned:
    if head := blk_text[last:pos].strip():
      out.append(head)
    lvl = h["level"]
    title = h["title"].strip()
    if lvl not in allowed_levels:
      errors.append(f"BAD_LEVEL at split p{p_idx}: {h}")
    if cur_level and lvl > cur_level + 1:
      errors.append(f"LEVEL_JUMP at split p{p_idx}: H{cur_level} -> H{lvl} ({title!r})")
    cur_level = lvl
    out.append(f"{'#' * lvl} {title}")
    last = pos
  if tail := blk_text[last:].strip():
    out.append(tail)
  return out, cur_level


def apply_heading_outline(
  text: str,
  headings: list[dict],
  *,
  allowed_levels: tuple[int, ...] = (2, 3, 4),
  place_footnotes: bool = True,
  preserve_footnote_ids: bool = True,
) -> tuple[str, list[str]]:
  """Insert topic headings and mid-paragraph splits cleanly, auditing hierarchy and parity."""
  from doc_curation.md.content_processor.footnote import helper as footnote_helper

  items, fn_defs = _split_blocks_and_footnotes(text)
  prose_count = sum(1 for it in items if not it["is_heading"])
  errors = []

  by_para = {}
  for h in headings:
    p_idx = h["para_idx"]
    if not (0 <= p_idx < prose_count):
      errors.append(f"BAD_PARA_IDX: {h}")
      continue
    by_para.setdefault(p_idx, []).append(h)

  out_blocks = []
  cur_level = 0 if any(it["is_heading"] for it in items) else 1
  for it in items:
    if it["is_heading"]:
      lvl = it["level"]
      if cur_level and lvl > cur_level + 1:
        errors.append(f"EXISTING_LEVEL_JUMP: H{cur_level} -> H{lvl} at {it['text']!r}")
      cur_level = lvl
      out_blocks.append(it["text"])
      continue

    p_idx = it["p_idx"]
    hs = by_para.get(p_idx, [])
    if not hs:
      out_blocks.append(it["text"])
      continue
    emitted, cur_level = _emit_paragraph_with_headings(
      it["text"], p_idx, hs, cur_level if cur_level else 1, allowed_levels, errors
    )
    out_blocks.extend(emitted)

  assembled = "\n\n".join(out_blocks)
  if fn_defs:
    assembled = assembled + "\n\n" + "\n\n".join(fn_defs)
  if place_footnotes:
    assembled = footnote_helper.define_footnotes_near_use(
      assembled, preserve_ids=preserve_footnote_ids
    )
  result = assembled.strip() + "\n"

  orig_tokens = prose_tokens_without_headings(text)
  new_tokens = prose_tokens_without_headings(result)
  if orig_tokens != new_tokens:
    errors.append(f"PROSE_PARITY_MISMATCH (orig={len(orig_tokens)}, new={len(new_tokens)})")
  errors.extend(audit_headings(result))
  return result, errors
