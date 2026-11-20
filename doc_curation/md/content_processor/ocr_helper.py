import os
from pathlib import Path

import pandas
import regex
import tqdm
from doc_curation import sanskrit as sanskrit_helper
from doc_curation.sanskrit.seeker import is_sanskrit_nagari
from indic_transliteration import sanscript


def get_gemini_flash_mangled_sanskrit_files(
    dir_path,
    regex_filter=r"\[\[[^\|]+\|(.+?)\]\]",
    regex_min=5,
    hyphenated_min=20,
):
  """Get Markdown paths with many Gemini OCR markers in Sanskrit Nagari.

  A file must contain at least ``regex_min`` matches of ``regex_filter``,
  at least ``hyphenated_min`` Devanagari hyphenated forms, and pass
  :func:`is_sanskrit_nagari`. Both minimums are inclusive.
  """
  dir_path = Path(dir_path)
  if not dir_path.is_dir():
    raise NotADirectoryError(dir_path)
  if regex_min < 0 or hyphenated_min < 0:
    raise ValueError("Match minimums must be non-negative")
  file_regex = regex.compile(regex_filter)
  hyphenated_sanskrit_regex = regex.compile(r"[\u0900-\u097F]+-[\u0900-\u097F]+")
  matching_files = []
  for file_path in sorted(dir_path.rglob("*.md")):
    if not file_path.is_file():
      continue
    content = file_path.read_text(encoding="utf-8")
    if not is_sanskrit_nagari(content):
      continue
    if len(file_regex.findall(content)) < regex_min:
      continue
    if len(hyphenated_sanskrit_regex.findall(content)) < hyphenated_min:
      continue
    matching_files.append(str(file_path))
  return matching_files


def fix_iast_for_pdfs(text):
  # When Google Drive api is used to extract text from copy-pasteable pdfs, certain replacements are needed to recover proper text.
  from doc_curation.utils import patterns
  text = regex.sub(rf"(n *\. *)(?={patterns.LOWER_CASE_ISO})", "ṇ", text)
  text = regex.sub(rf"( *\˙n)(?=[kg])", "ṇ", text)
  text = regex.sub(rf"(N *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṇ", text)

  text = regex.sub(rf"(c *\. *)(?={patterns.LOWER_CASE_ISO})", "c̣", text)
  text = regex.sub(rf"(C *\. *)(?={patterns.LOWER_CASE_ISO})", "C̣", text)
  text = regex.sub(rf"(d *\. *)(?={patterns.LOWER_CASE_ISO})", "ḍ", text)
  text = regex.sub(rf"(D *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḍ", text)

  text = regex.sub(rf"(t *\. *)(?={patterns.LOWER_CASE_ISO})", "ṭ", text)
  text = regex.sub(rf"(T *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṭ", text)

  text = regex.sub(rf"(s *\. *)(?={patterns.LOWER_CASE_ISO})", "ṣ", text)
  text = regex.sub(rf"(S *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṣ", text)

  text = regex.sub(rf"(l *\. *)(?={patterns.LOWER_CASE_ISO})", "ḷ", text)
  text = regex.sub(rf"(L *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḷ", text)

  text = regex.sub(rf"(r *\. *)(?={patterns.LOWER_CASE_ISO})", "r̥", text)
  text = regex.sub(rf"(R *\. *)(?={patterns.UPPER_CASE_ISO})", "R̥", text)

  text = regex.sub(rf"(h *\. *)(?={patterns.LOWER_CASE_ISO})", "ḥ", text)
  text = regex.sub(rf"(h *\. *)(?=[|:,])", "ḥ", text)
  text = regex.sub(rf"(H *\. *)(?={patterns.UPPER_CASE_ISO})", "Ḥ", text)

  text = regex.sub(rf"(m *\. *)(?={patterns.LOWER_CASE_ISO})", "ṁ", text)
  text = regex.sub(rf"( *˙m)", "ṁ", text)
  # text = regex.sub(rf"(m *\. *)(?=[|:,])", "ṁ", text)
  text = regex.sub(rf"(M *\. *)(?={patterns.UPPER_CASE_ISO})", "Ṁ", text)

  text = regex.sub(rf"(K\.)(?={patterns.LOWER_CASE_ISO})", "Ḳ", text)
  text = regex.sub(rf"(k\.)(?={patterns.LOWER_CASE_ISO})", "ḳ", text)

  text = regex.sub(r"¯\s*a", "ā", text)
  text = regex.sub(r"¯\s*i", "ī", text)
  text = regex.sub(r"¯?ı", "ī", text)
  text = regex.sub(r"¯\s*u", "ū", text)
  text = regex.sub("¯r̥", "r̥̄", text)
  text = regex.sub("¯l̥", "l̥̄", text)
  text = regex.sub(r"¯\s*A", "Ā", text)
  text = regex.sub(r"¯\s*I", "Ī", text)
  text = regex.sub(r"¯\s*U", "Ū", text)
  
  # The below are rarer, so substituted later.
  text = regex.sub(r"¯\s*e", "ē", text)
  text = regex.sub(r"¯\s*o", "ō", text)
  text = regex.sub("l¯", "ḻ", text)
  text = regex.sub("n¯", "ṉ", text)
  text = regex.sub("N¯", "Ṉ", text)
  text = regex.sub("r¯", "ṟ", text)
  text = regex.sub("R¯", "ṟ", text)


  text = regex.sub("¨a", "ä", text)
  text = regex.sub("¨A", "Ä", text)
  text = regex.sub("¨u", "ü", text)
  text = regex.sub("¨U", "Ü", text)

  text = regex.sub("˜n", "ñ", text)
  text = regex.sub("˜N", "Ñ", text)

  return text

