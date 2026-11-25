"""Reconcile, segment, and align Uvaṭa and Mahīdhara bhāṣyas onto VS Mādhyandina Markdown."""

from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict
from dataclasses import dataclass, field

import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader import cross_recension, interleave_aligner, interleave_helper

STATIC_SAMHITA_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/Rk"
)
CONTENT_SAMHITA_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA"
)

UVATA_TIKA_SUMMARY = "उवट-टीका"
MAHIDHARA_TIKA_SUMMARY = "महीधर-टीका"
UVATA_VINIYOGA_SUMMARY = "उवटः - विनियोगः"
MAHIDHARA_VINIYOGA_SUMMARY = "महीधरः - विनियोगः"
UVATA_AVATARIKA_SUMMARY = "उवटः - अवतारिका"
MAHIDHARA_AVATARIKA_SUMMARY = "महीधरः - अवतारिका"
SARVA_AVATARIKAH_SUMMARY = "सर्वा अवतारिकाः"

MANAGED_SUMMARIES = frozenset({
  "महीधरः",
  "उवटः",
  UVATA_TIKA_SUMMARY,
  MAHIDHARA_TIKA_SUMMARY,
  UVATA_VINIYOGA_SUMMARY,
  MAHIDHARA_VINIYOGA_SUMMARY,
  UVATA_AVATARIKA_SUMMARY,
  MAHIDHARA_AVATARIKA_SUMMARY,
  SARVA_AVATARIKAH_SUMMARY,
})

_ACCENT_STRIP_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff\u093c\u0903\u200c\u200d᳓᳙]")
_ANUSVARA_NORM_RE = regex.compile(r"[ँंᳪ᳭]")

_WIKISOURCE_COLOPHON_RE = regex.compile(
  r"(?:\s*इति\s+(?:उवटकृतौ\s+मन्त्रभाष्य(?:े|\s)|माध्यन्दिनीयायां\s+वाजसने[यव]ि?संहितायां)[^\n]*)+"
)
_MAHIDHARA_CHAPTER_VERSE_RE = regex.compile(
  r"(?:(?:श्रीमन्महीधरकृते|महीधरकृते)\s+वेददीपे[^\n]*|इति\s+(?:प्रथमा|द्वितीया|तृतीया|चतुर्थी)\s+चितिः\s+पूर्णा\s*॥?|अध्यायः\s+[^\n]*ईरितः[^\n]*|समाप्तोऽ?यं\s+ग्रन्थः[।.\s]*)"
)
# Match Devanagari word characters (letters + vowel matras + anusvara/visarga/nukta, excluding digits/dandas)
_DEV_ORD_WORD = r"[\u0900-\u0963]+"
_ORDINAL_SUFFIX = r"(?:प्रथमा|द्वितीया|तृतीया|चतुर्थी|" + _DEV_ORD_WORD + r"(?:मी|शी|ती|वी|नी|थी|ठी|मा|था|म्नी))"
_ORDINAL_LINE_RE = regex.compile(
  rf"(?m)^\s*(?:\[\d+\]\s*)?(?:तत्र\s+)?{_ORDINAL_SUFFIX}[।.\s]*$"
)
_LEADING_TATHA_ORD_RE = regex.compile(
  r"^\s*(?:तत्र\s+)?प्रथमा[।.\s]+(?:द्वितीया[।.\s]+)?|^\s*द्वितीया[।.\s]+"
)
_TRAILING_ORD_TOKEN_RE = regex.compile(
  rf"(?:[\s।॥]+(?:\[\d+\]\s*)?(?:तत्र\s+)?{_ORDINAL_SUFFIX}[।.\s]*)+$"
)
_END_VERSE_NUM_RE = regex.compile(r"॥\s*([०-९0-9]+(?:\.[०-९0-9]+)?)\s*॥\s*$")
_MULTI_END_RE = regex.compile(
  r"(?:॥\s*([०-९]+)\s*॥(?:[\s॥]*[०-९]+\s*॥)+|॥\s*([०-९]+)\s*[-–]\s*([०-९]+)\s*॥)[।.\s]*$"
)
_LEADING_MULTI_RE = regex.compile(r"^॥\s*([०-९]+)\s*॥(?:[\s॥]*[०-९]+\s*॥)+")
_MID_KANDIKA_SPLIT_RE = regex.compile(
  r"(?:॥\s*([०-९0-9]+(?:\.[०-९0-9]+)?)\s*॥?|(?<=[\s।])\b([०-९]{1,3})\b)\s*(?=\n|[‘'अ-ह])"
)

_KAT_SPLIT_IN_SEG_RE = regex.compile(
  r"(?=(?:कात्यायनः(?:\s*[-–—:]+\s*|\s+)?)?['‘“\"][^'‘’\"“”\n]{6,}?['’”\"]\s*(?:\([^)\n]{2,40}\))?(?:\s*इति\s*)?)"
)

_NOT_VINIYOGA_RE = regex.compile(
  r"विनियोगो\s+नास्ति"
  r"|श्रौते\s+विनियोगो\s+नास्ति"
  r"|कर्मसु\s+विनियोगो\s+नास्ति"
  r"|इति\s+(?:श्रुतेः|कात्यायनोक्तेः|यास्कः|निघ|निरु|स्मृतेः|ब्राह्मणम्|तित्तिरिवचनात्)"
  r"|तदुक्तं\s+तित्तिरिणा|तित्तिरिणा\s*['‘ऽ]"
  r"|\(\s*(?:पा|उ|निघ|निरु|अनु|श०\s*ब्रा०)[०.\s]"
  r"|अध्याहर्तव्य"
  r"|इति\s+क्रियापदम"
  r"|प्रत्यय|लट्|लिट्|लुङ्|लोट्|लङ्|विधिलिङ्"
  r"|विभक्तिव्यत्यय|पुरुषव्यत्यय|वचनव्यत्यय"
  r"|बहुव्रीहि|तत्पुरुष|कर्मधारय|समास"
)
_KAT_REF_RE = regex.compile(
  r"\(\s*का(?:त्या|श्रौ|०\s*श्रौ)?[०.]\s*[०-९0-9]"
  r"|\(\s*[०-९0-9]+[।.]\s*[०-९0-9]+[।.]\s*[०-९0-9]+\s*\)"
  r"|कात्यायनः(?:\s*[-–—:]+\s*|\s+)['‘“\"]"
  r"|तत्र\s+कात्यायनः"
)
_EXPLICIT_VINIYOGA_RE = regex.compile(
  r"(?<!नास्ति\s)विनियुज्यते|विनियुक्त[ःाःौै]?|विनियोगः|कर्मसु\s+विनियोग"
)
_RITUAL_VERB_RE = regex.compile(
  r"(?:"
  r"\b(?:जुहोति|जुहुयात्|गृह्णाति|गृह्णीयात्|जपति|वाचयति|प्रोक्षति|अभ्युक्षति|संनह्यति|परिदधाति"
  r"|प्राश्नाति|भक्षयति|प्रणयति|अवतरति|खनति|प्रहरति|निनयति|निषिञ्चति|निवपति|निदधाति"
  r"|सादयति|संमृष्टे|वपति|उपास्ते|प्रतिगृह्णाति|व्याघारयति|स्तृणाति|परिधत्ते|परिधापयति"
  r"|उत्सृजति|निर्मन्थति|प्रदक्षिणीकरोति|संप्रेष्यति|अभ्यनक्ति|संमार्ष्टि|निर्मार्ष्टि|प्रयाति|क्रमते)\b"
  r"|[उुो]प(?:तिष्ठते|तिष्ठन्ते|दधाति|दध्यात्|गूहति|स्पृशति|विशति)|उपाकरोति"
  r"|(?:अ|ा)(?:भिमन्त्रयते|भिषिञ्चति|नुमन्त्रयते|नुवीक्षते|वजिघ्रति|वरोहति)"
  r"|(?:^|[\s।॥मत्नयव])(?:आदत्ते|आदधाति|आरोहति|आलभते|आसजति|आचरति|आसिञ्चति|आनक्ति)"
  r"|प्रवेशयन्\s*वाचयति"
  r")"
)
_GLOSS_EQ_RE = regex.compile(
  r"इत्यर्थः|इति\s+भावः|इति\s+शेषः|इति\s+मन्त्रार्थः"
  r"|हे\s+\S+,|उच्यते|नाम\s|समासान्त|तस्यार्थः|संबन्धः"
  r"|(?:गायत्री|त्रिष्टुप्|जगती|बृहती|पङ्क्तिः|अनुष्टुप्|उष्णिक्|विराट्|अतिजगती|अतिशक्वरी|अत्यष्टिः)।"
)
_AVATARIKA_RE = regex.compile(
  r"(?:"
  r"इतः\s*पर[ंम्]|इत\s*उत्तर[ंम्]|इतौत्तर[ंम्]|अतः\s*पर[ंम्]|अतोऽनन्तर[ंम्]"
  r"|(?:[\u0900-\u0963]+ऽ?ध्याय(?:े|ैः|ेन))\s+[^\n।]{0,80}(?:प्रोक्त|उच्यन्ते|वक्ष्यते|निरूपित|कथित)"
  r"|इदानीं\s+[^\n।]{5,90}(?:निरूप्यते|प्रस्तूयते|उच्यते|कथ्यते)"
  r"|समाप्तं\s+कर्मकाण्ड|अस्मिन्[^\n]{0,20}ध्याये"
  r"|एवं\s+.{2,50}\s*(?:स्तुत्वा|उक्त्वा|निरूप्य).{0,30}(?:इदानीं|अथ|अधुना)"
  r"|अथ\s+(?:प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|षष्ठ|सप्तम|अष्टम|नवम|दशम|एकादश|द्वादश)[ःं]।"
  r"|अथातः\s+|अत\s+आर्ष|अत्राध्याये|तत्र\s+(?:चतस्रः|तिस्रः|द्वे|पञ्च|षट्|सप्त)"
  r"|आग्निष्टोमिका\s+मन्त्रा|आग्निकोऽध्यायः|पञ्चाध्यायी\s+आथर्वणेन"
  r"|द्वितीयां\s+चितिं|प्रथमा\s+चितिः|चतुर्थी\s+चितिः"
  r"|(?:मन्त्रेण|ऋचा|यजुषा|प्रार्थनया|उत्तरेण|अनेन)\s+[^\n।]{2,55}(?:स्तुतिः|स्तौति|स्तुवते|आह|प्रार्थयते|दर्शयति|निरूप्यते)[।॥]?\s*$"
  r"|[^\n।]{4,55}(?:मन्त्रा\s+उच्यन्ते|मन्त्रैर्.*स्तौति)[।॥]?\s*$"
  r")"
)
_UPODGHATA_U_END_RE = regex.compile(r"तत्र\s+इषे\s+त्वा\s+द्विपदो\s+मन्त्रः")
_UPODGHATA_M_END_RE = regex.compile(r"अथ\s+मन्त्रार्थः\s+क्रियापदाध्याहारेण")
_SECOND_PASS_RE = regex.compile(r"^\s*अथ\s+व्याकरणप्रक्रिया\b")


