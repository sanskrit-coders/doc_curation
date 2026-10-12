"""Sequential Sanskrit→translation matcher with minimal token usage.

Used for tasks like interleaving Śaṅkara-bhāṣya files: given the list of
Sanskrit sentences (``texts``) and one long ``translation_text``, return a
list of translation strings of the same length, in order, each element
being the (verbatim, single-space-joined) English sentences aligned to
that Sanskrit sentence.

Design goal: **no LLM calls on the default path**, so aligning a whole
adhikaraṇa costs (almost) zero LLM tokens.  Instead we:

1. split ``translation_text`` locally into English sentences,
2. get a cheap pivot gloss for each Sanskrit sentence via
   :func:`doc_curation.translation.translate` (a plain MT API call,
   not an LLM; failures fall back to pure local matching), and
3. solve a monotonic partition (DP, like DTW/Needleman-Wunsch) maximizing
   pivot + transliteration-keyword overlap.

An optional LLM touch-up can be layered later only on low-confidence
spans; it is deliberately *not* part of the default path.

Accuracy note (measured on six Śaṅkara-bhāṣya adhikaraṇas, 373 sentences,
``translators`` lib absent so pivot falls back to local signals):
~29% exact string match, mean token-F1 ~0.55, ref-anchor recall ~62%.
Residual gaps are (a) human judgment group/split calls no deterministic
rule replicates (reviewer fixes boundaries; content is usually right),
(b) philosophical paraphrase with no shared lexis — the case the
``translate()`` pivot is wired for (install ``translators`` to enable),
(c) forced "" spans when EN sentences < SA sentences.
"""

import functools
import logging
import unicodedata
from difflib import SequenceMatcher

import regex

try:
  from doc_curation.utils.sanskrit_helper import split_to_sentences as _sa_split
except Exception:  # pragma: no cover - helper optional at import time
  _sa_split = None


# ---------------------------------------------------------------------------
# English sentence splitting (local, protects abbreviations/footnotes).
# ---------------------------------------------------------------------------

_ABBREVS = (
  "Up", "Br", "Bṛ", "Br̥", "Cḥ", "Ch", "Taitt", "Tait", "Bha", "Bhā",
  "Sū", "Su", "Ṛk", "Rk", "Kau", "Kaus", "Mu", "Mun", "Mund", "Śve", "Sve",
  "Sv", "Pra", "Prau", "Ke", "Kena", "Ka", "Kat", "Katha", "Kh", "Brah",
  "Ār", "Ar", "Smṛ", "Smr", "Gītā", "Gita", "Chā", "Cha", "Śat", "Sat",
  "Tai", "Brh", "Samh", "Sam",
  "e", "i", "viz", "etc", "cf", "pp", "vol", "trans", "ed", "St", "Mr",
  "Dr", "Prof", "vs", "fig", "sec", "ch",
)

_STOP = frozenset(
  "the a an of to in on and or is are was were be been being it its this "
  "that these those as by with for from which who whom whose he she they "
  "we you i his her their our your him them us me my mine so than then "
  "there here thus hence also only even ever never not no nor but if when "
  "while where how what why whether because although though however "
  "therefore moreover further again one two which has have had has do does "
  "did will would shall should can could may might must such other same "
  "more most much many some any all every each own into out up down over "
  "under between within without about against during before after at".split()
)


def _ascii_fold(s):
  return "".join(
    c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
  )


