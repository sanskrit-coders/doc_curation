"""Interleave missing commentaries and set up ``सर्वा अवतारिकाः`` in ``manuH/``.

Also repairs structural gaps (missing Ch.3 verses 3.36–3.44, stale includes in
``daNDaH.md``, duplicate ``11/266.md``, orphaned Medhātithi footnotes, and
un-migrated Bhāruci fragments), preserves attribution/editorial/index
documents in ``articles/`` and ``yAJNavalkyaH/_index.md``, and cleans up obsolete
commentary source trees once verified.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

import regex

from doc_curation.md.content_processor.commentary.lemma_aligner import (
  VerseSpec,
  _bind_inline_footnotes,
  _compact_and_grams,
  _extract_inline_merged_footnotes,
  align_entry_stream_to_verses,
  extract_bold_shloka_sections,
  parse_footnotes_markdown,
  parse_paired_details_sections,
  split_leading_and_trailing_italic_avatarika,
  strip_frontmatter,
)
from doc_curation.md.content_processor.details import common as details_common
from doc_curation.md.content_processor.include import seeker as include_seeker
from doc_curation.md.content_processor.include import transformer as include_transformer


MANU_CONTENT_DIR = Path("/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/dharmaH/smRtiH/manuH")
MANU_SP_DIR = MANU_CONTENT_DIR / "sarva-prastutiH"
MANU_STATIC_DIR = Path("/home/vvasuki/gitland/vishvAsa/kalpAntaram/static/smRtiH/manuH/sarvASh_TIkAH")
YAJ_CONTENT_DIR = Path("/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/dharmaH/smRtiH/yAJNavalkyaH")
DANDA_PATH = Path(
  "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/dharmaH/nibandhaH/vishvAsaH/visheSha-dharmaH/sAmya-vaiShamye/violence/daNDaH.md"
)
STATIC_REPO = Path("/home/vvasuki/gitland/vishvAsa/kalpAntaram/static")
HUGO_BASE_DIR = "/home/vvasuki/gitland/vishvAsa"

_JS_INCLUDE_BLOCK_RE = regex.compile(
  r'<details open><summary>विश्वास-प्रस्तुतिः</summary>(.*?)</details>\s*'
  r'<div class="js_include[^>]*url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/([^"]+)"',
  flags=regex.DOTALL,
)

# Author ordering when adding new layers into static/sarvASh_TIkAH/
_PREFERRED_AFTER = (
  "गङ्गानथ-मूलानुवादः",
  "मानसतरङ्गिणीकृत्",
  "मेधातिथिः",
  "गङ्गानथ-भाष्यानुवादः",
  "गङ्गानथ-टिप्पन्यः",
  "गङ्गानथ-तुल्य-वाक्यानि",
  "कुल्लूकः",
  "गोविन्दराजः",
  "भारुचिः",
  "Bühler",
  "विश्वास-टिप्पनी",
)
_AVATARIKA_ORDER = (
  "मेधातिथिः - अवतारिका",
  "गङ्गानथ-भाष्यानुवादः - अवतारिका",
  "कुल्लूकः - अवतारिका",
  "गोविन्दराजः - अवतारिका",
  "भारुचिः - अवतारिका",
)

_NORM_TRANSLATE = str.maketrans("०१२३४५६७८९", "0123456789")


@dataclass(frozen=True)
class ManuVerseRef:
  """Canonical mapping between host ``sarva-prastutiH`` position and ``static/sarvASh_TIkAH`` file."""

  chapter: str
  verse_id: str
  rel_url: str
  sp_file: Path
  static_file: Path
  spec: VerseSpec


def _norm_digits(text: str) -> str:
  return text.translate(_NORM_TRANSLATE)


def load_manu_chapter_verses() -> dict[str, list[ManuVerseRef]]:
  """Load ordered ``ManuVerseRef`` lists per chapter (``01``..``12``) from ``sarva-prastutiH/``."""
  by_ch: dict[str, list[ManuVerseRef]] = defaultdict(list)
  for p in sorted(MANU_SP_DIR.rglob("*.md")):
    if p.name == "_index.md":
      continue
    txt = p.read_text()
    for m in _JS_INCLUDE_BLOCK_RE.finditer(txt):
      vp_text, rel_url = m.group(1).strip(), m.group(2)
      ch = rel_url.split("/")[0][:2]
      v_m = regex.search(r"(\d+(?:-\d+)?)_", rel_url.split("/")[1])
      vid = f"{int(ch)}.{v_m.group(1)}" if v_m else rel_url
      idx = len(by_ch[ch])
      by_ch[ch].append(
        ManuVerseRef(
          chapter=ch,
          verse_id=vid,
          rel_url=rel_url,
          sp_file=p,
          static_file=MANU_STATIC_DIR / rel_url,
          spec=VerseSpec.from_text(idx, vid, ch, vp_text),
        )
      )
  return dict(by_ch)


def _upsert_leaf_block(static_text: str, summary: str, body: str) -> str:
  """Insert or preserve a leaf ``<details><summary>{summary}</summary>`` in a static file."""
  clean = body.strip()
  if not clean:
    return static_text
  if f"<summary>{summary}</summary>" in static_text:
    return static_text
  new_block = f"<details><summary>{summary}</summary>\n\n{clean}\n</details>"

  # Parse top-level leaf details blocks and insert preserving relative author rank.
  blocks = details_common.parse_top_level_details(static_text)
  if not blocks:
    return static_text.rstrip() + f"\n\n{new_block}\n"

  fm, _ = strip_frontmatter(static_text)
  rank = {name: idx for idx, name in enumerate(_PREFERRED_AFTER)}
  target_rank = rank.get(summary, 90)
  out_blocks: list[str] = []
  inserted = False
  for b_start, b_end, b_title, _ in blocks:
    blk_rank = rank.get(b_title.strip(), 99)
    if not inserted and blk_rank > target_rank:
      out_blocks.append(new_block)
      inserted = True
    out_blocks.append(static_text[b_start:b_end].strip())
  if not inserted:
    out_blocks.append(new_block)
  prefix = fm.rstrip() + "\n\n" if fm else ""
  return prefix + "\n\n".join(out_blocks) + "\n"


def _replace_leaf_block_body(static_text: str, summary: str, new_body: str) -> str:
  """Replace or remove a specific leaf ``<details><summary>{summary}</summary>`` block."""
  pat = regex.compile(
    rf"<details>\s*<summary>{regex.escape(summary)}</summary>(?:(?!</?details\b).)*?</details>",
    flags=regex.DOTALL,
  )
  clean = new_body.strip()
  if not clean:
    updated = pat.sub("", static_text)
    return regex.sub(r"\n{3,}", "\n\n", updated).strip() + "\n"
  repl = f"<details><summary>{summary}</summary>\n\n{clean}\n</details>"
  return pat.sub(lambda _: repl, static_text, count=1)


def _get_leaf_block_body(static_text: str, summary: str) -> str | None:
  m = regex.search(
    rf"<details>\s*<summary>{regex.escape(summary)}</summary>((?:(?!</?details\b).)*?)</details>",
    static_text,
    flags=regex.DOTALL,
  )
  return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Phase A: Repair missing 03/036..044, duplicate 11/266, stale daNDaH.md
# ---------------------------------------------------------------------------

def repair_sarva_prastuti_and_external(*, dry_run: bool = False) -> dict[str, int]:
  """Restore omitted 3.36–3.44 verses, drop duplicate ``11/266.md``, fix ``daNDaH.md``."""
  stats = {"added_03_verses": 0, "removed_11_266": 0, "fixed_danda": 0}

  target_sp03 = MANU_SP_DIR / "03/03_vivAhaprakArAH.md"
  sp03_txt = target_sp03.read_text()
  if "036_yo_yasyaiShAm.md" not in sp03_txt:
    ls_out = subprocess.check_output(
      ["git", "-C", str(STATIC_REPO), "ls-tree", "e5075e7f28^", "smRtiH/manuH/vishvAsa-prastutiH/03/"],
      text=True,
    )
    chunks: list[str] = []
    for line in sorted(ls_out.splitlines(), key=lambda ln: ln.split("\t", 1)[1]):
      git_path = line.split("\t", 1)[1]
      fname = git_path.rsplit("/", 1)[-1]
      num = int(fname[:3])
      if 36 <= num <= 44:
        raw_vp = subprocess.check_output(
          ["git", "-C", str(STATIC_REPO), "show", f"e5075e7f28^:{git_path}"],
          text=True,
        )
        _, vp_body = strip_frontmatter(raw_vp)
        vp_body = vp_body.strip()
        # Preserve original vishvAsa-prastutiH body verbatim inside standard wrapper
        rel_static = f"03/{fname}"
        assert (MANU_STATIC_DIR / rel_static).exists(), f"Missing static file {rel_static}"
        chunks.append(
          f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp_body}\n</details>\n\n"
          f'<div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" unfilled="" url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/{rel_static}">\n</div>'
        )
        stats["added_03_verses"] += 1
    if chunks and not dry_run:
      target_sp03.write_text(sp03_txt.rstrip() + "\n\n" + "\n\n".join(chunks) + "\n")

  dup_266 = MANU_STATIC_DIR / "11/266.md"
  if dup_266.exists():
    # Confirm 11/265 already holds Bühler 266 before deleting duplicate
    b265 = (MANU_STATIC_DIR / "11/265_AdyaM_yat.md").read_text()
    if "triliteral Brahman" in b265:
      if not dry_run:
        dup_266.unlink()
      stats["removed_11_266"] = 1

  if DANDA_PATH.exists():
    danda_txt = DANDA_PATH.read_text()
    if "/kalpAntaram/smRtiH/manuH/gangAnatha-mUlAnuvAdaH/08/299_bhAryA_putrash.md" in danda_txt:
      new_danda = regex.sub(
        r'<div class="js_include[^>]*url="/kalpAntaram/smRtiH/manuH/gangAnatha-mUlAnuvAdaH/08/299_bhAryA_putrash\.md".*?'
        r'<div class="js_include[^>]*url="/kalpAntaram/smRtiH/manuH/buhler/08/299_bhAryA_putrash\.md".*?</div>\n*',
        '<div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" unfilled="" url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/08/299_bhAryA_putrash.md">\n</div>\n\n',
        danda_txt,
        count=1,
        flags=regex.DOTALL,
      )
      if new_danda != danda_txt:
        if not dry_run:
          DANDA_PATH.write_text(new_danda)
        stats["fixed_danda"] = 1
  return stats


# ---------------------------------------------------------------------------
# Phase B: Recover Medhātithi footnotes/colophon & Bhāruci leftover fragments
# ---------------------------------------------------------------------------

def _collect_medhatithi_footnotes() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
  """Collect per-chapter Medhātithi ``[^id]: ...`` defs from content and static."""
  by_ch_raw: dict[str, dict[str, str]] = defaultdict(dict)
  by_ch_norm: dict[str, dict[str, str]] = defaultdict(dict)

  def _scan_text(ch: str, txt: str) -> None:
    lines = txt.splitlines()
    i = 0
    while i < len(lines):
      m = regex.match(r"^\[\^([^\]]+)\]:(.*)$", lines[i])
      if m:
        fid = m.group(1).strip()
        body = [m.group(2).strip()] if m.group(2).strip() else []
        i += 1
        while i < len(lines):
          nxt = lines[i]
          if nxt.startswith("    ") or nxt.startswith("\t"):
            body.append(nxt.strip())
            i += 1
          elif nxt.strip() == "" and i + 1 < len(lines) and (lines[i + 1].startswith("    ") or lines[i + 1].startswith("\t")):
            i += 1
          else:
            break
        val = "\n".join(b for b in body if b).strip()
        if val:
          by_ch_raw[ch].setdefault(fid, val)
          by_ch_norm[ch].setdefault(_norm_digits(fid), val)
      else:
        i += 1

  medh_dir = MANU_CONTENT_DIR / "medhAtithiH"
  if medh_dir.exists():
    for p in sorted(medh_dir.glob("[0-9]*.md")):
      _scan_text(p.name[:2], p.read_text())

  for ch_dir in sorted(MANU_STATIC_DIR.iterdir()):
    if not ch_dir.is_dir():
      continue
    ch = ch_dir.name[:2]
    for f in sorted(ch_dir.glob("*.md")):
      if f.name == "_index.md":
        continue
      _scan_text(ch, f.read_text())
  return dict(by_ch_raw), dict(by_ch_norm)


def patch_medhatithi_and_bharuchi_gaps(*, dry_run: bool = False) -> dict[str, int]:
  """Patch missing Medhātithi footnotes/colophon, Bhāruci leftovers, and dup lines."""
  stats = {"patched_fns": 0, "patched_colophon_12": 0, "removed_stray_gm": 0, "patched_bharuchi": 0}
  raw_fns, norm_fns = _collect_medhatithi_footnotes()

  # 1. Remove stray _एतद् एव विस्तारयति ।_ in 01_praveshaH/028 गङ्गानथ-मूलानुवादः
  p28 = MANU_STATIC_DIR / "01_praveshaH/028_yan_tu.md"
  if p28.exists():
    txt28 = p28.read_text()
    gm = _get_leaf_block_body(txt28, "गङ्गानथ-मूलानुवादः")
    if gm and "_एतद् एव विस्तारयति ।_" in gm:
      cleaned_gm = regex.sub(r"\s*_एतद् एव विस्तारयति ।_\s*", "", gm).strip()
      if not dry_run:
        p28.write_text(_replace_leaf_block_body(txt28, "गङ्गानथ-मूलानुवादः", cleaned_gm))
      stats["removed_stray_gm"] = 1

  # 2. Recover missing Madana colophon on 12/126_ity_etan.md
  p126 = MANU_STATIC_DIR / "12/126_ity_etan.md"
  if p126.exists() and (MANU_CONTENT_DIR / "medhAtithiH/12.md").exists():
    txt126 = p126.read_text()
    medh126 = _get_leaf_block_body(txt126, "मेधातिथिः")
    if medh126 and "क्षोणीन्द्रो मदनः" not in medh126:
      colophon = (
        "**इति मानवे धर्मशास्त्रे भृगुप्रोक्तायां संहितायां**\n\n"
        "**द्वादशो ऽध्यायः ॥**\n\n"
        "**मान्या कापि मनुस्मृतिस् तदुचिता व्याख्या हि मेधातिथेः**  \n"
        "**सा लुप्तैव विधेर् वशात् क्वचिद् अपि प्राप्यं न यत् पुस्तकम् ।**  \n"
        "**क्षोणीन्द्रो मदनः सहारणसुतो देशान्तराद् आहृतं**  \n"
        "**जीर्णोद्धारम् अचीकरत् तत इतस् तत्पुस्तकैर् लेखितैः ।**\n\n"
        "**इति भट्टवीरस्वामिसूनोर् भट्टमेधातिथिकृतौ**  \n"
        "**मनुभाष्ये द्वादशो ऽध्यायः ॥**"
      )
      if not dry_run:
        p126.write_text(_replace_leaf_block_body(txt126, "मेधातिथिः", medh126 + "\n\n" + colophon))
      stats["patched_colophon_12"] = 1

  # 3. Recover missing footnote defs in static मेधातिथिः (and 07/206-1 [^३१४])
  for ch_dir in sorted(MANU_STATIC_DIR.iterdir()):
    if not ch_dir.is_dir():
      continue
    ch = ch_dir.name[:2]
    ch_raw = raw_fns.get(ch, {})
    ch_norm = norm_fns.get(ch, {})
    for f in sorted(ch_dir.glob("*.md")):
      if f.name == "_index.md":
        continue
      txt = f.read_text()
      changed = False
      for summary in ("मेधातिथिः", "Bühler"):
        body = _get_leaf_block_body(txt, summary)
        if not body:
          continue
        refs = list(dict.fromkeys(m.group(1).strip() for m in regex.finditer(r"\[\^([^\]\n]+)\](?!:)", body)))
        defs = {m.group(1).strip() for m in regex.finditer(r"^\[\^([^\]]+)\]:", body, regex.M)}
        norm_defs = {_norm_digits(d) for d in defs}
        additions: list[str] = []
        new_body = body
        for r in refs:
          if r in defs:
            continue
          rn = _norm_digits(r)
          if rn in norm_defs:
            # Normalize ref digits to match existing definition key (e.g. [^29] -> [^२९])
            matching_def = next(d for d in defs if _norm_digits(d) == rn)
            new_body = new_body.replace(f"[^{r}]", f"[^{matching_def}]")
            continue
          val = ch_raw.get(r) or ch_norm.get(rn)
          if val:
            additions.append(f"[^{r}]:\n     " + "\n     ".join(val.splitlines()))
            stats["patched_fns"] += 1
        if additions:
          new_body = new_body.rstrip() + "\n\n\n" + "\n\n\n".join(additions)
        if new_body != body:
          txt = _replace_leaf_block_body(txt, summary, new_body)
          changed = True
      if changed and not dry_run:
        f.write_text(txt)

  # 4. Fold the ~10 un-migrated non-italic Bhāruci fragments from derrett-pAThaH into static
  bharuchi_patches: list[tuple[str, str, bool]] = [
    # (static glob relative path, exact prose fragment, prepend=True else append)
    ("07/012_*.md", "यथोक्तम् उपदेशम् अपरिगणय्य पौनह्पुन्यन । यतस् तं न द्विष्याद् अन्यार्थापराधम्, येन-", True),
    ("07/068_*.md", "साध्वसाधु वा सभृत्यवर्गस्य", True),
    ("07/112_*.md", "राष्ट्रं हि तस्य शरीरम् इति । यतश् चैतद् एवम् अतस् तद्दोषपर्युदासाय ॥ ७.११२ ॥", False),
    ("07/178_*.md", "अनेकमुखत्वात् कार्याणां क्षणिकत्वाच् च तस्यां तस्याम् अवस्थायां तत्तत्कार्यम् आपद्यत इति सामान्यतः सर्वकार्यावधारणं दर्शयति ॥ ७.१७८ ॥", False),
    ("08/364_*.md", "अत ऊर्ध्वं विधिर् उच्यमानः कन्यागतो वेदितव्यः ॥ ८.३६३ ॥", False),
    ("08/394_*.md", "सप्तत्याः प्रभृति स्थविरो गृह्यते ।", True),
    ("09/007_*.md", "स्वधर्मं श्रौतं येनासंकीर्णापत्यस्याधानादिभिर् अधिकारः भवति गौणं वा तद् इति वक्ष्यामः । नामधेयं च स्त्रियाः संरक्षणार्थवादी कुर्वन्न् इदम् आह ॥ ९.७ ॥", False),
    ("09/297_*.md", "स्वविषयनियमाद् इन्द्रियवत् । एवं च सति,", True),
    ("09/335_*.md", "तद् एवंवृत्तह्,", True),
    ("11/201_*.md", "दण्डापूपिकया चोष्ट्रखरयोर् अव्यवधान एतद् एव स्यात्, ईषद् अधिकं वा ।", False),
    ("12/104_*.md", "समुच्चयप्रयोजनम् आचष्टे ।", True),
  ]
  for pat, frag, prepend in bharuchi_patches:
    matches = sorted(MANU_STATIC_DIR.glob(pat))
    if not matches:
      continue
    sf = matches[0]
    stxt = sf.read_text()
    probe = regex.sub(r"[,\s]+$", "", frag[:28])
    cur = _get_leaf_block_body(stxt, "भारुचिः") or ""
    if probe in cur:
      continue
    if not cur:
      new_bh = frag
    elif prepend:
      new_bh = f"{frag}\n\n{cur}"
    else:
      new_bh = f"{cur}\n\n{frag}"
    if not dry_run:
      sf.write_text(_upsert_leaf_block(stxt, "भारुचिः", new_bh) if not cur else _replace_leaf_block_body(stxt, "भारुचिः", new_bh))
    stats["patched_bharuchi"] += 1

  # Also recover Ch.1 भार्गव/भारुचि 01_praveshaH/001 if still un-prefixed? Wait: 001..005 in jagannAtha already have js_include.
  return stats


# ---------------------------------------------------------------------------
# Phase C: Interleave Govindarāja & Kullūka + extract opening/verse avatārikās
# ---------------------------------------------------------------------------

def interleave_govindaraja(
  by_ch: dict[str, list[ManuVerseRef]],
  avatarikas: dict[str, dict[str, list[str]]],
  *,
  dry_run: bool = False,
) -> dict[str, int]:
  """Interleave all 12 chapters of Govindarāja into ``sarvASh_TIkAH/`` & extract ch openings."""
  stats = {"inserted": 0, "skipped_existing": 0, "dropped": 0}
  gov_dir = MANU_CONTENT_DIR / "govindarAjaH"

  # Ch 1 mangala from govindarAjaH/_index.md -> अवतारिका at 1.1
  idx_path = gov_dir / "_index.md"
  if idx_path.exists():
    m0 = regex.search(r"<details><summary>गोविन्दराजः - ०</summary>(.*?)</details>", idx_path.read_text(), regex.DOTALL)
    if m0:
      ch1_ref = by_ch["01"][0]
      avatarikas[ch1_ref.rel_url]["गोविन्दराजः - अवतारिका"].append(m0.group(1).strip())

  for p in sorted(gov_dir.glob("[0-9]*.md")):
    ch = p.stem
    vrefs = by_ch[ch]
    vspecs = [vr.spec for vr in vrefs]
    vmap = {vr.verse_id: vr for vr in vrefs}

    entries = [
      e for e in parse_paired_details_sections(p.read_text(), commentary_prefix="गोविन्दराजः")
      if e["body"].strip()
    ]
    aligned = align_entry_stream_to_verses(entries, vspecs, min_score=0.22)
    matched_ids = {id(e) for lst in aligned.values() for e in lst}
    stats["dropped"] += sum(1 for e in entries if id(e) not in matched_ids)

    for vid, lst in aligned.items():
      vr = vmap[vid]
      combined_parts: list[str] = []
      for e_idx, entry in enumerate(lst):
        body = entry["body"].strip()
        # Separate Govindaraja's ch-opening pre-lemma intro at 1.1 and 2.1
        if ch == "01" and vid == "1.1" and e_idx == 0 and "\n\n**मनुम्**" in body:
          pre, post = body.split("\n\n**मनुम्**", 1)
          avatarikas[vr.rel_url]["गोविन्दराजः - अवतारिका"].append(pre.strip())
          body = "**मनुम्**" + post
        elif ch == "02" and vid == "2.1" and e_idx == 0 and body.startswith("ॐ नमः सरस्वत्यै") and "तत्र तावद्" in body:
          m2 = regex.match(r"^(ॐ नमः सरस्वत्यै । .*?उपक्रमते ।)\s*(.*)$", body, flags=regex.DOTALL)
          if m2:
            avatarikas[vr.rel_url]["गोविन्दराजः - अवतारिका"].append(m2.group(1).strip())
            body = m2.group(2).strip()
        combined_parts.append(body)
      combined = "\n\n".join(p_txt for p_txt in combined_parts if p_txt)
      cur_txt = vr.static_file.read_text()
      if "<summary>गोविन्दराजः</summary>" in cur_txt:
        stats["skipped_existing"] += 1
        continue
      new_txt = _upsert_leaf_block(cur_txt, "गोविन्दराजः", combined)
      if not dry_run:
        vr.static_file.write_text(new_txt)
      stats["inserted"] += 1
  return stats


def _split_kulluka_ch01_opening(raw_txt: str) -> tuple[str, str]:
  """Separate Kullūka's Ch.1 interpolated ms-ख śloka, 6 maṅgalas, and treatise intro from ``1.1`` onwards."""
  fm, body = strip_frontmatter(raw_txt)
  # Locate the actual 1.1 verse followed by Sri Ganesaya namah, then 6 mangalas + essay ending right before 'अभिगम्य'
  m1 = regex.search(r"(\*\*मनुमेकाग्रमासीनमभिगम्य महर्षयः ।\*\*.*?\*\*प्रतिपूज्य यथान्यायमिदं वचनमब्रुवन् ॥१॥\*\*)", body, regex.DOTALL)
  m_comm = regex.search(r"^\s*['‘]अभिगम्य['’]\s*['‘]प्रतिपूज्य", body, regex.MULTILINE)
  if not (m1 and m_comm):
    return "", raw_txt
  pre_v1 = body[: m1.start()].strip()
  v1_shloka = m1.group(1).strip()
  post_v1_opening = body[m1.end() : m_comm.start()].strip()
  rest = body[m_comm.start() :]
  opening_raw = f"{post_v1_opening}\n\n**(प्रक्षिप्तः श्लोकः ख-पुस्तके):**\n\n{pre_v1}".strip()
  # Strip chapter banner from opening
  opening_raw = regex.sub(r"^\*\*प्रथमोऽध्यायः ।\*\*\s*", "", opening_raw).strip()
  rebuilt = f"{fm}{v1_shloka}\n\n{rest}"
  return opening_raw, rebuilt