def dev_to_int(token: str) -> int | None:
  """Convert a Devanagari or ASCII integer string cleanly."""
  cleaned = token.strip().replace(".", "")
  if cleaned in {"३.१", "3.1"} and "." in token:
    # Known OCR typo for ३१ in U(18,30) tail.
    return 31
  tr = sanscript.transliterate(cleaned, sanscript.DEVANAGARI, sanscript.IAST)
  return int(tr) if tr.isdigit() else None


def normalize_for_matching(text: str) -> str:
  """Normalize Devanagari text for accent/anusvāra-insensitive matching."""
  text = _ACCENT_STRIP_RE.sub("", text)
  text = _ANUSVARA_NORM_RE.sub("न", text)
  text = regex.sub(r"[।॥०-९0-9.,;:!?\"'‘’“”()\[\]\-–—\n]+", " ", text)
  return regex.sub(r"\s+", " ", text).strip()


_PRATIKA_STOPWORDS = frozenset({
  "त्वा", "ते", "मे", "नः", "वः", "स्थ", "असि", "अस्ति", "सन्तु", "भवतु", "स्वाहा", "च", "वा",
  "हि", "नु", "उ", "इत्", "अथ", "तत्", "यत्", "ये", "या", "यः", "सः", "अयं", "इदं", "मा",
})


def _content_words(norm_text: str) -> list[str]:
  return [w for w in norm_text.split() if len(w) >= 3 and w not in _PRATIKA_STOPWORDS]


def pratika_overlap_score(comm: str, mula: str) -> float:
  """Score whole-word & sandhi-compound overlap between commentary body and a mantra's mūlam."""
  m_norm = normalize_for_matching(mula)
  m_words = _content_words(m_norm)
  if not m_words:
    m_words = [w for w in m_norm.split() if len(w) >= 3]
  if not m_words:
    return 0.0
  targets = list(dict.fromkeys(m_words[:14]))
  c_norm = normalize_for_matching(comm)
  c_words = set(c_norm.split())
  c_long_words = [cw for cw in _content_words(c_norm) if len(cw) >= 5]
  hits = 0.0
  for w in targets:
    if w in c_words:
      hits += 1.0
    elif len(w) >= 6 and w in c_norm:
      hits += 0.85
    elif len(w) >= 6 and any(cw.startswith(w[:5]) for cw in c_words):
      hits += 0.55
    elif len(w) >= 6 and any(cw in w or (len(cw) >= 6 and cw[:5] in w) for cw in c_long_words):
      hits += 0.65
  return hits / len(targets)


def clean_commentary_boilerplate(text: str, *, keep_vedadipa_colophon: bool = True) -> str:
  """Clean Wikisource artifacts, author tags, and bare ordinal labels from commentary."""
  if not text:
    return ""
  t = text.strip()
  # Strip repeated author prefix at paragraph starts
  t = regex.sub(r"(?m)^(?:उ|मा?)[०।.]+\s*", "", t)
  t = regex.sub(r"^(?:उ|मा?)[०।.]*\s+(?=[‘'अ-ह])", "", t)
  # Strip Wikisource chapter colophons (always before optional Mahīdhara signature verse)
  if keep_vedadipa_colophon:
    t = _WIKISOURCE_COLOPHON_RE.sub("", t)
  else:
    t = _WIKISOURCE_COLOPHON_RE.sub("", t)
    t = _MAHIDHARA_CHAPTER_VERSE_RE.sub("", t)
  t = _LEADING_TATHA_ORD_RE.sub("", t)
  t = _ORDINAL_LINE_RE.sub("", t)
  t = _TRAILING_ORD_TOKEN_RE.sub("", t)
  # Normalize blank lines
  t = regex.sub(r"\n{3,}", "\n\n", t).strip()
  # Reject empty / number-and-danda-only shells (e.g. `॥ ३२॥ ३३॥ ३४॥`)
  if not regex.search(r"[अ-ह]", t):
    return ""
  return t


def _strip_end_number_for_split(text: str) -> str:
  """Clean stray ordinal artifacts from split commentary pieces."""
  t = clean_commentary_boilerplate(text)
  return regex.sub(r"\s+", " ", t).strip() if "\n\n" not in t else t


def _extract_last_end_number(text: str) -> int | None:
  """Return verse number from trailing `॥ N॥` or standalone terminal Devanagari number."""
  tail = _WIKISOURCE_COLOPHON_RE.sub("", text.strip())
  tail = _ORDINAL_LINE_RE.sub("", tail).strip()
  tail = _TRAILING_ORD_TOKEN_RE.sub("", tail).strip()
  m = _END_VERSE_NUM_RE.search(tail)
  if m:
    raw = m.group(1)
    if raw == "३.१":
      return 31
    return dev_to_int(raw)
  m2 = regex.search(r"(?<=\s)([०-९]{1,3})\s*$", tail)
  if m2:
    return dev_to_int(m2.group(1))
  return None