def _split_english_sentences(translation_text):
  """Split English translation into sentences, keeping footnote defs whole.

  Line-wrapped paragraphs are re-joined first: a paragraph not ending in
  terminal punctuation (e.g. dangling ``Compare``, ``...departed``,
  ``(the`` from mid-sentence file wraps) is merged with the next
  paragraph, so wraps don't become phantom sentences.
  """
  text = translation_text.replace("\r\n", "\n").strip()
  if not text:
    return []
  # Paragraphs first: footnote definitions (lines starting with [^x]:)
  # stay atomic so their marker token keeps them with the host sentence.
  raw_paras = [p for p in regex.split(r"\n\s*\n", text) if p.strip()]
  paras = []
  buf = ""
  for para in raw_paras:
    ps = para.strip()
    if regex.match(r"\[\^[^\]]+\]:", ps):
      if buf.strip():
        paras.append(buf.strip())
        buf = ""
      paras.append(ps)
      continue
    buf = (buf + " " + ps).strip() if buf else ps
    # Flush once the buffer ends with terminal punctuation (optionally
    # followed by closing quotes/brackets).
    if regex.search(r"[.?!;:][\"'’”\)\]]?\s*$", buf):
      paras.append(buf)
      buf = ""
  if buf.strip():
    paras.append(buf.strip())
  units = []
  for para in paras:
    ps = para.strip()
    if regex.match(r"\[\^[^\]]+\]:", ps):
      units.append(regex.sub(r"\s+", " ", ps))
      continue
    # Protect abbreviations + enumerations ("28. ", "13. ", "I, 1, 20").
    protected = ps
    for ab in _ABBREVS:
      protected = regex.sub(
        r"\b%s\." % regex.escape(ab), ab + "<DOT>", protected
      )
    # Sūtra/verse numbers anywhere ("13. If...", "...there? 13. If..."):
    # keep the label glued to its sentence; the split before it (after
    # the previous terminator) still happens normally.
    protected = regex.sub(r"\b(\d{1,3})\.(\s)", r"\1<DOT>\2", protected)
    # Split on . ? ! ; followed by whitespace + next-sentence starter
    # (capital/digit, optionally quoted).  Keeping ";" capital-gated
    # avoids shredding Thibaut's ";" + lowercase continuations, which
    # manual alignment usually keeps with their host sentence; the DP
    # can still group separate units when they belong together.
    parts = regex.split(
      r"([.?!;])\s+(?=[\"'‘“\(\[]?[A-Z0-9\[\(])", protected)
    # Re-assemble terminator with its sentence (None = idle group).
    cur = ""
    for part in parts:
      if part is None or part == "":
        continue
      if part in (".", "?", "!", ";"):
        cur += part
        s = cur.strip().replace("<DOT>", ".")
        s = regex.sub(r"\s+", " ", s)
        if s:
          units.append(s)
        cur = ""
      else:
        cur += part
    tail = cur.strip().replace("<DOT>", ".")
    tail = regex.sub(r"\s+", " ", tail)
    if tail:
      units.append(tail)
  return [u for u in units if u]


def _tokens(s):
  s = _ascii_fold(s).lower()
  return [t for t in regex.findall(r"[a-z0-9\^_]+", s) if t]


def _content_tokens(s):
  return [t for t in _tokens(s) if t not in _STOP and len(t) > 1]


@functools.lru_cache(maxsize=4096)
def _pivot_cached(text, source_language, dest_language, translator):
  import time

  from doc_curation.translation import translate

  last = None
  for attempt in range(3):
    try:
      return translate(
        text, source_language=source_language, dest_language=dest_language,
        translator=translator,
      )
    except Exception as e:  # transient scrape/connection flakes
      last = e
      logging.debug("pivot attempt %d failed: %s", attempt + 1, e)
      time.sleep(1.5 * (attempt + 1))
  raise last


def _pivot_english(sa_text, source_language="sa", dest_language="en",
                   translator="google", use_pivot=True):
  if not use_pivot or not sa_text or not sa_text.strip():
    return ""
  try:
    out = _pivot_cached(
      sa_text.strip(), source_language, dest_language, translator
    )
    return out if isinstance(out, str) else ""
  except Exception as e:  # offline / unsupported pair → local-only matching
    logging.debug("pivot translate failed, using local match: %s", e)
    return ""


def _norm_sa_for_match(sa_text):
  """Normalize sandhi-split विश्वास form for matching (output unaffected).

  Strips ``+++n+++`` markers, leading ``>`` quote marks and the hyphens
  used to split compounds (``सर्व-शक्तिर्`` → ``सर्वशक्तिर्``), then
  collapses whitespace.  The verbatim sentence is still what gets
  returned/compared; this only feeds pivot/transliteration features.
  """
  t = sa_text or ""
  t = regex.sub(r"\+\+\+.*?\+\+\+", " ", t)
  t = regex.sub(r"(?m)^\s*>\s*", "", t)
  t = regex.sub(r"(?<=[\u0900-\u097F])-(?=[\u0900-\u097F\s])", "", t)
  t = regex.sub(r"(?<=\s)-(?=[\u0900-\u097F])", "", t)
  return regex.sub(r"\s+", " ", t).strip()


_DEV_DIGITS = {c: str(i) for i, c in enumerate("०१२३४५६७८९")}
_ROMAN = (
  ("viii", 8), ("vii", 7), ("xii", 12), ("xiii", 13), ("xiv", 14),
  ("xix", 19), ("xvi", 16), ("xii", 12), ("iv", 4), ("ix", 9), ("vi", 6),
  ("xii", 12), ("xi", 11), ("xv", 15), ("xx", 20), ("x", 10), ("v", 5),
  ("iii", 3), ("ii", 2), ("i", 1),
)

