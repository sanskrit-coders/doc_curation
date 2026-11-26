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
  r"(?:प्रति\s*तिष्ठति|प्रति\s*तिष्ठन्ति|प्रति\s*तिष्ठापयति|प्रत्यतिष्ठत्|(?:अव|(?<=[क-ह])व)\s*रुन्धे|(?:अ|(?<=[क-ह]))वरुन्धते|एव\s*वेद|असृजत|भवति|भवतः|भवन्ति|"
  r"करोति|कुर्वन्ति|भविष्यति|भविष्यन्ति|साद्यन्ते|प्रतिगृह्णाति|अपक्रामति|अजायेताम्|अजायन्त|अवद्यति|असिञ्चत्|आसीत्|"
  r"निर्वपेत्|आलभेत|जुहोति|जुह्वति|जुहुयात्|यजति|यजन्ति|यजते|दधाति|दधति|पधावति|उपधावति|परिगृह्णाति|खनति|गृह्णाति|समर्धयति|वदन्ति|अन्तरेति|"
  r"प्रसूत्यै|समष्ट्यै|अभिजित्यै|अनवच्छित्त्यै|शान्त्यै|विजिती|इत्याह|कुर्वीत|लोकम्\s*एति|व्यार्ध्यत|अपतत्|ऽपतत्|अगच्छत्|"
  r"वीर्यावत्तर|मन्यमानः|(?:^|\s)वै(?=\s|$)|(?:^|\s)वा\s+(?:एत|अय|इय|अधि|इद)|^(?:तस्मा(?:त्|द्)?|अथो?|अथ\s+यो)\s)"
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
  is_yantra_svara: bool = False  # True when accents are synthetic Viterbi rather than manuscript-attested
  host_path: str = ""
  slot_key: str = ""


_BRAHMANA_CORPORA = frozenset({"SB-M", "SB-K", "TB", "TS", "TA"})

_SBK_TO_SBM_KANDAS: dict[str, tuple[str, ...]] = {
  "01": ("02",),
  "02": ("01",),
  "04": ("03",),
  "05": ("04",),
  "06": ("05",),
  "07": ("05",),
  "08": ("06",),
  "09": ("07",),
  "10": ("08",),
  "11": ("09", "08"),
  "12": ("10",),
  "13": ("11",),
  "14": ("12",),
  "15": ("13",),
  "16": ("14",),
  "17": ("14",),
}

_BRAHMANA_PROSE_CUES_RE = re.compile(
  r"(?:ह\s+वै|तस्मा[द्त्]|स\s+यः|स\s+यदा|यदा?\s+वै|एतद्\s*वै|अथ\s+(?:खलु|एते|ह|वै)|"
  r"जुहोति|भवति|भवन्ति|अभव[त्न्]|उवाच|होवाच|ब्रवीति|अब्रवी[द्त्]|इत्याह|आह|"
  r"असृजत|अस्पर्धन्त|दधाति|आधत्ते|विजहाति|उपजगाम|अगच्छत्|अशकत|"
  r"उदक्रामत्|अक्रामत्|प्राविशत्|प्रविशति|सम्पद्यते|सम्पद्यन्ते|प्रभवति)"
)
_YAJUH_FORMULA_CUES_RE = re.compile(r"(?:स्वाहा|स्वधा|वषट्|नमः|उपयामगृहीतो|जुषताम्)(?:\s*[।॥\d०-९]*)?$")


def _kanda_num(rel: str) -> str:
  first = (rel or "").split("/", 1)[0].split("_", 1)[0]
  m = re.match(r"^(\d+)$", first)
  return f"{int(m.group(1)):02d}" if m else ""


def _sb_kanda_alignment_rank(src_corpus: str, src_rel: str, tgt_corpus: str, tgt_rel: str) -> int:
  """Return 0 when two ŚB paths belong to corresponding kāṇḍas, 1 otherwise."""
  if not src_rel or not tgt_rel:
    return 1
  sk = _kanda_num(src_rel)
  tk = _kanda_num(tgt_rel)
  if not sk or not tk:
    return 1
  if src_corpus == "SB-K" and tgt_corpus == "SB-M":
    return 0 if tk in _SBK_TO_SBM_KANDAS.get(sk, ()) else 1
  if src_corpus == "SB-M" and tgt_corpus == "SB-K":
    return 0 if sk in _SBK_TO_SBM_KANDAS.get(tk, ()) else 1
  if src_corpus == tgt_corpus:
    return 0 if sk == tk else 1
  return 1


def _allow_brahmana_pair(src_corpus: str, tgt_corpus: str) -> bool:
  if src_corpus in ("SB-M", "SB-K") and tgt_corpus in _BRAHMANA_CORPORA:
    return True
  if tgt_corpus in ("SB-M", "SB-K") and src_corpus in _BRAHMANA_CORPORA:
    return True
  return False


