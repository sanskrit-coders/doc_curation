"""Corpus-wide diagnostic auditor for ``पद-पाठः (यान्त्रिकः)`` and ``विश्वास-प्रस्तुतिः`` Markdown files.

Complements :mod:`doc_curation.sanskrit.accent.validator` (which enforces zero-tolerance structural
and grammatical invariants) with scholarly/editorial heuristics that surface candidate errors across
Vedic corpora (*EK*, *TA*, *TB*, *TS*, *ŚB*, etc.) for adjudication:

- ``validator_issue``: hard integrity errors from :mod:`validator`.
- ``reconciler_diff``: pending ``[[OLD|NEW]]`` or direct-VP updates from :mod:`reconciler`.
- ``commentator_missing_block`` / ``commentator_unstated_svara``: trailing ``— हरदत्तः`` / ``— भास्करः`` /
  ``— सायणः`` stamps where the commentator is absent or does not discuss svara/grammar for that pada.
- ``svarita_824_placement``: ``पा॰ ८.२.४`` citations where ``᳙`` does not sit on a ``यण्`` syllable.
- ``ekadesha_multi_accent_ar``: vyatyasta arrows whose ``ar`` carries ≥ 2 accents (candidate sandhi
  *ekādeśa* ``पा॰ ८.२.५`` boundary misattribution).
- ``non_initial_61198_vocative``: ``पा॰ ६.१.१९८`` vocatives not standing at mantra/pāda start.
- ``possible_missed_vocative``: 0-accent → accented arrows where commentary/VP marks a vocative
  (``हे <stem>`` or ``<stem>!``).
- ``mw_only_arrow``: vyatyasta arrows lacking both counted corpus tags and Pāṇinian/Phiṭ/Uṇādi sūtras.
- ``mula_svarita_misread``: vyatyasta arrows whose ``ar`` has ``᳓`` while ``to_US_accents(मूलम्)``
  shows independent svarita ``᳙`` on that word.
- ``false_compound_candidate``: hyphenated padas split by whitespace in ``विश्वास-प्रस्तुतिः`` or with
  inflected/enclitic first members on arrows.
- ``false_corpus_citation``: bare corpus tags ``*CORPUS*`` on ``OLD → **NEW**`` where ``VedicCorpusCounter``
  shows ``NEW`` has 0 attestations while ``OLD`` is attested (optional ``counter`` check).
- ``weak_rv_av_override``: ``*RV*``/``*AV*``-only non-Pāṇinian arrow overrides against YV-attested ``OLD``
  (or weak ≤2/bare ``*RV*``/``*AV*`` arrows offline).
- ``missing_yv_corpus_counts``: entries citing only unattested corpus tags (0 hits) while Yajurveda corpora
  attest that accented form (optional ``counter`` check).
- ``known_false_svara_antipattern``: ``मा ... हिंसीः᳓`` (``पा॰ ८.१.२८`` finite verb mis-marked),
  ``दीप्य᳓मान`` (``यक् पा॰ ३.१.६७`` instead of ``श्यन् पा॰ ३.१.६९``), ``कन्`` cited with
  ``पा॰ ३.१.३`` (omitting ``पा॰ ६.१.१९७``), false ``पा॰ ८.१.३`` on enclitics or unmatched
  words, relative ``यद्``-clause verbs stripped via ``पा॰ ८.१.२८``, ``लुट्`` forms marked
  ``पा॰ ८.१.२८``, and inverted ``पा॰ ८.१.७०`` / ``पा॰ ८.१.५७`` citations (arrows and non-arrows).
- ``non_arrow_8166_without_yad`` / ``non_tinanta_8128_8166``: direct-bullet ``पा॰ ८.१.६६`` with
  no preceding ``यद्``-word/conjunction in the block, and non-verbal pronouns/participles/nominals
  erroneously citing ``पा॰ ८.१.२८ तिङन्तम्`` or ``पा॰ ८.१.६६``.
- ``vp_includes_tiikaa``: ``vishvAsa-prastutiH/`` files including ``sarvASh_TIkAH/`` or embedding
  ``पद-पाठः (यान्त्रिकः)`` blocks.
- ``redundant_ek_external_padapatha``: ``ekAgnikANDam/sarvASh_TIkAH`` files retaining canonical
  ``पद-पाठः (यान्त्रिकः)`` blocks when the paired VP ``js_include``s an external mantra.
- ``redundant_ek_external_wrapper``: ``ekAgnikANDam/vishvAsa-prastutiH`` files still wrapping
  external mantras via ``js_include`` instead of deleting the wrapper pair.

CLI usage::

  ~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.auditor <dir1> [dir2 ...] [--with-reconciler] [--with-corpus-counter] [--json out.json]
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import dataclasses
import json
import os
import re
from typing import Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent import reconciler, validator
from doc_curation.sanskrit.accent.provenance import (
  DETAILS_RE,
  VedicCorpusCounter,
  _TAG_TOKEN_RE,
  find_js_include_spans,
)
from doc_curation.sanskrit.accent.reconciler import US_SVARITA, US_UDATTA, parse_padapatha_items

PP_SUMMARY_RE = re.compile(r"^पद-पाठः\s*\(यान्त्रिकः")
_JS_INCLUDE_URL_RE = re.compile(r'<div\s+class="js_include"[^>]*url=["\']([^"\']+)["\'][^>]*>')
CORPUS_COUNT_TAG_RE = re.compile(r"\*(?:TS|RV|TB|TK|AV|SB-M|SB-K|ŚB|VS-M|VS-K|VS|KS|MS)\*-\d+(?:/\d+)?")
SUTRA_REF_RE = re.compile(r"(?:पा[॰०]|फि[॰०]|उणादि[॰०]|वा[॰०])")
SVARA_MARK_RE = re.compile(rf"[{US_UDATTA}{US_SVARITA}]")
_YV_CORPORA: tuple[str, ...] = ("TS", "TB", "TK", "SB-M", "SB-K", "VS-M", "VS-K", "KS", "MS")
_RV_AV_ONLY_SET: frozenset[str] = frozenset({"RV", "AV"})
DASH_COMM_RE = re.compile(
  r"[—–]\s*(हरदत्त-सायणौ|भास्कर-सायणौ|सायण-भास्करौ|भास्कर-रामानुजौ|भट्टभास्करः|हरदत्तः|भास्करः|सायणः|रङ्गरामानुजः|शङ्करः)(?=\s*(?:[,;)]|$))"
)
STRICT_COMM_SVARA_RE = re.compile(
  r"(?:उदात्त|अनुदात्त|स्वरित|निघात|प्रकृतिस्वर|स्वरव्यत्यय|स्वरान्यत्व|आद्युदात्त|अन्तोदात्त|मध्योदात्त|"
  r"नित्स्वर|चित्स्वर|लित्स्वर|तित्स्वर|प्रत्ययस्वर|परादिश्छन्दसि|समासस्य|यतोऽनाव|अविद्यमानवत्|"
  r"छान्दस|छन्दसि|सुपां सुलुक्|ह एति|नित्त्वात्|चित्त्वात्|लित्त्वात्|पित्त्वात्|प्रत्ययात्|"
  r"स्वरः|स्वरेण|स्वरात्|स्वरं|स्वरत्व|स्वराः)"
)
_INFLECTED_P0_ENDINGS_RE = re.compile(r"(?:सु|ए|आत्|स्य|भिः|भ्यः|एण|एन|अया|एषु|आसु)$")
_PARTICLE_P0_SET = frozenset({
  "अपि", "उत", "इह", "अत्र", "न", "मा", "च", "वा", "हि", "तु", "वै", "उ", "अध", "अथ", "एव", "इति",
})
_AMREDITA_ENCLITIC_SET = frozenset({"ते", "मे", "नः", "वः", "त्वा"})
_YAD_RELATIVE_SET = frozenset({
  "यः", "या", "यत्", "यद्", "यम्", "याम्", "येन", "यया", "यस्मै", "यस्यै", "यस्मात्",
  "यस्याः", "यस्य", "यस्मिन्", "यस्याम्", "यत्र", "यत्रा", "यदा", "यदि", "यदी", "यथा", "यतः",
  "ये", "यौ", "याः", "यान्", "यानि", "याभ्याम्", "यैः", "येभिः", "याभिः", "येषाम्", "यासाम्",
  "येभ्यः", "याभ्यः", "ययोः", "येषु", "यासु",
  "यतमः", "यतमम्", "यतमा", "यतरः", "यतरम्", "यतमेन", "यावत्", "यावती", "यतिथः", "यतिथम्", "यतिथ्याम्", "यादृश्", "यादृक्", "यद्वा",
})
_CLAUSE_BOUNDARY_SET = frozenset({
  "तत्", "तद्", "सः", "सा", "तत्र", "तदा", "तस्मात्", "ततः", "तथा", "अथ", "तेन", "तया", "इति",
  "तम्", "ताम्", "तस्मै", "तस्यै", "तस्मिन्", "तस्य", "तस्याः", "तस्याम्", "ताः", "ते", "तौ", "तानि",
  "तैः", "ताभिः", "तेभ्यः", "ताभ्यः", "तेषाम्", "तासाम्", "तेषु", "तासु",
})
_FINITE_VERB_PROV_RE = re.compile(
  r"(?:तिङन्त|८\.१\.(?:२[८९]|[३-६][०-९]|७१)|लट्|लिट्|लङ्|लोट्|लुङ्|लृट्|लेट्|विधिलिङ्|आशीर्लिङ्|√)"
)
_AMREDITA_PROV_RE = re.compile(r"८\.१\.३(?!\d)|द्विर्वचने|आम्रेडित")
_KAN_PROV_RE = re.compile(r"(?<![अ-औक-ह])कन्(?![अ-औक-ह])")
_VOWEL_CASE_TAIL_RE = re.compile(r"(?:ाम्|म्|ः|ा|ि|ी|ु|ू|े|ो)$")
_LUT_EXEMPT_FORMS = frozenset({
  "कर्ता", "कर्तारौ", "कर्तारः", "कर्तासि", "कर्तास्मः", "कर्तास्मि",
  "हन्ता", "हन्तारौ", "हन्तारः", "हन्तासि",
  "दाता", "दातारौ", "दातारः",
  "भविता", "भवितारौ", "भवितारः", "भवितासि", "भवितास्मः", "भवितास्मि",
  "वक्ता", "वक्तारौ", "वक्तारः", "भोक्ता", "भोक्तारौ", "भोक्तारः", "द्रष्टा", "स्रष्टा",
  "वेत्ता", "वेत्तासि", "जाता", "जातासि", "जातास्मि", "मातासि", "जनिता", "जनितासि",
})
_LUT_FINITE_RE = re.compile(r"(?:ता|्धा|ोढा|ूढा|ष्टा)(?:सि|स्मि|स्वः|स्मः|स्थः|स्थ)$")
_KIM_INDEF_RE = re.compile(
  r"^(?:कः|किम्|कम्|का|काम्|केन|कया|कस्मै|कस्यै|कस्मात्|कस्याः|कस्य|कस्मिन्|कस्याम्|के|कौ|काः|कानि|कति|कदा|कथम्|कुतः|कुत्र|क्व)$"
)
_NON_TINANTA_CASE_TAIL_RE = re.compile(r"(?:भ्यः|भिः|एषु|आसु|आयै|स्यै|ानाम्|ईनाम्|आनाम्|त्वम्)$")
_UPASARGA_BARE_SET = frozenset({
  "प्र", "परा", "अप", "सम्", "अनु", "अव", "निस्", "निर्", "दुस्", "दुर्",
  "वि", "आ", "नि", "अधि", "अपि", "अति", "सु", "उत्", "उद्", "अभि", "प्रति", "परि", "उप",
})
_BLOCKED_61182_OBLIQUES = frozenset({
  "गवा", "गवे", "गोभिः", "गोभ्यः", "गोसु", "गोः",
  "शुना", "शुने", "शुनः", "शुनि", "श्वभिः", "श्वभ्यः",
  "येभ्यः", "तेभ्यः", "केभ्यः", "येषु", "तेषु", "केषु", "येषाम्", "तेषाम्", "केषाम्",
  "राज्ञा", "राज्ञे", "राज्ञः", "राज्ञि", "राजभिः", "राजभ्यः", "राजसु",
})
_NAJ_62116_STEMS_RE = re.compile(r"^अ(?:जर|मर|मित्र|मृत)")


def _same_clause_preceding_words(flat: Sequence[tuple[str, object]], idx_it: int, window: int = 16) -> list[str]:
  """Collect bare forms preceding ``idx_it`` back to the nearest finite verb or correlative boundary."""
  words: list[str] = []
  for k in range(idx_it - 1, max(-1, idx_it - window), -1):
    prev_it = flat[k][1]
    prev_bare = _strip_marks_for_probe(prev_it.ref)
    prev_prov = prev_it.prov or ""
    if prev_bare in _UPASARGA_BARE_SET or prev_bare in ("निः", "दुः"):
      words.append(prev_bare)
      continue
    if prev_bare == "ते" and ("८.१.१८" in prev_prov or not SVARA_MARK_RE.search(prev_it.ref)):
      words.append(prev_bare)
      continue
    if _FINITE_VERB_PROV_RE.search(prev_prov):
      break
    if prev_bare in _CLAUSE_BOUNDARY_SET:
      # If adverbial `तत्`/`तद्` resumes a leading `यद्`-word across discourse
      # particles (e.g. `य᳓त् वै᳓ त᳓त् न᳓ रस᳓यते`), stay in the relative clause;
      # bare adjacent correlatives like `याः᳓ ताः᳓` still start a new clause.
      if prev_bare in ("तत्", "तद्"):
        m = k - 1
        limit = max(0, idx_it - window)
        while m >= limit and _strip_marks_for_probe(flat[m][1].ref) in (
          _PARTICLE_P0_SET | frozenset({"किल", "खलु", "स्म", "नाम", "नूनम्", "तु"})
        ):
          if _FINITE_VERB_PROV_RE.search(flat[m][1].prov or ""):
            break
          m -= 1
        if m < k - 1 and m >= limit and _strip_marks_for_probe(flat[m][1].ref) in _YAD_RELATIVE_SET:
          words.append(prev_bare)
          continue
      break
    # Skip indefinite relative phrases like `य᳓त् कि᳓म् चि᳓त्` / `यः᳓ क᳓श् चन᳓` / `य᳓त् कि᳓ञ् च`.
    if prev_bare in _YAD_RELATIVE_SET and (
      any(
        _strip_marks_for_probe(flat[m][1].ref) in ("चित्", "चन")
        for m in range(k + 1, min(idx_it, k + 3))
      )
      or (
        k + 2 < idx_it
        and _KIM_INDEF_RE.match(_strip_marks_for_probe(flat[k + 1][1].ref))
        and _strip_marks_for_probe(flat[k + 2][1].ref) == "च"
      )
    ):
      continue
    words.append(prev_bare)
  return words


@dataclasses.dataclass(frozen=True)
class CanonicalPadapathaBlock:
  """One canonical (non-``js_include``) ``पद-पाठः (यान्त्रिकः)`` block with its local context."""

  pp_summary: str
  pp_body: str
  mula: str
  vp: str
  commentaries: dict[str, str]


@dataclasses.dataclass(frozen=True)
class AuditFinding:
  """One diagnostic finding reported by :mod:`auditor`."""

  category: str
  path: str
  line: str
  detail: str = ""


@dataclasses.dataclass
class CorpusAuditReport:
  """Aggregated diagnostic audit results across one or more Markdown files or directory trees."""

  files_scanned: int = 0
  blocks_scanned: int = 0
  findings: list[AuditFinding] = dataclasses.field(default_factory=list)

  def counts(self) -> dict[str, int]:
    return dict(sorted(Counter(f.category for f in self.findings).items()))

  def by_category(self) -> dict[str, list[AuditFinding]]:
    grouped: dict[str, list[AuditFinding]] = defaultdict(list)
    for finding in self.findings:
      grouped[finding.category].append(finding)
    return dict(grouped)

  def to_dict(self) -> dict:
    return {
      "files_scanned": self.files_scanned,
      "blocks_scanned": self.blocks_scanned,
      "counts": self.counts(),
      "findings": [dataclasses.asdict(f) for f in self.findings],
    }

  def format_summary(self, *, max_per_category: int = 10) -> str:
    lines = [
      f"Files scanned: {self.files_scanned} | Canonical padapāṭha blocks: {self.blocks_scanned} | Findings: {len(self.findings)}",
    ]
    counts = self.counts()
    if not counts:
      lines.append("No findings.")
      return "\n".join(lines)
    lines.append("\nCounts by category:")
    for cat, cnt in counts.items():
      lines.append(f"  {cat}: {cnt}")
    if max_per_category > 0:
      grouped = self.by_category()
      for cat, items in sorted(grouped.items()):
        lines.append(f"\n--- {cat} ({len(items)}) ---")
        for it in items[:max_per_category]:
          suffix = f"  [{it.detail}]" if it.detail else ""
          lines.append(f"  {it.path}: {it.line}{suffix}")
        if len(items) > max_per_category:
          lines.append(f"  ... ({len(items) - max_per_category} more)")
    return "\n".join(lines)


def _strip_js_includes(text: str) -> str:
  spans = find_js_include_spans(text)
  if not spans:
    return text
  parts: list[str] = []
  last = 0
  for a, b in sorted(spans):
    if a > last:
      parts.append(text[last:a])
    if b > last:
      last = b
  parts.append(text[last:])
  return "".join(parts)


def _strip_marks_for_probe(s: str) -> str:
  return re.sub(r"[᳓᳙॒᳜॑᳚᳛\-*~\[\]|]", "", s)


def _stem_probes(ar: str, ref: str) -> list[str]:
  probes: set[str] = set()
  for raw in (ar, ref):
    w = _strip_marks_for_probe(raw)
    w = re.sub(r"[ःम्न्]$", "", w)
    if len(w) >= 3:
      probes.add(w[: min(len(w), 5)])
      if len(w) >= 5:
        probes.add(w[:4])
    elif len(w) >= 2:
      probes.add(w)
  return sorted(probes, key=len, reverse=True)


def _commentator_keys_from_title(title: str) -> list[str]:
  keys: list[str] = []
  if "हरदत्त" in title:
    keys.append("हरदत्तः")
  if "भास्कर" in title and "विनियोग" not in title and "अवतारिका" not in title:
    keys.append("भास्करः")
  if "सायण" in title and "विनियोग" not in title:
    keys.append("सायणः")
  if "रङ्ग" in title:
    keys.append("रङ्गरामानुजः")
  if "शङ्कर" in title or "शंकर" in title:
    keys.append("शङ्करः")
  return keys


def _needed_commentators(cited: str) -> list[str]:
  if cited == "हरदत्त-सायणौ":
    return ["हरदत्तः", "सायणः"]
  if cited in ("भास्कर-सायणौ", "सायण-भास्करौ"):
    return ["भास्करः", "सायणः"]
  if cited == "भास्कर-रामानुजौ":
    return ["भास्करः", "रङ्गरामानुजः"]
  if cited == "भट्टभास्करः":
    return ["भास्करः"]
  return [cited]


def extract_canonical_padapatha_blocks(
  markdown_text: str,
  *,
  paired_vp_text: str | None = None,
) -> list[CanonicalPadapathaBlock]:
  """Extract canonical (non-``js_include``) ``पद-पाठः (यान्त्रिकः)`` blocks with surrounding ``मूलम्``, ``विश्वास-प्रस्तुतिः``, and commentaries."""
  own_txt = _strip_js_includes(markdown_text)
  blocks = list(DETAILS_RE.finditer(own_txt))
  vp_paired_clean: str | None = None
  if paired_vp_text is not None:
    vp_body = re.sub(r"^\+\+\+.*?\+\+\+\s*", "", paired_vp_text, flags=re.S)
    vp_paired_clean = _strip_js_includes(vp_body).strip()

  results: list[CanonicalPadapathaBlock] = []
  for idx, m in enumerate(blocks):
    summ = m.group(1).strip()
    if not PP_SUMMARY_RE.match(summ):
      continue
    pp_body = m.group(2)
    mula = ""
    vp = vp_paired_clean
    for j in range(idx - 1, max(-1, idx - 6), -1):
      ps = blocks[j].group(1).strip()
      if ps.startswith("मूलम्") and not mula:
        mula = blocks[j].group(2).strip()
      elif "विश्वास-प्रस्तुतिः" in ps and vp is None:
        vp = blocks[j].group(2).strip()
      elif PP_SUMMARY_RE.match(ps):
        break

    comms: dict[str, str] = {}
    for j in range(idx + 1, min(len(blocks), idx + 12)):
      ns = blocks[j].group(1).strip()
      if ns.startswith("मूलम्") or "विश्वास-प्रस्तुतिः" in ns or PP_SUMMARY_RE.match(ns):
        break
      body = blocks[j].group(2).strip()
      for ckey in _commentator_keys_from_title(ns):
        comms[ckey] = (comms.get(ckey, "") + "\n" + body).strip()

    results.append(
      CanonicalPadapathaBlock(
        pp_summary=summ,
        pp_body=pp_body,
        mula=mula,
        vp=vp or "",
        commentaries=comms,
      )
    )
  return results


def audit_vp_file_for_tiikaa_includes(vp_text: str, *, path: str = "") -> list[AuditFinding]:
  """Flag ``vishvAsa-prastutiH/`` files that ``js_include`` a ``sarvASh_TIkAH/`` file or embed ``पद-पाठः (यान्त्रिकः)``."""
  findings: list[AuditFinding] = []
  for m in _JS_INCLUDE_URL_RE.finditer(vp_text):
    url = m.group(1)
    if "/sarvASh_TIkAH/" in url:
      findings.append(AuditFinding("vp_includes_tiikaa", path, url, "VP file js_includes sarvASh_TIkAH"))
  if not findings and "पद-पाठः (यान्त्रिकः" in vp_text:
    findings.append(AuditFinding("vp_includes_tiikaa", path, "पद-पाठः (यान्त्रिकः)", "VP file contains padapatha block"))
  return findings


def _has_external_ek_vp_include(vp_text: str) -> bool:
  """Return True if ``vp_text`` ``js_include``s a ``vishvAsa-prastutiH`` outside ``ekAgnikANDam/``."""
  for m in _JS_INCLUDE_URL_RE.finditer(vp_text):
    url = m.group(1)
    if "/vishvAsa-prastutiH/" in url and "ekAgnikANDam/" not in url:
      return True
  return False


def _check_provenance_guards(
  it,
  ln: str,
  recent_bare_words: Sequence[str],
  path: str,
  counter: VedicCorpusCounter | None,
  *,
  same_clause_bare_words: Sequence[str] | None = None,
  block_preceding_bare_words: Sequence[str] | None = None,
  prev_bare: str = "",
  next_bare: str = "",
) -> list[AuditFinding]:
  """Run known-antipattern, weak RV/AV override, and optional corpus-counter provenance checks."""
  findings: list[AuditFinding] = []
  prov = it.prov or ""
  old_w = it.ar.strip("* ")
  new_w = it.ref.strip("* ")
  new_bare = _strip_marks_for_probe(new_w)

  # Known false-svara antipatterns (work both offline and with counter).
  if new_bare == "हिंसीः" and SVARA_MARK_RE.search(new_w):
    if (
      "*SB-M*-15" in prov
      or "*SB-K*-32" in prov
      or ("मा" in recent_bare_words and ("८.१.६६" in prov or not SUTRA_REF_RE.search(prov)))
    ):
      findings.append(
        AuditFinding(
          "known_false_svara_antipattern",
          path,
          ln,
          "prohibitive मा ... हिंसीः takes पा॰ ८.१.२८ अनुदात्तम् (not *SB-M*-15/*SB-K*-32 or पा॰ ८.१.६६)",
        )
      )
  if new_bare.startswith("दीप्यमान") and (
    re.search(rf"दीप्य{US_UDATTA}मान", new_w) or "३.१.६७" in prov or "यक्" in prov
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "दीप् takes दिवादि श्यन् पा॰ ३.१.६९ (दी᳓प्यमान), not passive यक् पा॰ ३.१.६७",
      )
    )

  if (
    _KAN_PROV_RE.search(prov)
    and "३.१.३" in prov
    and "६.१.१९७" not in prov
    and "न पा॰ ३.१.३" not in prov
    and "आद्युदात्त" not in prov
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "नित् कन् suffix is ādyudātta by पा॰ ६.१.१९७ (or svārthe कः पा॰ ५.३.७० + ३.१.३), not bare कन् + पा॰ ३.१.३",
      )
    )

  if not SVARA_MARK_RE.search(new_w) and "न पा॰ ८.१.३" not in prov and _AMREDITA_PROV_RE.search(prov):
    if new_bare in _AMREDITA_ENCLITIC_SET or (new_bare == "मा" and "८.१.१०" not in prov):
      findings.append(
        AuditFinding(
          "known_false_svara_antipattern",
          path,
          ln,
          f"Enclitic '{new_bare}' uses पा॰ ८.१.१८–२३ (or पा॰ ८.१.१० for मा मा), not plain पा॰ ८.१.३ āmreḍita",
        )
      )
    elif (
      "-" not in new_w
      and recent_bare_words
      and recent_bare_words[-1] != new_bare
      and "पूर्वकण्डिकान्त" not in prov
      and "पूर्ववाक्य" not in prov
      and not (len(recent_bare_words) >= 2 and recent_bare_words[-1] == "वा" and recent_bare_words[-2] == new_bare)
      and _VOWEL_CASE_TAIL_RE.sub("", recent_bare_words[-1]) != _VOWEL_CASE_TAIL_RE.sub("", new_bare)
    ):
      findings.append(
        AuditFinding(
          "known_false_svara_antipattern",
          path,
          ln,
          f"पा॰ ८.१.३ āmreḍita requires preceding repeated word, found '{recent_bare_words[-1]}' before '{new_bare}'",
        )
      )

  clause_words = same_clause_bare_words if same_clause_bare_words is not None else recent_bare_words
  if (
    it.vyat
    and "८.१.२८" in prov
    and not SVARA_MARK_RE.search(new_w)
    and "यद्" not in prov
    and "मुख्यवाक्य" not in prov
    and "८.१.६६" not in prov
    and "८.१.६४" not in prov
    and any(w in _YAD_RELATIVE_SET for w in clause_words)
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "Same-clause relative यद् blocks पा॰ ८.१.२८ nighāta (keep accent via पा॰ ८.१.६६ or वै/वाव पा॰ ८.१.६४)",
      )
    )

  if (
    "८.१.२८" in prov
    and not SVARA_MARK_RE.search(new_w)
    and ("लुट्" in prov or new_bare in _LUT_EXEMPT_FORMS or _LUT_FINITE_RE.search(new_bare))
    and "८.१.२९" not in prov
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "लुट् (periphrastic future / -तृ) is exempt from पा॰ ८.१.२८ nighāta by पा॰ ८.१.२९ न लुट्",
      )
    )

  if "८.१.५६" in prov and next_bare not in ("यत्", "यद्", "हि", "तु"):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        f"पा॰ ८.१.५६ यद्धितुपरं छन्दसि requires immediately following यत्/हि/तु (found '{next_bare}')",
      )
    )

  if (
    "८.१.२८" in prov
    and not SVARA_MARK_RE.search(new_w)
    and next_bare in ("चन", "चित्", "इव")
    and prev_bare not in _UPASARGA_BARE_SET
    and prev_bare != "निः"
    and "-" not in new_bare
    and "८.१.५७" not in prov
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        f"Verb without preceding गति keeps accent before '{next_bare}' by पा॰ ८.१.५७",
      )
    )
  elif "८.१.५७" in prov and (prev_bare in _UPASARGA_BARE_SET or prev_bare == "निः" or "-" in new_bare):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        f"पा॰ ८.१.५७ applies only without preceding गति (found '{prev_bare}' / '{new_bare}')",
      )
    )

  if _NAJ_62116_STEMS_RE.match(new_bare) and "६.२.१७२" in prov and "६.२.११६" not in prov:
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "नञ् + जर/मर/मित्र/मृत bahuvrīhi takes uttarapada-ādyudātta by पा॰ ६.२.११६, not पा॰ ६.२.१७२",
      )
    )

  if (
    ("६.१.१६८" in prov or "६.१.१७१" in prov)
    and SVARA_MARK_RE.search(new_w)
    and new_bare in _BLOCKED_61182_OBLIQUES
    and "६.१.१८२" not in prov
  ):
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        f"'{new_bare}' blocks पा॰ ६.१.१६८/१७१ case-ending shift by पा॰ ६.१.१८२ न गोश्वन्त्साववर्ण...",
      )
    )

  if "६.१.१७४" in prov and any(tok in new_bare for tok in ("बन्ध्व", "भू", "धू")) and "६.१.१७५" not in prov:
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "ऊङ्/root stems block पा॰ ६.१.१७४ by पा॰ ६.१.१७५ नोङ्धात्वोः (taking पा॰ ८.२.४ svarita)",
      )
    )

  if not SVARA_MARK_RE.search(new_w) and "८.१.७२" in prov and "८.१.७३" not in prov:
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "Unaccented co-referential vocative after initial vocative uses पा॰ ८.१.७३ / ८.१.१९, not पा॰ ८.१.७२",
      )
    )

  if SVARA_MARK_RE.search(new_w) and "८.१.७०" in prov and "कर्मप्रवचनीय" not in prov:
    findings.append(
      AuditFinding(
        "known_false_svara_antipattern",
        path,
        ln,
        "पा॰ ८.१.७० गतिर्गतौ de-accents the preceding गति, never restores an accent",
      )
    )

  if (
    ("८.१.६६" in prov or ("८.१.२८" in prov and "तिङन्त" in prov))
    and "न तिङन्त" not in prov
    and (
      new_bare == "अस्यै"
      or (
        new_bare == "अस्य"
        and "८.१.२८" in prov
        and ("२.४.३२" in prov or bool(re.search(r"\*(?:RV|TS|AV|MS|SB-[KM])\*-[1-9]\d{2,}", prov)))
      )
      or _NON_TINANTA_CASE_TAIL_RE.search(new_bare)
      or any(k in prov for k in ("शतृ", "शानच्", "फि॰", "प्रातिपदिक"))
    )
  ):
    findings.append(
      AuditFinding(
        "non_tinanta_8128_8166",
        path,
        ln,
        f"'{new_w}' appears nominal/participle/pronoun rather than a तिङन्तम् for पा॰ ८.१.२८ / ८.१.६६",
      )
    )

  if (
    "८.१.६६" in prov
    and SVARA_MARK_RE.search(new_w)
    and not any(tok in prov for tok in ("८.१.२८", "८.१.५९", "८.१.६४", "मुख्यवाक्य", "अनेकाख्यात", "चवायोग"))
  ):
    if (
      it.vyat
      and not any(w in _YAD_RELATIVE_SET for w in clause_words)
      and "च" not in clause_words
      and "वा" not in clause_words
    ):
      findings.append(
        AuditFinding(
          "known_false_svara_antipattern",
          path,
          ln,
          "पा॰ ८.१.६६ arrow without same-clause यद्-word (preceding finite verb already closed clause)",
        )
      )
    elif (
      not it.vyat
      and block_preceding_bare_words is not None
      and "पादादि" not in prov
      and not any(
        w in _YAD_RELATIVE_SET or w.startswith(("यद", "यद्", "याव")) or w in ("च", "वा")
        for w in block_preceding_bare_words
      )
    ):
      findings.append(
        AuditFinding(
          "non_arrow_8166_without_yad",
          path,
          ln,
          "पा॰ ८.१.६६ cited on direct bullet with no preceding यद्-word or च/वा in this block",
        )
      )

  corpus_mentions = [(m.group(1), m.group(2)) for m in _TAG_TOKEN_RE.finditer(prov)]
  if not corpus_mentions:
    return findings
  mentioned_corpora = {c for c, _ in corpus_mentions}

  if (
    it.vyat
    and mentioned_corpora <= _RV_AV_ONLY_SET
    and not SUTRA_REF_RE.search(prov)
    and not DASH_COMM_RE.search(prov)
    and not any(tok in prov for tok in ("Weber", "श्रीधरादि", "मते"))
  ):
    is_weak = False
    detail = ""
    if counter is not None:
      yv_old = {c: counter.count_with_stem(old_w, c, allow_stem=True)[1] for c in _YV_CORPORA}
      yv_pos = {c: v for c, v in yv_old.items() if v > 0}
      if yv_pos:
        is_weak = True
        detail = f"RV/AV-only non-Paninian override against YV-attested {old_w} ({yv_pos})"
    elif all(cnt is None or int(cnt) <= 2 for _, cnt in corpus_mentions):
      is_weak = True
      detail = f"RV/AV-only weak non-Paninian override on {old_w}"
    if is_weak:
      findings.append(AuditFinding("weak_rv_av_override", path, ln, detail))

  if counter is None:
    return findings

  if it.vyat:
    seen_bare: set[str] = set()
    for corp, cnt in corpus_mentions:
      if cnt is not None or corp in seen_bare:
        continue
      seen_bare.add(corp)
      _, new_stem = counter.count_with_stem(new_w, corp, allow_stem=True)
      old_exact, old_stem = counter.count_with_stem(old_w, corp, allow_stem=True)
      if new_stem == 0 and old_stem > 0:
        findings.append(
          AuditFinding(
            "false_corpus_citation",
            path,
            ln,
            f"*{corp}*: NEW={new_w} unattested (0) while OLD={old_w} attested ({old_exact}/{old_stem})",
          )
        )
  elif (
    not SUTRA_REF_RE.search(prov)
    and "अनाम्नातम्" not in prov
    and "Weber" not in prov
    and "श्रीधरादि" not in prov
    and not re.search(r"-[1-9]|/[1-9]", prov)
    and all(
      counter.count(new_w, corp) == 0 and counter.count_with_stem(new_w, corp, allow_stem=True)[1] == 0
      for corp in mentioned_corpora
    )
  ):
    yv_hits = {c: counter.count(new_w, c) for c in _YV_CORPORA}
    yv_pos = {c: v for c, v in yv_hits.items() if v > 0}
    if yv_pos:
      findings.append(
        AuditFinding(
          "missing_yv_corpus_counts",
          path,
          ln,
          f"cited={sorted(mentioned_corpora)} all 0 for {new_w}, attested in YV={yv_pos}",
        )
      )

  return findings


def audit_padapatha_markdown(
  markdown_text: str,
  *,
  path: str = "",
  paired_vp_text: str | None = None,
  include_validator_issues: bool = True,
  include_reconciler_diffs: bool = False,
  is_ekAgnikANDam: bool | None = None,
  counter: VedicCorpusCounter | None = None,
) -> tuple[list[AuditFinding], int]:
  """Audit all canonical ``पद-पाठः (यान्त्रिकः)`` blocks in ``markdown_text``.

  Returns ``(findings, blocks_scanned)``.
  """
  findings: list[AuditFinding] = []

  if include_validator_issues:
    if paired_vp_text is not None:
      val_issues = validator.validate_paired_vp_and_tk(paired_vp_text, markdown_text)
    else:
      val_issues = validator.validate_accented_markdown(markdown_text)
    for iss in val_issues:
      findings.append(AuditFinding("validator_issue", path, iss.line or iss.kind, f"{iss.kind}: {iss.message}"))

  if include_reconciler_diffs:
    if paired_vp_text is not None:
      new_vp, logs = reconciler.reconcile_vprastuti_and_tiikaa_texts(paired_vp_text, markdown_text)
      if new_vp != paired_vp_text:
        findings.append(AuditFinding("reconciler_diff", path, f"{len(logs)} VP ops", "; ".join(logs[:3])))
    elif "विश्वास-प्रस्तुतिः" in markdown_text:
      new_md, logs = reconciler.reconcile_markdown_blocks(markdown_text)
      if new_md != markdown_text:
        findings.append(AuditFinding("reconciler_diff", path, f"{len(logs)} inline VP ops", "; ".join(logs[:3])))

  blocks = extract_canonical_padapatha_blocks(markdown_text, paired_vp_text=paired_vp_text)
  norm_path = path.replace(os.sep, "/")
  check_ek = is_ekAgnikANDam if is_ekAgnikANDam is not None else (
    "/ekAgnikANDam/" in norm_path or norm_path.startswith("ekAgnikANDam/")
  )
  if blocks and paired_vp_text and check_ek and _has_external_ek_vp_include(paired_vp_text):
    for blk in blocks:
      findings.append(
        AuditFinding(
          "redundant_ek_external_padapatha",
          path,
          blk.pp_summary,
          "ekAgnikANDam VP js_includes external mantra; move TIkA to target and remove yAntrika pada-pATha",
        )
      )
  for blk in blocks:
    pp_lines = [ln.strip() for ln in blk.pp_body.splitlines() if ln.strip().startswith("- ")]
    parsed = [(ln, parse_padapatha_items(ln)) for ln in pp_lines]
    flat = [(ln, its[0]) for ln, its in parsed if its]

    mula_us = accent.to_US_accents(blk.mula, pauses=r"[।॥,;]+") if blk.mula else ""
    comm_all_text = "\n".join(blk.commentaries.values())
    vp_plain = _strip_marks_for_probe(re.sub(r"\+\+\+.*?\+\+\+", " ", blk.vp))

    for idx_it, (ln, it) in enumerate(flat):
      prov = it.prov
      ar = it.ar
      ref = it.ref
      is_arrow = it.vyat

      # 1. Commentator attribution checks (skipping explicit quoted remarks / मते comparisons)
      if prov and '"' not in prov and "“" not in prov and "मते" not in prov:
        for dm in DASH_COMM_RE.finditer(prov):
          cited = dm.group(1)
          needed = _needed_commentators(cited)
          present = [c for c in needed if c in blk.commentaries]
          if len(present) < len(needed):
            findings.append(
              AuditFinding("commentator_missing_block", path, ln, f"cited={cited}, local={sorted(blk.commentaries)}")
            )
            continue
          combined = re.sub(r"स्वरू\S*", "", "\n".join(blk.commentaries[c] for c in present))
          probes = _stem_probes(ar, ref)
          sents = re.split(r"[।॥\n]+", combined)
          matched = [s.strip() for s in sents if any(p in s for p in probes)]
          if not any(STRICT_COMM_SVARA_RE.search(s) for s in matched):
            findings.append(
              AuditFinding("commentator_unstated_svara", path, ln, f"cited={cited}, probes={probes[:2]}")
            )

      # 2. पा॰ ८.२.४ svarita ᳙ placement check
      if "८.२.४" in prov and US_SVARITA in ref:
        m_sv = re.search(rf"([^\s{US_UDATTA}{US_SVARITA}\-]*){US_SVARITA}", ref)
        if m_sv:
          seg = m_sv.group(1)
          has_yan = bool(re.search(r"[यवरल][ािीुूृॄेैोौँंः]*$", seg))
          if not has_yan:
            findings.append(AuditFinding("svarita_824_placement", path, ln, f"svarita_seg={seg}"))

      # 3. False dual-udātta / ekādeśa boundary check
      if is_arrow and len(SVARA_MARK_RE.findall(ar)) >= 2:
        nxt = flat[idx_it + 1][1] if idx_it + 1 < len(flat) else None
        if nxt is not None:
          nxt_bare = _strip_marks_for_probe(nxt.ref)
          if nxt_bare and nxt_bare[0] in "अआइईउऊऋॠएऐओऔ" and not SVARA_MARK_RE.search(nxt.ar):
            findings.append(
              AuditFinding("ekadesha_multi_accent_ar", path, ln, f"next={nxt.ar}->{nxt.ref}")
            )

      # 4a. Non-initial पा॰ ६.१.१९८ vocative candidate (skip when valid पा॰ ८.१.७२ follows initial vocative)
      prev_prov = flat[idx_it - 1][1].prov if idx_it > 0 else ""
      has_8172_after_init_voc = (
        "८.१.७२" in prov and idx_it > 0 and ("६.१.१९८" in prev_prov or "पादादि" in prev_prov)
      )
      if (
        idx_it > 0
        and SVARA_MARK_RE.search(ref)
        and ("६.१.१९८" in prov or re.search(r"(?<!अ)पादादावामन्त्रित", prov) is not None)
        and not has_8172_after_init_voc
      ):
        # Quick check: does bare word start a line or follow a danda in mula or vp?
        bare_w = _strip_marks_for_probe(ref)
        stem = bare_w[:-1] if len(bare_w) >= 4 else bare_w
        src_bare = accent.strip_accents((blk.mula + "\n" + blk.vp).strip())
        stem_probe = stem[: min(len(stem), 4)]
        at_boundary = bool(
          stem_probe and re.search(rf"(?:^|[।॥\n]\s*){re.escape(stem_probe)}", src_bare)
        )
        if not at_boundary:
          findings.append(AuditFinding("non_initial_61198_vocative", path, ln, f"idx={idx_it}"))

      # 4b. Possible missed vocative (0-accent ar -> accented ref, or non-arrow accented ref when mula/VP has unaccented form,
      #     while commentary has `हे ... <stem>` or VP has `<stem>!`)
      if SVARA_MARK_RE.search(ref):
        bare_w = _strip_marks_for_probe(ref)
        stem = bare_w[:-1] if len(bare_w) > 2 else bare_w
        unaccented_in_source = (
          (is_arrow and not SVARA_MARK_RE.search(ar))
          or (
            not is_arrow
            and idx_it > 0
            and bare_w
            and f"[[{bare_w}|{ref.strip('* ')}]]" in blk.vp
          )
          or (
            not is_arrow
            and idx_it > 0
            and stem
            and bool(re.search(rf"{re.escape(stem)}[^\s{US_UDATTA}{US_SVARITA}]*(?=\s|[।॥]|$)", mula_us))
            and not bool(re.search(rf"{re.escape(stem)}[^\s]*[{US_UDATTA}{US_SVARITA}]", mula_us))
          )
        )
        if (
          unaccented_in_source
          and stem
          and (is_arrow or not any(t in prov for t in ("आमन्त्रित", "६.१.१९८", "८.१.१९")))
          and re.search(rf"(?:हे\s+{re.escape(stem[:-1] if len(stem) >= 4 else stem)}|{re.escape(stem)}[^\s]*!)", comm_all_text + "\n" + blk.vp)
        ):
          findings.append(AuditFinding("possible_missed_vocative", path, ln, f"stem={stem}"))

      # 5. MW-only / weak provenance arrow (neither counted corpus tag nor sūtra)
      if is_arrow and not CORPUS_COUNT_TAG_RE.search(prov) and not SUTRA_REF_RE.search(prov):
        findings.append(AuditFinding("mw_only_arrow", path, ln))

      # 6. Mūla independent svarita ᳙ misread as ᳓ in arrow `ar`
      if is_arrow and US_SVARITA in mula_us and US_UDATTA in ar and US_SVARITA not in ar:
        bare_ar = _strip_marks_for_probe(ar)
        if len(bare_ar) >= 3 and re.search(rf"{re.escape(bare_ar[:3])}[^\s]*{US_SVARITA}", mula_us):
          findings.append(AuditFinding("mula_svarita_misread", path, ln))

      # 7. False compound candidate (spaced in VP or inflected/enclitic first member on arrow)
      if "-" in ref:
        parts = ref.split("-")
        p0_bare = _strip_marks_for_probe(parts[0])
        p1_bare = _strip_marks_for_probe(parts[1]) if len(parts) > 1 else ""
        p1_probe = p1_bare[:-1] if len(p1_bare) >= 4 else p1_bare
        p0_root = re.sub(r"[ःम्न्]$", "", p0_bare)
        p0_tail = p0_root[1:] if len(p0_root) >= 2 and p0_root[0] in "अआइईउऊऋएऐओऔ" else ""
        vp_tokens = vp_plain.split()
        has_concat_tok = bool(
          len(p0_root) >= 2
          and len(p1_probe) >= 2
          and any(
            (
              p0_root in tok
              and p1_probe[: min(len(p1_probe), 4)] in tok[max(0, tok.find(p0_root) + len(p0_root) - 1) :]
            )
            or (
              p0_tail
              and re.search(
                rf"[ािीुूृेैोौ]{re.escape(p0_tail)}.{{0,2}}{re.escape(p1_probe[:3])}",
                tok,
              )
            )
            for tok in vp_tokens
          )
        )
        vp_spaced = bool(
          not has_concat_tok
          and p0_bare
          and p1_probe
          and len(p0_bare) >= 2
          and len(p1_probe) >= 2
          and re.search(rf"(?:^|\s){re.escape(p0_bare)}\s+{re.escape(p1_probe)}", vp_plain)
        )
        suspicious_p0 = bool(is_arrow and (_INFLECTED_P0_ENDINGS_RE.search(p0_bare) or p0_bare in _PARTICLE_P0_SET))
        if vp_spaced or suspicious_p0:
          findings.append(
            AuditFinding("false_compound_candidate", path, ln, f"vp_spaced={vp_spaced}, p0={p0_bare}")
          )

      # 8. Provenance guard checks (known antipatterns, weak RV/AV overrides, bare/missing YV citations)
      recent_bare = [_strip_marks_for_probe(flat[k][1].ref) for k in range(max(0, idx_it - 3), idx_it)]
      block_preceding_bare = [_strip_marks_for_probe(flat[k][1].ref) for k in range(idx_it)]
      clause_bare = _same_clause_preceding_words(flat, idx_it)
      prev_bare = _strip_marks_for_probe(flat[idx_it - 1][1].ref) if idx_it > 0 else ""
      next_bare = _strip_marks_for_probe(flat[idx_it + 1][1].ref) if idx_it + 1 < len(flat) else ""
      new_tok = ref.strip("* ")
      prev_prov_gati = (flat[idx_it - 1][1].prov or "") if idx_it > 0 else ""
      if (
        idx_it > 0
        and not SVARA_MARK_RE.search(new_tok)
        and "८.१.७०" in prov
        and prev_bare in _UPASARGA_BARE_SET
        and SVARA_MARK_RE.search(flat[idx_it - 1][1].ref)
        and "कर्मप्रवचनीय" not in prev_prov_gati
        and "कर्मप्रवचनीय" not in prov
      ):
        findings.append(
          AuditFinding(
            "known_false_svara_antipattern",
            path,
            ln,
            f"पा॰ ८.१.७० गतिर्गतौ de-accents preceding गति ('{flat[idx_it - 1][1].ref}'), not '{(ar if is_arrow else ref).strip('* ')}'",
          )
        )
      findings.extend(
        _check_provenance_guards(
          it,
          ln,
          recent_bare,
          path,
          counter,
          same_clause_bare_words=clause_bare,
          block_preceding_bare_words=block_preceding_bare,
          prev_bare=prev_bare,
          next_bare=next_bare,
        )
      )

  return findings, len(blocks)


def _paired_vp_path(tk_path: str) -> str | None:
  if "/sarvASh_TIkAH/" in tk_path:
    vp = tk_path.replace("/sarvASh_TIkAH/", "/vishvAsa-prastutiH/")
    if os.path.exists(vp):
      return vp
  return None


def audit_directory_trees(
  roots: Sequence[str],
  *,
  include_validator_issues: bool = True,
  include_reconciler_diffs: bool = False,
  check_vp_tiikaa_includes: bool = True,
  base_dir: str | None = None,
  counter: VedicCorpusCounter | None = None,
) -> CorpusAuditReport:
  """Walk ``roots`` and audit all Markdown files containing canonical ``पद-पाठः (यान्त्रिकः)`` blocks."""
  report = CorpusAuditReport()
  seen: set[str] = set()
  for root in roots:
    if not os.path.exists(root):
      continue
    if os.path.isfile(root):
      candidates = [root]
    else:
      candidates = []
      for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
          if fn.endswith(".md"):
            candidates.append(os.path.join(dp, fn))
    for path in candidates:
      ap = os.path.abspath(path)
      if ap in seen:
        continue
      seen.add(ap)
      rel = os.path.relpath(ap, base_dir) if base_dir else ap
      with open(ap, encoding="utf-8", errors="ignore") as f:
        txt = f.read()

      if "/vishvAsa-prastutiH/" in ap:
        if check_vp_tiikaa_includes:
          report.findings.extend(audit_vp_file_for_tiikaa_includes(txt, path=rel))
        norm_ap = ap.replace(os.sep, "/")
        if "/ekAgnikANDam/vishvAsa-prastutiH/" in norm_ap and _has_external_ek_vp_include(txt):
          report.findings.append(
            AuditFinding(
              "redundant_ek_external_wrapper",
              rel,
              "js_include",
              "ekAgnikANDam VP js_includes external mantra; delete wrapper pair and replace host refs",
            )
          )
        continue

      if "पद-पाठः (यान्त्रिकः" not in txt:
        continue

      vp_path = _paired_vp_path(ap)
      vp_txt = open(vp_path, encoding="utf-8", errors="ignore").read() if vp_path else None
      report.files_scanned += 1
      file_findings, n_blocks = audit_padapatha_markdown(
        txt,
        path=rel,
        paired_vp_text=vp_txt,
        include_validator_issues=include_validator_issues,
        include_reconciler_diffs=include_reconciler_diffs,
        is_ekAgnikANDam=("/ekAgnikANDam/" in ap.replace(os.sep, "/")),
        counter=counter,
      )
      report.blocks_scanned += n_blocks
      report.findings.extend(file_findings)
  return report


def main(argv: Sequence[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    description="Audit Vedic padapāṭha (पद-पाठः (यान्त्रिकः)) and विश्वास-प्रस्तुतिः Markdown files."
  )
  parser.add_argument("roots", nargs="+", help="Markdown files or directories to audit")
  parser.add_argument("--base-dir", default=None, help="Base directory for relative paths in report output")
  parser.add_argument("--no-validator", action="store_true", help="Skip validator.py checks")
  parser.add_argument("--with-reconciler", action="store_true", help="Check for pending reconciler VP diffs")
  parser.add_argument(
    "--with-corpus-counter",
    action="store_true",
    help="Load VedicCorpusCounter to check bare corpus tags and YV attestations",
  )
  parser.add_argument("--categories", nargs="*", default=None, help="Filter reported findings to these categories")
  parser.add_argument("--max-per-category", type=int, default=15, help="Max sample findings printed per category")
  parser.add_argument("--json", dest="json_out", default=None, help="Write full JSON audit report to this file")
  args = parser.parse_args(argv)

  counter = VedicCorpusCounter.load_or_build() if args.with_corpus_counter else None
  report = audit_directory_trees(
    args.roots,
    include_validator_issues=not args.no_validator,
    include_reconciler_diffs=args.with_reconciler,
    base_dir=args.base_dir,
    counter=counter,
  )
  if args.categories:
    allowed = set(args.categories)
    report.findings = [f for f in report.findings if f.category in allowed]

  print(report.format_summary(max_per_category=args.max_per_category))
  if args.json_out:
    with open(args.json_out, "w", encoding="utf-8") as f:
      json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"\nWrote JSON report to {args.json_out}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