_SA_WORK = (
  ("तैत्तिरीय", "taitt"), ("तै", "taitt"), ("बृ", "brh"), ("छा", "chand"),
  ("खा", "chand"), ("श्वे", "svet"), ("कौ", "kaus"), ("मु", "mund"),
  ("के", "kena"), ("कठ", "katha"), ("क", "katha"), ("प्रश्न", "prasna"),
  ("प्र", "prasna"), ("शत", "satap"), ("गीता", "gita"), ("भगवद्गीता", "gita"),
  ("भ", "gita"), ("ऋ", "rgv"), ("सू", "sutra"), ("उ", "up"),
  ("ब्रा", "brahma"), ("आ", "ar"),
)

_EN_WORK = (
  ("taitt", "taitt"), ("tait", "taitt"), ("brh", "brh"), ("br", "brh"),
  ("chand", "chand"), ("khand", "chand"), ("ch", "chand"), ("kh", "chand"),
  ("svet", "svet"), ("sve", "svet"), ("sv", "svet"), ("kaus", "kaus"),
  ("kau", "kaus"), ("mund", "mund"), ("mun", "mund"), ("mu", "mund"),
  ("kena", "kena"), ("ke", "kena"), ("katha", "katha"), ("kat", "katha"),
  (("ka",), "katha"), ("prasna", "prasna"), ("pra", "prasna"),
  ("satap", "satap"), ("sat", "satap"), ("gita", "gita"), ("bha", "gita"),
  ("rgv", "rgv"), ("rk", "rgv"), ("sutra", "sutra"), ("su", "sutra"),
  ("up", "up"), ("ar", "ar"), ("samh", "rgv"), ("sam", "rgv"),
  ("brahma", "brahma"), ("ved", "sutra"),
)


def _roman_to_int(tok):
  t = tok.lower()
  for pat, val in _ROMAN:
    if t == pat:
      return val
  return None


def _canon_work_sa(first):
  f = first.replace(".", "").strip()
  for pat, canon in _SA_WORK:
    if f.startswith(pat):
      return canon
  return None


def _canon_work_en(tok):
  t = _ascii_fold(tok).lower().rstrip(".")
  for pat, canon in _EN_WORK:
    if isinstance(pat, tuple):
      if t in pat:
        return canon
    elif t.startswith(pat):
      return canon
  return None


def _refs_sa(sa_text):
  """Canonical scripture refs from Sanskrit: {(work, num-tuple)}."""
  refs = set()
  t = _norm_sa_for_match(sa_text)
  for m in regex.finditer(r"\(([^()]*)\)", t):
    inside = m.group(1)
    if not regex.search(r"[उसू\.।]", inside):
      continue
    subtoks = [x for x in regex.split(r"[\s।,\.]+", inside) if x]
    if not subtoks:
      continue
    work = _canon_work_sa(subtoks[0])
    nums = tuple(
      int("".join(_DEV_DIGITS.get(c, c) for c in tok))
      for tok in subtoks[1:]
      if regex.fullmatch(r"[०-९0-9]+", tok)
    )
    # Dash-separated ranges like १२ - १९ keep both ends.
    if work and nums:
      refs.add((work, nums))
    elif work and regex.search(r"सू", inside):
      refs.add((work, ()))
  for m in regex.finditer(r"॥\s*([०-९0-9]+(?:\s*[–—\-]\s*[०-९0-9]+)?)\s*॥", t):
    nums = tuple(
      int("".join(_DEV_DIGITS.get(c, c) for c in tok))
      for tok in regex.findall(r"[०-९0-9]+", m.group(1))
    )
    if nums:
      refs.add(("sutra-no", nums))
  return refs