def _preprocess_kulluka_chapter(ch: str, raw_txt: str) -> tuple[str, str]:
  """Prepare a raw ``kullUkaH/{ch}.md`` text before ``extract_bold_shloka_sections``."""
  if ch == "01":
    return _split_kulluka_ch01_opening(raw_txt)
  if ch in ("02", "03"):
    # Strip the Benares chapter-opening mangala verse + prose essay before verse 1
    fm, body = strip_frontmatter(raw_txt)
    m_v1 = regex.search(
      r"^\*\*(?:विद्वद्भिः|षट्त्रिंशद्)",
      body,
      flags=regex.MULTILINE,
    )
    if m_v1:
      opening_raw = body[: m_v1.start()].strip()
      opening_raw = regex.sub(r"^\*\*(?:अथ\s+)?[अ-ौक-हऽ]+ऽध्यायः\s*।\*\*\s*", "", opening_raw).strip()
      return opening_raw, f"{fm}{body[m_v1.start():]}"
  return "", raw_txt


def _is_non_manu_kulluka_entry(ch: str, entry: dict) -> bool:
  """Filter Kullūka closing author verses or stray OCR citations falsely split as verses."""
  mula = entry["mula"]
  norm = _compact_and_grams(mula)[0]
  # Chapter 11 & 12 closing author verses
  if ch == "11" and "नैतन्मेधातिथिरभिदधे" in norm:
    return True
  if ch == "12" and any(k in norm for k in ("स्तोकंवस्तुनिगूढमल्पवचनाद्", "प्रायोमुनिभिर्विवृतं", "सेयंमयामानवधर्मशास्त्रे", "इतिवारेन्द्रिनन्दना")):
    return True
  # Stray one-line prose quotes mistakenly matched inside commentary
  if any(k in norm for k in ("मेधातिथिप्रभृतिभिर्वृद्धैरलिखितं", "नमेधातिथिगोविन्दराजव्याख्या", "हन्तगोविन्दराजेनविशेषमविवृण्वता", "मन्येनकल्पितंगर्वाद्", "भृगुसरष्टरपि", "मेधातिथिःप्राहनिराश्रमम्")):
    return True
  return False


