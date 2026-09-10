"""Hindi-vs-Sanskrit paragraph classifier for mixed-language texts.

Used e.g. by the divyaprabandha sa_hi splitter to group consecutive
same-language sentences into their own details blocks.
"""
import re


# ---------------------------------------------------------------------------
# Language scoring: Hindi (hai/mem/haim ...) vs Sanskrit (~N/iti/ity ...).
# Both Devanagari boundaries are required so that sandhi-glued Sanskrit
# (sarpoyam-iti) still counts while words like itihAsa do not, and Hindi
# जो/थे/वे do not match inside Sanskrit तेजो/दूरस्थे/भगवत्परत्वे.
# ---------------------------------------------------------------------------

# NOTE: ये/था/तो/यदि/हम are deliberately absent -- they collide with
# Sanskrit विषये, तथा/यथा/स्वस्था, ततो, यदि (yadi = "if") and
# visarga-dropped अहम्. पर is absent (Sanskrit पर); तथा likewise.
# का/के/की are safe (no Sanskrit standalone use); को stays out only via
# the singleton rule (Sanskrit कः), पर/सहित/विना stay out (Sanskrit words).
_HINDI_WORDS = (
  "है|हैं|थी|थे|होगा|होगी|में|ने|को|से|द्वारा|लिये|का|के|की|"
  "गया|गयी|गये|हुआ|हुई|हुए|रहा|रही|रहे|किया|किये|कहा|कहते|"
  "बताया|बताते|नहीं|कैसे|क्या|यह|वह|वे|इस|उस|इन|उन|जिन|जिस|"
  "अपनी|अपने|तुम|आप|लोग|वाला|वाली|वाले|और|क्योंकि|लेकिन|"
  "जब|तब|यहाँ|वहाँ|होता|होती|होते|करना|करें|करो|लो|भी|ही|जो"
)
_SANSKRIT_WORDS = (
  "इति|इत्य|इत्याह|चेत्|ननु|अत्र|तत्र|यत्र|तदा|यथा|कथम्|किम्|किमर्थम्|"
  "कुतः|तर्हि|यद्वा|अथवा|एवम्|एव|तद्|एतद्|अस्य|तस्य|एतस्य|भवति|"
  "भवेत्|उच्यते|आह|प्राह|उवाच|अवोचत्|अर्थः|इत्यर्थः|अतः|खलु|हि|"
  "तु|अपि|अस्ति|नास्ति"
)
# Sandhi-glued "-ित्य-" (इत्युक्तम्, इत्याह, ...) has no independent इ;
# it counts only mid-word before more Devanagari (नित्यता-style Hindi
# lookalikes are rare here).
_SANSKRIT_GLUED_RE = re.compile(r"ित्य(?=[\u0900-\u097F])")
# A lone weak hit (को/के/से ...) proves nothing; singletons only count
# when they are high-precision markers.
_STRONG_HINDI = {"है", "हैं", "में", "नहीं", "क्या"}
# Both sides need a left boundary too: without one, Hindi जो/थे/वे
# match inside Sanskrit तेजो/दूरस्थे/भगवत्परत्वे, and Sanskrit तु/हि
# match inside हेतु/चाहिए.
_HINDI_RE = re.compile(r"(?<![\u0900-\u097F])(?:%s)(?![\u0900-\u097F])" % _HINDI_WORDS)
_SANSKRIT_RE = re.compile(r"(?<![\u0900-\u097F])(?:%s)(?![\u0900-\u097F])" % _SANSKRIT_WORDS)


def score_paragraph(text):
  """Return (hindi_hits, sanskrit_hits) for a paragraph."""
  h = len(_HINDI_RE.findall(text))
  s = 2 * text.count("ऽ") + len(_SANSKRIT_RE.findall(text))
  return h, s


def classify_paragraph(text):
  """Classify a paragraph as hindi / sanskrit / unknown.

  Standalone hai/mem/haim-type words mark Hindi; ~N (avagraha) and
  iti/ity/cet-type words mark Sanskrit. Hyphenated line-breaks are
  rejoined for scoring only (so "त- \\n था" cannot fake a hit). Decisive
  majorities win either way; near-ties (ratio below 1.5) stay unknown
  so that neighbouring sentences (continuity) decide -- a near-tie
  inside commentary is usually shared vocabulary (एवं/तथा-style
  lookalikes) or a long embedded quote, not a switch.
  Lone weak hits (को/के/से ...) stay unknown.
  """
  joined = re.sub(r"-\s*\n\s*", "", text)
  h_list = _HINDI_RE.findall(joined)
  h = len(h_list)
  s = 2 * joined.count("ऽ") + len(_SANSKRIT_RE.findall(joined)) + len(
    _SANSKRIT_GLUED_RE.findall(joined))
  if h >= 2 and (s == 0 or h / s >= 1.5):
    return "hindi"
  if s >= 1 and (h == 0 or s / h >= 1.5):
    return "sanskrit"
  if h == 1 and s == 0 and h_list[0] in _STRONG_HINDI:
    return "hindi"
  return "unknown"
