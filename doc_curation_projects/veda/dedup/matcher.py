"""Precision 5-gram inverted index and mantra/Brāhmaṇa matching guards for cross-Veda dedup."""
from __future__ import annotations

import dataclasses
import difflib
import re
from collections import defaultdict
from typing import Sequence

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  is_no_patha_bheda,
  normalize_phonetic,
)

# Short Brāhmaṇa prose clichés/arthavāda verbs that recur across unrelated ritual contexts.
_PROSE_ARTHAVADA_CLICHE_RE = re.compile(
  r"(?:प्रति\s*तिष्ठति|प्रति\s*तिष्ठन्ति|प्रत्यतिष्ठत्|अव\s*रुन्धे|अवरुन्धते|एव\s*वेद|असृजत|भवति|भवन्ति|"
  r"यजति|यजन्ति|यजते|दधाति|दधति|पधावति|उपधावति|परिगृह्णाति|खनति|गृह्णाति|समर्धयति|वदन्ति|अन्तरेति|प्रसूत्यै|"
  r"समष्ट्यै|अभिजित्यै|अनवच्छित्त्यै|शान्त्यै|विजिती|इत्याह|कुर्वीत|लोकम्\s*एति|व्यार्ध्यत|अपतत्|ऽपतत्|अगच्छत्|"
  r"वीर्यावत्तर|मन्यमानः|^(?:तस्माद्?|अथो)\s)"
)
_ACCENT_STRIP_RE = re.compile(r"\+\+\+.*?\+\+\+|[᳓᳙\u0951\u0952\*]|(?<=[\u0900-\u097f])-(?=[\u0900-\u097f])")


@dataclasses.dataclass
class TargetEntry:
  """One indexed canonical or promotable target passage in an upstream Vedic corpus."""

  corpus: str
  kind: str  # "rk_2part", "yajuh_2part", "yajuh_combined", "inline"
  rel: str
  vp: str
  pb: str
  vp_path: str = ""
  sarva_path: str = ""
  vp_url: str = ""
  sarva_url: str = ""
  combined_url: str = ""
  av_inline: bool = False  # True if the source/static file contains सर्वा अवतारिकाः
  host_path: str = ""
  slot_key: str = ""


def looks_prose_brahmana(vp_text: str, pb_len: int, *, summary: str = "") -> bool:
  """Return True when a short block looks like contextual Brāhmaṇa arthavāda prose rather than a mantra."""
  if "ऋक्" in summary:
    return False
  lines = [ln for ln in vp_text.strip().splitlines() if ln.strip()]
  plain = _ACCENT_STRIP_RE.sub("", vp_text).strip()
  if len(lines) >= 3 or any(m in plain for m in ("स्वाहा", "स्वधा", "वषट्")):
    return False
  if pb_len < 120 and _PROSE_ARTHAVADA_CLICHE_RE.search(re.sub(r"\s+", " ", plain)):
    return True
  return False


def classify_match(
  vp_a: str,
  pb_a: str,
  vp_b: str,
  pb_b: str,
  *,
  allow_variant: bool = True,
  min_len_exact: int = 20,
  min_len_var: int = 30,
  min_ratio: float = 0.88,
) -> tuple[bool, float, bool]:
  """Return ``(matched, similarity_ratio, is_exact_reading)`` using strict edge-anchored guards."""
  min_len = min(len(pb_a), len(pb_b))
  if min_len < min_len_exact:
    return False, 0.0, False
  if is_no_patha_bheda(vp_a, vp_b):
    return True, 1.0, True
  if not allow_variant or min_len < min_len_var:
    return False, 0.0, False
  if abs(len(pb_a) - len(pb_b)) > max(12, int(0.18 * min_len)):
    return False, 0.0, False

  rat = 1.0 if pb_a == pb_b else difflib.SequenceMatcher(None, pb_a, pb_b).ratio()
  if rat < min_ratio:
    return False, rat, False
  k = min(14, len(pb_a) // 3, len(pb_b) // 3)
  if k >= 6:
    pref_r = difflib.SequenceMatcher(None, pb_a[:k], pb_b[:k]).ratio()
    suff_r = difflib.SequenceMatcher(None, pb_a[-k:], pb_b[-k:]).ratio()
    if pref_r < 0.65 or suff_r < 0.65:
      return False, rat, False
  return True, rat, False


class InvertedVedaIndex:
  """5-gram index over ordered upstream target entries."""

  def __init__(self, entries: Sequence[TargetEntry], corpus_priority: Sequence[str]):
    self.entries = list(entries)
    self.priority = {c: idx for idx, c in enumerate(corpus_priority)}
    self.grams: dict[str, list[int]] = defaultdict(list)
    for idx, ent in enumerate(self.entries):
      pb = ent.pb
      for pos in range(max(1, len(pb) - 4)):
        self.grams[pb[pos : pos + 5]].append(idx)

  def add_entry(self, entry: TargetEntry) -> int:
    idx = len(self.entries)
    self.entries.append(entry)
    pb = entry.pb
    for pos in range(max(1, len(pb) - 4)):
      self.grams[pb[pos : pos + 5]].append(idx)
    return idx

  def find_best(
    self,
    vp: str,
    *,
    src_summary: str = "",
    src_corpus: str = "",
    allow_variant: bool = True,
    exclude_path: str = "",
    allow_target_variants_from_inline: bool = False,
  ) -> tuple[TargetEntry, float, bool] | None:
    """Find best matching upstream TargetEntry, preferring exact reading over minor pāṭha variant."""
    pb = normalize_phonetic(vp, include_accents=False, fold_orthography=True)
    if len(pb) < 20:
      return None
    src_prose = looks_prose_brahmana(vp, len(pb), summary=src_summary)
    cands: dict[int, int] = defaultdict(int)
    for pos in range(max(1, len(pb) - 4)):
      for ri in self.grams.get(pb[pos : pos + 5], ()):
        cands[ri] += 1
    if not cands:
      return None

    exact_hits: list[tuple[int, float, int, TargetEntry]] = []
    var_hits: list[tuple[float, int, int, TargetEntry]] = []
    top = sorted(cands, key=lambda i: (-cands[i], self.priority.get(self.entries[i].corpus, 99), i))[:36]

    for ri in top:
      ent = self.entries[ri]
      if ent.corpus == src_corpus:
        continue
      if exclude_path and ent.vp_path == exclude_path:
        continue
      if src_prose and ent.kind == "inline":
        continue
      is_rk_like = ent.kind == "rk_2part" or "ऋक्" in src_summary
      ent_allow_var = allow_variant and not (
        src_prose
        or (ent.kind in ("inline", "yajuh_combined") and not allow_target_variants_from_inline and not is_rk_like)
      )
      min_exact = 35 if (src_prose or (ent.kind == "inline" and src_corpus in ("TB", "TK"))) else 20
      matched, rat, eq = classify_match(
        vp, pb, ent.vp, ent.pb,
        allow_variant=ent_allow_var,
        min_len_exact=min_exact,
        min_len_var=30,
        min_ratio=0.88,
      )
      if not matched:
        continue
      prio = self.priority.get(ent.corpus, 99)
      if eq:
        exact_hits.append((prio, -cands[ri], ri, ent))
      else:
        var_hits.append((-round(rat, 4), prio, ri, ent))

    if exact_hits:
      exact_hits.sort(key=lambda x: (x[0], x[1], x[2]))
      return exact_hits[0][3], 1.0, True
    if var_hits:
      var_hits.sort(key=lambda x: (x[0], x[1], x[2]))
      return var_hits[0][3], -var_hits[0][0], False
    return None