def interleave_kulluka(
  by_ch: dict[str, list[ManuVerseRef]],
  avatarikas: dict[str, dict[str, list[str]]],
  *,
  dry_run: bool = False,
) -> dict[str, int]:
  """Interleave all 12 chapters of Kullūka into ``sarvASh_TIkAH/`` & extract avatārikās."""
  stats = {"inserted": 0, "skipped_existing": 0, "non_mono_recovered": 0, "dropped": 0}
  kull_dir = MANU_CONTENT_DIR / "kullUkaH"

  for p in sorted(kull_dir.glob("[0-9]*.md")):
    ch = p.stem
    vrefs = by_ch[ch]
    vspecs = [vr.spec for vr in vrefs]
    vmap = {vr.verse_id: vr for vr in vrefs}

    raw_txt = p.read_text()
    opening_pre, prepared_txt = _preprocess_kulluka_chapter(ch, raw_txt)
    opening_parsed, entries = extract_bold_shloka_sections(prepared_txt)

    if opening_pre:
      repaired_raw, inl_raw = _extract_inline_merged_footnotes(raw_txt)
      raw_defs = {**parse_footnotes_markdown(repaired_raw), **inl_raw}
      open_text = _bind_inline_footnotes(opening_pre, [raw_defs])
    else:
      open_text = opening_parsed

    open_text = regex.sub(r"<MISSING_FIG[^>]*/?>", "", open_text).strip()
    if open_text:
      avatarikas[vrefs[0].rel_url]["कुल्लूकः - अवतारिका"].append(open_text)

    # Separate closing colophons/non-Manu quotes before verse alignment
    closing_colophons: list[str] = []
    manu_entries: list[dict] = []
    for e in entries:
      if _is_non_manu_kulluka_entry(ch, e):
        if ch in ("11", "12") and ("मेधातिथिरभिदधे" not in e["mula"] or ch == "11"):
          closing_colophons.append(f"**{e['mula']}**" + (f"\n\n{e['body']}" if e["body"] else ""))
        continue
      manu_entries.append(e)

    # First pass: monotonic DP alignment
    aligned = align_entry_stream_to_verses(manu_entries, vspecs, min_score=0.22)
    matched_ids = {id(e) for lst in aligned.values() for e in lst}

    # Second pass: recover genuine out-of-order (page-shuffled) entries onto unfilled verses
    unfilled_specs = [vspecs[idx] for idx, vr in enumerate(vrefs) if vr.verse_id not in aligned]
    rem_entries = [e for e in manu_entries if id(e) not in matched_ids and (e["body"].strip() or e["avatarika"].strip())]
    if unfilled_specs and rem_entries:
      for e in rem_entries:
        _, e_grams = _compact_and_grams(e["mula"])
        if not e_grams:
          continue
        best_v, best_jacc = None, 0.0
        for vs in unfilled_specs:
          jacc = len(e_grams & vs.grams) / max(1, len(e_grams | vs.grams))
          if jacc > best_jacc:
            best_jacc = jacc
            best_v = vs
        if best_v is not None and best_jacc >= 0.42:
          aligned.setdefault(best_v.verse_id, []).append(e)
          matched_ids.add(id(e))
          unfilled_specs = [u for u in unfilled_specs if u.verse_id != best_v.verse_id]
          stats["non_mono_recovered"] += 1

    # Check if any genuinely distinct non-duplicate non-empty entries remain dropped
    for e in manu_entries:
      if id(e) in matched_ids:
        continue
      _, e_grams = _compact_and_grams(e["mula"])
      # If another matched entry already covers this verse (>0.55 similarity), it's an OCR duplicate page scan
      is_dup = any(
        len(e_grams & vmap[vid].spec.grams) / max(1, len(e_grams | vmap[vid].spec.grams)) >= 0.45
        for vid in aligned
      )
      if not is_dup and (e["body"].strip() or e["avatarika"].strip()):
        stats["dropped"] += 1
        print(f"  KULL DROPPED ch={ch} hint={e['verse_hint']}: {e['mula'][:55]!r} | {e['body'][:55]!r}")

    # Attach Ch 11/12 author colophon cleanly to the last aligned verse
    last_vid = sorted(aligned.keys(), key=lambda x: vmap[x].spec.index)[-1] if aligned else None

    for vid in sorted(aligned.keys(), key=lambda x: vmap[x].spec.index):
      vr = vmap[vid]
      lst = aligned[vid]
      av_parts = [e["avatarika"] for e in lst if e.get("avatarika", "").strip()]
      body_parts = [e["body"] for e in lst if e.get("body", "").strip()]
      if closing_colophons and vid == last_vid:
        body_parts.extend(closing_colophons)
      for av in av_parts:
        clean_av = regex.sub(r"<MISSING_FIG[^>]*/?>", "", av).strip()
        if clean_av:
          avatarikas[vr.rel_url]["कुल्लूकः - अवतारिका"].append(clean_av)

      combined_body = "\n\n".join(body_parts)
      combined_body = regex.sub(r"<MISSING_FIG[^>]*/?>", "", combined_body)
      combined_body = regex.sub(r"\n{3,}", "\n\n", combined_body).strip()
      if not combined_body:
        continue
      cur_txt = vr.static_file.read_text()
      if "<summary>कुल्लूकः</summary>" in cur_txt:
        stats["skipped_existing"] += 1
        continue
      new_txt = _upsert_leaf_block(cur_txt, "कुल्लूकः", combined_body)
      if not dry_run:
        vr.static_file.write_text(new_txt)
      stats["inserted"] += 1
  return stats