def _refs_en(en_sent):
  """Canonical scripture refs from English: {(work, num-tuple)}."""
  refs = set()
  for m in regex.finditer(r"\(([^()]*)\)", en_sent):
    inside = m.group(1)
    parts = [x for x in regex.split(r"[\s,;:\.]+", inside) if x]
    if not parts:
      continue
    work = None
    nums = []
    for tok in parts:
      if work is None:
        w = _canon_work_en(tok)
        if w is not None:
          work = w
          continue
      v = _roman_to_int(tok)
      if v is not None:
        nums.append(v)
        continue
      if regex.fullmatch(r"\d+", tok):
        nums.append(int(tok))
    if work and nums:
      refs.add((work, tuple(nums)))
    elif work and regex.search(r"(?i)sutra|ved", inside):
      refs.add((work, ()))
    elif nums and len(nums) >= 2 and regex.search(r"(?i)up|sutra|brah", inside):
      refs.add(("up", tuple(nums)))
  # Bare sūtra cross-refs like "(I, 10)", "(I, 1, 22)".
  for m in regex.finditer(r"\(\s*([IVXivx]+|\d+)\s*,\s*(\d+)(?:\s*,\s*(\d+))?\s*\)", en_sent):
    a = m.group(1)
    v = _roman_to_int(a)
    first = v if v is not None else (int(a) if a.isdigit() else None)
    if first is None:
      continue
    rest = [int(m.group(2))]
    if m.group(3):
      rest.append(int(m.group(3)))
    refs.add(("sutra-no", tuple([first] + rest)))
    refs.add(("up", tuple([first] + rest)))
  for m in regex.finditer(r"(?:S[ūu]tra)\s+([IVXivx\d]+)(?:\s*,\s*(\d+))?(?:\s*,\s*(\d+))?", en_sent):
    nums = []
    for g in m.groups():
      if not g:
        continue
      v = _roman_to_int(g)
      nums.append(v if v is not None else int(g) if g.isdigit() else None)
    nums = [x for x in nums if x is not None]
    if nums:
      refs.add(("sutra-no", tuple(nums)))
  m2 = regex.match(r"(\d{1,3})\.\s", en_sent)
  if m2:
    refs.add(("sutra-no", (int(m2.group(1)),)))
  return refs


