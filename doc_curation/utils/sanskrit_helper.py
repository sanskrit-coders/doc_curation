import regex
from indic_transliteration import sanscript, sacred_texts_scheme
from indic_transliteration.sanscript.schemes.brahmic.accent import ACCENTS_PATTERN




def deduce_root(text):
  root = regex.sub(r"([^ा]+)(ः|ं|म्)$", r"\1", text)
  root = regex.sub(r"(.+)(श्रव|मन)ाः$", r"\1\2स्", root)
  root = regex.sub(r"(.+)(त्म|शर्म)ा$", r"\1\2न्", root)
  return root


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण, गम्यते, तन्मध्य, अस्मिन्काले, मृण्मय, प्राङ्मुखं etc.. - so can't do - r"(?<!्)म्(\**[क-नय-ह])": r"ं\1" etc..
  replacements = {r"[ञणम](्[क-घ])": r"ङ\1", r"[ङनणम](्[च-झ])": r"ञ\1", r"[ञङनम](्[ट-ढ])": r"ण\1", r"म्([श])": r"ं\1",
                  r"ं$": "म्", r"ं(\**\s*[अ-औ।॥])": r"म्\1", r"म्(\**\s+[क-नय-ह])": r"ं\1", "ंल् ": "ल्ँ "}
  output = ""
  for c in regex.split(r"(?<=\n|^)(#.+)(?=\n|$)", text):
    for pattern, replacement in replacements.items():
      c = regex.sub(pattern, replacement, c)
    output += c
  return output


def fix_avagrahas(text):
  replacements = {r"(?<=[ोॆ])’(?=\S)" : "ऽ"}
  for pattern, replacement in replacements.items():
    text = regex.sub(pattern, replacement, text)
  return text


def fix_lazy_anusvaara(text, script=sanscript.DEVANAGARI):
  text = regex.sub("ं+", "ं", text)
  text = regex.sub("ंऽ", "ऽं", text)
  text = regex.sub("ं(?= +[।॥])", "म्", text)
  text = sanscript.SCHEMES[script].fix_lazy_anusvaara(text, ignore_padaanta=True, omit_yrl=True)
  return text