def fix_shuunya_ansvaaras(text):
  # ऒ०दॊ०दर → ऒन्दॊन्दर
  text = regex.sub(r"(?<=[ऀ-ॣ])[०o]", "ं", text)
  text = sanskrit_helper.fix_anunaasikaadi(text=text)
  return text

def fix_google_ocr_devanaagarii(text, new_line_substitute="\n\n"):
  text = fix_dandas(text)
  text = regex.sub(r"(?<=\n)[\-=]+ *(?=\n)", "", text)
  text = regex.sub(r"(?<=\n)([०-९\d]+) *(?=\n)", r"[[\1]]", text)
  text = regex.sub("(?<=[ँ-९]):", "ः", text)
  text = regex.sub(r"(?<=\S) ?\n", new_line_substitute, text)
  # text = regex.sub("(?<=[a-zA-Z])- +(?=[a-zA-Z])", "", text)
  text = strip_word_continuation_dashes(text)
  return text

def fix_mid_shloka_empty_lines(text):
  text = regex.sub(r"।\n\n+", "।  \n", text)
  return text

def fix_dandas(text):
  text = regex.sub("ll(?= +\n|$)", "॥", text)
  text = regex.sub("l(?= +\n|$)", "।", text)
  text = regex.sub(r"\|\|", "॥", text)
  # Pipes are used in md tables. So, taking care below.
  lines = text.split("\n")
  lines_out = []
  for line in lines:
    if line.strip().startswith("|") and line.strip().endswith("|"):
      lines_out.append(line)
    else:
      lines_out.append(regex.sub(r"\|", "।", line))
  text = "\n".join(lines_out)
  text = regex.sub(r"।।।+", r"…", text)
  text = regex.sub(r"।।", "॥", text)
  return text


def fix_tables(text):
  # Fix md tables with pipes and colons erroneously transliterated
  lines = text.split("\n")
  lines_out = []
  for line in lines:
    if len(line.strip()) >= 2 and line.strip()[0] in ("|", "।") and line.strip()[-1] in ("|", "।"):
      l = regex.sub(r"।", "|", line)
      l = regex.sub("-ः", "-:", l)
      l = regex.sub("ः-", ":-", l)
      lines_out.append(l)
    else:
      lines_out.append(line)
  return "\n".join(lines_out)

def misc_manipravaala_typos(text):
  text = fix_dandas(text)
  sanskrit_helper.fix_bad_anunaasikas(text)
  # text = regex.sub(":-", "--", text)
  text = regex.sub("(?<=[ँ-ॣ]):", "ः", text)
  text = regex.sub("(?<=[ँ-ॣ])[sS]", "ऽ", text)
  text = regex.sub(r"(?<=[ऀ-ॣ])[०]", "॰", text)
  return text

def misc_sanskrit_typos(text, strict=False, *args, **kwargs):
  text = misc_manipravaala_typos(text=text)
  text = sanskrit_helper.fix_anunaasikaadi(text=text)
  text = sanskrit_helper.fix_accent_typos(text=text)
  if strict:
    text = regex.sub("ळ", "ल", text)
    text = regex.sub("ढ़", "ढ", text)
  text = regex.sub("(?<=[अ-ौ]|[ॎ-ॣ]):", "ः", text)
  # text = regex.sub("(?<=[ँ-ॣ])- +(?=[ँ-ॣ])", "", text)
  return text


