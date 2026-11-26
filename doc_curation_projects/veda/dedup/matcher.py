"""Precision 5-gram inverted index and mantra/Brāhmaṇa matching guards for cross-Veda dedup."""
from __future__ import annotations

import dataclasses
import difflib
import heapq
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
  kind: str  # "rk_2part", "yajuh_2part", "yajuh_combined", "brahmana_2part", "brahmana_combined", "inline", "inline_vp_shared_sarva"
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
  "03": ("02", "11"),
  "04": ("03",),
  "05": ("04",),
  "06": ("05",),
  "07": ("05",),
  "08": ("06", "07"),
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
  r"जुहोति|भवति|भवन्ति|अभव[त्न्]|उवाच|होवाच|ब्रवीति|अब्रवी[द्त्]|इत्याह|आह|अकामयत|"
  r"असृजत|अस्पर्धन्त|दधाति|आधत्ते|विजहाति|उपजगाम|अगच्छत्|अशकत|"
  r"उदक्रामत्|अक्रामत्|प्राविशत्|प्रविशति|सम्पद्यते|सम्पद्यन्ते|प्रभवति)"
)
_DEFAULT_BRAHMANA_PROSE_CUES_RE = re.compile(
  r"वै(?![\u0900-\u097f])|(?<![\u0900-\u097f])(?:हि|ह|अथ|अथाह|उवाच|होवाच|तदाहुः|तद्यत्|तस्मा[द्त्]|"
  r"भवति|भवन्ति|जुहोति|आह|ब्रूया[द्त्]|करोति|जायते|पश्यति|एवम्)(?![\u0900-\u097f])|"
  r"(?:अब्रवी[द्त्]|अब्रुवन्|अभिषिञ्चति|अभिषिञ्चन्ति|अकामयत|सादयति|दधाति)(?![\u0900-\u097f])|"
  r"वा\s+अ|ह्येत"
)
_YAJUH_FORMULA_CUES_RE = re.compile(r"(?:स्वाहा|स्वाहेति|स्वधा|स्वधेति|वषट्|वषडिति|नमः|उपयामगृहीतो|जुषताम्)(?:\s*[।॥\d०-९]*)?$")
_CHANDAS_ACCENT_STRIP_RE = re.compile(r"[\u1cd0-\u1cff\u0951-\u0954\ua8e0-\ua8f1\u200c\u200d\u00b2\u00b3\u00b9\u2070-\u2079]")
_METRICAL_STD_NAMES = (
  "anuṣṭup", "triṣṭup", "jagatī", "gāyatrī", "uṣṇik", "bṛhatī", "paṅkti",
  "upajāti", "indravajrā", "upendravajrā", "vaṃśastha", "śālinī", "virāṭ", "svarāṭ",
)


def _strip_markup_for_kind(vp_text: str) -> str:
  plain = _CHANDAS_ACCENT_STRIP_RE.sub("", _ACCENT_STRIP_RE.sub("", vp_text))
  plain = re.sub(r"\[\[([^|\]]*)\|[^\]]*\]\]", r"\1", plain)
  plain = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|\*\*|__|[*~]", " ", plain, flags=re.S)
  return plain.strip()