def fix_bad_visargas(text):
  replacements = {r"(?<=[ि-ौ])ः(?=\s+[अ-औगघङजझञदधनडढणबभमयलवह])": r"र्",
                  r"(?<=[ा])ः(?=\s+[अ-औगघङजझञदधनडढणबभमयरलवह])": r"", r"(?<=[क-ह])ः(\s+)अ": r"ो\1ऽ",
                  r"ः(?=\s+[चछ])": r"श्", r"ः(?=\s+[टठ])": r"ष्", r"ः(?=\s+[तथ])": r"स्",
                  r"(?<=[क-ह])ः(?=\s+[आ-औ])": r"", r"(?<=[क-ह])ः(?=\s*ऽ)": r"ो", }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_bad_vyanjanaantas(text):
  replacements = {r"त्(?=\s+[चछ])": r"च्", r"त्(?=\s+[जझ])": r"ज्", r"त्(?=\s+[टठ])": r"ट्", r"त्(?=\s+[डढ])": r"ड्",
                  r"त्(?=\s+[अ-औगघदधबभयरलव])": r"द्", r"त्(?=\s+[मन])": r"न्"}
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_accent_typos(text):
  replacements = {
    r"(॒){2,}": r"॒", r"(॑){2,}": r"॑",
    rf"({ACCENTS_PATTERN})(ः)": r"\2\1",
    rf"({ACCENTS_PATTERN})(ँ)+\1?": r"\2\1",
    rf"(?<![यलव]्)(ँ{ACCENTS_PATTERN}?)([यलव]्)": r"\2\1",
    rf"({ACCENTS_PATTERN})([यलव]्ँ)": r"\2\1",
    r"([यलव]्ँ)(वै|वा अ|य॒?ज्ञ|वाव |लो॒?क)": r"\1 \2",  
    "": "३॒॑", "": "१॒॑", "": "ᳶ", r"[]": r"ँ", "": r"॑",
  }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def undo_taittirIya_forms(text):
  SP_QUOT = r"[\s\"',;*]*"
  # Bad replacements 
  # पृथग्ग्रहणम् rf"({ACCENTS_PATTERN}?)ग्ग्\1": r"ँ\1",
  
  replacements = {
    r"[᳚᳛]": r"॑", r"२?[ꣲ-ꣷ]": r"ँ", r"ग्ं": r"ँ", rf"({ACCENTS_PATTERN})(ग्)?ग्\1": r"ँ\1", 
    rf"ख्({SP_QUOT}[सष])": r"क्\1", rf"थ्({SP_QUOT}[सष])": r"त्\1", rf"फ्({SP_QUOT}[सष])": r"प्\1",
    fr"({ACCENTS_PATTERN})र्\1": r"\1र्",
    rf"(न्)?न्({ACCENTS_PATTERN})": r"\2न्", rf"न्न्({ACCENTS_PATTERN}?){SP_QUOT}।": r"\1न् ।",
    rf"({ACCENTS_PATTERN})(\S्)\1": r"\1\2", 
  }
  # To test - "(॑|॒)(\S्)+\1": r"\1\2"
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_yaNs(text):
  replacements = {r"[ुू](?=\s+[अ-ईऋ-औ])": r"्व्", r"[िी](?=\s+[अआउ-औ])": r"्य्", r"[ृॄ](?=\s+[अ-ऊऌ-औ])": r"्र्",
                  r"[ॢॣ](?=\s+[अ-ॠए-औ])": r"्ल्", }
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def fix_anunaasikaadi(text, level=0, *args, **kwargs):
  from doc_curation.md.content_processor import ocr_helper
  text = ocr_helper.misc_manipravaala_typos(text)
  text = fix_bad_anunaasikas(text)
  text = fix_lazy_anusvaara(text)
  if level > 0:
    text = fix_yaNs(text)
    text = fix_bad_vyanjanaantas(text)
  return text


def numerify_shloka_numbering(text, encoding="कखगघङचछजझञ"):
  def transformer(match):
    return "॥%s.%d॥" % (match.group(1), encoding.index(match.group(2)) + 1)

  c = regex.sub(r"॥ *(\d+)[ (]*([%s])[ )]*॥" % encoding, transformer, text)
  return c


def undo_gretil_analysis(text):
  """
  Given text like: "अस्मिन्.वै.लोक.उभये.देव.मनुष्या.आसुः  । ते.देवाः.स्वर्गल्ँ.लोकम्.यन्तो.अग्निम्.ऊचुः  । ",  
  produce : "अस्मिन् वै लोक उभये देव मनुष्या आसुः  । ते देवाः स्वर्गल्ँ लोकं यन्तो ऽग्निम् ऊचुः  । ", 
  though, ideally, it ought to be "देव-मनुष्या". 
  
  :param text: 
  :return: 
  """
  text = text.replace("ंल्", "ल्ँ")
  text = regex.sub(r"म्[\. ]+(?=[अ-औ])", text)
  return text


def seperate_uvaacha(text):
  text = regex.sub(r"वाच॥\s*", r"वाच॥\n\n", text)
  return text


def fix_repha_duplication(text):
  text = regex.sub("र्क्ख", "र्ख", text)
  text = regex.sub("र्ग्घ", "र्घ", text)
  text = regex.sub("र्च्छ", "र्छ", text)
  text = regex.sub("र्ज्झ", "र्झ", text)
  text = regex.sub("र्त्थ", "र्थ", text)
  text = regex.sub("र्द्ध", "र्ध", text)
  text = regex.sub("र्ड्ढ", "र्ढ", text)
  text = regex.sub("र्प्फ", "र्फ", text)
  text = regex.sub("र्ब्भ्", "र्भ्", text)
  text = regex.sub("र्व्व", "र्व", text)
  text = regex.sub("र्य्य", "र्य", text)
  text = regex.sub(r"र्([ङञणनमयवशषसहलकगचजतदपब])्\1", r"र्\1", text)
  return text