def classify_unit_kind(vp_text: str, *, summary: str = "", default_brahmana: bool = False) -> str:
  """Classify a cluster as ``'rk'``, ``'yajuh'``, or ``'brahmana'``."""
  if "ऋक्" in summary:
    return "rk"
  plain = _ACCENT_STRIP_RE.sub("", vp_text)
  plain = re.sub(r"\[\[([^|\]]*)\|[^\]]*\]\]", r"\1", plain)
  plain = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", plain, flags=re.S).strip()
  lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
  norm_plain = re.sub(r"\s+", " ", plain)
  has_brahmana_cues = bool(_BRAHMANA_PROSE_CUES_RE.search(norm_plain))
  if looks_prose_brahmana(vp_text, len(re.sub(r"\s+", "", norm_plain)), summary=summary):
    return "brahmana"
  if has_brahmana_cues:
    return "brahmana"
  if _YAJUH_FORMULA_CUES_RE.search(norm_plain) and len(lines) <= 2:
    return "yajuh"
  if len(lines) >= 2 and (not default_brahmana or ("॥" in norm_plain and not norm_plain.endswith(("इति ।", "इति", "इति ॥")))):
    return "rk"
  if default_brahmana:
    return "yajuh" if _YAJUH_FORMULA_CUES_RE.search(norm_plain) else "brahmana"
  return "yajuh"


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
  trust_consonants_as_exact: bool = False,
) -> tuple[bool, float, bool]:
  """Return ``(matched, similarity_ratio, is_exact_reading)`` using strict edge-anchored guards."""
  min_len = min(len(pb_a), len(pb_b))
  if min_len < min_len_exact:
    return False, 0.0, False
  if is_no_patha_bheda(vp_a, vp_b) or (trust_consonants_as_exact and pb_a == pb_b):
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
    src_rel: str = "",
    allow_variant: bool = True,
    exclude_path: str = "",
    allow_target_variants_from_inline: bool = False,
    allow_self_static: bool = False,
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

    exact_hits: list[tuple[int, int, float, int, TargetEntry]] = []
    var_hits: list[tuple[float, int, int, int, TargetEntry]] = []
    top = sorted(
      cands,
      key=lambda i: (
        -cands[i],
        self.priority.get(self.entries[i].corpus, 99),
        _sb_kanda_alignment_rank(src_corpus, src_rel, self.entries[i].corpus, self.entries[i].rel),
        i,
      ),
    )[:64]

    for ri in top:
      ent = self.entries[ri]
      if ent.corpus == src_corpus:
        if not (allow_self_static and ent.kind != "inline"):
          continue
      if exclude_path and ent.vp_path == exclude_path:
        continue
      brahmana_pair = _allow_brahmana_pair(src_corpus, ent.corpus)
      if src_prose and ent.kind == "inline" and not brahmana_pair:
        continue
      is_rk_like = ent.kind == "rk_2part" or "ऋक्" in src_summary
      ent_is_brahmana = brahmana_pair and (
        src_prose
        or ent.kind in ("brahmana_combined", "brahmana_2part")
        or classify_unit_kind(vp, summary=src_summary) == "brahmana"
        or classify_unit_kind(ent.vp) == "brahmana"
      )
      ent_allow_var = allow_variant and (
        ent_is_brahmana
        or not (
          src_prose
          or (ent.kind in ("inline", "yajuh_combined") and not allow_target_variants_from_inline and not is_rk_like)
        )
      )
      if ent_is_brahmana:
        min_exact = 22
        min_var = 35
        min_rat = 0.90 if src_corpus in ("SB-M", "SB-K") and ent.corpus in ("SB-M", "SB-K") else 0.92
      else:
        min_exact = 35 if (
          src_prose or (ent.kind == "inline" and src_corpus in ("TB", "TK", "MS", "KS") and ent.corpus != "VS-M" and not is_rk_like)
        ) else 20
        min_var = 30
        min_rat = 0.88
      trust_cons = src_corpus == "KS" and "यन्त्र-स्वरः" in src_summary and not ent.is_yantra_svara
      matched, rat, eq = classify_match(
        vp, pb, ent.vp, ent.pb,
        allow_variant=ent_allow_var,
        min_len_exact=min_exact,
        min_len_var=min_var,
        min_ratio=min_rat,
        trust_consonants_as_exact=trust_cons,
      )
      if not matched:
        continue
      prio = self.priority.get(ent.corpus, 99)
      align_r = _sb_kanda_alignment_rank(src_corpus, src_rel, ent.corpus, ent.rel)
      if eq:
        exact_hits.append((prio, align_r, -cands[ri], ri, ent))
      else:
        var_hits.append((-round(rat, 4), prio, align_r, ri, ent))

    if exact_hits:
      exact_hits.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
      return exact_hits[0][4], 1.0, True
    if var_hits:
      var_hits.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
      return var_hits[0][4], -var_hits[0][0], False
    return None
