"""Migrate Yājñavalkya Smṛti ``sarva-prastutiH`` to inline ``विश्वास-प्रस्तुतिः`` + ``sarvASh_TIkAH`` includes.

Reads the 44 prakaraṇas under ``content/dharmaH/smRtiH/yAJNavalkyaH/sarva-prastutiH/``,
aligns Mitākṣarā (विज्ञानेश्वरः), Aparārka (अपरार्कः), and Bālakrīḍā (विश्वरूपः)
commentaries via ``doc_curation.md.content_processor.commentary.lemma_aligner``,
writes per-verse unwrapped leaf files to ``static/smRtiH/yAjJNavalkyaH/sarvASh_TIkAH/``,
rewrites ``sarva-prastutiH/`` with inline ``विश्वास-प्रस्तुतिः``, ``सर्वा अवतारिकाः``
(where present), and prefilled ``सर्वाष् टीकाः`` includes matching ``manuH/``.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path

import regex
from curation_utils import file_helper
from doc_curation.md.content_processor.commentary.helper import wrap_commentaries_in_details
from doc_curation.md.content_processor.commentary.lemma_aligner import (
  CommentaryAlignment,
  VerseSpec,
  align_commentary_sections,
  build_sarva_tikah_entry,
  inline_footnotes_for_block,
  parse_footnotes_markdown,
  strip_frontmatter,
)
from doc_curation.md.content_processor.include import seeker as include_seeker
from doc_curation.md.content_processor.include import transformer as include_transformer
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


HUGO_BASE = "/home/vvasuki/gitland/vishvAsa"
SITE_NAME = "kalpAntaram"
CONTENT_BASE = os.path.join(HUGO_BASE, SITE_NAME, "content/dharmaH/smRtiH/yAJNavalkyaH")
STATIC_BASE = os.path.join(HUGO_BASE, SITE_NAME, "static/smRtiH/yAjJNavalkyaH")

SARVA_PRASTUTI_DIR = os.path.join(CONTENT_BASE, "sarva-prastutiH")
MULAM_STATIC_DIR = os.path.join(STATIC_BASE, "mUlam")
VP_STATIC_DIR = os.path.join(STATIC_BASE, "vishvAsa-prastutiH")
TIKAH_STATIC_DIR = os.path.join(STATIC_BASE, "sarvASh_TIkAH")

COMMENTARIES: list[tuple[str, str]] = [
  ("विज्ञानेश्वरः", "mitAxarA"),
  ("अपरार्कः", "aparArkaH"),
  ("विश्वरूपः", "bAlakrIDA"),
]

# Known stray text outside js_include in existing sarva-prastutiH that should move
# into विश्वास-टिप्पनी for the corresponding verse.
EXTRA_VERSE_NOTES: dict[str, list[tuple[str, str]]] = {
  "01_AchAraH/06_snAtaka-dharma-prakaraNam/144_tryaham_preteShv.md": [
    ("विश्वास-टिप्पनी", "[स्वाशाखा-श्रोत्रिये त्xत्]"),
  ],
}


@dataclass(frozen=True)
class PrakaranaUnit:
  rel_path: str
  chapter: str
  section_id: str
  frontmatter: str
  verses: list[tuple[VerseSpec, str]]  # (VerseSpec, vp_body)


def _index_vp_by_basename() -> dict[str, str]:
  by_name: dict[str, str] = {}
  for path in sorted(glob.glob(os.path.join(VP_STATIC_DIR, "**/*.md"), recursive=True)):
    base = os.path.basename(path)
    if base in by_name:
      raise ValueError(f"Duplicate vishvAsa-prastutiH basename: {base}")
    by_name[base] = path
  return by_name


def _extract_inline_block_for_verse(sp_body: str, index: int, tag_title: str) -> str:
  pat = regex.compile(rf"<details[^>]*><summary>{regex.escape(tag_title)}</summary>\s*([\s\S]*?)\s*</details>")
  matches = pat.findall(sp_body)
  return matches[index].strip() if index < len(matches) else ""


def _resolve_mula_source(rel_v: str, tik_path: str) -> tuple[str, str]:
  """Read ``(title, mula_body)`` from static ``mUlam/`` or an already-migrated ``sarvASh_TIkAH/`` file."""
  m_path = os.path.join(MULAM_STATIC_DIR, rel_v)
  if os.path.isfile(m_path):
    m_meta, m_body = MdFile(file_path=m_path).read()
    return str(m_meta.get("title", "")).strip(), m_body.strip()
  if os.path.isfile(tik_path):
    t_meta, t_body = MdFile(file_path=tik_path).read()
    m = regex.search(r"<details><summary>मूलम्</summary>\s*([\s\S]*?)\s*</details>", t_body)
    if m:
      return str(t_meta.get("title", "")).strip(), m.group(1).strip()
  raise FileNotFoundError(f"Could not resolve root verse {rel_v} in mUlam/ or sarvASh_TIkAH/")


def _resolve_vp_body(rel_verse_path: str, mula_body: str, vp_by_name: dict[str, str], inline_fallback: str = "") -> str:
  direct = os.path.join(VP_STATIC_DIR, rel_verse_path)
  if os.path.isfile(direct):
    _, vp_body = strip_frontmatter(Path(direct).read_text())
    return vp_body.strip()
  by_name = vp_by_name.get(os.path.basename(rel_verse_path))
  if by_name and os.path.isfile(by_name):
    _, vp_body = strip_frontmatter(Path(by_name).read_text())
    return vp_body.strip()
  return inline_fallback.strip() or mula_body.strip()


def _load_prakaranas() -> tuple[list[PrakaranaUnit], dict[str, list[VerseSpec]], list[VerseSpec]]:
  """Load all 44 prakaraṇas and expand any multi-verse ``mUlam`` file cleanly (idempotent)."""
  vp_by_name = _index_vp_by_basename() if os.path.isdir(VP_STATIC_DIR) else {}
  sp_files = sorted(
    p for p in glob.glob(os.path.join(SARVA_PRASTUTI_DIR, "**/*.md"), recursive=True)
    if not p.endswith("_index.md")
  )
  units: list[PrakaranaUnit] = []
  by_chapter: dict[str, list[VerseSpec]] = {}
  global_verses: list[VerseSpec] = []

  for sp_path in sp_files:
    raw_sp = Path(sp_path).read_text()
    fm, sp_body = strip_frontmatter(raw_sp)
    rel_sp = os.path.relpath(sp_path, SARVA_PRASTUTI_DIR)
    chapter = rel_sp.split("/")[0]
    sec_id = os.path.basename(sp_path)[:-3]
    by_chapter.setdefault(chapter, [])

    urls = regex.findall(r'url="([^"]+)"', sp_body)
    unit_verses: list[tuple[VerseSpec, str]] = []
    for u_idx, u in enumerate(urls):
      if "/yAjJNavalkyaH/mUlam/" in u:
        rel_v = u.split("/yAjJNavalkyaH/mUlam/", 1)[1]
      elif "/yAjJNavalkyaH/sarvASh_TIkAH/" in u:
        rel_v = u.split("/yAjJNavalkyaH/sarvASh_TIkAH/", 1)[1]
      else:
        raise ValueError(f"Unexpected include URL in {rel_sp}: {u}")
      tik_path = os.path.join(TIKAH_STATIC_DIR, rel_v)
      m_title, m_body = _resolve_mula_source(rel_v, tik_path)
      inline_vp = _extract_inline_block_for_verse(sp_body, u_idx, "विश्वास-प्रस्तुतिः")

      parts = [p.strip() for p in regex.split(r"\n\s*\n", m_body) if p.strip()]
      if len(parts) > 1 and all("॥" in pt for pt in parts):
        # 03_prAyashchittam/5_prAyashchitta-prakaraNam/283_kriyamANopakAre_tu.md contains two verses (283: and 284).
        for idx_p, pt in enumerate(parts):
          if idx_p == 0:
            sub_rel = os.path.join(os.path.dirname(rel_v), "283-1_kriyamANopakAre_tu.md")
            sub_title = "283-१ क्रियमाणोपकारे तु"
          else:
            slug = file_helper.get_storage_name(text="284 मिथ्याभिशंसिनो दोषो", source_script=sanscript.DEVANAGARI)
            sub_rel = os.path.join(os.path.dirname(rel_v), f"{slug}.md")
            sub_title = "284 मिथ्याभिशंसिनो दोषो"
          vp_body = _resolve_vp_body(sub_rel, pt, vp_by_name)
          spec = VerseSpec.from_text(len(by_chapter[chapter]), sub_rel, sec_id, pt, title=sub_title)
          by_chapter[chapter].append(spec)
          global_verses.append(spec)
          unit_verses.append((spec, vp_body))
      else:
        vp_body = _resolve_vp_body(rel_v, m_body, vp_by_name, inline_fallback=inline_vp)
        spec = VerseSpec.from_text(len(by_chapter[chapter]), rel_v, sec_id, m_body, title=m_title)
        by_chapter[chapter].append(spec)
        global_verses.append(spec)
        unit_verses.append((spec, vp_body))

    units.append(
      PrakaranaUnit(
        rel_path=rel_sp,
        chapter=chapter,
        section_id=sec_id,
        frontmatter=fm,
        verses=unit_verses,
      )
    )

  return units, by_chapter, global_verses


def _align_all_commentaries(
  by_chapter: dict[str, list[VerseSpec]],
  global_verses: list[VerseSpec],
) -> dict[str, tuple[dict[str, CommentaryAlignment], dict[str, str]]]:
  """Align each commentary chapter-by-chapter and parse its footnotes."""
  aligned: dict[str, tuple[dict[str, CommentaryAlignment], dict[str, str]]] = {}
  for author_label, comm_dir in COMMENTARIES:
    fn_path = os.path.join(CONTENT_BASE, comm_dir, "Footnotes.md")
    fn_map = parse_footnotes_markdown(Path(fn_path).read_text()) if os.path.isfile(fn_path) else {}
    per_ch: dict[str, CommentaryAlignment] = {}
    for chapter, verses in by_chapter.items():
      ch_path = os.path.join(CONTENT_BASE, comm_dir, chapter)
      if not os.path.isdir(ch_path):
        continue
      sec_files = [
        (os.path.basename(cp)[:-3], Path(cp).read_text())
        for cp in sorted(glob.glob(os.path.join(ch_path, "*.md")))
        if os.path.basename(cp) != "_index.md"
      ]
      per_ch[chapter] = align_commentary_sections(
        sec_files,
        verses,
        global_unmatched_verses=global_verses,
      )
    aligned[author_label] = (per_ch, fn_map)
  return aligned


def migrate(dry_run: bool = False) -> tuple[int, int]:
  """Run the full migration and prefill; return ``(num_static_written, num_host_written)``."""
  units, by_chapter, global_verses = _load_prakaranas()
  aligned = _align_all_commentaries(by_chapter, global_verses)

  # Build lookup of all aligned verse slices and chapter/section avatārikās per author
  author_verse_body: dict[str, dict[str, str]] = {}
  author_section_av: dict[str, dict[tuple[str, str], str]] = {}
  for author_label, (per_ch, fn_map) in aligned.items():
    v_map: dict[str, str] = {}
    av_map: dict[tuple[str, str], str] = {}
    for ch, res in per_ch.items():
      for vid, chunks in res.per_verse.items():
        merged = "\n\n".join(chunks).strip()
        v_map[vid] = inline_footnotes_for_block(merged, fn_map)
      for sec_id, av in res.per_section_avatarika.items():
        av_map[(ch, sec_id)] = inline_footnotes_for_block(av, fn_map)
    author_verse_body[author_label] = v_map
    author_section_av[author_label] = av_map

  static_count = 0
  host_count = 0

  # Root _index.md for static sarvASh_TIkAH/ matching manuH
  root_idx_path = os.path.join(TIKAH_STATIC_DIR, "_index.md")
  if not dry_run:
    os.makedirs(TIKAH_STATIC_DIR, exist_ok=True)
    MdFile(file_path=root_idx_path).dump_to_file(metadata={"title": "+सर्वाष् टीकाः"}, content="", dry_run=False)

  for unit in units:
    host_blocks: list[str] = []

    # File-top prakaraṇa introductions wrapped via wrap_commentaries_in_details
    for author_label, _ in COMMENTARIES:
      av_text = author_section_av[author_label].get((unit.chapter, unit.section_id), "").strip()
      if av_text:
        host_blocks.append(f"<details><summary>{author_label} - अवतारिका</summary>\n\n{av_text}\n</details>")

    for vspec, vp_body in unit.verses:
      comm_blocks = [
        (author_label, author_verse_body[author_label].get(vspec.verse_id, ""))
        for author_label, _ in COMMENTARIES
      ]
      extra = EXTRA_VERSE_NOTES.get(vspec.verse_id, ())
      static_body = build_sarva_tikah_entry(vspec.text, comm_blocks, extra_blocks=extra)
      static_path = os.path.join(TIKAH_STATIC_DIR, vspec.verse_id)
      if not dry_run:
        MdFile(file_path=static_path).dump_to_file(
          metadata={"title": vspec.title},
          content=static_body.strip() + "\n",
          dry_run=False,
        )
      static_count += 1

      tikah_url = f"/{SITE_NAME}/smRtiH/yAjJNavalkyaH/sarvASh_TIkAH/{vspec.verse_id}"
      host_blocks.append(f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp_body}\n</details>")
      host_blocks.append(
        f'<div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" unfilled="" url="{tikah_url}">\n'
        f"<details><summary><h4>सर्वाष् टीकाः …{{Loading}}…</h4></summary>\n"
        f"</details>\n"
        f"</div>"
      )

    raw_host_body = "\n\n".join(host_blocks) + "\n"
    wrapped_host_body = wrap_commentaries_in_details(
      raw_host_body,
      block_name="सर्वाष् टीकाः",
      exclude=("विश्वास-प्रस्तुतिः",),
      avatarika_block_name="सर्वा अवतारिकाः",
    )
    host_text = f"{unit.frontmatter.rstrip()}\n\n{wrapped_host_body.lstrip()}"
    host_path = os.path.join(SARVA_PRASTUTI_DIR, unit.rel_path)
    if not dry_run:
      Path(host_path).write_text(host_text)
    host_count += 1

  if not dry_run:
    include_transformer.surgical_prefill_includes(
      dir_path=SARVA_PRASTUTI_DIR,
      hugo_base_dir=HUGO_BASE,
      dry_run=False,
    )
    report = include_seeker.audit_includes(
      dir_paths=[SARVA_PRASTUTI_DIR, TIKAH_STATIC_DIR],
      hugo_base_dir=HUGO_BASE,
      url_prefix=f"/{SITE_NAME}/",
      strict=True,
      check_tags=True,
    )
    if report.broken_includes or report.unbalanced_files:
      raise RuntimeError(
        f"Audit failed: broken={len(report.broken_includes)} ({report.broken_includes[:3]}), "
        f"unbalanced={len(report.unbalanced_files)} ({report.unbalanced_files[:3]})"
      )
    print(f"Audit clean across {report.scanned_files} files.")

  return static_count, host_count


if __name__ == "__main__":
  s_cnt, h_cnt = migrate(dry_run=False)
  print(f"Migrated {s_cnt} sarvASh_TIkAH verse files and {h_cnt} sarva-prastutiH prakaraNa files.")
