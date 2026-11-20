"""Download and build Kāṇva Śatapatha Brāhmaṇa ``sarva-prastutiH`` from svarupa.org (scriptureId=22)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from curation_utils import file_helper
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.scraping.misc_sites import svarupa
from indic_transliteration import sanscript

SCRIPTURE_ID = 22
CONTENT_BASE = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/"
DEFAULT_DEST_ROOT = os.path.join(CONTENT_BASE, "sarva-prastutiH")


def to_deva_num(n: int, min_digits: int = 1) -> str:
  """Format integer ``n`` in Devanagari digits zero-padded to at least ``min_digits``."""
  s = f"{n:0{min_digits}d}" if min_digits > 1 else str(n)
  return sanscript.transliterate(s, sanscript.OPTITRANS, sanscript.DEVANAGARI)


def kanda_dir_name(kanda_node: Mapping[str, Any]) -> str:
  """Return canonical directory name like ``01_ekapAtkANDam`` from a svarupa kāṇḍa node."""
  order = int(kanda_node["order"])
  name = str(kanda_node.get("type") or kanda_node.get("name") or "").strip()
  storage = file_helper.get_storage_name(name.lower(), source_script=sanscript.IAST)
  return f"{order:02d}_{storage}"


def format_kandika_section(
  kandika_num: int,
  mula_text: str,
  *,
  commentaries: list[tuple[str, str]] | None = None,
) -> str:
  """Format one kaṇḍikā heading and ``<details>`` blocks."""
  heading = f"## {to_deva_num(kandika_num, 2)}"
  blocks = [f"<details open><summary>मूलम्</summary>\n\n{mula_text}\n</details>"]
  for label, body in commentaries or ():
    blocks.append(f"<details><summary>{label}</summary>\n\n{body}\n</details>")
  return heading + "\n\n" + "\n\n".join(blocks)


def _extract_sanskrit_text(mantra_item: Mapping[str, Any]) -> str:
  for lang in mantra_item.get("language") or ():
    if lang.get("languageName") == "Sanskrit":
      return str(lang.get("vedamanatra") or "")
  raise KeyError(f"Missing Sanskrit text for mantra {mantra_item.get('mantraIndex')}")


def build_sarva_prastuti(
  tree: list[dict[str, Any]],
  overviews: Mapping[str, Any],
  mantras_by_leaf: Mapping[str, list[dict[str, Any]]],
  *,
  dest_root: str | os.PathLike[str] = DEFAULT_DEST_ROOT,
  views_by_id: Mapping[str, Any] | None = None,
  commentary_language: str = "English",
  preferred_mahatma: str | None = "C R Swaminathan",
) -> dict[str, Any]:
  """Write ``sarva-prastutiH`` directory tree, ``_index.md`` files, Brāhmaṇas, and ``file_list.md``."""
  root = Path(dest_root)
  root.mkdir(parents=True, exist_ok=True)
  views_by_id = views_by_id or {}

  anomalies_udatta: list[str] = []
  anomalies_backtick: list[str] = []
  missing_units: list[str] = []
  files_written = 0
  kandikas_written = 0
  commentaries_written = 0

  for kanda in tree:
    k_ord = int(kanda["order"])
    k_name_iast = str(kanda.get("type") or kanda.get("name") or "")
    k_name_deva = sanscript.transliterate(k_name_iast.lower(), sanscript.IAST, sanscript.DEVANAGARI)
    k_dirname = kanda_dir_name(kanda)
    k_dir = root / k_dirname
    k_dir.mkdir(parents=True, exist_ok=True)

    k_ov = svarupa.clean_overview_html((overviews.get(str(kanda["hierarchyIndex"])) or {}).get("overView"))
    k_index_content = f"<details><summary>सङ्क्षेपः</summary>\n\n{k_ov}\n</details>\n" if k_ov else ""
    MdFile(file_path=str(k_dir / "_index.md"), frontmatter_type=MdFile.TOML).dump_to_file(
      metadata={"title": f"+{to_deva_num(k_ord, 2)} {k_name_deva}"},
      content=k_index_content,
      dry_run=False,
      silent=True,
    )

    expected_a = 1
    for adh in kanda.get("_children") or ():
      a_ord = int(adh["order"])
      while expected_a < a_ord:
        missing_units.append(f"Adhyāya {k_ord}.{expected_a}")
        expected_a += 1
      expected_a = a_ord + 1

      a_dirname = f"{a_ord:02d}"
      a_dir = k_dir / a_dirname
      a_dir.mkdir(parents=True, exist_ok=True)
      MdFile(file_path=str(a_dir / "_index.md"), frontmatter_type=MdFile.TOML).dump_to_file(
        metadata={"title": f"+{to_deva_num(a_ord, 2)}"},
        content="",
        dry_run=False,
        silent=True,
      )

      expected_b = 1
      for br in adh.get("_children") or ():
        b_ord = int(br["order"])
        while expected_b < b_ord:
          missing_units.append(f"Brāhmaṇa {k_ord}.{a_ord}.{expected_b}")
          expected_b += 1
        expected_b = b_ord + 1

        mlist = mantras_by_leaf.get(str(br["hierarchyIndex"])) or []
        rel_md = f"{k_dirname}/{a_dirname}/{b_ord}.md"
        sections: list[str] = []
        expected_m = 1
        for m in mlist:
          mid = str(m["mantraIndex"])
          m_num = int(mid.split(".")[-1])
          while expected_m < m_num:
            missing_units.append(f"Kaṇḍikā {k_ord}.{a_ord}.{b_ord}.{expected_m} (`{rel_md}`)")
            expected_m += 1
          expected_m = m_num + 1

          raw_text = _extract_sanskrit_text(m)
          if "\u0951" in raw_text:
            anomalies_udatta.append(f"`{rel_md}` `## {to_deva_num(m_num, 2)}` (`{m.get('displayIndex', mid)}`)")
          if "`" in raw_text:
            anomalies_backtick.append(f"`{rel_md}` `## {to_deva_num(m_num, 2)}` (`{m.get('displayIndex', mid)}`)")

          mula_text = svarupa.to_madhyandina_svara(raw_text)
          comms = svarupa.extract_commentary_blocks(
            views_by_id.get(mid),
            language=commentary_language,
            preferred_mahatma=preferred_mahatma,
          )
          commentaries_written += len(comms)
          sections.append(format_kandika_section(m_num, mula_text, commentaries=comms))
          kandikas_written += 1

        file_content = "\n\n\n".join(sections) + ("\n" if sections else "")
        MdFile(file_path=str(a_dir / f"{b_ord}.md"), frontmatter_type=MdFile.TOML).dump_to_file(
          metadata={"title": to_deva_num(b_ord, 1)},
          content=file_content,
          dry_run=False,
          silent=True,
        )
        files_written += 1

  root_ov = svarupa.clean_overview_html((overviews.get(str(SCRIPTURE_ID)) or {}).get("overView"))
  root_parts: list[str] = []
  if root_ov:
    root_parts.append(f"<details><summary>सङ्क्षेपः</summary>\n\n{root_ov}\n</details>")

  notes = [
    f"- Source: [svarupa.org (scriptureId={SCRIPTURE_ID})](https://svarupa.org/scriptures?scriptureId={SCRIPTURE_ID})",
    "- Svara conversion: `॒` (`U+0952`) replaced with Mādhyandina Śatapatha Brāhmaṇa svara `᳘` (`U+1CD8`).",
  ]
  if missing_units:
    notes.append("- Missing units on source site: " + ", ".join(missing_units))
  if anomalies_udatta:
    notes.append("- Stray/classical `॑` (`U+0951`) present in source at: " + ", ".join(anomalies_udatta))
  if anomalies_backtick:
    notes.append("- Stray backtick `` ` `` present in source at: " + ", ".join(anomalies_backtick))

  root_parts.append("<details><summary>Notation & TODO</summary>\n\n" + "\n".join(notes) + "\n</details>")
  MdFile(file_path=str(root / "_index.md"), frontmatter_type=MdFile.TOML).dump_to_file(
    metadata={"title": "+सर्व-प्रस्तुतिः"},
    content="\n\n".join(root_parts) + "\n",
    dry_run=False,
    silent=True,
  )

  library.dump_matching_files(dir_path=str(root))
  return {
    "files_written": files_written,
    "kandikas_written": kandikas_written,
    "commentaries_written": commentaries_written,
    "missing_units": missing_units,
    "anomalies_udatta": anomalies_udatta,
    "anomalies_backtick": anomalies_backtick,
  }


def load_views_dir(views_dir: str | os.PathLike[str]) -> dict[str, Any]:
  """Merge all per-kāṇḍa JSON view files in ``views_dir`` into a single ``{mantraIndex: summary}`` dict."""
  merged: dict[str, Any] = {}
  for path in sorted(Path(views_dir).glob("k*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
      merged.update(data)
  return merged


def download_and_build(
  *,
  scratch_profile_dir: str | os.PathLike[str],
  dest_root: str | os.PathLike[str] = DEFAULT_DEST_ROOT,
  fetch_views: bool = True,
  views_cache_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
  """Authenticate from Chrome profile copy, download Kāṇva Śatapatha Brāhmaṇa, and write ``sarva-prastutiH``."""
  tokens = svarupa.extract_tokens_from_chrome_profile(scratch_profile_dir=scratch_profile_dir)
  client = svarupa.SvarupaClient(tokens["authToken"], tokens.get("refreshToken", ""))
  tree, overviews, mantras_by_leaf = client.fetch_tree_and_mantras(SCRIPTURE_ID)

  views_by_id: dict[str, Any] = {}
  if fetch_views:
    cache_dir = Path(views_cache_dir) if views_cache_dir else None
    if cache_dir:
      cache_dir.mkdir(parents=True, exist_ok=True)
    for kanda in tree:
      ord_ = int(kanda["order"])
      if ord_ == 17:
        continue
      cache_path = cache_dir / f"k{ord_:02d}.json" if cache_dir else None
      if cache_path and cache_path.exists():
        views_by_id.update(json.loads(cache_path.read_text(encoding="utf-8")))
        continue
      ids = [
        str(m["mantraIndex"])
        for a in (kanda.get("_children") or ())
        for b in (a.get("_children") or ())
        for m in (mantras_by_leaf.get(str(b["hierarchyIndex"])) or ())
      ]
      k_views = client.fetch_many_mantra_views(ids, compact=True)
      if cache_path:
        cache_path.write_text(json.dumps(k_views, ensure_ascii=False, indent=2), encoding="utf-8")
      views_by_id.update(k_views)

  return build_sarva_prastuti(
    tree,
    overviews,
    mantras_by_leaf,
    dest_root=dest_root,
    views_by_id=views_by_id,
  )


if __name__ == "__main__":
  pass