# ---------------------------------------------------------------------------
# Phase D: Collect Medhātithi & Bhāruci openings + per-verse _..._ avatārikās
# ---------------------------------------------------------------------------

def extract_medhatithi_bharuchi_avatarikas(
  by_ch: dict[str, list[ManuVerseRef]],
  avatarikas: dict[str, dict[str, list[str]]],
  *,
  dry_run: bool = False,
) -> dict[str, int]:
  """Move Ch. openings & leading/trailing ``_..._`` avatārikās out of static into host map."""
  stats = {"ch_openings": 0, "medh_leading": 0, "medh_trailing": 0, "bh_leading": 0, "bh_trailing": 0}
  _, norm_fns = _collect_medhatithi_footnotes()

  # 1. Ch 1 Medhātithi + Jha Bhāṣyānuvāda openings from 01_praveshaH/001
  vr1 = by_ch["01"][0]
  t1 = vr1.static_file.read_text()
  m1 = _get_leaf_block_body(t1, "मेधातिथिः")
  if m1 and "वेदान्तवेद्यतत्त्वाय" in m1 and "तत्र मनुम् अभिगम्य" in m1:
    pre, post = m1.split("तत्र मनुम् अभिगम्य", 1)
    clean_pre = regex.sub(r"(?:\n+[-\s]*)+\Z", "", pre.strip()).strip()
    avatarikas[vr1.rel_url]["मेधातिथिः - अवतारिका"].append(clean_pre)
    t1 = _replace_leaf_block_body(t1, "मेधातिथिः", "तत्र मनुम् अभिगम्य" + post)
    stats["ch_openings"] += 1
  g1 = _get_leaf_block_body(t1, "गङ्गानथ-भाष्यानुवादः")
  if g1 and "Salutation to the Supreme Brahman!" in g1 and "Now, in the text we have" in g1:
    gpre, gpost = g1.split("Now, in the text we have", 1)
    avatarikas[vr1.rel_url]["गङ्गानथ-भाष्यानुवादः - अवतारिका"].append(gpre.strip())
    t1 = _replace_leaf_block_body(t1, "गङ्गानथ-भाष्यानुवादः", "Now, in the text we have" + gpost)
    stats["ch_openings"] += 1
  if not dry_run and t1 != vr1.static_file.read_text():
    vr1.static_file.write_text(t1)

  # 2. Bhāruci chapter-opening essays from jagannAtha-pAThaH/01..04 & derrett-pAThaH/07..09
  bh_open_files: list[tuple[str, Path, str, str]] = [
    ("01", MANU_CONTENT_DIR / "bhAruchiH/jagannAtha-pAThaH/01.md", "स्वस्ति श्रीगणाधिपतये", r"\n\{?मनुम् एकाग्रम्"),
    ("02", MANU_CONTENT_DIR / "bhAruchiH/jagannAtha-pAThaH/02.md", "एवं तावच् छास्त्रारम्भ", r"\n\{?विद्वद्भिः"),
    ("03", MANU_CONTENT_DIR / "bhAruchiH/jagannAtha-pAThaH/03.md", "द्विविधो ब्रह्मचारी", r"\n\{?षट्त्रिंशद्"),
    ("04", MANU_CONTENT_DIR / "bhAruchiH/jagannAtha-pAThaH/04.md", "आश्रमाणां समुच्चयपक्षम्", r"\n\{?चतुर्थम्"),
    ("07", MANU_CONTENT_DIR / "bhAruchiH/derrett-pAThaH/07.md", "एवम् एकाश्रम्यं", r"\n>\s*\*\*राजधर्मान्"),
    ("08", MANU_CONTENT_DIR / "bhAruchiH/derrett-pAThaH/08.md", "एवम् अयं सप्तमाध्यायोपदिष्टेन", r"\n>\s*\*\*व्यवहारान्"),
    ("09", MANU_CONTENT_DIR / "bhAruchiH/derrett-pAThaH/09.md", "स्वधर्मं श्रौतं", r"\n>\s*\*\*पुरुषस्य"),
  ]
  for ch, src_path, start_marker, end_re in bh_open_files:
    if not src_path.exists():
      continue
    st = src_path.read_text()
    ms = regex.search(rf"({regex.escape(start_marker)}.*?)(?={end_re})", st, flags=regex.DOTALL)
    if ms:
      avatarikas[by_ch[ch][0].rel_url]["भारुचिः - अवतारिका"].append(ms.group(1).strip())
      stats["ch_openings"] += 1

  # 3. Walk EVERY verse across ch 01..12 and extract leading/trailing _..._ from मेधातिथिः & भारुचिः
  for ch, vrefs in sorted(by_ch.items()):
    ch_pool = norm_fns.get(ch, {})
    for idx, vr in enumerate(vrefs):
      stxt = vr.static_file.read_text()
      changed = False
      # Also look ahead one verse in case Medhātithi's trailing _..._ footnote def landed in vr[idx+1]!
      nxt_medh_defs = {}
      if idx + 1 < len(vrefs):
        nxt_body = _get_leaf_block_body(vrefs[idx + 1].static_file.read_text(), "मेधातिथिः") or ""
        nxt_medh_defs = parse_footnotes_markdown(nxt_body)
      merged_pool = {**ch_pool, **nxt_medh_defs}

      for auth, av_key, lead_stat, trail_stat in (
        ("मेधातिथिः", "मेधातिथिः - अवतारिका", "medh_leading", "medh_trailing"),
        ("भारुचिः", "भारुचिः - अवतारिका", "bh_leading", "bh_trailing"),
      ):
        body = _get_leaf_block_body(stxt, auth)
        if not body:
          continue
        # Pass both raw & normalized-digit keys in extra_footnotes
        raw_pool = {**merged_pool}
        for r_m in regex.finditer(r"\[\^([^\]\n]+)\](?!:)", body):
          rk = r_m.group(1).strip()
          rn = _norm_digits(rk)
          if rk not in raw_pool and rn in merged_pool:
            raw_pool[rk] = merged_pool[rn]
        lead_av, core_body, trail_av = split_leading_and_trailing_italic_avatarika(body, extra_footnotes=raw_pool)
        if lead_av:
          avatarikas[vr.rel_url][av_key].append(lead_av)
          stats[lead_stat] += 1
        if trail_av and idx + 1 < len(vrefs):
          avatarikas[vrefs[idx + 1].rel_url][av_key].append(trail_av)
          stats[trail_stat] += 1
        if core_body != body:
          stxt = _replace_leaf_block_body(stxt, auth, core_body)
          changed = True
      if changed and not dry_run:
        vr.static_file.write_text(stxt)
  return stats