def fix_sacred_texts_transliteration(text):
  def italicized_fixer(match):
    return sacred_texts_scheme.decode_italicized_text(match.group(1))

  text = regex.sub("_(..?)_", italicized_fixer, text)
  text = sacred_texts_scheme.decode_nonitalicized(text)
  return text


def fix_intra_word_bolds(content, *args, **kwargs):
  content = regex.sub(r"([ऀ-ॣ]*)(\*+)([ऀ-ॣ]+)\2([ऀ-ॣ]+)", r"\2\1\3\4\2", content)
  return content


def _approx_syllables(line):
  """Approximate svara/syllable count (svara-count clue for verse detection)."""
  try:
    from chandas.syllabize import get_syllables
    return len(get_syllables(line).split())
  except Exception:
    pass
  t = regex.sub(r"[^ऀ-ॣ]", "", line)
  t = regex.sub(r"[।॥]", "", t)
  if not t:
    return 0
  indep = len(regex.findall(r"[अ-औ]", t))
  signs = len(regex.findall(r"[ा-ौ]", t))
  inher = len(regex.findall(r"[क-ह](?![्ा-ौ])", t))
  return indep + signs + inher


def _is_verse_block(para):
  """True if a paragraph is an unquoted verse (do not split internally).

  Clues: ends with ``॥`` (optionally numbered), 2-4 lines each ending
  with ``।``/``॥``, no prose markers (``? ! ; :``), no brackets/refs,
  plus meter check via ``chandas`` when available, else svara-count
  equality.
  """
  lines = [l.strip() for l in para.strip().splitlines() if l.strip()]
  if len(lines) < 2 or len(lines) > 4:
    return False
  if not regex.search(r"॥\s*[०-९0-9\s\.\-–—]*॥?\s*$", lines[-1]):
    return False
  # Quoted verses are already kept intact via quote protection.
  if regex.search(r"[‘’“\"']", para):
    return False
  # Brackets/refs indicate prose with citations, not bare verse.
  if "(" in para or ")" in para or "[" in para:
    return False
  for l in lines:
    if regex.search(r"[?!;:—–]", l):
      return False
    if not regex.search(r"[।॥]\s*[०-९0-9\s\.\-–—]*[।॥]?\s*$", l):
      return False
  # Meter check via chandas when available.
  try:
    from chandas import to_pattern_lines, svat_identifier
    pl = to_pattern_lines(lines)
    res = svat_identifier.IdentifyFromPatternLines(pl)
    if res and res.get("exact"):
      return True
  except Exception:
    pass
  # Fallback: svara-count equality + minimum length.
  try:
    counts = [_approx_syllables(l) for l in lines]
  except Exception:
    return False
  if any(c < 8 for c in counts):
    return False
  if max(counts) / max(1, min(counts)) > 1.6:
    return False
  return True


