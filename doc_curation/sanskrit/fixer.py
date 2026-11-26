import unicodedata

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


_MADHYANDINA_ACCENTS = r"[\u0951-\u0954\u0957\u1cd0-\u1ce8\u1cdf\u1cf4\u1cf8\u1cf9\ua8e0-\ua8f1]"
_MADHYANDINA_VOWELS = "अआइईउऊऋॠऌॡएऐओऔ"


def normalize_mAdhyandina(
  text: str,
  *,
  normalize_pre_vowel_avagrahas: bool = True,
  normalize_double_nasal: bool = True,
) -> str:
  """Normalize Vājasaneyi Mādhyandina orthographic and Vedic-accent quirks.

  1. Moves misplaced Vedic accents off halant conjuncts/codas (``त्॒वा`` -> ``त्वा॒``,
     ``द्वि॒ऽपदीम्॑`` -> ``द्वि॒ऽपदी॑म्``).
  2. Moves Vedic accents placed before a yogavāha to canonical post-yogavāha position
     (``बह्वी᳓ः`` -> ``बह्वीः᳓``, ``बु॒ध्न्य᳙ः`` -> ``बु॒ध्न्यः᳙``), collapsing doubled
     nasals ``ंँ`` -> ``ँ`` and repeated identical accent marks.
  3. Replaces Mādhyandina pre-vowel hiatus avagrahas with spaces
     (``प्र᳓त्युष्टाऽअ᳓रातयः`` -> ``प्र᳓त्युष्टा अ᳓रातयः``; ``॥ऽअ`` -> ``॥ अ``)
     while preserving true *pūrvarūpa* elision avagrahas before consonants.
  4. Replaces bad pausa / prevocalic anusvāras with ``म्`` while preserving trailing accents
     on the preceding vowel (``भागं᳓`` -> ``भाग᳓म्``, ``भा॒गं।`` -> ``भा॒गम्।``).
  """
  if not text:
    return text

  masks: dict[str, str] = {}

  def _mask(prefix: str):
    def _repl(m):
      k = f"§§{prefix}{len(masks)}§§"
      masks[k] = m.group(0)
      return k

    return _repl

  s = regex.sub(r"\+\+\+.*?\+\+\+|\[\[[^\]]+\]\]|\[\^[^\]\n]+\]|https?://\S+", _mask("ANN"), text, flags=regex.DOTALL)
  s = regex.sub(r"<[^>]+>", _mask("TAG"), s)

  s = regex.sub(rf"([क-ह]्)({_MADHYANDINA_ACCENTS}+)([क-ह][ािीुूृॄॢॣेैोौ]?)", r"\1\3\2", s)
  s = regex.sub(rf"([क-ह]्)({_MADHYANDINA_ACCENTS}+)(?![क-हअ-औा-ौ])", r"\2\1", s)
  s = regex.sub(rf"({_MADHYANDINA_ACCENTS}+)([ःंँꣳᳫ᳭ᳮ]+)", r"\2\1", s)
  if normalize_double_nasal:
    s = s.replace("ंँ", "ँ")
    s = regex.sub(rf"(?<![ेैोौ])ं({_MADHYANDINA_ACCENTS}*)म्", r"\1म्", s)
  s = regex.sub(rf"({_MADHYANDINA_ACCENTS}+)([ःंँꣳᳫ᳭ᳮ]+)", r"\2\1", s)
  for acc in ("॒", "॑", "᳓", "᳙"):
    s = regex.sub(rf"{acc}{{2,}}", acc, s)

  if normalize_pre_vowel_avagrahas:
    s = regex.sub(rf"(^|\s)ऽ[ \t]*(?={_MADHYANDINA_ACCENTS}*[{_MADHYANDINA_VOWELS}])", r"\1", s, flags=regex.M)
    s = regex.sub(rf"([।॥,;])ऽ[ \t]*(?={_MADHYANDINA_ACCENTS}*[{_MADHYANDINA_VOWELS}])", r"\1 ", s)
    s = regex.sub(rf"ऽ[ \t]*(?={_MADHYANDINA_ACCENTS}*[{_MADHYANDINA_VOWELS}])", " ", s)

  s = regex.sub(
    rf"(?<![ेैोौ])ं({_MADHYANDINA_ACCENTS}*)(?=\s*(?:$|[।॥,;.\)\]]|§§TAG\d+§§|[{_MADHYANDINA_VOWELS}])|[{_MADHYANDINA_VOWELS}])",
    r"\1म्",
    s,
    flags=regex.M,
  )

  for k, v in masks.items():
    s = s.replace(k, v)
  return s


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
  text = regex.sub(r"म्[\. ]+(?=[अ-औ])", "म् ", text)
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
  content = regex.sub(r"([ऀ-ॣ\u1cd0-\u1cff]*)(\*+)([ऀ-ॣ\u1cd0-\u1cff]+)\2([ऀ-ॣ\u1cd0-\u1cff]+)", r"\2\1\3\4\2", content)
  return content