def _render_avatarika_wrapper(blocks_by_author: dict[str, list[str]]) -> str:
  """Render `<details><summary>सर्वा अवतारिकाः</summary>` in deterministic author order."""
  inner: list[str] = []
  seen: set[str] = set()
  for author in list(_AVATARIKA_ORDER) + sorted(blocks_by_author.keys()):
    if author in seen or author not in blocks_by_author:
      continue
    seen.add(author)
    parts: list[str] = []
    for p in blocks_by_author[author]:
      cp = p.strip()
      if cp and cp not in parts:
        parts.append(cp)
    if parts:
      inner.append(f"<details><summary>{author}</summary>\n\n" + "\n\n".join(parts) + "\n</details>")
  if not inner:
    return ""
  return "<details><summary>सर्वा अवतारिकाः</summary>\n\n" + "\n\n".join(inner) + "\n</details>"


def write_avatarika_blocks_to_sarva_prastuti(
  avatarikas: dict[str, dict[str, list[str]]],
  *,
  dry_run: bool = False,
) -> dict[str, int]:
  """Insert or merge ``सर्वा अवतारिकाः`` wrappers immediately above target ``विश्वास-प्रस्तुतिः`` blocks."""
  stats = {"files_updated": 0, "verse_clusters_with_av": 0}
  if not avatarikas:
    return stats

  for p in sorted(MANU_SP_DIR.rglob("*.md")):
    if p.name == "_index.md":
      continue
    orig = p.read_text()
    rebuilt_parts: list[str] = []
    pos = 0
    file_changed = False
    for m in regex.finditer(
      r'<details open><summary>विश्वास-प्रस्तुतिः</summary>.*?</details>\s*'
      r'<div class="js_include[^>]*url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/([^"]+)"',
      orig,
      flags=regex.DOTALL,
    ):
      rel_url = m.group(1)
      av_map = avatarikas.get(rel_url)
      prefix_slice = orig[pos : m.start()]
      if av_map:
        merged: dict[str, list[str]] = defaultdict(list)
        if "<summary>सर्वा अवतारिकाः</summary>" in prefix_slice:
          top_blks = [b for b in details_common.parse_top_level_details(prefix_slice, skip_js_includes=True) if b[2].strip() == "सर्वा अवतारिकाः"]
          if top_blks and prefix_slice[top_blks[-1][1] :].strip() == "":
            av_s, _, _, av_body = top_blks[-1]
            for _, _, sub_t, sub_b in details_common.parse_top_level_details(av_body):
              t, b = sub_t.strip(), sub_b.strip()
              if t and b:
                merged[t].append(b)
            prefix_slice = prefix_slice[:av_s]
        for k, vlist in av_map.items():
          merged[k].extend(vlist)
        rendered = _render_avatarika_wrapper(merged)
        rebuilt_parts.append(prefix_slice.rstrip("\n") + ("\n\n" if prefix_slice.strip() else ""))
        rebuilt_parts.append(rendered + "\n\n")
        stats["verse_clusters_with_av"] += 1
        file_changed = True
      else:
        rebuilt_parts.append(prefix_slice)
      rebuilt_parts.append(orig[m.start() : m.end()])
      pos = m.end()
    rebuilt_parts.append(orig[pos:])
    updated = "".join(rebuilt_parts)
    if updated != orig and file_changed:
      if not dry_run:
        p.write_text(updated)
      stats["files_updated"] += 1
  return stats