# Small Sanskrit→English gloss lexicon for recurrent bhāṣya vocabulary.
# Lets local matching see paraphrases MT would otherwise provide
# (translators lib is often unavailable offline): e.g. SA
# गतिसामान्योपन्यासेन ↔ EN "uniformity of view".  Substring match on
# normalized (de-hyphenated) Sanskrit; English side uses content tokens.
_GLOSS = (
  ("संशय", {"doubt"}),
  ("पूर्वपक्ष", {"purvapakshin", "former", "view", "maintains"}),
  ("सिद्धान्त", {"established", "conclusion", "settled"}),
  ("उच्यते", {"reply", "rejoin", "say", "said"}),
  ("ब्रूम", {"reply", "say"}),
  ("परिहार", {"refute", "invalidate", "reply", "objection"}),
  ("आक्षिप", {"object", "raise", "modest"}),
  ("आक्षेप", {"objection"}),
  ("ननु", {"objection", "opponent", "asked", "said"}),
  ("चेत्", {"if", "objected", "said"}),
  ("किम्", {"what", "whether"}),
  ("कुतः", {"why", "whence", "reason"}),
  ("कथम्", {"how"}),
  ("कथं", {"how"}),
  ("तस्मात्", {"therefore", "hence", "thus"}),
  ("अतः", {"hence", "therefore", "thus"}),
  ("तथा", {"thus", "so", "like"}),
  ("यथा", {"just", "like", "according"}),
  ("एवम्", {"thus", "accordingly"}),
  ("अपि च", {"moreover", "further", "also"}),
  ("किञ्च", {"moreover", "further"}),
  ("ब्रह्म", {"brahman"}),
  ("परमात्म", {"highest", "self"}),
  ("ईश्वर", {"lord"}),
  ("भगव", {"lord", "blessed"}),
  ("कारण", {"cause"}),
  ("जन्म", {"origin", "birth"}),
  ("स्थिति", {"subsistence"}),
  ("लय", {"dissolution"}),
  ("उत्पत्ति", {"origin", "creation"}),
  ("सृष्टि", {"creation", "emitted"}),
  ("ज्ञान", {"knowledge", "knows", "cognition"}),
  ("अज्ञान", {"nescience", "ignorance"}),
  ("अविद्या", {"nescience", "ignorance"}),
  ("विद्या", {"knowledge"}),
  ("उपास", {"devotion", "meditation", "worship"}),
  ("भक्ति", {"devotion"}),
  ("आनन्द", {"bliss", "delight"}),
  ("रस", {"flavour", "flavor"}),
  ("मोक्ष", {"release", "emancipation", "freedom"}),
  ("मुक्ति", {"release", "emancipation", "freedom"}),
  ("संसार", {"transmigrat", "worldly", "soul"}),
  ("जीव", {"soul", "individual"}),
  ("शरीर", {"body"}),
  ("इन्द्रिय", {"sense", "organ"}),
  ("प्राण", {"breath", "vital", "air"}),
  ("वायु", {"wind", "air"}),
  ("आकाश", {"ether", "akasa"}),
  ("ज्योति", {"light"}),
  ("अन्तर्", {"within", "inner", "inside"}),
  ("सर्वज्ञ", {"all-knowing", "omniscient"}),
  ("सर्वशक्ति", {"all-powerful", "omnipotent"}),
  ("सर्वव्यापि", {"all-pervading", "omnipresent"}),
  ("नित्य", {"eternal", "permanent"}),
  ("अमृत", {"immortal", "immortality"}),
  ("अभय", {"fearless", "fear"}),
  ("पाप्म", {"evil", "sin"}),
  ("श्रुति", {"scripture", "scriptural", "text"}),
  ("स्मृति", {"smriti", "tradition"}),
  ("सूत्र", {"sutra"}),
  ("वाक्य", {"passage", "sentence", "text"}),
  ("अर्थ", {"meaning", "matter", "sense"}),
  ("लिङ्ग", {"mark", "sign", "indication"}),
  ("लक्षण", {"characteristic", "category"}),
  ("गति", {"view", "meaning", "course"}),
  ("सामान्य", {"uniformity", "general", "common"}),
  ("विशेष", {"distinct", "special", "quality"}),
  ("गुण", {"quality", "attribute"}),
  ("उपाधि", {"limiting", "condition", "adjunct"}),
  ("अवयव", {"member", "limb", "part"}),
  ("पुच्छ", {"tail"}),
  ("प्रतिष्ठा", {"support", "rest"}),
  ("अभ्यास", {"repetition", "repeated"}),
  ("प्राचुर्य", {"abundance", "abundant"}),
  ("विकार", {"modification", "product", "effect"}),
  ("प्रधान", {"pradhana", "principal"}),
  ("अचेतन", {"non-intelligent", "insentient"}),
  ("चेतन", {"intelligent", "sentient"}),
  ("सगुण", {"qualified", "qualities"}),
  ("निर्गुण", {"devoid", "absolute"}),
  ("निर्विशेष", {"devoid", "absolute"}),
  ("सविशेष", {"distinguished", "qualified"}),
  ("माया", {"maya", "illusory", "illusive"}),
  ("कर्म", {"work", "action", "deed"}),
  ("फल", {"fruit", "result", "reward"}),
  ("भय", {"fear"}),
  ("दुःख", {"pain", "suffering"}),
  ("सुख", {"pleasure", "bliss"}),
  ("एक", {"one", "same"}),
  ("अन्य", {"other", "different", "another"}),
  ("सर्व", {"all", "every"}),
  ("द्वि", {"two"}),
  ("त्रि", {"three"}),
  ("रूप", {"form", "nature"}),
  ("नाम", {"name", "called"}),
  ("प्रश्न", {"question"}),
  ("उत्तर", {"answer", "reply", "later"}),
  ("आदि", {"beginning", "rest", "etc"}),
  ("सूत्र", {"sutra"}),
  ("ग्रन्थ", {"part", "book", "work"}),
  ("उत्थान", {"occasion", "arise"}),
  ("विषय", {"object", "topic", "matter"}),
  ("व्याख्या", {"explained", "interpretation"}),
  ("प्रतिपाद", {"prove", "show", "declare", "establish"}),
  ("सिद्ध", {"established", "proved", "settled", "conclusion"}),
  ("युक्त", {"right", "proper", "appropriate"}),
  ("शक्य", {"possible"}),
  ("नित्य", {"eternal", "permanent"}),
  ("सत्य", {"true", "real", "existence"}),
  ("अनन्त", {"infinite", "endless"}),
  ("आत्म", {"self", "soul"}),
  ("देवता", {"god", "divinity", "deity"}),
  ("मनुष्य", {"man", "human"}),
  ("लोक", {"world", "people"}),
  ("अग्नि", {"fire"}),
  ("आदित्य", {"sun"}),
  ("चक्षुस्", {"eye"}),
  ("चक्षुष्", {"eye"}),
  ("हिरण्मय", {"golden", "gold"}),
  ("पाद", {"foot", "feet", "quarter"}),
)


def _gloss_bonus(sa_norm, en_tokset):
  bonus = 0.0
  for substr, kws in _GLOSS:
    if substr in sa_norm:
      hit = len(kws & en_tokset)
      if hit:
        bonus += 0.18 * hit
        if bonus >= 0.9:
          break
  return min(0.9, bonus)