def split_to_sentences(text):
  """Split Sanskrit prose (e.g. bhāṣya) into sentences.

  - Splits on ``।``, ``॥`` (with optional verse numbers like ``॥ १३ ॥``),
    ``?``, ``!`` and ``;`` occurring *outside* protected spans.
  - Does NOT split inside round/square brackets ``(...)``/``[...]``
    (reference numbers like ``(तै. उ. २। ५। १)`` contain ``।``),
    nor inside short quotations
    ``‘...’``/``'...'``/``“...”``/``"..."``
    (verses and śruti quotes like ``‘यदा ... विन्दते। ... भवति’``
    stay intact).
  - Does NOT split unquoted verse blocks (e.g. Gītā śloka on two
    lines ending in ``॥``): detected via ``॥``, svara-count equality
    and ``chandas`` meter identification when available.
  - Returns list of stripped non-empty sentences, preserving original
    characters. Trailing fragment without terminator (e.g. lead-in
    ending in ``—``) is returned as-is so nothing is lost.

  :param text: Sanskrit text (possibly multi-paragraph).
  :return: list of sentences.
  """
  if not text:
    return []
  text = text.replace("\r\n", "\n").strip()
  if not text:
    return []

  # Respect paragraph breaks: split first on blank lines so lead-in
  # fragments ending in — / : and standalone verses stay separate,
  # then split each paragraph on terminators and flatten.
  paragraphs = [p for p in regex.split(r"\n\s*\n", text) if p.strip()]
  if len(paragraphs) > 1:
    out = []
    for p in paragraphs:
      out.extend(split_to_sentences(p))
    return out

  # Unquoted verse block: keep whole paragraph together.
  if _is_verse_block(text):
    return [text.strip()]

  # --- protected spans: (...) [...] and '...' "..." ‘...’ “...” ---
  spans = []

  def _add_spans(pattern, flags=0):
    try:
      for m in regex.finditer(pattern, text, flags=flags):
        if m.end() > m.start():
          spans.append((m.start(), m.end()))
    except Exception:
      pass

  # Balanced round brackets (refs); regex module supports recursion.
  try:
    _add_spans(r"\((?:[^()]|(?R))*\)", flags=regex.DOTALL)
  except Exception:
    _add_spans(r"\([^()]*\)", flags=regex.DOTALL)
  _add_spans(r"\[[^\[\]]*\]", flags=regex.DOTALL)
  # Curly/straight quotes (non-greedy, must close on same paragraph).
  _add_spans(r"‘[^’]*’", flags=regex.DOTALL)
  _add_spans(r"“[^”]*”", flags=regex.DOTALL)
  _add_spans(r"'[^'\n]*'", flags=0)
  _add_spans(r'"[^"\n]*"', flags=0)

  spans.sort()
  # Merge overlaps.
  merged = []
  for s, e in spans:
    if merged and s <= merged[-1][1]:
      merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    else:
      merged.append((s, e))

  def _protected(pos):
    for s, e in merged:
      if s <= pos < e:
        return True
      if pos < s:
        return False
    return False

  # --- terminators outside protected spans ---
  # Double daṇḍa with optional number/range: ॥ १३ ॥, ॥१२ – १९ ॥, ॥.
  double_pat = regex.compile(r"॥\s*[०-९0-9\s\.\-–—]*॥|॥")
  single_pat = regex.compile(r"(?<!।)।(?!।)")
  punct_pat = regex.compile(r"[?!;]")

  bounds = []  # end offsets (exclusive of trailing spaces, inclusive of terminator)
  for m in double_pat.finditer(text):
    if not _protected(m.start()):
      bounds.append(("d", m.start(), m.end()))
  for m in single_pat.finditer(text):
    if not _protected(m.start()):
      # Skip if part of an already-recorded double-daṇḍa bound.
      skip = False
      for _, ds, de in bounds:
        if ds <= m.start() < de:
          skip = True
          break
      if not skip:
        bounds.append(("s", m.start(), m.end()))
  for m in punct_pat.finditer(text):
    if not _protected(m.start()):
      bounds.append(("p", m.start(), m.end()))
  bounds.sort(key=lambda x: x[1])

  sentences = []
  start = 0
  for _, bs, be in bounds:
    # Include immediately following closing quotes/brackets if any
    # (e.g. `...?’, ...।’` is rare; terminator is usually outside).
    end = be
    # Do not consume the whitespace; slicing + strip handles it.
    sent = text[start:end].strip()
    # Attach leading whitespace-separated? No, keep as-is.
    if sent:
      sentences.append(sent)
    start = end
  tail = text[start:].strip()
  if tail:
    sentences.append(tail)
  return [s for s in sentences if s]