def fix_line_end_dashes(text):
  text = regex.sub("(?<=[ँ-ॣ])- +(?=[ँ-ॣ])", "", text)
  return text

def fix_avagraha_quotations(text):
  text = regex.sub(r"(?<=\s)ऽ", "\"", text)
  text = regex.sub(r"ऽ(?=\s)", "\"", text)
  return text


def fix_hyphenation(text):
  text = sanscript.SCHEMES[sanscript.DEVANAGARI].redo_upapada_sandhis(text)
  text = regex.sub(r"-([ा-ौ])", r"\1", text)
  text = regex.sub(r"\*\*(.्) ", r"\1** ", text)
  return text


def fix_gemini_flash_errors(text):
  text = regex.sub(r"-न्त", r"-अन्त", text)
  text = fix_hyphenation(text)
  text = regex.sub(r"त्(?=[ -][चछ])", r"च्", text)
  text = regex.sub(r"(?<=च्[ -])श", r"छ", text)
  text = regex.sub(r"स्(?=[ -][चछश])", r"श्", text)
  text = regex.sub(r"इति इत्य्", r"इत्य्", text)
  text = regex.sub(r"अतैव", r"अत एव", text)
  text = regex.sub(r"्-इ-", r"ि", text)
  text = regex.sub(r"(?<=ा)[अआ]", r"", text)
  text = regex.sub(r"(?<=[ँ-०])b", "ब", text)
  text = regex.sub(r"(?<=[ँ-०])g", "ग", text)
  text = regex.sub(r"\\u0bca", "ॊ", text)
  text = regex.sub(r"\\u0bc5", "ॆ", text)
  text = regex.sub(r"maय", "माय", text)

  return text

def replace_casewise(text, pattern, replacement):
  text = regex.sub(pattern.lower(), replacement.lower(), text)
  text = regex.sub(pattern.upper(), replacement.upper(), text)
  return text


def fix_google_ocr_iast_iso(text):
  text = replace_casewise(text, "ş", "ṣ")
  text = regex.sub("ń(?=[kg])", "ṅ", text)
  text = regex.sub("ń(?=[cj])", "ñ", text)
  text = replace_casewise(text, "ņ", "ṇ")
  text = replace_casewise(text, "Š|Ç", "Ś")
  text = replace_casewise(text, "Ş|ș", "Ṣ")
  text = replace_casewise(text, "ț|ṱ", "ṭ")
  text = replace_casewise(text, "ḑ", "ḍ")
  text = replace_casewise(text, "ä|ă|å|Ã", "ā")
  text = replace_casewise(text, "ü|û", "ū")
  text = replace_casewise(text, "õ", "ō")
  text = replace_casewise(text, "Ï|ī|î", "Ī")
  text = replace_casewise(text, "ě", "ē")
  text = regex.sub(r"(?<=[a-z])- +(?=[a-z])", "", text)
  return text


def strip_word_continuation_dashes(text):
  text = regex.sub(r"(?<=\S)- +(?=\S)", "", text)
  return text

def fix_typos(text):
  import doc_curation
  typos_df = pandas.read_csv(os.path.join(os.path.dirname(doc_curation.__file__), "data/ocr_typos/sa/iast/manual.tsv"), sep="\t")
  typos_df = typos_df.set_index("correct")
  for typo in tqdm.tqdm(typos_df.index):
    ta_words = typos_df.loc[typo, "typo"].split(",")
    for ta_word in ta_words:
      text = text.replace(ta_word, typo)
  return text


def fix_foxit(text):
  text = regex.sub(r"(\S) ᐀्", r"र्\1", text)
  return text

def fix_poppler_ocular(text):
  text = regex.sub(r"([ \-])\�(([क-ह]्)*([क-ह]))(?<![ा-ॏ])", r"\1\2ि", text)
  text = regex.sub(r"(([क-ह]्)*([क-ह][ा-ॏ]?))\�(?=[ \-])", r"र्\1", text)
  return text

def fix_dangling_maatraas(text):
  text = regex.sub(r"(\*+)(\s+)([ऀ-ःऺ-ॏ])", r"\3\1", text)
  return text

def fix_pandoc_md(text):
  text = regex.sub(r" ", r" ", text)
  text = regex.sub(r"\\\*", r"_", text)
  text = regex.sub(r"\\_", r"_", text)
  text = regex.sub("(?<=\n) +", "", text)
  text = regex.sub(r"\*\*\*\*", "", text)
  from doc_curation.md.content_processor import space_helper
  text = space_helper.fix_markup(text=text)
  return text