def _translit_tokens(sa_text):
  try:
    from indic_transliteration import sanscript
    for scheme in (sanscript.SLP1, sanscript.HK, sanscript.IAST):
      try:
        return _tokens(
          sanscript.transliterate(sa_text, sanscript.DEVANAGARI, scheme)
        )
      except Exception:
        continue
  except Exception:
    pass
  return []


def _sim(pivot_en, sa_text, en_sent):
  """Combined similarity (pivot + tokens + transliteration + ref anchors)."""
  sa_n = _norm_sa_for_match(sa_text)
  en_l = en_sent.lower()
  score = 0.0
  if pivot_en:
    score += 0.55 * SequenceMatcher(
      None, pivot_en.lower()[:600], en_l[:600]
    ).ratio()
  a = set(_content_tokens(sa_n)) if regex.search(r"[\u0900-\u097F]", sa_text) else set(_content_tokens(pivot_en))
  b = set(_content_tokens(en_sent))
  if a and b:
    inter = len(a & b)
    # Jaccard-ish with recall bias toward short EN sentences.
    score += 0.45 * (2 * inter / max(1, len(a) + len(b)))
  tr = set(_translit_tokens(sa_n)) if regex.search(r"[\u0900-\u097F]", sa_text) else set()
  if tr and b:
    tb = set(_ascii_fold(" ".join(b)).split())
    inter = len({t for t in tr if len(t) > 3} & {t for t in tb if len(t) > 3})
    score += 0.35 * (inter / max(1, min(len(tr), len(tb))))
  # Domain-gloss bonus: recurrent bhāṣya paraphrases (doubt, uniformity…).
  try:
    score += _gloss_bonus(sa_n, set(_tokens(en_sent)))
  except Exception:
    pass
  # Transliteration substring bonus for glued compounds (sūtra quotes).
  try:
    score += _substr_bonus(sa_text, en_sent)
  except Exception:
    pass
  # Scripture-reference anchors (strong): (तै. उ. २।७।१) ↔ (Taitt. Up. II, 7).
  try:
    if _refs_sa(sa_text) & _refs_en(en_sent):
      score += 1.2
  except Exception:
    pass
  # Number anchors (sūtra numbers, "II, 7", fn markers); SA digits are
  # Devanagari, so fold them to ASCII first.
  nums_a = set(regex.findall(
    r"\d+", "".join(_DEV_DIGITS.get(c, c) for c in (sa_n + " " + (pivot_en or "")))))
  nums_b = set(regex.findall(r"\d+|fn_\d+", en_sent.lower()))
  if nums_a & nums_b:
    score += 0.25
  fn = set(regex.findall(r"fn_\d+", en_sent.lower()))
  if fn and any(f in (pivot_en or "").lower() for f in fn):
    score += 0.3
  return score


def _fine_split_unit(unit):
  """One extra split for deficit-driven granularity (EN units < SA count).

  Returns [first, rest] split at the first safe point, else [unit].
  Priority: ";" + space, then "," + subordinating/relative conjunction.
  Coordinating "," + and/but/or is deliberately NOT split.
  """
  m = regex.search(r";\s+(?![\"'‘“\(\[]?[^ -~])", unit)
  if m:
    a, b = unit[:m.end()].strip(), unit[m.end():].strip()
    if a and b:
      return [a, b]
  m = regex.search(
    r",\s+(?=(?:which|whom|whose|where|when|since|because|although|though|while|whereas|if|as)\b)",
    unit, flags=regex.IGNORECASE)
  if m:
    cut = m.start() + 1  # keep "," with the first fragment
    a, b = unit[:cut].strip(), unit[cut:].strip()
    if a and b:
      return [a, b]
  return [unit]