def _split_cross_author_leaks(
  u_raw: dict[tuple[int, int], str],
  m_raw: dict[tuple[int, int], str],
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
  """Separate `\\nम...` leaked into Uvaṭa and `\\nउ...` leaked into Mahīdhara."""
  u_out = dict(u_raw)
  m_out = dict(m_raw)

  # 1) U -> M leaks: `\nम[।.०]` OR inline `॥ N॥ म[०।] ` OR `मा०` (`19.48`) OR `24.24` (`\nम त्रयाणां...`)
  u_leak_re = regex.compile(
    r"(?:(?:\n|^)\s*|(?<=॥\s*[०-९]{1,3}\s*॥\s*))(?=म(?:[।.०]\s*|\s+त्रयाणां)|मा[।.०]\s+)"
  )
  for key, text in list(u_out.items()):
    parts = u_leak_re.split(text, maxsplit=1)
    if len(parts) == 2:
      u_part, m_part = parts[0].strip(), parts[1].strip()
      if key == (22, 27) and "आग्नये" in u_part and "आग्नये" in m_part:
        u_out[key] = u_part
        m_out.setdefault(key, m_part)
        continue
      u_out[key] = u_part
      if key not in m_out or not m_out[key].strip():
        m_out[key] = m_part
      else:
        # e.g. 24.24 had 24.39 wrongly sitting under m_raw[(24,24)]; keep both for re-anchoring!
        m_out[(key[0], -key[1])] = m_part  # staged below

  # Move staged negative keys: swap misplaced M[key] out if its ending num belongs elsewhere
  staged = [k for k in m_out if k[1] < 0]
  for ch, neg_v in staged:
    v = -neg_v
    staged_m = m_out.pop((ch, neg_v))
    cur = clean_commentary_boilerplate(m_out.get((ch, v), ""))
    cur_end = _extract_last_end_number(cur)
    if cur and cur_end and cur_end != v and (ch, cur_end) not in m_out:
      m_out[(ch, cur_end)] = cur
      m_out[(ch, v)] = staged_m
    elif not cur:
      m_out[(ch, v)] = staged_m

  # 2) M -> U leaks: `M[v-1] ...॥ v-1॥ \n<ord>\n[। ]*उ[।.०] U[v]`
  m_leak_re = regex.compile(r"(?:\n|^)[।\s]*उ[।.०]\s+")
  for key, text in list(m_out.items()):
    ch, v = key
    if v <= 0:
      continue
    parts = m_leak_re.split(text, maxsplit=1)
    if len(parts) == 2:
      m_head, u_tail = parts[0].strip(), parts[1].strip()
      m_head_clean = clean_commentary_boilerplate(m_head)
      target_v = _extract_last_end_number(m_head_clean) or (v - 1)
      m_out.pop(key)
      if 1 <= target_v and (ch, target_v) not in m_out:
        m_out[(ch, target_v)] = m_head_clean
      u_out[key] = u_tail if key not in u_out or not u_out[key].strip() else u_out[key]

  return u_out, m_out


def _reanchor_misplaced(
  data: dict[tuple[int, int], str],
  sec_counts: dict[int, int],
  mula_by_key: dict[tuple[int, int], str],
  *,
  is_mahidhara: bool,
) -> dict[tuple[int, int], str]:
  """Re-anchor chapter colophon (`ch.ch`) and shifted entries (e.g. `19.55->54`, `26.26->25`)."""
  out = dict(data)
  # Special fix for M(40,40): contains 40.16 + bare unglossed quote of 40.17 ("सप्तदशी। ओ३म् खं ब्रह्म॑॥ १७॥")
  if is_mahidhara and (40, 40) in out:
    out[(40, 40)] = regex.sub(
      r"\s*(?:सप्तदशी[।.\s]*)?ओ३म्\s+खं\s+ब्रह्म[^\n]*॥\s*१७\s*॥.*$", "", out[(40, 40)], flags=regex.S
    )

  for (ch, v), raw in sorted(list(out.items())):
    nmax = sec_counts[ch]
    cleaned = clean_commentary_boilerplate(raw)
    out[(ch, v)] = cleaned
    if not cleaned:
      out.pop((ch, v), None)
      continue
    end_n = _extract_last_end_number(clean_commentary_boilerplate(raw, keep_vedadipa_colophon=False))
    # 1) ch.ch beyond nmax where end_n is valid chapter end / target
    if v > nmax and end_n and 1 <= end_n <= nmax:
      out.pop((ch, v))
      if (ch, end_n) not in out:
        out[(ch, end_n)] = cleaned
      continue
    # 2) Valid key index v <= nmax, yet its true verse is missing v-1 or end_n
    if 1 <= v <= nmax and (ch, v) in mula_by_key and len(cleaned) >= 40 and "व्याख्यात" not in cleaned:
      cur_ov = pratika_overlap_score(cleaned, mula_by_key[(ch, v)])
      # Check explicit end number first if target slot is currently empty
      if end_n and end_n != v and 1 <= end_n <= nmax and (ch, end_n) not in out:
        alt_ov = pratika_overlap_score(cleaned, mula_by_key[(ch, end_n)])
        if alt_ov >= cur_ov + 0.2 or cur_ov == 0.0:
          out.pop((ch, v))
          out[(ch, end_n)] = cleaned
          continue
      # Known off-by-1 shift without matching end number (e.g. U 19.55 printed with typo ॥५५॥ for 19.54)
      if cur_ov == 0.0 and v > 1 and (ch, v - 1) not in out:
        prev_ov = pratika_overlap_score(cleaned, mula_by_key[(ch, v - 1)])
        if prev_ov >= 0.4:
          out.pop((ch, v))
          out[(ch, v - 1)] = cleaned
  return out


def _split_merged_entries(
  data: dict[tuple[int, int], str],
  sec_counts: dict[int, int],
  mula_by_key: dict[tuple[int, int], str],
) -> dict[tuple[int, int], str]:
  """Split multi-kaṇḍikā entries when internal `॥ v॥` separates v and a missing sibling."""
  out = dict(data)
  for (ch, v), raw in sorted(list(out.items())):
    if "\n" not in raw and "॥" not in raw:
      continue
    nmax = sec_counts[ch]
    # Look for internal split boundary matching verse number n == v (or v-1, or v..v+1) where next verse is missing
    best_split = None
    # Match `॥ N॥` or `\sN\s` followed by newline or quote/devanagari start, NOT at very end
    for m in regex.finditer(
      r"(?:॥\s*([०-९0-9]+)\s*॥|(?<=[\s।])\b([०-९]{1,3})\b)\s*(?=\n|[‘'अ-ह])",
      raw,
    ):
      if m.end() > len(raw) - 8:
        continue
      num_tok = m.group(1) or m.group(2)
      n_val = dev_to_int(num_tok)
      if n_val is None or not (1 <= n_val < nmax):
        continue
      # Must be close to current key v (prevents matching Śatapatha quote ॥१॥ or ॥१४॥)
      if abs(n_val - v) > 2:
        continue
      head = raw[: m.end()].strip()
      tail = raw[m.end() :].strip()
      if len(head) < 20 or len(tail) < 12:
        continue
      # Avoid splitting before a trailing Vedadipa verse, colophon, or bare ordinal
      if _WIKISOURCE_COLOPHON_RE.match(tail) or _MAHIDHARA_CHAPTER_VERSE_RE.match(tail) or _ORDINAL_LINE_RE.match(tail):
        continue
      if regex.match(r"^(?:ततः\s+षष्ठ|अथाष्टम|द्वितीया|नवभिः)", tail):
        continue
      # Target keys: either head is v and tail is v+1 (if v+1 missing), OR head is v-1 (if v-1 missing) and tail is v
      if n_val == v and (ch, v + 1) not in out:
        # Extra confidence check: tail isn't just a short postscript note
        if len(tail) >= 18 and (
          m.group(1) is not None
          or pratika_overlap_score(tail, mula_by_key.get((ch, v + 1), "")) > 0.1
          or regex.match(r"^[‘'अ-ह]", tail)
        ):
          best_split = (v, v + 1, head, tail)
          break
      if n_val == v - 1 and (ch, v - 1) not in out:
        best_split = (v - 1, v, head, tail)
        break
    if best_split:
      k1, k2, head, tail = best_split
      out[(ch, k1)] = clean_commentary_boilerplate(head)
      out[(ch, k2)] = clean_commentary_boilerplate(tail)
  return out


def _extract_multi_verse_nums(txt: str) -> list[int]:
  """Extract combined verse number ranges from trailing or leading `॥ १ ॥ २ ॥` markers."""
  stripped = txt.strip()
  m = _MULTI_END_RE.search(stripped)
  if m:
    if m.group(1) is not None:
      nums = [dev_to_int(x) for x in regex.findall(r"[०-९]+", m.group(0))]
      return [x for x in nums if x is not None]
    a, b = dev_to_int(m.group(2)), dev_to_int(m.group(3))
    return list(range(a, b + 1)) if a and b and b >= a else []
  m_lead = _LEADING_MULTI_RE.match(stripped)
  if m_lead:
    nums = [dev_to_int(x) for x in regex.findall(r"[०-९]+", m_lead.group(0))]
    return [x for x in nums if x is not None]
  return []


_PROSE_UVATA_GROUP_NOTES: dict[tuple[int, int], tuple[int, str]] = {
  # (target_ch, target_v): (anchor_v, required_substring_in_anchor_uvata)
  (10, 12): (11, "चतस्रः कण्डिका व्याख्येयाः"),
  (12, 41): (40, "द्वे व्याख्याते"),
  (14, 10): (9, "निगदव्याख्याताः"),
  (14, 25): (24, "दशभिर्मन्त्रैः"),
}


def _reposition_combined_entries(
  data: dict[tuple[int, int], str],
  sec_counts: dict[int, int],
  *,
  apply_prose_group_notes: bool = False,
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
  """Move combined entries (`॥ 1॥2॥ 3॥` stored under last key) to opening verse + note siblings."""
  out = dict(data)
  notes: dict[tuple[int, int], str] = {}
  # Handle explicit M(12, 41) `द्वे व्याख्याते (क० ९)॥४०॥ (क० १०)॥४१॥`
  if (12, 41) in out and "॥४०॥" in out[(12, 41)] and (12, 40) not in out:
    out[(12, 40)] = "द्वे व्याख्याते (क० ९)॥ ४०॥"
    out[(12, 41)] = "द्वे व्याख्याते (क० १०)॥ ४१॥"

  for (ch, v), txt in sorted(list(out.items())):
    nums = _extract_multi_verse_nums(txt)
    if len(nums) < 2:
      continue
    first_v, last_v = nums[0], nums[-1]
    if (
      last_v == v
      and 1 <= first_v < v <= sec_counts[ch]
      and (ch, first_v) not in out
      and "समाप्त" not in txt
    ):
      out.pop((ch, v))
      out[(ch, first_v)] = txt
    start_anchor = first_v if (ch, first_v) in out else v
    dv_anchor = sanscript.transliterate(str(start_anchor), sanscript.IAST, sanscript.DEVANAGARI)
    for sib in nums:
      if sib != start_anchor and (ch, sib) not in out and 1 <= sib <= sec_counts[ch]:
        notes[(ch, sib)] = f"(अस्याः कण्डिकाया व्याख्या {dv_anchor}-कण्डिकया सहिता द्रष्टव्या।)"

  if apply_prose_group_notes:
    for (ch, v), (anchor_v, needle) in _PROSE_UVATA_GROUP_NOTES.items():
      if (ch, v) not in out and (ch, v) not in notes and needle in out.get((ch, anchor_v), ""):
        dv_anchor = sanscript.transliterate(str(anchor_v), sanscript.IAST, sanscript.DEVANAGARI)
        notes[(ch, v)] = f"(अस्याः कण्डिकाया व्याख्या {dv_anchor}-कण्डिकया सहिता द्रष्टव्या।)"
  return out, notes


def parse_wikisource_bhashya_dir(
  ws_dir: pathlib.Path,
  sec_counts: dict[int, int],
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
  """Parse cached `sa.wikisource.org` chapter wikitext (`{ch:02d}.wt`) into U/M maps."""
  u_out: dict[tuple[int, int], str] = {}
  m_out: dict[tuple[int, int], str] = {}
  for wt_path in sorted(ws_dir.glob("*.wt")):
    if not wt_path.stem.isdigit():
      continue
    ch = int(wt_path.stem)
    if ch not in sec_counts:
      continue
    raw = wt_path.read_text()
    idx = raw.find("{{भाष्यम्")
    if idx != -1:
      raw = raw[idx:]
    raw = regex.sub(r"<!--.*?-->", "", raw, flags=regex.S)
    raw = regex.sub(r"<ref>.*?</ref>", "", raw, flags=regex.S)
    raw = regex.sub(r"</?(?:poem|span|div|br|p)[^>]*>", "\n", raw, flags=regex.I)
    raw = regex.sub(r"\{\{[^{}\n]*\}\}", "", raw)
    raw = regex.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", raw)
    raw = raw.replace("}}", "").replace("।।", "॥").replace("||", "॥")

    cur_v: int | None = None
    cur_auth: str | None = None
    buf: list[str] = []

    def _flush():
      nonlocal buf
      if cur_v and cur_auth and buf and 1 <= cur_v <= sec_counts[ch]:
        body = clean_commentary_boilerplate("\n".join(buf))
        if body:
          target = u_out if cur_auth == "उ" else m_out
          target[(ch, cur_v)] = (
            f"{target[(ch, cur_v)]}\n\n{body}".strip() if (ch, cur_v) in target else body
          )
      buf = []

    for line in raw.splitlines():
      s = line.strip().lstrip("|").strip()
      if not s or s.startswith("{{"):
        continue
      m_hdr = regex.search(
        r"॥\s*([०-९]+(?:\s+[०-९]+)?)\s*॥(?:\s*(?:[०-९]+\s*॥)+)?\s*(?:\([^)]*\)\s*)?$",
        s,
      )
      if m_hdr and regex.search(r"[॒॑]", s) and not regex.match(r"^(?:उ|म)[०।.]", s):
        v_num = dev_to_int(regex.sub(r"\s+", "", m_hdr.group(1)))
        if v_num and 1 <= v_num <= sec_counts[ch]:
          _flush()
          cur_v = v_num
          cur_auth = None
          continue
      if regex.match(r"^(?:उ|म)[०।.]\s*", s):
        _flush()
        cur_auth = s[0]
        m_other = regex.search(
          r"^(.+?॥(?:\s*[०-९]+\s*॥)+(?:\s*इति\s+उवटकृतौ[^।\n]*॥)?)\s*((?:उ|म)[०।.].*)$",
          s,
        )
        if m_other and m_other.group(2)[0] != cur_auth:
          buf = [m_other.group(1)]
          _flush()
          cur_auth = m_other.group(2)[0]
          buf = [m_other.group(2)]
        else:
          buf = [s]
        continue
      if _WIKISOURCE_COLOPHON_RE.match(s) or _ORDINAL_LINE_RE.match(s):
        _flush()
        cur_auth = None
        continue
      m_mid = regex.search(
        r"^(.+?॥(?:\s*[०-९]+\s*॥)+(?:\s*इति\s+उवटकृतौ[^।\n]*॥)?)\s*((?:उ|म)[०।.].*)$",
        s,
      )
      if m_mid and cur_auth is not None:
        buf.append(m_mid.group(1))
        _flush()
        cur_auth = m_mid.group(2)[0]
        buf = [m_mid.group(2)]
        continue
      if cur_auth:
        buf.append(s)
    _flush()
  return u_out, m_out


def enrich_corpus_with_wikisource(corpus: dict, ws_dir: pathlib.Path) -> dict:
  """Layer `sa.wikisource.org` chapters onto an existing corpus dict without regressing existing data."""
  sec_counts = {int(k): v for k, v in corpus["sec_counts"].items()}
  ws_u, ws_m = parse_wikisource_bhashya_dir(ws_dir, sec_counts)
  u_map: dict[tuple[int, int], str] = {}
  m_map: dict[tuple[int, int], str] = {}
  for k_str, rec in corpus["records"].items():
    ch, v = map(int, k_str.split("."))
    if rec.get("uvata", "").strip():
      u_map[(ch, v)] = rec["uvata"].strip()
    if rec.get("mahidhara", "").strip():
      m_map[(ch, v)] = rec["mahidhara"].strip()

  for k, val in ws_m.items():
    if k not in m_map or not m_map[k].strip():
      m_map[k] = val

  # Repair NS 1929 printed mis-number `21.45` inside Uvaṭa's 21.43 (`होता यक्षदश्विनौ`)
  if (21, 43) in ws_u and "यक्षदश्विनौ" in ws_u[(21, 43)] and (21, 45) in ws_u:
    u_map[(21, 43)] = ws_u[(21, 43)]
    u_map[(21, 45)] = ws_u[(21, 45)]

  for k, val in ws_u.items():
    if k not in u_map or not u_map[k].strip():
      u_map[k] = val
    else:
      ws_nums = _extract_multi_verse_nums(val)
      cur_nums = _extract_multi_verse_nums(u_map[k])
      if len(ws_nums) > len(cur_nums) and ws_nums and cur_nums[:1] == ws_nums[:1] or (
        len(ws_nums) >= 2 and len(cur_nums) < 2 and k[1] in ws_nums
      ):
        u_map[k] = val

  u_map, u_notes = _reposition_combined_entries(u_map, sec_counts, apply_prose_group_notes=True)
  m_map, m_notes = _reposition_combined_entries(m_map, sec_counts)
  for k, note in u_notes.items():
    if k not in u_map or not u_map[k].strip():
      u_map[k] = note
  for k, note in m_notes.items():
    if k not in m_map or not m_map[k].strip():
      m_map[k] = note

  new_records = {
    f"{ch}.{v}": {
      "uvata": u_map.get((ch, v), "").strip(),
      "mahidhara": m_map.get((ch, v), "").strip(),
    }
    for ch in range(1, 41)
    for v in range(1, sec_counts[ch] + 1)
  }
  return {
    **corpus,
    "sec_counts": sec_counts,
    "records": new_records,
  }


def parse_uvatamahidharau_dir(
  um_dir: pathlib.Path,
  sec_counts: dict[int, int],
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
  """Parse `uvaTa-mahIdharau/{01..19}.md` into `(ch, v)` Uvaṭa and Mahīdhara maps."""
  u_out: dict[tuple[int, int], str] = {}
  m_out: dict[tuple[int, int], str] = {}
  for ch in range(1, 20):
    path = um_dir / f"{ch:02d}.md"
    if not path.exists():
      continue
    txt = path.read_text()
    cur_v: int | None = None
    cur_auth: str | None = None
    buf: list[str] = []

    def _flush():
      nonlocal buf
      if cur_v and cur_auth and buf and 1 <= cur_v <= sec_counts[ch]:
        # Note: UM 19 jumps to ch 26 at verse 77+. Do not mix ch 26 into ch 19!
        if ch == 19 and cur_v >= 77:
          buf = []
          return
        body = clean_commentary_boilerplate("\n".join(buf))
        if body:
          target = u_out if cur_auth == "उ" else m_out
          target[(ch, cur_v)] = (
            f"{target[(ch, cur_v)]}\n\n{body}".strip() if (ch, cur_v) in target else body
          )
      buf = []

    for line in txt.splitlines():
      s = line.strip()
      if not s or s == "+++" or s.startswith("title ="):
        continue
      if regex.match(r"^(?:उ|म)[०।]", s):
        _flush()
        cur_auth = s[0]
        buf = [s]
        continue
      if regex.search(r"[॒॑]", s) and "॥" in s:
        mm = regex.search(r"॥\s*([०-९]+)\s*॥(?:\s*॥)?\s*$", s)
        if mm:
          _flush()
          cur_v = dev_to_int(mm.group(1))
          cur_auth = None
          continue
      if _WIKISOURCE_COLOPHON_RE.match(s) or _ORDINAL_LINE_RE.match(s):
        _flush()
        cur_auth = None
        continue
      if cur_auth:
        buf.append(s)
    _flush()
  return u_out, m_out


def extract_old_mahidhara_pool(
  content_dir: pathlib.Path,
  static_tikah_dir: pathlib.Path,
) -> dict[int, list[tuple[int, str, int | None]]]:
  """Collect existing repo `<summary>महीधरः</summary>` blocks per chapter before replacement."""
  pool: dict[int, list[tuple[int, str, int | None]]] = defaultdict(list)
  for ch in range(1, 41):
    path = content_dir / "sarva-prastutiH" / f"{ch:02d}.md"
    if not path.exists():
      continue
    txt = path.read_text()
    secs = [s for s in regex.split(r"(?m)^(?=## )", txt) if s.startswith("## ")]
    for idx, sec in enumerate(secs, 1):
      blocks = regex.findall(
        r"<details[^>]*>\s*<summary>महीधरः</summary>\s*(.*?)\s*</details>", sec, flags=regex.S
      )
      body = "\n\n".join(b.strip() for b in blocks if b.strip())
      if not body:
        # Check static sarvASh_TIkAH file for this section if included
        m_inc = regex.search(r'url="[^"]*/sarvASh_TIkAH/\d{2}/([^"]+)"', sec)
        if m_inc:
          s_path = static_tikah_dir / f"{ch:02d}" / m_inc.group(1)
          if s_path.exists():
            s_blocks = regex.findall(
              r"<details[^>]*>\s*<summary>महीधरः</summary>\s*(.*?)\s*</details>",
              s_path.read_text(),
              flags=regex.S,
            )
            body = "\n\n".join(b.strip() for b in s_blocks if b.strip())
      if body:
        cleaned = clean_commentary_boilerplate(body)
        no_verse = clean_commentary_boilerplate(body, keep_vedadipa_colophon=False)
        nums = [
          dev_to_int(x)
          for x in regex.findall(r"॥\s*([०-९]+)\s*॥", no_verse[-120:])
        ]
        # Ignore chapter-ending colophon numbers if the block also ends with combined numbers or earlier verse number
        end_nums = [n for n in nums if n is not None and (n != ch or idx == ch)]
        end_n = end_nums[-1] if end_nums else (nums[-1] if nums else None)
        pool[ch].append((idx, cleaned, end_n))
  return pool


def _backfill_from_old_m(
  m_map: dict[tuple[int, int], str],
  old_pool: dict[int, list[tuple[int, str, int | None]]],
  sec_counts: dict[int, int],
  mula_by_key: dict[tuple[int, int], str],
) -> dict[tuple[int, int], str]:
  """Backfill missing or `(???)`-truncated Mahīdhara entries from repo `old_pool` safely."""
  out = dict(m_map)
  # Replace `(???)` truncated entries if repo OLD_M has a clean match without `(???)`
  for (ch, v), txt in list(out.items()):
    if "(???)" in txt and ch in old_pool:
      mula = mula_by_key.get((ch, v), "")
      cands = [
        (idx, b, en)
        for idx, b, en in old_pool[ch]
        if "(???)" not in b and (en == v or pratika_overlap_score(b, mula) >= 0.45)
      ]
      if cands:
        best = max(cands, key=lambda x: ((1.0 if x[2] == v else 0.0) + pratika_overlap_score(x[1], mula), -abs(x[0] - v)))
        out[(ch, v)] = best[1]

  for ch in range(1, 41):
    nmax = sec_counts[ch]
    entries = old_pool.get(ch, [])
    for v in range(1, nmax + 1):
      if (ch, v) in out:
        continue
      mula = mula_by_key[(ch, v)]
      scored = []
      for idx, body, end_n in entries:
        ov = pratika_overlap_score(body, mula)
        # Check whether body explicitly ends with combined verse range including v (e.g. `॥ ४३ ॥ ४४ ॥`)
        no_v = clean_commentary_boilerplate(body, keep_vedadipa_colophon=False)
        tail_nums = {
          dev_to_int(x) for x in regex.findall(r"[०-९]+", no_v[-45:])
        }
        has_v_in_tail = v in tail_nums
        exact_num = 1.0 if (end_n == v and abs(idx - v) <= 6) else (0.8 if (has_v_in_tail and abs(idx - v) <= 5) else 0.0)
        if exact_num > 0 and (ov >= 0.1 or len(normalize_for_matching(mula).split()) <= 6 or ch == 39 or "व्याख्यात" in no_v[-80:]):
          scored.append((exact_num + ov, -abs(idx - v), body))
        elif ov >= 0.48 and abs(idx - v) <= 5:
          scored.append((ov, -abs(idx - v), body))
        elif idx == v == nmax and ov >= 0.15:
          scored.append((0.6 + ov, 0, body))
      if scored:
        scored.sort(reverse=True)
        chosen = scored[0][2]
        # Avoid copying the entire combined block when idx < v just referenced v via `॥ v-1 ॥ v ॥` or v == 18.62
        prev_txt = out.get((ch, v - 1), "")
        if prev_txt and chosen.strip()[:45] == prev_txt.strip()[:45]:
          dv_prev = sanscript.transliterate(str(v - 1), sanscript.IAST, sanscript.DEVANAGARI)
          chosen = f"(अस्याः कण्डिकाया व्याख्या {dv_prev}-कण्डिकया सहिता द्रष्टव्या।)"
        elif len(chosen) > 350 and end_n != v and v in {dev_to_int(x) for x in regex.findall(r"[०-९]+", clean_commentary_boilerplate(chosen, keep_vedadipa_colophon=False)[-45:])}:
          if (ch, v - 1) in out:
            dv_prev = sanscript.transliterate(str(v - 1), sanscript.IAST, sanscript.DEVANAGARI)
            chosen = f"(अस्याः कण्डिकाया व्याख्या {dv_prev}-कण्डिकया सहिता द्रष्टव्या।)"
        out[(ch, v)] = chosen
  # Handle M(25,47) cross-referenced inside M(25,46) (`OLD_M[25,46]` ends `॥ ४६ ॥ ४७ ॥`)
  if (25, 47) not in out and (25, 46) in out and "समिद्धो" in out[(25, 46)]:
    out[(25, 47)] = "(अस्याः कण्डिकाया व्याख्या ४६-कण्डिकया सहिता द्रष्टव्या।)"
  return out


def build_reconciled_corpus(
  indike_uvata_path: pathlib.Path,
  indike_mahidhara_path: pathlib.Path,
  *,
  um_dir: pathlib.Path | None = None,
  ws_dir: pathlib.Path | None = None,
  content_dir: pathlib.Path = CONTENT_SAMHITA_DIR,
  static_tikah_dir: pathlib.Path | None = None,
  old_m_pool: dict[int, list[tuple[int, str, int | None]]] | None = None,
) -> dict:
  """Build cleaned & reconciled per-kaṇḍikā `{ (ch, v): {'uvata': ..., 'mahidhara': ...} }`."""
  static_tikah_dir = static_tikah_dir or (STATIC_SAMHITA_DIR / "sarvASh_TIkAH")
  um_dir = um_dir or (content_dir / "uvaTa-mahIdharau")

  sec_counts: dict[int, int] = {}
  mula_by_key: dict[tuple[int, int], str] = {}
  sub_mulas_by_key: dict[tuple[int, int], list[str]] = {}
  for ch in range(1, 41):
    txt = (content_dir / "sarva-prastutiH" / f"{ch:02d}.md").read_text()
    secs = [s for s in regex.split(r"(?m)^(?=## )", txt) if s.startswith("## ")]
    sec_counts[ch] = len(secs)
    for v, sec in enumerate(secs, 1):
      cores = regex.findall(
        r"<details[^>]*>\s*<summary>मूलम्</summary>\s*(.*?)\s*</details>", sec, flags=regex.S
      )
      clean_cores = [regex.sub(r"\s+", " ", c).strip() for c in cores if c.strip()]
      sub_mulas_by_key[(ch, v)] = clean_cores
      mula_by_key[(ch, v)] = " ".join(clean_cores)

  def _join_segments(segs: list[dict]) -> dict[tuple[int, int], str]:
    groups: dict[str, list[str]] = defaultdict(list)
    order: list[str] = []
    for s in segs:
      t = (s.get("text") or "").strip()
      if not t:
        continue
      loc = s["loc"]
      m = regex.match(r"^(\d+\.\d+)\.(?:p?\d+)$", loc)
      base = m.group(1) if m else loc
      if base not in groups:
        order.append(base)
      groups[base].append(t)
    res = {}
    for base in order:
      ch, v = map(int, base.split("."))
      res[(ch, v)] = "\n\n".join(groups[base])
    return res

  u_segs = json.loads(indike_uvata_path.read_text())["segments"]
  m_segs = json.loads(indike_mahidhara_path.read_text())["segments"]
  u0 = _join_segments(u_segs)
  m0 = _join_segments(m_segs)

  u1, m1 = _split_cross_author_leaks(u0, m0)
  u2 = {k: clean_commentary_boilerplate(v) for k, v in u1.items()}
  m2 = {k: clean_commentary_boilerplate(v) for k, v in m1.items()}

  u3 = _reanchor_misplaced(u2, sec_counts, mula_by_key, is_mahidhara=False)
  m3 = _reanchor_misplaced(m2, sec_counts, mula_by_key, is_mahidhara=True)

  u4 = _split_merged_entries(u3, sec_counts, mula_by_key)
  m4 = _split_merged_entries(m3, sec_counts, mula_by_key)

  u5, u_notes = _reposition_combined_entries(u4, sec_counts, apply_prose_group_notes=True)
  m5, m_notes = _reposition_combined_entries(m4, sec_counts)

  # Backfill U & M gaps from uvaTa-mahIdharau (01..19)
  if um_dir.exists():
    um_u, um_m = parse_uvatamahidharau_dir(um_dir, sec_counts)
    for k, val in um_u.items():
      if k not in u5 or not u5[k].strip():
        u5[k] = val
    for k, val in um_m.items():
      if k not in m5 or not m5[k].strip():
        m5[k] = val

  # Backfill remaining M gaps & truncated `(???)` from existing repo Mahīdhara pool
  if old_m_pool is None:
    old_m_pool = extract_old_mahidhara_pool(content_dir, static_tikah_dir)
  m6 = _backfill_from_old_m(m5, old_m_pool, sec_counts, mula_by_key)

  # Add combined cross-reference note ONLY if still missing after all backfills
  for k, note in u_notes.items():
    if k not in u5 or not u5[k].strip():
      u5[k] = note
  for k, note in m_notes.items():
    if k not in m6 or not m6[k].strip():
      m6[k] = note

  # Handle cross-ref in U(24,3): "महीधरोक्तमर्थं विलिखामि।" is genuine Uvaṭa; keep cleanly.
  records: dict[str, dict[str, str]] = {}
  for ch in range(1, 41):
    for v in range(1, sec_counts[ch] + 1):
      records[f"{ch}.{v}"] = {
        "uvata": u5.get((ch, v), "").strip(),
        "mahidhara": m6.get((ch, v), "").strip(),
      }
  corpus = {
    "sec_counts": sec_counts,
    "sub_mulas_by_key": {f"{k[0]}.{k[1]}": v for k, v in sub_mulas_by_key.items()},
    "records": records,
  }
  if ws_dir is not None and ws_dir.exists():
    corpus = enrich_corpus_with_wikisource(corpus, ws_dir)
  return corpus


def _fix_malformed_citations(text: str) -> str:
  """Repair unbalanced parens and verse-quote breaks so sentence splitting stays intact."""
  # Fix double-open `(का० (१८। १२.१०)` -> `(का० १८। १२.१०)`
  t = regex.sub(r"\(\s*(का(?:त्या)?[०.]\s*)\(\s*([०-९0-9])", r"(\1\2", text)
  # Close unclosed `(का० १९। ७.१॥` right before space + commentary Devanagari word
  t = regex.sub(
    r"\(\s*(का(?:त्या)?[०.]\s*[०-९0-9।.\-\s]{2,25})॥\s+(?=[अ-ह‘'])",
    r"(\1)। ",
    t,
  )
  # Ensure a quote like `‘ऋतस्य द्वाराविति द्वार्ये (का. ९.८.२३)` closes `’` before `(का...`
  t = regex.sub(
    r"(‘[^'‘’\n]{6,}?)\s+(?=\(\s*(?:का(?:त्या)?[०.]\s*))",
    r"\1’ ",
    t,
  )
  # Join multiline śloka inside `‘...’` so `।` + `\n` before closing `॥’` stays one quote segment
  t = regex.sub(r"(?s)(‘[^'‘’]{4,140}?।)\s*\n\s*([^'‘’]{4,140}?॥’)", r"\1 \2", t)
  # Separate trailing mantra/viniyoga right after closing `॥’` (e.g. `॥’ ऊर्जे त्वा।`)
  t = regex.sub(r"(॥’)\s+(?=[\u0900-\u097f])", r"\1\n", t)
  return t


def _split_ka_sentences(text: str) -> list[str]:
  """Split text into quote-safe sentences, also isolating inline `कात्यायनः ‘...’` clauses."""
  fixed = _fix_malformed_citations(text)
  raw_segs = interleave_helper.split_quote_safe_segments(fixed)
  merged = cross_recension._merge_orphan_ref_segments(raw_segs)
  out: list[str] = []
  for seg in merged:
    # Also split right after `॥’` if a śloka quote (`उक्तंच-‘...॥’ ऊर्जे त्वा।`) glued the next clause
    m_verse = regex.match(r"^(.+?॥’)\s+(.+)$", seg, flags=regex.S)
    if m_verse and not regex.match(r"^(?:इति|तथा|अस्य)", m_verse.group(2)):
      out.append(m_verse.group(1).strip())
      out.extend(_split_ka_sentences(m_verse.group(2).strip()))
      continue
    # Also merge unclosed leading half-quote backward with `’` segment if split_quote_safe_segments broke on `-‘`
    if out and out[-1].count("‘") > out[-1].count("’") and "’" in seg and seg.count("’") > seg.count("‘"):
      out[-1] = out[-1] + " " + seg
      continue
    # Check if an inline Kātyāyana sūtra quote (or `(का० ...)` / `(४। २। ७)`) precedes commentary
    m = regex.search(
      r"((?:कात्यायनः\s*)?['‘][^'‘’\n]{6,}?['’][।.]?\s*\(\s*(?:का(?:त्या)?[०.]\s*)?[०-९0-9।.\-\s]+\)\s*(?:इति\s*)?[।.]?\s*)",
      seg,
    )
    if m and (m.start() > 0 or len(seg) - m.end() > 15):
      before = seg[: m.start()].strip()
      quote_part = m.group(1).strip()
      after = seg[m.end() :].strip()
      if before:
        out.append(before)
      out.append(quote_part)
      if after:
        out.extend(_split_ka_sentences(after))
      continue
    # Break runaway >450 char segment caused by an unmatched opening `(` or `‘`
    if len(seg) > 450 and (seg.count("(") != seg.count(")") or seg.count("‘") != seg.count("’")):
      parts = regex.split(r"(?<=[।॥])\s+(?=[अ-ह‘'])", seg)
      if len(parts) > 1:
        out.extend(p.strip() for p in parts if p.strip())
        continue
    out.append(seg)
  return [s.strip() for s in out if s.strip()]


def _classify_bhashya_segment(
  seg: str,
  *,
  author: str,
  cluster_started_tika: bool,
  at_kandika_start: bool,
  next_seg: str | None = None,
) -> str:
  """Classify a single quote-safe commentary sentence as `avatarika`, `viniyoga`, or `tika`."""
  s = seg.strip()
  if not s:
    return "tika"
  if _SECOND_PASS_RE.match(s) or _MAHIDHARA_CHAPTER_VERSE_RE.search(s):
    return "tika"

  has_gloss_marker = bool(_GLOSS_EQ_RE.search(s))
  has_gram_or_neg = bool(_NOT_VINIYOGA_RE.search(s))

  # 1) Explicit Kātyāyana reference or explicit विनियुज्यते/विनियोगः (when not arthavāda/śruti/negation)
  if (
    _KAT_REF_RE.search(s)
    and "विनियोगो नास्ति" not in s
    and "इति कात्यायनोक्तेः" not in s
    and not regex.search(r"तित्तिरि|श०\s*ब्रा०|इति\s+श्रुतेः", s)
  ):
    return "viniyoga"
  if _EXPLICIT_VINIYOGA_RE.search(s) and not has_gram_or_neg:
    return "viniyoga"

  # 2) Section / topic avatarika BEFORE tika starts (never match prose glosses once tika started!)
  if not cluster_started_tika and not has_gloss_marker and not has_gram_or_neg and not _RITUAL_VERB_RE.search(s):
    if _AVATARIKA_RE.search(s) and not regex.search(r"\b(?:सः|ते|वयं|त्वं|अयं|इमं|ये|वुरीत)\b", s):
      return "avatarika"

  # 3) Concise ritual prayoga sentence (primarily Uvaṭa concise injunctions like `अपः प्रणयति।`, `जपति ...।`, `शाखामुपगूहति।`)
  if _RITUAL_VERB_RE.search(s) and not has_gram_or_neg and not has_gloss_marker and len(s) <= 135:
    if not cluster_started_tika or len(s) <= 75:
      if not regex.search(r"\b(?:यः|ये|या|यत्|यत्र|यदा|त्वं|यूयं|वयं|अयं|एते|सः|ते)\b", s):
        return "viniyoga"

  # 4) Explicit mid-kandika topic switch ONLY for strong group openers (`इतौत्तरं ...`, `अतः परं ...`, `अथ ...ः।`), never trailing verb heuristics!
  if (
    not has_gloss_marker
    and not has_gram_or_neg
    and regex.match(
      r"^\s*(?:इतः\s*पर[ंम्]|इत\s*उत्तर[ंम्]|इतौत्तर[ंम्]|अतः\s*पर[ंम्]|अथ\s+(?:प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|षष्ठ)[ःं]।)",
      s,
    )
    and len(s) <= 130
  ):
    return "avatarika"

  return "tika"


def _assign_segments_to_submantras(
  segs: list[str],
  cores: list[str],
  *,
  author: str,
) -> list[list[dict[str, str]]]:
  """Split `segs` into `(role, text)` and map across `len(cores)` sub-mantras cleanly."""
  num_cores = len(cores)
  if num_cores == 0:
    return []
  if not segs:
    return [[] for _ in range(num_cores)]

  if num_cores == 1:
    cluster_segs: list[dict[str, str]] = []
    started_tika = False
    for idx, seg in enumerate(segs):
      nxt = segs[idx + 1] if idx + 1 < len(segs) else None
      role = _classify_bhashya_segment(
        seg,
        author=author,
        cluster_started_tika=started_tika,
        at_kandika_start=(idx < 4 and not started_tika),
        next_seg=nxt,
      )
      if role == "tika":
        started_tika = True
      cluster_segs.append({"role": role, "text": seg})
    return [cluster_segs]

  # Multi-submantra section: partition segments cleanly across two passes if `अथ व्याकरणप्रक्रिया` present
  pass_split_idx = next((i for i, s in enumerate(segs) if _SECOND_PASS_RE.match(s)), None)
  pass_ranges = [(0, len(segs))] if pass_split_idx is None else [(0, pass_split_idx), (pass_split_idx, len(segs))]

  # Precompute roles / scores for lookahead of short opening viniyoga (`जपति।`) before next sub-mantra anchor
  # Also detect pass boundary (`अथ व्याकरणप्रक्रिया`) cleanly
  pass_split_idx = next((i for i, s in enumerate(segs) if _SECOND_PASS_RE.match(s)), None)
  pass_ranges = [(0, len(segs))] if pass_split_idx is None else [(0, pass_split_idx), (pass_split_idx, len(segs))]

  # Precompute overlap scores per (seg_idx, core_idx) + content words per core for clean advances
  core_assignments = [0] * len(segs)
  seg_scores = [[pratika_overlap_score(s, c) for c in cores] for s in segs]
  core_tokens = [set(_content_words(normalize_for_matching(c))) for c in cores]
  for p_start, p_end in pass_ranges:
    if p_start >= p_end:
      continue
    cur_core = 0
    for i in range(p_start, p_end):
      s = segs[i]
      scores = seg_scores[i]
      best_c = max(range(num_cores), key=lambda k: (scores[k], -abs(k - cur_core)))
      best_sc = scores[best_c]
      cur_sc = scores[cur_core]
      s_head_words = set(normalize_for_matching(s[:80]).split())
      if _MAHIDHARA_CHAPTER_VERSE_RE.search(s):
        core_assignments[i] = num_cores - 1
        cur_core = num_cores - 1
        continue
      is_closing_tag = bool(regex.search(r"^\s*इति\s+", s))
      if best_sc == 0.0 and not is_closing_tag and len(s) <= 120 and i + 1 < p_end:
        nxt_scores = seg_scores[i + 1]
        nxt_best = max(range(num_cores), key=lambda k: (nxt_scores[k], -abs(k - cur_core)))
        if nxt_best > cur_core and nxt_scores[nxt_best] >= max(0.25, nxt_scores[cur_core] + 0.12):
          cur_core = nxt_best
          core_assignments[i] = cur_core
          continue
      if best_c > cur_core and (best_sc >= max(0.30, cur_sc + 0.15)):
        cur_core = best_c
      elif best_c < cur_core and _SECOND_PASS_RE.match(s):
        cur_core = best_c
      elif best_c > cur_core and (
        (cur_sc == 0.0 and (s_head_words & core_tokens[best_c]))
        or best_sc >= 0.16 and cur_sc == 0.0 and any(len(cw) >= 5 and cw in normalize_for_matching(cores[best_c]) for cw in s_head_words)
      ):
        if best_c - cur_core <= 2 or best_sc >= 0.25:
          cur_core = best_c
      core_assignments[i] = cur_core

  per_core: list[list[dict[str, str]]] = [[] for _ in range(num_cores)]
  started_tika_per_core = [False] * num_cores
  for idx, seg in enumerate(segs):
    c_idx = core_assignments[idx]
    nxt = segs[idx + 1] if idx + 1 < len(segs) else None
    role = _classify_bhashya_segment(
      seg,
      author=author,
      cluster_started_tika=started_tika_per_core[c_idx],
      at_kandika_start=(c_idx == 0 and not started_tika_per_core[0]),
      next_seg=nxt,
    )
    if role == "tika":
      started_tika_per_core[c_idx] = True
    per_core[c_idx].append({"role": role, "text": seg})
  return per_core


def _extract_leading_upodghata(text: str, author: str) -> tuple[str, str]:
  """For 1.1 only, split the treatise/chapter upodghāta cleanly before mantra commentary starts."""
  if not text:
    return "", ""
  marker = _UPODGHATA_U_END_RE if author == "uvata" else _UPODGHATA_M_END_RE
  m = marker.search(text)
  if m:
    return text[: m.start()].strip(), text[m.start() :].strip()
  return "", text


def plan_kandika_alignment(
  uvata_text: str,
  mahidhara_text: str,
  cores: list[str],
  *,
  kandika_key: str | None = None,
) -> list[dict[str, dict[str, str]]]:
  """Produce per-submantra dicts mapping `avatarika|viniyoga|tika` per author."""
  n = len(cores)
  u_clean = clean_commentary_boilerplate(uvata_text) if uvata_text else ""
  m_clean = clean_commentary_boilerplate(mahidhara_text) if mahidhara_text else ""

  u_upod, u_body = _extract_leading_upodghata(u_clean, "uvata") if kandika_key == "1.1" else ("", u_clean)
  m_upod, m_body = _extract_leading_upodghata(m_clean, "mahidhara") if kandika_key == "1.1" else ("", m_clean)

  u_segs = _split_ka_sentences(u_body) if u_body else []
  m_segs = _split_ka_sentences(m_body) if m_body else []

  u_assigned = _assign_segments_to_submantras(u_segs, cores, author="uvata")
  m_assigned = _assign_segments_to_submantras(m_segs, cores, author="mahidhara")

  if u_upod and u_assigned:
    u_assigned[0].insert(0, {"role": "avatarika", "text": u_upod})
  if m_upod and m_assigned:
    m_assigned[0].insert(0, {"role": "avatarika", "text": m_upod})

  clusters = []
  for k in range(n):
    c = {"uvata": {}, "mahidhara": {}}
    for auth, lst in [("uvata", u_assigned[k]), ("mahidhara", m_assigned[k])]:
      by_role: dict[str, list[str]] = defaultdict(list)
      for item in lst:
        by_role[item["role"]].append(item["text"])
      for role in ("avatarika", "viniyoga", "tika"):
        if by_role[role]:
          c[auth][role] = "\n\n".join(by_role[role])
    clusters.append(c)
  return clusters


def _format_details_block(summary: str, body: str) -> str:
  return f"<details><summary>{summary}</summary>\n\n{body.strip()}\n</details>"


_VSM_AVATARIKA_SPECS = (
  ("uvata", UVATA_AVATARIKA_SUMMARY, UVATA_VINIYOGA_SUMMARY),
  ("mahidhara", MAHIDHARA_AVATARIKA_SUMMARY, MAHIDHARA_VINIYOGA_SUMMARY),
)


def _format_sarva_avatarikah(
  cluster: dict[str, dict[str, str]],
  *,
  author_specs: tuple[tuple[str, str, str], ...] = _VSM_AVATARIKA_SPECS,
) -> str:
  """Group non-empty avatārikā and viniyoga blocks under `<summary>सर्वा अवतारिकाः</summary>`."""
  upper_blocks = []
  for role, idx in (("avatarika", 1), ("viniyoga", 2)):
    for auth_key, *labels in author_specs:
      sum_label = labels[idx - 1]
      val = cluster.get(auth_key, {}).get(role)
      if val:
        upper_blocks.append(_format_details_block(sum_label, val))
  if not upper_blocks:
    return ""
  return f"<details><summary>{SARVA_AVATARIKAH_SUMMARY}</summary>\n" + "\n".join(upper_blocks) + "\n</details>\n"


def _strip_existing_managed_blocks(md_text: str) -> str:
  """Remove previously inserted Uvaṭa / Mahīdhara `<details>` blocks (depth-safe & idempotent)."""
  titles_pat = "|".join(regex.escape(t) for t in sorted(MANAGED_SUMMARIES, key=len, reverse=True))
  open_pat = regex.compile(
    rf"(?:\n|^)<details(?:\s+open)?><summary>(?:{titles_pat})</summary>",
  )
  tag_pat = regex.compile(r"<details\b[^>]*>|</details>")
  out = md_text
  while True:
    m = open_pat.search(out)
    if not m:
      break
    tag_start = out.find("<details", m.start())
    depth = 0
    end_pos = None
    for tm in tag_pat.finditer(out, pos=tag_start):
      if tm.group(0).startswith("</details>"):
        depth -= 1
        if depth == 0:
          end_pos = tm.end()
          break
      else:
        depth += 1
    if end_pos is None:
      break
    out = out[: m.start()] + out[end_pos:]
  return regex.sub(r"\n{3,}", "\n\n", out)


def render_static_sarvash_tikah(
  static_md_text: str,
  u_tika: str,
  m_tika: str,
) -> str:
  """Insert `<summary>उवट-टीका</summary>` and `<summary>महीधर-टीका</summary>` in static file."""
  cleaned = _strip_existing_managed_blocks(static_md_text)
  tika_blocks = []
  if u_tika.strip():
    tika_blocks.append(_format_details_block(UVATA_TIKA_SUMMARY, u_tika))
  if m_tika.strip():
    tika_blocks.append(_format_details_block(MAHIDHARA_TIKA_SUMMARY, m_tika))
  if not tika_blocks:
    return cleaned
  insertion = "\n".join(tika_blocks)
  padapatha_end_re = regex.compile(
    r"(<details(?:\s+open)?><summary>पदपाठः[^<]*</summary>.*?</details>)",
    flags=regex.S,
  )
  if padapatha_end_re.search(cleaned):
    return padapatha_end_re.sub(rf"\1\n{insertion}", cleaned, count=1)
  adhimantram_re = regex.compile(
    r"(<details(?:\s+open)?><summary>(?:अधिमन्त्रम्|दयानन्द)[^<]*</summary>)",
    flags=regex.S,
  )
  if adhimantram_re.search(cleaned):
    return adhimantram_re.sub(rf"{insertion}\n\1", cleaned, count=1)
  return cleaned.rstrip() + "\n" + insertion + "\n"


def _find_matching_div_end(text: str, div_open_start: int) -> int | None:
  """Return character index right after the matching closing `</div>` for `div_open_start`."""
  depth = 0
  for m in regex.finditer(r"<div\b[^>]*>|</div>", text[div_open_start:]):
    if m.group(0).startswith("</div>"):
      depth -= 1
      if depth == 0:
        return div_open_start + m.end()
    else:
      depth += 1
  return None


def render_host_section(
  sec_text: str,
  plan: list[dict[str, dict[str, str]]],
  *,
  static_tikah_dir: pathlib.Path | None = None,
) -> tuple[str, tuple[pathlib.Path, str] | None]:
  """Update one `## ...` section in `sarva-prastutiH/{ch}.md` and optional static file."""
  hdr_nl = sec_text.find("\n")
  if hdr_nl == -1:
    return sec_text, None
  hdr = sec_text[: hdr_nl + 1]
  body = _strip_existing_managed_blocks(sec_text[hdr_nl + 1 :])

  # Case A: js_include section
  vp_inc_re = regex.compile(
    r'(<div\s+class="js_include"[^>]*url="[^"]*/vishvAsa-prastutiH/[^"]*"[^>]*>)',
    flags=regex.S,
  )
  st_open_re = regex.compile(
    r'<div\s+class="js_include[^"]*"[^>]*url="([^"]*/sarvASh_TIkAH/([^"]+))"[^>]*>\s*<details[^>]*><summary><h3>सर्वाष् टीकाः \.\.\.\{Loading\}\.\.\.</h3></summary>\s*',
    flags=regex.S,
  )
  m_vp_inc = vp_inc_re.search(body)
  m_st_open = st_open_re.search(body)
  if m_vp_inc and m_st_open:
    div_end = _find_matching_div_end(body, m_st_open.start())
    if div_end is not None:
      closing_tail_re = regex.compile(r"\s*</details>\s*</div>\s*$")
      outer_slice = body[m_st_open.end() : div_end]
      m_close = closing_tail_re.search(outer_slice)
      if m_close:
        inner_start = m_st_open.end()
        inner_end = m_st_open.end() + m_close.start()
        c = plan[0]
        upper_str = _format_sarva_avatarikah(c)

        rel_static = m_st_open.group(2)
        u_tika = c["uvata"].get("tika", "")
        m_tika = c["mahidhara"].get("tika", "")

        static_update = None
        if static_tikah_dir is not None:
          s_path = static_tikah_dir / rel_static
          if s_path.exists():
            new_static = render_static_sarvash_tikah(s_path.read_text(), u_tika, m_tika)
            static_update = (s_path, new_static)

        # Update host fallback content inside sarvASh_TIkAH js_include identically!
        new_inner = render_static_sarvash_tikah(body[inner_start:inner_end], u_tika, m_tika)
        body = body[:inner_start] + new_inner + body[inner_end:]
        body = vp_inc_re.sub(lambda mm: upper_str + mm.group(1), body, count=1)
        body = regex.sub(r"\n{3,}", "\n\n", body)
        return hdr + body.lstrip("\n"), static_update

  # Case B: inline / split-mantra section
  vp_open_pat = regex.compile(r"<details\s+open><summary>विश्वास-प्रस्तुतिः</summary>")
  vp_matches = list(vp_open_pat.finditer(body))
  if not vp_matches:
    return sec_text, None

  # Match each sub-cluster's पदपाठः end inside `body` (1-to-1 with vp_matches)
  pada_pat = regex.compile(
    r"(<details(?:\s+open)?><summary>पदपाठः[^<]*</summary>.*?</details>)",
    flags=regex.S,
  )
  pada_matches = list(pada_pat.finditer(body))

  # Rebuild body cleanly inserting upper group before each vp_matches[k] and tikas after pada_matches[k]
  edits: list[tuple[int, int, str]] = []
  for k, m_vp in enumerate(vp_matches):
    c = plan[k] if k < len(plan) else {"uvata": {}, "mahidhara": {}}
    upper_str = _format_sarva_avatarikah(c)
    if upper_str:
      edits.append((m_vp.start(), m_vp.start(), upper_str))

    tika_blocks = []
    if c["uvata"].get("tika"):
      tika_blocks.append(_format_details_block(UVATA_TIKA_SUMMARY, c["uvata"]["tika"]))
    if c["mahidhara"].get("tika"):
      tika_blocks.append(_format_details_block(MAHIDHARA_TIKA_SUMMARY, c["mahidhara"]["tika"]))
    if tika_blocks and k < len(pada_matches):
      m_p = pada_matches[k]
      edits.append((m_p.end(), m_p.end(), "\n" + "\n".join(tika_blocks)))

  # Apply edits in reverse offset order
  out_body = body
  for start, end, repl in sorted(edits, key=lambda x: x[0], reverse=True):
    out_body = out_body[:start] + repl + out_body[end:]
  out_body = regex.sub(r"\n{3,}", "\n\n", out_body)
  return hdr + out_body.lstrip("\n"), None


def apply_all_bhashyas(
  indike_uvata_path: pathlib.Path,
  indike_mahidhara_path: pathlib.Path,
  *,
  dry_run: bool = True,
  content_dir: pathlib.Path = CONTENT_SAMHITA_DIR,
  static_dir: pathlib.Path = STATIC_SAMHITA_DIR,
  cached_corpus_path: pathlib.Path | None = None,
) -> dict:
  """Align reconciled Uvaṭa and Mahīdhara bhāṣyas across all 40 VS Mādhyandina chapters."""
  static_tikah_dir = static_dir / "sarvASh_TIkAH"
  if cached_corpus_path and cached_corpus_path.exists():
    corpus = json.loads(cached_corpus_path.read_text())
    corpus["sec_counts"] = {int(k): v for k, v in corpus["sec_counts"].items()}
  else:
    corpus = build_reconciled_corpus(
      indike_uvata_path,
      indike_mahidhara_path,
      content_dir=content_dir,
      static_tikah_dir=static_tikah_dir,
    )
    if cached_corpus_path:
      cached_corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2))

  recs = corpus["records"]
  stats = {
    "chapters_updated": 0,
    "static_updated": 0,
    "sections_processed": 0,
    "broken_balance": [],
    "static_leaks": [],
    "leftover_raw_m": [],
  }

  for ch in range(1, 41):
    ch_path = content_dir / "sarva-prastutiH" / f"{ch:02d}.md"
    txt = ch_path.read_text()
    secs = regex.split(r"(?m)^(?=## )", txt)
    new_secs = [secs[0]]
    for v_idx, sec in enumerate(secs[1:], 1):
      k = f"{ch}.{v_idx}"
      stats["sections_processed"] += 1
      r = recs.get(k, {"uvata": "", "mahidhara": ""})
      cores = corpus["sub_mulas_by_key"][k]
      plan = plan_kandika_alignment(r["uvata"], r["mahidhara"], cores, kandika_key=k)
      new_sec, st_upd = render_host_section(sec, plan, static_tikah_dir=static_tikah_dir)
      if "<summary>महीधरः</summary>" in new_sec:
        stats["leftover_raw_m"].append(k)
      if new_sec.count("<details") != new_sec.count("</details>"):
        stats["broken_balance"].append(("host", k))
      new_secs.append(new_sec)

      if st_upd:
        s_path, s_txt = st_upd
        if s_txt.count("<details") != s_txt.count("</details>"):
          stats["broken_balance"].append(("static", k))
        if "विनियोगः" in s_txt or "अवतारिका" in s_txt or "<summary>महीधरः</summary>" in s_txt:
          stats["static_leaks"].append(k)
        if not dry_run and s_txt != s_path.read_text():
          s_path.write_text(s_txt)
          stats["static_updated"] += 1
        elif dry_run:
          stats["static_updated"] += 1

    new_txt = "".join(new_secs)
    if new_txt != txt:
      if not dry_run:
        ch_path.write_text(new_txt)
      stats["chapters_updated"] += 1
  return stats