# ---------------------------------------------------------------------------
# Phase F: Metadata preservation & obsolete file cleanup
# ---------------------------------------------------------------------------

def preserve_and_cleanup_yajnavalkya(*, dry_run: bool = False) -> dict[str, int]:
  """Preserve Yājñavalkya edition credits/TOC and delete obsolete commentary folders."""
  stats = {"updated_indexes": 0, "deleted_entries": 0}
  toc_src = YAJ_CONTENT_DIR / "mitAxarA/01_AchAraH/_index.md"
  toc_dst = YAJ_CONTENT_DIR / "sarva-prastutiH/01_AchAraH/_index.md"
  if toc_src.exists() and toc_dst.exists():
    _, toc_body = strip_frontmatter(toc_src.read_text())
    dst_txt = toc_dst.read_text()
    if toc_body.strip() and toc_body.strip() not in dst_txt:
      if not dry_run:
        toc_dst.write_text(dst_txt.rstrip() + "\n\n" + toc_body.strip() + "\n")
      stats["updated_indexes"] += 1

  idx_dst = YAJ_CONTENT_DIR / "_index.md"
  idx_txt = idx_dst.read_text()
  if "संस्करण-परिचयः" not in idx_txt:
    sections: list[str] = []
    meta_sources = [
      ("मिताक्षरा — Acknowledgement (Olivelle / Davis)", YAJ_CONTENT_DIR / "mitAxarA/Acknowledgement.md"),
      ("मिताक्षरा — About the Author and the Work", YAJ_CONTENT_DIR / "mitAxarA/About_the_Author_and_the_Work.md"),
      ("मिताक्षरा — Formatting & Editorial Notes", YAJ_CONTENT_DIR / "mitAxarA/Formatting_and_Editorial_Notes.md"),
      ("मिताक्षरा — Abbreviations", YAJ_CONTENT_DIR / "mitAxarA/ABBREVIATIONS.md"),
      ("अपरार्कः — Meta (Olivelle)", YAJ_CONTENT_DIR / "aparArkaH/meta.md"),
      ("बालक्रीडा — Meta & Abbreviations (Olivelle)", YAJ_CONTENT_DIR / "bAlakrIDA/Meta.md"),
    ]
    for title, spath in meta_sources:
      if spath.exists():
        _, sbody = strip_frontmatter(spath.read_text())
        if sbody.strip():
          sections.append(f"<details><summary>{title}</summary>\n\n{sbody.strip()}\n</details>")
    sections.append(
      "<details><summary>मूलपाठः (MUM / Nirnayasagara Press 1949)</summary>\n\n"
      "Narayan Ram Acharya, *Yājñavalkyasmṛti of Yogīśvara Yājñavalkya with the commentary Mitākṣarā of Vijñāneśvara*, "
      "Nirnayasagara Press, Bombay 1949. Typescript edited by Muneo Tokunaga, checked by Yasuke Ikari; Devanagari conversion "
      "by Ralph Bunker; MUM Vedic Literature Collection.\n</details>"
    )
    wrapper = "<details><summary>संस्करण-परिचयः (Editions, Credits & Abbreviations)</summary>\n\n" + "\n\n".join(sections) + "\n</details>\n"
    if not dry_run:
      idx_dst.write_text(idx_txt.rstrip() + "\n\n" + wrapper)
    stats["updated_indexes"] += 1

  for target in ("mitAxarA", "aparArkaH", "bAlakrIDA", "MUM.md"):
    p = YAJ_CONTENT_DIR / target
    if p.exists():
      if not dry_run:
        if p.is_dir():
          shutil.rmtree(p)
        else:
          p.unlink()
      stats["deleted_entries"] += 1
  return stats