def _remove_spaces_and_punctuation(text):
  return "".join(char for char in text if not char.isspace() and unicodedata.category(char)[0] not in "PS")

# OLD and NEW may contain footnote refs (eg. [[names160s|names[^151]]]), but not nested markers or newlines: a naive pattern such as r"\[\[([^\|]+)\|(.+?)\]\]" lets a page marker ([[P12]]) swallow the paragraphs that follow it up to the next "|" and "]]".
SUGGESTION_PATTERN = r"\[\[((?:(?!\[\[|\]\]|\n).)+?)\|((?:(?!\[\[|\n).)+?)\]\]"

def is_minor_roman_change(old, new):
  """
  Check whether the only differences between old and new are IAST/ ISO diacritics, spaces or punctuation (including - and +).

  Eg. "śivaṃ" vs "sivam", "devā-lokaḥ" vs "deva loka", "ṛtam" vs "r̥tam" and "tapaḥ + sva" vs "tapa sva" are minor changes, while "rāma" vs "nāma" is not.

  :param old: original text
  :param new: changed text
  :return: True if the change is minor.
  """
  def fold_diacritics(text):
    # IAST/ ISO diacritics decompose to a base Latin letter + combining marks (eg. ā -> a + macron, r̥ -> r + ring below), while devanagari and other scripts are left untouched.
    folded = []
    for char in unicodedata.normalize("NFD", text):
      if folded and unicodedata.category(char).startswith("M") and folded[-1].isascii() and folded[-1].isalpha():
        continue
      folded.append(char)
    return "".join(folded)

  def normalize(text):
    text = fold_diacritics(text or "")
    return _remove_spaces_and_punctuation(text)

  return normalize(old) == normalize(new)

def is_minor_dev_change(old, new):
  """
  Check whether the only differences between old and new (after conversion to ISO 15919) are in spaces, punctuation, anunāsika/ anusvāra or word-final visarga/ s/ r.

  Eg. "अँगुलिः" vs "अंगुलिः", "देवाः" vs "देवास्", "अग्निः" vs "अग्निर्" and "संस्कृतम् ।" vs "संस्कृतम्।" are minor changes, while "रामः" vs "नामः" is not.

  :param old: original text
  :param new: changed text
  :return: True if the change is minor.
  """
  def normalize(text):
    text = sanscript.transliterate(text or "", sanscript.DEVANAGARI, sanscript.ISO)
    text = text.replace("m̐", "ṁ")  # anunAsika and anusvAra are equivalent.
    # Word-final visarga, s and r are equivalent (eg. devaḥ, devas, devar). Non-final s and r are left intact (eg. rasa vs hasa).
    text = regex.sub(r"[ḥsrḤSR](?![A-Za-z\u00C0-\u024F\u0300-\u036F])", "s", text)
    return _remove_spaces_and_punctuation(text)

  return normalize(old) == normalize(new)

def accept_minor_changes(text, suggestion_pattern=SUGGESTION_PATTERN, *args, **kwargs):
  """
  Accept minor suggestions of the form [[OLD|NEW]] (as emitted by LLM proofreading) by replacing them with NEW, while leaving non-minor suggestions intact for manual review.

  A change is minor if it only involves spaces, punctuation, IAST/ ISO diacritics or (for Devanagari) anunāsika/ anusvāra/ visarga variations - see :func:`is_minor_dev_change` and :func:`is_minor_roman_change`.

  Eg. "[[tejaḥ sva|tejaḥsva]]" and "[[रामः|रामस्]]" are accepted, while "[[prarabvaṁ|prārabdhaṁ]]", "[[मातुलंगकैः|मातुलुङ्गकैः]]" and "[[tejaḥ|tejaḥ sva]]" are left intact.

  :param text: text containing [[OLD|NEW]] suggestions.
  :param suggestion_pattern: pattern matching a suggestion, with OLD in group 1 and NEW in group 2. It should not let OLD or NEW span nested markers or lines (see :const:`SUGGESTION_PATTERN`).
  :return: text with minor suggestions applied. Extra args (eg. metadata passed by :meth:`doc_curation.md.file.MdFile.transform`) are ignored.
  """
  def replacer(match):
    old, new = match.group(1), match.group(2)
    if regex.search(r"[\u0900-\u097F]", old + new):
      is_minor = is_minor_dev_change(old, new)
    else:
      is_minor = is_minor_roman_change(old, new)
    return new if is_minor else match.group(0)

  return regex.sub(suggestion_pattern, replacer, text or "")