def _is_metrical_verse(vp_text: str) -> bool:
  """Return True when a multi-line cluster is a true metrical ṛk/śloka verified with ``chandas``."""
  if any(x in vp_text for x in ("—", "–", "?", "!")):
    return False
  plain = _strip_markup_for_kind(vp_text)
  raw_lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
  if not (2 <= len(raw_lines) <= 6):
    return False
  if not re.search(r"॥\s*[०-९0-9\s\.\-]*॥?\s*$", raw_lines[-1]):
    return False
  lines = [re.sub(r"[।॥०-९0-9]+$", "", ln).strip() for ln in raw_lines]
  joined = " ".join(lines)
  if re.search(r"(?<![\u0900-\u097f])इति(?![\u0900-\u097f])", joined):
    return False
  if _BRAHMANA_PROSE_CUES_RE.search(joined) or _DEFAULT_BRAHMANA_PROSE_CUES_RE.search(joined):
    return False
  try:
    from chandas import svat_identifier, to_pattern_lines
    from chandas.syllabize import get_syllables
  except Exception:
    return False
  def _safe_syl_cnt(line_s: str) -> int | None:
    cl = re.sub(r"(?:^|\s)ऽ", " अ", line_s).replace("ऽ", "अ").strip()
    if not cl:
      return 0
    try:
      return len(get_syllables(cl))
    except ValueError:
      return None

  lines = [re.sub(r"(?:^|\s)ऽ", " अ", ln).strip() for ln in lines]
  syl_counts: list[int] = []
  for ln in lines:
    sc = _safe_syl_cnt(ln)
    if sc is None:
      return False
    syl_counts.append(sc)
  if min(syl_counts) < 6 or (len(lines) == 2 and min(syl_counts) < 12):
    return False
  if max(syl_counts) / max(1, min(syl_counts)) > 1.35:
    return False
  cands: list[list[str]] = [lines]
  if len(lines) == 2:
    halves: list[str] = []
    for ln in lines:
      ws = ln.split()
      if len(ws) < 2:
        break
      tot = _safe_syl_cnt(ln)
      if tot is not None and 13 <= tot <= 26:
        bs = min(range(1, len(ws)), key=lambda i: abs((_safe_syl_cnt(" ".join(ws[:i])) or 0) - tot / 2))
        halves.extend([" ".join(ws[:bs]), " ".join(ws[bs:])])
    if len(halves) == 4:
      cands.append(halves)
  for c in cands:
    res = svat_identifier.IdentifyFromPatternLines(to_pattern_lines(c))
    ex = [
      k for k in (res.get("exact") or {})
      if "loose" not in k.lower() and "āryā" not in k.lower() and any(m in k.lower() for m in _METRICAL_STD_NAMES)
    ]
    if ex:
      return True
    if len(c) == 4:
      cs = [_safe_syl_cnt(x) for x in c]
      if all(n is not None and 7 <= n <= 9 for n in cs) or all(n is not None and 10 <= n <= 12 for n in cs) or all(n is not None and 11 <= n <= 13 for n in cs):
        return True
  return False


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
  plain = _strip_markup_for_kind(vp_text)
  lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
  norm_plain = re.sub(r"\s+", " ", plain)
  has_brahmana_cues = bool(_BRAHMANA_PROSE_CUES_RE.search(norm_plain))
  if looks_prose_brahmana(vp_text, len(re.sub(r"\s+", "", norm_plain)), summary=summary):
    return "brahmana"
  if has_brahmana_cues or (default_brahmana and bool(_DEFAULT_BRAHMANA_PROSE_CUES_RE.search(norm_plain))):
    return "brahmana"
  if _YAJUH_FORMULA_CUES_RE.search(norm_plain) and len(lines) <= 2:
    return "yajuh"
  if default_brahmana:
    return "rk" if _is_metrical_verse(vp_text) else "brahmana"
  if len(lines) >= 2:
    return "rk"
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
  """5-gram index over ordered upstream target entries with O(1) exact-pāṭha lookup."""

  def __init__(self, entries: Sequence[TargetEntry], corpus_priority: Sequence[str]):
    self.entries: list[TargetEntry] = []
    self.priority = {c: idx for idx, c in enumerate(corpus_priority)}
    self.grams: dict[str, list[int]] = defaultdict(list)
    self.pb_map: dict[str, list[int]] = defaultdict(list)
    self.ent_prio: list[int] = []
    self.ent_kanda: list[str] = []
    self.ent_is_brahmana: list[bool] = []
    self.ent_len: list[int] = []
    for ent in entries:
      self.add_entry(ent)

  def add_entry(self, entry: TargetEntry) -> int:
    idx = len(self.entries)
    self.entries.append(entry)
    pb = entry.pb
    self.pb_map[pb].append(idx)
    self.ent_prio.append(self.priority.get(entry.corpus, 99))
    self.ent_kanda.append(_kanda_num(entry.rel))
    self.ent_len.append(len(pb))
    is_br = entry.kind in ("brahmana_combined", "brahmana_2part") or (
      entry.corpus in _BRAHMANA_CORPORA and classify_unit_kind(entry.vp) == "brahmana"
    )
    self.ent_is_brahmana.append(is_br)
    for pos in range(max(1, len(pb) - 4)):
      self.grams[pb[pos : pos + 5]].append(idx)
    return idx

  def _align_rank(self, src_corpus: str, src_kanda: str, ri: int) -> int:
    if not src_kanda:
      return 1
    ent = self.entries[ri]
    tk = self.ent_kanda[ri]
    if not tk:
      return 1
    if src_corpus == "SB-K" and ent.corpus == "SB-M":
      return 0 if tk in _SBK_TO_SBM_KANDAS.get(src_kanda, ()) else 1
    if src_corpus == "SB-M" and ent.corpus == "SB-K":
      return 0 if src_kanda in _SBK_TO_SBM_KANDAS.get(tk, ()) else 1
    if src_corpus == ent.corpus:
      return 0 if src_kanda == tk else 1
    return 1

  def _score_candidate(
    self,
    ri: int,
    vp: str,
    pb: str,
    *,
    src_summary: str,
    src_corpus: str,
    src_kanda: str,
    src_prose: bool,
    src_is_brahmana_kind: bool,
    src_default_brahmana: bool,
    allow_variant: bool,
    require_variant_eligible: bool,
    exclude_path: str,
    allow_target_variants_from_inline: bool,
    allow_self_static: bool,
  ) -> tuple[bool, float, bool, int, int, TargetEntry] | None:
    """Evaluate candidate entry index `ri` against source `(vp, pb)` and enforce recension guards."""
    ent = self.entries[ri]
    is_inline_like = ent.kind in ("inline", "inline_vp_shared_sarva")
    if ent.corpus == src_corpus and not (allow_self_static and ent.kind != "inline"):
      return None
    if exclude_path and (ent.vp_path == exclude_path or ent.host_path == exclude_path):
      return None
    brahmana_pair = _allow_brahmana_pair(src_corpus, ent.corpus)
    if src_prose and is_inline_like and not brahmana_pair:
      return None
    is_rk_like = ent.kind == "rk_2part" or "ऋक्" in src_summary
    ent_is_brahmana = brahmana_pair and (src_prose or src_is_brahmana_kind or self.ent_is_brahmana[ri])
    al = self._align_rank(src_corpus, src_kanda, ri)
    # Cross-recension SB-K <-> SB-M Brāhmaṇa prose must belong to corresponding kāṇḍas so stock clichés don't mix commentaries.
    if (
      src_corpus in ("SB-M", "SB-K")
      and ent.corpus in ("SB-M", "SB-K")
      and src_corpus != ent.corpus
      and src_kanda
      and ent_is_brahmana
      and src_default_brahmana
      and al != 0
    ):
      return None

    ent_allow_var = allow_variant and (
      ent_is_brahmana
      or not (
        src_prose
        or (ent.kind in ("inline", "inline_vp_shared_sarva", "yajuh_combined") and not allow_target_variants_from_inline and not is_rk_like)
      )
    )
    if require_variant_eligible and not ent_allow_var:
      return None
    min_exact = 22 if ent_is_brahmana else (
      35 if (src_prose or (is_inline_like and src_corpus in ("TB", "TK", "MS", "KS") and ent.corpus != "VS-M" and not is_rk_like)) else 20
    )
    min_var = 35 if ent_is_brahmana else 30
    min_rat = (0.90 if src_corpus in ("SB-M", "SB-K") and ent.corpus in ("SB-M", "SB-K") else 0.92) if ent_is_brahmana else 0.88
    trust_cons = (
      not ent.is_yantra_svara
      and (
        (src_corpus == "KS" and "यन्त्र-स्वरः" in src_summary)
        or (
          src_corpus == "AV-P"
          and ("यन्त्र-स्वरः" in src_summary or ("\u1cd3" not in vp and "\u1cd9" not in vp and "**" not in vp and "+++" not in vp and "…" not in vp))
        )
      )
    )
    matched, rat, eq = classify_match(
      vp, pb, ent.vp, ent.pb,
      allow_variant=ent_allow_var,
      min_len_exact=min_exact,
      min_len_var=min_var,
      min_ratio=min_rat,
      trust_consonants_as_exact=trust_cons,
    )
    if not matched:
      return None
    return True, rat, eq, self.ent_prio[ri], al, ent

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
    L = len(pb)
    if L < 20:
      return None
    src_prose = looks_prose_brahmana(vp, L, summary=src_summary)
    src_kanda = _kanda_num(src_rel) if src_rel else ""
    src_is_brahmana_kind = classify_unit_kind(vp, summary=src_summary) == "brahmana"
    src_default_brahmana = classify_unit_kind(vp, summary=src_summary, default_brahmana=True) == "brahmana"

    # 1. Fast O(1) exact-consonant check via pb_map (every is_no_patha_bheda exact hit has pb_a == pb_b).
    pb_hits = self.pb_map.get(pb)
    if pb_hits:
      exact_fast: list[tuple[int, int, int, TargetEntry]] = []
      var_pb: list[tuple[float, int, int, int, TargetEntry]] = []
      for ri in pb_hits:
        ev = self._score_candidate(
          ri, vp, pb,
          src_summary=src_summary, src_corpus=src_corpus, src_kanda=src_kanda,
          src_prose=src_prose, src_is_brahmana_kind=src_is_brahmana_kind,
          src_default_brahmana=src_default_brahmana,
          allow_variant=allow_variant, require_variant_eligible=False,
          exclude_path=exclude_path, allow_target_variants_from_inline=allow_target_variants_from_inline,
          allow_self_static=allow_self_static,
        )
        if ev is None:
          continue
        _, rat, eq, prio, al, ent = ev
        if eq:
          exact_fast.append((prio, al, ri, ent))
        else:
          var_pb.append((-round(rat, 4), prio, al, ri, ent))
      if exact_fast:
        exact_fast.sort(key=lambda x: (x[0], x[1], x[2]))
        return exact_fast[0][3], 1.0, True
      if var_pb and not allow_variant:
        return None
      # Remember pb_map variant hits (`pb_a == pb_b`, ratio 1.0) in case no better exact hit exists!
      if var_pb:
        var_pb.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        return var_pb[0][4], -var_pb[0][0], False

    if not allow_variant or L < 30:
      return None

    # 2. Fuzzy 5-gram scan with length & coverage prefilter (subsampling long prose cleanly).
    max_delta = max(12, int(0.22 * L))
    grams_dict = self.grams
    step = 1 if L <= 45 else max(1, (L - 5) // 40)
    raw_grams = [pb[pos : pos + 5] for pos in range(0, max(1, L - 4), step)]
    uniq_grams = list(dict.fromkeys(raw_grams))
    # Prefer informative rarer 5-grams first so common prose particles don't trigger quadratic loops.
    non_empty = [grams_dict[g] for g in uniq_grams if g in grams_dict]
    rare_postings = [p for p in non_empty if len(p) <= 1000]
    probes = (rare_postings if len(rare_postings) >= 6 else sorted(non_empty, key=len))[:36]
    if not probes:
      return None
    cands: dict[int, int] = defaultdict(int)
    for posting in probes:
      for ri in posting:
        cands[ri] += 1
    if not cands:
      return None

    min_grams = max(2, len(probes) // 4)
    ent_len = self.ent_len
    ent_prio = self.ent_prio
    filtered = [
      (cnt, -ent_prio[ri], -ri, ri)
      for ri, cnt in cands.items()
      if cnt >= min_grams and abs(ent_len[ri] - L) <= max_delta
    ]
    if not filtered:
      return None

    top = [t[3] for t in heapq.nlargest(48, filtered)]
    var_hits: list[tuple[float, int, int, int, TargetEntry]] = []
    for ri in top:
      ev = self._score_candidate(
        ri, vp, pb,
        src_summary=src_summary, src_corpus=src_corpus, src_kanda=src_kanda,
        src_prose=src_prose, src_is_brahmana_kind=src_is_brahmana_kind,
        src_default_brahmana=src_default_brahmana,
        allow_variant=allow_variant, require_variant_eligible=True,
        exclude_path=exclude_path, allow_target_variants_from_inline=allow_target_variants_from_inline,
        allow_self_static=allow_self_static,
      )
      if ev is None:
        continue
      _, rat, _, prio, al, ent = ev
      var_hits.append((-round(rat, 4), prio, al, ri, ent))

    if var_hits:
      var_hits.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
      return var_hits[0][4], -var_hits[0][0], False
    return None