def preserve_and_cleanup_manu(*, dry_run: bool = False) -> dict[str, int]:
  """Preserve Manu edition credits, Intro, Abbreviations, and Kullūka indices; delete obsolete folders."""
  stats = {"preserved_articles": 0, "deleted_dirs": 0}
  articles_dir = MANU_CONTENT_DIR / "articles"
  editions_path = articles_dir / "editions.md"
  anukrama_path = articles_dir / "kullUka-parishiShTam.md"

  if not editions_path.exists():
    blocks: list[str] = []
    medh_sources = [
      ("मेधातिथिः — Introduction (Patrick Olivelle)", MANU_CONTENT_DIR / "medhAtithiH/Intro.md"),
      ("मेधातिथिः — Abbreviations", MANU_CONTENT_DIR / "medhAtithiH/Abbreviations.md"),
      ("मेधातिथिः — Digitization Info", MANU_CONTENT_DIR / "medhAtithiH/Digitization_info.md"),
      ("मेधातिथिः — Formatting & Editorial Notes", MANU_CONTENT_DIR / "medhAtithiH/Formatting_and_Editorial_Notes.md"),
    ]
    for title, sp in medh_sources:
      if sp.exists():
        _, b = strip_frontmatter(sp.read_text())
        if b.strip():
          blocks.append(f"## {title}\n\n{b.strip()}")

    gov_idx = MANU_CONTENT_DIR / "govindarAjaH/_index.md"
    if gov_idx.exists():
      gm = regex.search(r"<details><summary>विस्तारः \(द्रष्टुं नोद्यम्\)</summary>(.*?)</details>", gov_idx.read_text(), regex.DOTALL)
      if gm:
        blocks.append(f"## गोविन्दराजः — Edition & Credits (Patrick Olivelle)\n\n{gm.group(1).strip()}")

    kull_idx = MANU_CONTENT_DIR / "kullUkaH/_index.md"
    if kull_idx.exists():
      _, kb = strip_frontmatter(kull_idx.read_text())
      # Cut off before विषय-अनुक्रमणिका table
      bhumika = regex.split(r"\n\*\*मनुस्मृतिविषयानुक्रमणिका|\n\|", kb, maxsplit=1)[0]
      bhumika = regex.sub(r"<MISSING_FIG[^>]*/?>", "", bhumika).strip()
      if bhumika:
        blocks.append(f"## कुल्लूकभट्टः — मन्वर्थमुक्तावली भूमिका (बनारस १९३५)\n\n{bhumika}")

    bh_idx = MANU_CONTENT_DIR / "bhAruchiH/_index.md"
    if bh_idx.exists():
      _, bb = strip_frontmatter(bh_idx.read_text())
      if bb.strip():
        blocks.append(f"## भारुचिः — मनुशास्त्रविवरणम्\n\n{bb.strip()}\n\nChapters 1–6 follow J. N. Jagannatha's edition; Chapters 6.9–12 follow J. D. M. Derrett's edition.")

    if not dry_run:
      editions_path.write_text('+++\ntitle = "Editions, Credits & Notes"\n+++\n\n' + "\n\n".join(blocks) + "\n")
    stats["preserved_articles"] += 1

  if not anukrama_path.exists():
    parts: list[str] = []
    kull_idx = MANU_CONTENT_DIR / "kullUkaH/_index.md"
    if kull_idx.exists():
      _, kb = strip_frontmatter(kull_idx.read_text())
      m_vi = regex.search(r"(\*\*मनुस्मृतिविषयानुक्रमणिका.*)", kb, regex.DOTALL)
      if m_vi:
        parts.append("## मनुस्मृति-विषयानुक्रमणिका\n\n" + m_vi.group(1).strip())
    kull12 = MANU_CONTENT_DIR / "kullUkaH/12.md"
    if kull12.exists():
      _, k12b = strip_frontmatter(kull12.read_text())
      m_app = regex.search(r"(\*\*परिशिष्टम्।.*)", k12b, regex.DOTALL)
      if m_app:
        app_txt = regex.sub(r"<MISSING_FIG[^>]*/?>", "", m_app.group(1)).strip()
        parts.append("## परिशिष्टम् — श्लोकार्धानुक्रमणिका च\n\n" + app_txt)
    if parts and not dry_run:
      anukrama_path.write_text('+++\ntitle = "कुल्लूकः — अनुक्रमणिका परिशिष्टं च"\nunicode_script = "devanagari"\n+++\n\n' + "\n\n".join(parts) + "\n")
    stats["preserved_articles"] += 1

  for target in ("medhAtithiH", "kullUkaH", "govindarAjaH", "bhAruchiH"):
    p = MANU_CONTENT_DIR / target
    if p.exists():
      if not dry_run:
        shutil.rmtree(p)
      stats["deleted_dirs"] += 1
  return stats