def _collect_page_marker_issues(text, expected_pages=None):
  """Check page-marker completeness, uniqueness, monotonic order, and spacing."""
  found_ids = regex.findall(r"\[\[P([0-9]+[a-zA-Z]?)\]\]", text)
  seen = set()
  duplicate_pages = []
  for pid in found_ids:
    if pid in seen and pid not in duplicate_pages:
      duplicate_pages.append(pid)
    seen.add(pid)

  missing_pages = []
  if expected_pages is not None:
    expected_strs = [str(p) for p in expected_pages]
    missing_pages = [p for p in expected_strs if p not in seen]

  numeric_pages = [int(pid) for pid in found_ids if pid.isdigit()]
  out_of_order_pages = [
    numeric_pages[i] for i in range(1, len(numeric_pages)) if numeric_pages[i] < numeric_pages[i - 1]
  ]
  unspaced_page_markers = [
    m.group(0)
    for m in regex.finditer(r"\S*(\[\[P[0-9]+[a-zA-Z]?\]\])\S*", text)
    if m.group(0) != m.group(1)
  ]
  return {
    "found_pages": found_ids,
    "missing_pages": missing_pages,
    "duplicate_pages": duplicate_pages,
    "out_of_order_pages": out_of_order_pages,
    "unspaced_page_markers": unspaced_page_markers,
  }


def _collect_footnote_issues(text):
  """Check Markdown footnote ref/definition parity and duplicated number prefixes."""
  refs = regex.findall(r"\[\^([^\]\n]+)\](?!:)", text)
  defs = regex.findall(r"(?m)^\[\^([^\]\n]+)\]:", text)
  ref_set = set(refs)
  def_set = set(defs)
  duplicate_fn_prefixes = regex.findall(r"(?m)^\[\^\d+_(\d+)\]:\s*\1\b\.?", text)
  return {
    "fn_refs": len(refs),
    "fn_defs": len(defs),
    "missing_defs": sorted(ref_set - def_set),
    "orphan_defs": sorted(def_set - ref_set),
    "duplicate_fn_prefixes": duplicate_fn_prefixes,
  }


def validate_proofread_markdown(
  text: str,
  *,
  expected_pages=None,
  ignore_html_tags=(),
  check_headings: bool = False,
) -> dict:
  """Validate multi-page scan-proofread Markdown structure and editorial markers.

  Checks ``[[Pnnn]]`` page coverage, ordering, duplicates, spacing, continuity
  artifacts (``[[CONT*]]`` / ``[[FN_CONT*]]``), ``[^id]`` footnote pairing,
  raw HTML tags, unbalanced italic asterisks, and collects ``[[OLD|NEW]]`` /
  ``[[??]]`` editorial flags for human review. When ``check_headings`` is
  ``True``, also includes :func:`section_helper.audit_headings` findings.
  """
  page_info = _collect_page_marker_issues(text, expected_pages=expected_pages)
  fn_info = _collect_footnote_issues(text)

  leftover_tags = regex.findall(r"\[\[(?:CONT|CONT_HYPH|FN_CONT)[^\]]*\]\]", text)
  flags = regex.findall(r"\[\[(?!P\d+[a-zA-Z]?\]\]|(?:CONT|CONT_HYPH|FN_CONT)\b)[^\]]+\]\]", text)
  ignored_tag_names = {t.lower() for t in ignore_html_tags}
  html_tags = [
    tag for tag in regex.findall(r"<[^>]+>", text)
    if (m := regex.match(r"^</?\s*([A-Za-z0-9_-]+)", tag)) is None or m.group(1).lower() not in ignored_tag_names
  ]
  odd_asterisk_paragraphs = [
    idx for idx, para in enumerate(text.split("\n\n"), 1)
    if para.replace("\\*", "").count("*") % 2 != 0
  ]

  report = {
    "chars": len(text),
    **page_info,
    **fn_info,
    "leftover_tags": leftover_tags,
    "flags": flags,
    "html_tags": html_tags,
    "odd_asterisk_paragraphs": odd_asterisk_paragraphs,
  }
  if check_headings:
    from doc_curation.md.content_processor.section_helper import audit_headings
    report["heading_issues"] = audit_headings(text)

  report["ok"] = not (
    report["missing_pages"]
    or report["duplicate_pages"]
    or report["out_of_order_pages"]
    or report["unspaced_page_markers"]
    or report["leftover_tags"]
    or report["missing_defs"]
    or report["orphan_defs"]
    or report["duplicate_fn_prefixes"]
    or report["html_tags"]
    or report["odd_asterisk_paragraphs"]
    or report.get("heading_issues")
  )
  return report
