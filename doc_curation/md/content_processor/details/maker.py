import logging
import os
import textwrap

import regex
from doc_curation.md import library
from doc_curation.md.content_processor import get_quasi_section_int_map
from doc_curation.md.content_processor.details.common import _normalize_spaces, _remap_source_matches
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
  if not callable(source_file):
    source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
  for md_file in md_files:
    logging.info("Interleaving into %s", md_file.file_path)
    if callable(source_file):
      source_file = source_file(md_file.file_path)
      source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
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
      logging.info(f"Removing {source_file}")
      if not dry_run:
        os.remove(source_file)
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
                               muula_title="मूलम्"):
  """Wrap each sentence of bare Sanskrit text in विश्वास + मूलम् blocks.

  Takes ```content`` (a full file body or section), and for every
  non-detail paragraph after ``start_text`` splits it with
  :func:`doc_curation.sanskrit.split_to_sentences` and
  replaces each sentence with an (open) विश्वास-प्रस्तुतिः block plus a
  मूलम् block — no translations involved (those are inserted later,
  above each मूलम् block, once mapped).

  :param content: markdown text.
  :param start_text: only text after this marker's line is processed;
    ``None`` processes from the top (leading ``+++`` frontmatter and
    markdown headings are always skipped).
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
    m = regex.match(r"^\+\+\+.*?\+\+\+\n?", content, flags=regex.DOTALL)
    head = m.group(0) if m else ""
    rest = content[len(head):]

  out = []
  for seg in regex.split(r"(<details\b.*?</details>)", rest,
                         flags=regex.DOTALL):
    if not seg:
      continue
    if seg.strip().startswith("<details"):
      out.append(seg)
      continue
    chunks = []
    for tok in regex.split(r"(\n\s*\n)", seg):
      if not tok.strip() or regex.fullmatch(r"\n\s*\n", tok):
        chunks.append(tok)
        continue
      if tok.strip().startswith("#") \
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
          groups = [
            Detail(title=vishvaasa_title, content=s).to_md_html() + "\n\n"
            + Detail(title=muula_title, content=s).to_md_html()
            for s in [x for x in split_to_sentences(chunk) if x.strip()]]
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


if __name__ == '__main__':
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/07_antaradhikaraNam.md", content_transformer=lambda c, *args, **kwargs: generic_sanskrit_vipra_mUla(c))