def run_migration(*, dry_run: bool = False, cleanup_obsolete: bool = True) -> dict:
  """Execute all manuH interleaving + avatārikā steps, prefill/audit, and obsolete cleanup."""
  rep = repair_sarva_prastuti_and_external(dry_run=dry_run)
  print("Phase A (repair):", rep)

  patch = patch_medhatithi_and_bharuchi_gaps(dry_run=dry_run)
  print("Phase B (patch medh/bh):", patch)

  by_ch = load_manu_chapter_verses()
  avatarikas: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

  gov_stats = interleave_govindaraja(by_ch, avatarikas, dry_run=dry_run)
  print("Phase C1 (govindarAja):", gov_stats)

  kull_stats = interleave_kulluka(by_ch, avatarikas, dry_run=dry_run)
  print("Phase C2 (kullUka):", kull_stats)

  av_extract = extract_medhatithi_bharuchi_avatarikas(by_ch, avatarikas, dry_run=dry_run)
  print("Phase D1 (extract avatārikās):", av_extract)

  av_write = write_avatarika_blocks_to_sarva_prastuti(avatarikas, dry_run=dry_run)
  print("Phase D2 (write सर्वा अवतारिकाः):", av_write)

  if not dry_run:
    pf1 = include_transformer.surgical_prefill_includes(dir_path=str(MANU_SP_DIR), hugo_base_dir=HUGO_BASE_DIR)
    pf2 = include_transformer.surgical_prefill_includes(dir_path=str(DANDA_PATH.parent), file_name_filter=lambda p: str(p).endswith("daNDaH.md"), hugo_base_dir=HUGO_BASE_DIR)
    print("Phase E1 (surgical_prefill):", {"manu_sp": pf1, "danda": pf2})
    audit = include_seeker.audit_includes([str(MANU_SP_DIR), str(DANDA_PATH.parent)], hugo_base_dir=HUGO_BASE_DIR)
    print("Phase E2 (audit_includes):", audit)

  if cleanup_obsolete:
    yaj_clean = preserve_and_cleanup_yajnavalkya(dry_run=dry_run)
    manu_clean = preserve_and_cleanup_manu(dry_run=dry_run)
    print("Phase F (cleanup):", {"yAJNavalkyaH": yaj_clean, "manuH": manu_clean})

  return {
    "repair": rep,
    "patch": patch,
    "govindaraja": gov_stats,
    "kulluka": kull_stats,
    "av_extract": av_extract,
    "av_write": av_write,
  }


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--dry-run", action="store_true", help="Inspect actions without modifying files.")
  parser.add_argument("--no-cleanup", action="store_true", help="Skip obsolete folder removal.")
  args = parser.parse_args()
  run_migration(dry_run=args.dry_run, cleanup_obsolete=not args.no_cleanup)


if __name__ == "__main__":
  main()