def _close_deficit(en, deficit):
  """Split longest units first until the EN<SA deficit is closed."""
  en = list(en)
  target = deficit + max(2, len(en) // 20 + 1)  # small headroom for multis
  made = 0
  while made < target:
    best = -1
    for i, u in enumerate(en):
      if len(u) < 120:
        continue
      if len(_fine_split_unit(u)) == 2:
        if best == -1 or len(u) > len(en[best]):
          best = i
    if best == -1:
      break
    en[best:best + 1] = _fine_split_unit(en[best])
    made += 1
  return en


def _run_dp(n, m, sim, max_en_per_sa):
  """Monotonic partition; returns takes list (len n, sum m)."""
  density = m / max(1, n)
  if m >= n:
    max_k = min(max_en_per_sa, m - n + 1)
    min_k = 1
  else:
    max_k = 1
    min_k = 0
  max_k = max(1, max_k)

  NEG = float("-inf")
  # dp[i][j]: best score for first i SA covering first j EN.
  dp = [[NEG] * (m + 1) for _ in range(n + 1)]
  back = [[0] * (m + 1) for _ in range(n + 1)]
  dp[0][0] = 0.0
  for i in range(1, n + 1):
    for j in range(0, m + 1):
      best, bk = NEG, 0
      for k in range(min_k if not (m < n) else 0, min(max_k, j) + 1):
        if m >= n and k == 0:
          continue
        prev = dp[i - 1][j - k]
        if prev == NEG:
          continue
        g = 0.0
        if k:
          g = sum(sim[i - 1][jj] for jj in range(j - k, j)) - 0.08 * (k - 1)
          # Density prior: break score ties toward the expected group
          # size instead of piling empties/leftovers at the edges.
          g += 1e-3 * (1.0 - abs(k - density) / max(1.0, density))
        val = prev + g
        if val > best:
          best, bk = val, k
      # Allow trailing empties only when EN < SA.
      if m < n and j <= m and dp[i - 1][j] != NEG:
        if dp[i - 1][j] > best:
          best, bk = dp[i - 1][j], 0
      dp[i][j] = best
      back[i][j] = bk

  if dp[n][m] == NEG:
    return None
  # Backtrack.
  takes = [0] * n
  j = m
  for i in range(n, 0, -1):
    k = back[i][j]
    takes[i - 1] = k
    j -= k
  # Any leftover EN (rounding) goes to the first non-empty group.
  if j > 0:
    for i in range(n):
      if takes[i] > 0:
        takes[i] += j
        break
    else:
      takes[-1] = j
  return takes


def _split_sutra_heading(unit):
  """(23, rest) if unit is a sūtra heading like "23. For the same…", else None."""
  m = regex.match(r"(\d{1,3})\.\s+(.*)$", unit, flags=regex.DOTALL)
  return (int(m.group(1)), m.group(2)) if m else None


def _sa_sutra_no(sa_text):
  """Single sūtra number from ॥ N ॥, else None (ranges skipped)."""
  t = _norm_sa_for_match(sa_text)
  nums = []
  for m in regex.finditer(r"॥\s*([०-९0-9]+)\s*॥", t):
    nums.append(int("".join(_DEV_DIGITS.get(c, c) for c in m.group(1))))
  return nums[0] if len(nums) == 1 else None


def _is_sutra_sa(sa_text):
  """True if an SA block is/starts with sūtra text: short first sentence
  that is numbered (॥ N ॥) or a short quotation (sūtra quote)."""
  t = _norm_sa_for_match(sa_text)
  if _sa_sutra_no(t) is not None:
    return True
  first = regex.split(r"[।?!;]\s*", t, maxsplit=1)[0]
  if len(first.split()) <= 12 and regex.match(r"\s*[‘'\"“]", first):
    return True
  return False


def _substr_bonus(sa_text, en_sent):
  """Transliteration substring overlap for glued compounds.

  Token equality misses SA compounds (e.g. translit
  "akasastallingat" vs EN "akasa"); a long token containing the other
  still signals shared matter (sūtra quotes ↔ headings).
  """
  try:
    tr = set(_translit_tokens(_norm_sa_for_match(sa_text)))
    en = set(_tokens(en_sent))
  except Exception:
    return 0.0
  tr = {t for t in tr if len(t) > 4}
  en = {t for t in en if len(t) > 4 and t not in _STOP}
  if not tr or not en:
    return 0.0
  hit = 0
  for a in tr:
    for b in en:
      if a in b or b in a:
        hit += 1
        break
  return min(0.6, 0.2 * hit)


def sequentially_match_to_translation(texts, translation_text,
                                      source_language="sa",
                                      dest_language="en", translator="google",
                                      use_pivot=True, max_en_per_sa=10):
  """Align each Sanskrit sentence to a contiguous English span, in order.

  :param texts: list of Sanskrit sentences (e.g. from
    :func:`doc_curation.utils.sanskrit_helper.split_to_sentences`).
  :param translation_text: full English translation (e.g. concatenated
    Thibaut files, footnotes included).
  :return: list of translation strings, ``len == len(texts)``; each is
    the verbatim English sentence(s) joined with single spaces (``""``
    if no English remains, e.g. more SA than EN).  Footnote *markers*
    (``[^fn_N]``) stay inline; footnote *definitions*
    (``[^fn_N]: ...``) are excluded from the partition — look them up
    in ``translation_text`` by marker when building
    ``Translation - Notes`` blocks.
  """
  texts = list(texts or [])
  n = len(texts)
  if n == 0:
    return []
  units = _split_english_sentences(translation_text or "")
  # Footnote definitions ride along as metadata, not sequence positions.
  footnote_defs = {}
  en = []
  for u in units:
    m = regex.match(r"(\[\^fn_\d+\]):", u)
    if m:
      footnote_defs.setdefault(m.group(1), u)
    else:
      en.append(u)
  # Sūtra headings ("23. For the same reason…") are editorial labels, not
  # sequence content.  Pre-assign each to its sūtra SA: first by exact
  # ॥ N ॥ number, then leftovers in order (k-th unmatched heading ↔ k-th
  # unmatched sūtra-quote SA, e.g. file 08's number-less ‘आकाशस्तल्लिङ्गात्’).
  # Unmatched headings stay in the stream as sequential fallback.
  headings = []  # (num, unit, en_index)
  for j, u in enumerate(en):
    h = _split_sutra_heading(u)
    if h is not None and all(h[0] != n0 for n0, _, _ in headings):
      headings.append((h[0], u, j))
  attach = {}  # sa_idx -> heading unit text
  drop_j = set()
  if headings:
    used_h = set()
    for i, t in enumerate(texts):
      no = _sa_sutra_no(t)
      if no is None:
        continue
      for k, (num, u, j) in enumerate(headings):
        if num == no and k not in used_h:
          attach[i] = u
          used_h.add(k)
          drop_j.add(j)
          break
    left_h = [k for k in range(len(headings)) if k not in used_h]
    left_sa = [i for i, t in enumerate(texts)
               if i not in attach and _is_sutra_sa(t)]
    for k, i in zip(left_h, left_sa):
      attach[i] = headings[k][1]
      drop_j.add(headings[k][2])
  en = [u for j, u in enumerate(en) if j not in drop_j]
  m = len(en)

  # Adaptive granularity: when EN units < SA sentences, forced "" spans
  # are unavoidable, so split the longest EN units at safe clause
  # boundaries until counts balance (manual alignment splits the same
  # long Thibaut sentences).  Untouched when m >= n.
  if m < n:
    en = _close_deficit(en, n - m)
    m = len(en)

  def _sims(pivots):
    return [[_sim(pivots[i], texts[i], en[j]) for j in range(m)]
            for i in range(n)]

  # Pass 1: local signals only (zero API cost).
  sim = _sims([""] * n)
  takes = _run_dp(n, m, sim, max_en_per_sa)

  # Pass 2: pivot MT only for uncertain spans (empty takes or weak best
  # match), keeping API/token spend to a fraction of the file.
  if use_pivot:
    need = set()
    if takes is None:
      need = set(range(n))
    else:
      idx = 0
      for i, k in enumerate(takes):
        span = sim[i][idx:idx + k] if k else []
        row_best = max(sim[i]) if m else 0.0
        if k == 0 or (span and sum(span) / len(span) < 0.25) or row_best < 0.4:
          need.add(i)
        idx += k
    # Pivot the uncertain SAs plus immediate neighbours (boundary context).
    want = set()
    for i in need:
      want.update({max(0, i - 1), i, min(n - 1, i + 1)})
    pivots = [""] * n
    for i in sorted(want):
      pivots[i] = _pivot_english(
        _norm_sa_for_match(texts[i]), source_language, dest_language,
        translator, True)
    if any(pivots):
      sim = _sims(pivots)
      takes = _run_dp(n, m, sim, max_en_per_sa)

  if takes is None:
    logging.warning("matcher DP failed; falling back to even split")
    out, idx = [], 0
    for i in range(n):
      take = max(0, min(m - idx - (n - i - 1), max(1, round(m / max(1, n)))))
      span = " ".join(en[idx:idx + take])
      if i in attach:
        span = (attach[i] + " " + span).strip()
      out.append(span)
      idx += take
    while len(out) < n:
      out.append("")
    return out[:n]

  out, idx = [], 0
  for i, k in enumerate(takes):
    span = " ".join(en[idx:idx + k])
    if i in attach:
      span = (attach[i] + " " + span).strip()
    out.append(span)
    idx += k
  return out
