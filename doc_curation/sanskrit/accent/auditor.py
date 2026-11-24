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
- ``vp_includes_tiikaa``: ``vishvAsa-prastutiH/`` files including ``sarvASh_TIkAH/`` or embedding
  ``पद-पाठः (यान्त्रिकः)`` blocks.
- ``redundant_ek_external_padapatha``: ``ekAgnikANDam/sarvASh_TIkAH`` files retaining canonical
  ``पद-पाठः (यान्त्रिकः)`` blocks when the paired VP ``js_include``s an external mantra.
- ``redundant_ek_external_wrapper``: ``ekAgnikANDam/vishvAsa-prastutiH`` files still wrapping
  external mantras via ``js_include`` instead of deleting the wrapper pair.

CLI usage::

  ~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.auditor <dir1> [dir2 ...] [--with-reconciler] [--json out.json]
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
from doc_curation.sanskrit.accent.provenance import DETAILS_RE, find_js_include_spans
from doc_curation.sanskrit.accent.reconciler import US_SVARITA, US_UDATTA, parse_padapatha_items

PP_SUMMARY_RE = re.compile(r"^पद-पाठः\s*\(यान्त्रिकः")
_JS_INCLUDE_URL_RE = re.compile(r'<div\s+class="js_include"[^>]*url=["\']([^"\']+)["\'][^>]*>')
CORPUS_COUNT_TAG_RE = re.compile(r"\*(?:TS|RV|TB|TK|AV|SB-M|SB-K|ŚB|VS-M|VS-K|VS|KS|MS)\*-\d+(?:/\d+)?")
SUTRA_REF_RE = re.compile(r"(?:पा[॰०]|फि[॰०]|उणादि[॰०]|वा[॰०])")
SVARA_MARK_RE = re.compile(rf"[{US_UDATTA}{US_SVARITA}]")
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


def audit_padapatha_markdown(
  markdown_text: str,
  *,
  path: str = "",
  paired_vp_text: str | None = None,
  include_validator_issues: bool = True,
  include_reconciler_diffs: bool = False,
  is_ekAgnikANDam: bool | None = None,
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

      # 4a. Non-initial पा॰ ६.१.१९८ vocative candidate
      if idx_it > 0 and ("६.१.१९८" in prov or re.search(r"(?<!अ)पादादावामन्त्रित", prov) is not None):
        # Quick check: does bare word start a line or follow a danda in mula?
        bare_w = _strip_marks_for_probe(ref)
        stem = bare_w[:-1] if len(bare_w) >= 4 else bare_w
        mula_bare = accent.strip_accents(blk.mula)
        at_boundary = bool(
          stem and re.search(rf"(?:^|[।॥\n]\s*){re.escape(stem[: min(len(stem), 4)])}", mula_bare)
        )
        if not at_boundary:
          findings.append(AuditFinding("non_initial_61198_vocative", path, ln, f"idx={idx_it}"))

      # 4b. Possible missed vocative (0-accent ar -> accented ref, while commentary has `हे <stem>` or VP has `<stem>!`)
      if is_arrow and not SVARA_MARK_RE.search(ar) and SVARA_MARK_RE.search(ref):
        bare_w = _strip_marks_for_probe(ref)
        stem = bare_w[:-1] if len(bare_w) > 2 else bare_w
        if stem and re.search(rf"(?:हे\s+{re.escape(stem)}|{re.escape(stem)}[^\s]*!)", comm_all_text + "\n" + blk.vp):
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
        vp_spaced = bool(
          p0_bare
          and p1_bare
          and len(p0_bare) >= 2
          and len(p1_bare) >= 2
          and re.search(rf"(?:^|\s){re.escape(p0_bare)}\s+{re.escape(p1_bare[:3])}", vp_plain)
        )
        suspicious_p0 = bool(is_arrow and (_INFLECTED_P0_ENDINGS_RE.search(p0_bare) or p0_bare in _PARTICLE_P0_SET))
        if vp_spaced or suspicious_p0:
          findings.append(
            AuditFinding("false_compound_candidate", path, ln, f"vp_spaced={vp_spaced}, p0={p0_bare}")
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
  parser.add_argument("--categories", nargs="*", default=None, help="Filter reported findings to these categories")
  parser.add_argument("--max-per-category", type=int, default=15, help="Max sample findings printed per category")
  parser.add_argument("--json", dest="json_out", default=None, help="Write full JSON audit report to this file")
  args = parser.parse_args(argv)

  report = audit_directory_trees(
    args.roots,
    include_validator_issues=not args.no_validator,
    include_reconciler_diffs=args.with_reconciler,
    base_dir=args.base_dir,
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
