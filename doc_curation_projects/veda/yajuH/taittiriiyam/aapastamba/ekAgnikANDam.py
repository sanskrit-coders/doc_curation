"""Merge external ``sarvASh_TIkAH`` into ``ekAgnikANDam/sarvASh_TIkAH``.

For each mantra in ``ekAgnikANDam/vishvAsa-prastutiH`` that includes an external
``vishvAsa-prastutiH`` (from Śākala Ṛgveda, Śaunaka Atharvaveda, Taittirīya
Saṃhitā, etc.), moves the ekAgnikANDa-specific ``हरदत्तः`` ``<details>`` block
into the external ``sarvASh_TIkAH`` target, links and surgically prefills that
external ``sarvASh_TIkAH`` inside ``ekAgnikANDam/sarvASh_TIkAH``, and refreshes
affected host ``js_include`` prefills across the repository tree.
"""

import argparse
import logging
from pathlib import Path
from typing import Callable, Iterable, Optional

import regex

from doc_curation.md.content_processor.include.seeker import file_path_from_url
from doc_curation.md.content_processor.include.transformer import (
  find_js_include_divs,
  surgical_prefill_content,
)
from doc_curation.md.file import MdFile

DEFAULT_HUGO_BASE_DIR = "/home/vvasuki/gitland/vishvAsa"
EK_REL_BASE = Path("vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam")

_DETAILS_TAG_RE = regex.compile(r"<details\b[^>]*>|</details>", regex.S)
_SUMMARY_OPEN_RE = regex.compile(r"^<details\b[^>]*>\s*<summary>(.*?)</summary>", regex.S)
_URL_ATTR_RE = regex.compile(r"""url=(["'])([^"']+)\1""")

_TARGET_ANCHOR_PRIORITY = (
  "भट्टभास्कर-टीका",
  "सायण-भाष्यम्",
  "रङ्गनाथः",
  "Hellwig Grammar",
  "पण्डित क्षेमकरणदास त्रिवेदी - विषयः",
  "अधिमन्त्रम् (VC)",
  "पद-पाठः",
  "पदपाठः",
  "मूलम्",
)

HARADATTA_TITLE = "हरदत्तः"


def normalize_vp_url(url: str) -> str:
  """Fix known path typos in ``ekAgnikANDam`` include URLs."""
  return url.replace("/vedAH_RkshAkalam/", "/vedAH_Rk/shAkalam/")


def is_external_vp_url(url: str) -> bool:
  """Return True if ``url`` points to an external ``vishvAsa-prastutiH`` file."""
  return "/vishvAsa-prastutiH/" in url and "ekAgnikANDam/" not in url


def vp_url_to_st_url(vp_url: str) -> str:
  """Map a ``vishvAsa-prastutiH`` include URL to its sibling ``sarvASh_TIkAH`` URL."""
  return vp_url.replace("/vishvAsa-prastutiH/", "/sarvASh_TIkAH/")


def _normalize_ws(text: str) -> str:
  return regex.sub(r"\s+", " ", text).strip()


def _strip_js_include_ranges(content: str) -> list[tuple[int, int]]:
  """Return top-level ``[start, end)`` spans occupied by ``js_include`` divs."""
  spans = sorted((d[0], d[4]) for d in find_js_include_divs(content))
  merged: list[tuple[int, int]] = []
  for s, e in spans:
    if not merged or s >= merged[-1][1]:
      merged.append((s, e))
  return merged


def _in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
  return any(s <= pos < e for s, e in ranges)


def find_top_level_details(
  content: str,
  *,
  exclude_js_includes: bool = True,
) -> list[tuple[int, int, str, str]]:
  """Return ``(start, end, summary, body)`` for top-level ``<details>`` blocks."""
  excluded = _strip_js_include_ranges(content) if exclude_js_includes else []
  stack: list[int] = []
  results: list[tuple[int, int, str, str]] = []
  for m in _DETAILS_TAG_RE.finditer(content):
    if excluded and _in_ranges(m.start(), excluded) and not stack:
      continue
    tok = m.group(0)
    if tok.startswith("<details"):
      stack.append(m.start())
    elif stack:
      start = stack.pop()
      if not stack:
        block = content[start:m.end()]
        m_sum = _SUMMARY_OPEN_RE.match(block)
        if m_sum:
          summary = m_sum.group(1).strip()
          body = block[m_sum.end(): -len("</details>")].strip()
          results.append((start, m.end(), summary, body))
  return results


def merge_details_into_target(target_content: str, summary_title: str, body: str) -> tuple[str, str]:
  """Insert or merge ``<details><summary>{summary_title}</summary>`` into ``target_content``.

  Returns ``(updated_content, action)`` where ``action`` is one of
  ``"unchanged"``, ``"appended_to_existing"``, ``"replaced_existing"``, or
  ``"inserted"``.
  """
  clean_body = body.strip()
  if not clean_body:
    return target_content, "unchanged"

  top_blocks = find_top_level_details(target_content, exclude_js_includes=False)
  for start, end, summary, existing_body in top_blocks:
    if summary == summary_title:
      norm_new = _normalize_ws(clean_body)
      norm_existing = _normalize_ws(existing_body)
      if norm_new in norm_existing:
        return target_content, "unchanged"
      if norm_existing in norm_new:
        new_block = f"<details><summary>{summary_title}</summary>\n\n{clean_body}\n</details>"
        return target_content[:start] + new_block + target_content[end:], "replaced_existing"
      merged_body = f"{existing_body.strip()}\n\n_________\n\n{clean_body}"
      new_block = f"<details><summary>{summary_title}</summary>\n\n{merged_body}\n</details>"
      return target_content[:start] + new_block + target_content[end:], "appended_to_existing"

  new_block = f"<details><summary>{summary_title}</summary>\n\n{clean_body}\n</details>"
  anchor_end = None
  for anchor in _TARGET_ANCHOR_PRIORITY:
    for _, end, summary, _ in top_blocks:
      if summary == anchor:
        anchor_end = end
    if anchor_end is not None:
      break

  if anchor_end is not None:
    before = target_content[:anchor_end].rstrip()
    after = target_content[anchor_end:].lstrip()
    if after:
      return f"{before}\n\n{new_block}\n\n{after}", "inserted"
    return f"{before}\n\n{new_block}", "inserted"

  base = target_content.rstrip()
  sep = "\n\n" if base else ""
  return f"{base}{sep}{new_block}", "inserted"


def remove_top_level_details(content: str, summary_title: str) -> tuple[str, Optional[str]]:
  """Remove first top-level ``<details>`` matching ``summary_title`` outside ``js_include``.

  Returns ``(updated_content, extracted_body_or_none)``.
  """
  for start, end, summary, body in find_top_level_details(content, exclude_js_includes=True):
    if summary == summary_title:
      before = content[:start].rstrip()
      after = content[end:].lstrip()
      if before and after:
        updated = f"{before}\n\n{after}"
      else:
        updated = before or after
      return updated, body
  return content, None


def _build_include_skeleton(target_st_url: str, target_title: str) -> str:
  h1_level = 2 if "/atharva/" in target_st_url else 5
  return (
    f'<div class="js_include" includetitle="false" newlevelforh1="{h1_level}" unfilled url="{target_st_url}">\n'
    f"<details open><summary><h{h1_level}>{target_title} ...{{Loading}}...</h{h1_level}></summary>\n"
    "__PENDING_PREFILL__\n"
    "</details>\n"
    "</div>"
  )


def _rewrite_include_url(content: str, old_url: str, new_url: str) -> tuple[str, bool]:
  """Replace an existing ``js_include`` ``url`` attribute matching ``old_url``."""
  for s_open, e_open, _, _, _, open_tag in find_js_include_divs(content):
    m_url = _URL_ATTR_RE.search(open_tag)
    if m_url and m_url.group(2) == old_url:
      quote = m_url.group(1)
      new_open = open_tag[:m_url.start()] + f"url={quote}{new_url}{quote}" + open_tag[m_url.end():]
      return content[:s_open] + new_open + content[e_open:], True
  return content, False


def _fix_loading_title(content: str, target_st_url: str, old_titles: tuple[str, ...], target_title: str) -> str:
  """Update a ``js_include`` loading header when its summary used a stem or old vp title."""
  if not target_title or target_title in old_titles:
    return content
  for s_open, e_open, b_start, b_end, _, open_tag in find_js_include_divs(content):
    m_url = _URL_ATTR_RE.search(open_tag)
    if not (m_url and m_url.group(2) == target_st_url):
      continue
    body = content[b_start:b_end]
    for old_title in old_titles:
      if not old_title or old_title == target_title:
        continue
      pat = regex.compile(
        rf"(<details\b[^>]*><summary>(?:<h\d+>)?){regex.escape(old_title)}(\s*(?:\.\.\.|…)\{{Loading\}}(?:\.\.\.|…)(?:</h\d+>)?\s*</summary>)"
      )
      new_body, count = pat.subn(rf"\g<1>{target_title}\g<2>", body, count=1)
      if count:
        return content[:b_start] + new_body + content[b_end:]
  return content


def _static_path_to_url(file_path: Path, hugo_base_dir: Path) -> str:
  rel = file_path.relative_to(hugo_base_dir)
  parts = rel.parts
  # <repo>/static/<rest...> -> /<repo>/<rest...>
  if len(parts) >= 3 and parts[1] == "static":
    return "/" + parts[0] + "/" + "/".join(parts[2:])
  raise ValueError(f"Not a static Hugo path under {hugo_base_dir}: {file_path}")


def _update_vp_file_if_typo(vp_file: Path, *, dry_run: bool) -> tuple[list[str], bool]:
  vp_md = MdFile(str(vp_file))
  meta, content = vp_md.read()
  urls = [m.group(2) for m in _URL_ATTR_RE.finditer(content)]
  fixed_content = content
  for raw_url in urls:
    fixed_url = normalize_vp_url(raw_url)
    if fixed_url != raw_url:
      fixed_content = fixed_content.replace(raw_url, fixed_url)
  changed = fixed_content != content
  if changed and not dry_run:
    vp_md.replace_content_metadata(new_content=fixed_content, new_metadata=meta, dry_run=False)
  return [normalize_vp_url(u) for u in urls if is_external_vp_url(normalize_vp_url(u))], changed


def merge_ekAgnikANDam_includes(
  hugo_base_dir: str = DEFAULT_HUGO_BASE_DIR,
  *,
  dry_run: bool = False,
  filter_rel: Optional[Callable[[str], bool]] = None,
) -> dict:
  """Merge external ``sarvASh_TIkAH`` into ``ekAgnikANDam/sarvASh_TIkAH``.

  Returns a dictionary with counts and sets of modified file paths and URLs.
  """
  base = Path(hugo_base_dir)
  ek_dir = base / EK_REL_BASE
  vp_dir = ek_dir / "vishvAsa-prastutiH"
  st_dir = ek_dir / "sarvASh_TIkAH"

  modified_target_files: set[Path] = set()
  modified_ek_st_files: set[Path] = set()
  modified_ek_vp_files: set[Path] = set()
  modified_urls: set[str] = set()
  skipped_no_ek_st: list[str] = []
  target_actions: dict[str, str] = {}
  errors: list[str] = []

  for vp_file in sorted(vp_dir.rglob("*.md")):
    if not vp_file.is_file():
      continue
    rel = str(vp_file.relative_to(vp_dir))
    if filter_rel is not None and not filter_rel(rel):
      continue

    ext_urls, vp_changed = _update_vp_file_if_typo(vp_file, dry_run=dry_run)
    if not ext_urls:
      continue

    if vp_changed:
      modified_ek_vp_files.add(vp_file)
      modified_urls.add(_static_path_to_url(vp_file, base))

    ek_st_file = st_dir / rel
    if not ek_st_file.exists():
      skipped_no_ek_st.append(rel)
      continue

    ek_st_md = MdFile(str(ek_st_file))
    ek_meta, ek_st_content = ek_st_md.read()
    updated_ek_content = ek_st_content
    extracted_haradatta: Optional[str] = None

    for ext_vp_url in ext_urls:
      target_st_url = vp_url_to_st_url(ext_vp_url)
      target_fp_str = file_path_from_url(target_st_url, str(base), str(ek_st_file))
      if not target_fp_str:
        errors.append(f"Missing target sarvASh_TIkAH for {rel}: {target_st_url}")
        continue
      target_fp = Path(target_fp_str)
      target_md = MdFile(str(target_fp))
      target_meta, target_content = target_md.read()
      target_title = str(target_meta.get("title") or target_fp.stem)

      if extracted_haradatta is None:
        updated_ek_content, extracted_haradatta = remove_top_level_details(updated_ek_content, HARADATTA_TITLE)

      new_target_content = target_content
      action = "unchanged"
      if extracted_haradatta:
        new_target_content, action = merge_details_into_target(
          target_content, HARADATTA_TITLE, extracted_haradatta
        )
      target_actions[rel] = action
      if new_target_content != target_content:
        modified_target_files.add(target_fp)
        modified_urls.add(target_st_url)
        if not dry_run:
          target_md.replace_content_metadata(new_content=new_target_content, new_metadata=dict(target_meta), dry_run=False)

      existing_urls = [
        m.group(2)
        for _, _, _, _, _, tok in find_js_include_divs(updated_ek_content)
        for m in [_URL_ATTR_RE.search(tok)]
        if m
      ]
      if target_st_url in existing_urls:
        updated_ek_content = _fix_loading_title(updated_ek_content, target_st_url, (target_fp.stem,), target_title)
      elif ext_vp_url in existing_urls:
        updated_ek_content, _ = _rewrite_include_url(updated_ek_content, ext_vp_url, target_st_url)
        updated_ek_content = _fix_loading_title(updated_ek_content, target_st_url, (target_fp.stem,), target_title)
      else:
        skeleton = _build_include_skeleton(target_st_url, target_title)
        updated_ek_content = updated_ek_content.rstrip() + "\n\n" + skeleton

      if not dry_run:
        updated_ek_content, _ = surgical_prefill_content(
          updated_ek_content,
          str(ek_st_file),
          url_filter=lambda u, u_t=target_st_url: u == u_t,
          hugo_base_dir=str(base),
        )

    if updated_ek_content != ek_st_content:
      modified_ek_st_files.add(ek_st_file)
      modified_urls.add(_static_path_to_url(ek_st_file, base))
      if not dry_run:
        ek_st_md.replace_content_metadata(new_content=updated_ek_content, new_metadata=ek_meta, dry_run=False)

  return {
    "modified_ek_vp_files": sorted(modified_ek_vp_files),
    "modified_target_files": sorted(modified_target_files),
    "modified_ek_st_files": sorted(modified_ek_st_files),
    "modified_urls": sorted(modified_urls),
    "skipped_no_ek_st": skipped_no_ek_st,
    "target_actions": target_actions,
    "errors": errors,
  }


def refresh_host_prefills(
  modified_urls: Iterable[str],
  search_dirs: Iterable[Path],
  *,
  hugo_base_dir: str = DEFAULT_HUGO_BASE_DIR,
  dry_run: bool = False,
) -> list[Path]:
  """Surgically refresh ``js_include`` prefills referencing any URL in ``modified_urls``."""
  url_set = set(modified_urls)
  if not url_set:
    return []

  def _matches(u: str) -> bool:
    return u in url_set or normalize_vp_url(u) in url_set

  # Pre-filter files by basename stem substring to avoid unnecessary parsing.
  needles = {u.rsplit("/", 1)[-1] for u in url_set}
  updated_hosts: list[Path] = []

  for search_dir in search_dirs:
    if not search_dir.exists():
      continue
    for md_path in sorted(search_dir.rglob("*.md")):
      if not md_path.is_file():
        continue
      raw = md_path.read_text(encoding="utf-8")
      if "js_include" not in raw or not any(n in raw for n in needles):
        continue
      md_file = MdFile(str(md_path))
      meta, content = md_file.read()
      new_content = content
      for raw_u in list(url_set):
        if "/vedAH_Rk/shAkalam/" in raw_u:
          broken = raw_u.replace("/vedAH_Rk/shAkalam/", "/vedAH_RkshAkalam/")
          if broken in new_content:
            new_content = new_content.replace(broken, raw_u)
      new_content, num_edits = surgical_prefill_content(
        new_content,
        str(md_path),
        url_filter=_matches,
        hugo_base_dir=hugo_base_dir,
      )
      if new_content != content or num_edits > 0:
        updated_hosts.append(md_path)
        if not dry_run:
          md_file.replace_content_metadata(new_content=new_content, new_metadata=meta, dry_run=False)

  return updated_hosts


def merge_and_refresh_all(
  hugo_base_dir: str = DEFAULT_HUGO_BASE_DIR,
  *,
  dry_run: bool = False,
) -> dict:
  """Run the ``ekAgnikANDam`` merge and refresh affected host prefills in order."""
  base = Path(hugo_base_dir)
  res = merge_ekAgnikANDam_includes(str(base), dry_run=dry_run)

  target_urls = {u for u in res["modified_urls"] if "/ekAgnikANDam/" not in u}
  ek_urls = {u for u in res["modified_urls"] if "/ekAgnikANDam/" in u}

  host_search_dirs = [
    base / "vedAH_Rk" / "content",
    base / "vedAH_Rk" / "static",
    base / "vedAH" / "content",
    base / "vedAH" / "static",
    base / "vedAH_yajuH" / "content",
    base / "vedAH_yajuH" / "static",
  ]
  # Pass 1: refresh hosts pointing directly to modified targets (and any ek_vp typo hosts).
  pass1_urls = target_urls | {u for u in ek_urls if "/vishvAsa-prastutiH/" in u}
  hosts_pass1 = refresh_host_prefills(pass1_urls, host_search_dirs, hugo_base_dir=str(base), dry_run=dry_run)
  # Pass 2: refresh hosts pointing to modified ekAgnikANDam/sarvASh_TIkAH files.
  ek_st_urls = {u for u in ek_urls if "/sarvASh_TIkAH/" in u}
  hosts_pass2 = refresh_host_prefills(ek_st_urls, host_search_dirs, hugo_base_dir=str(base), dry_run=dry_run)

  res["refreshed_hosts_targets"] = hosts_pass1
  res["refreshed_hosts_ek"] = hosts_pass2
  return res


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
  parser = argparse.ArgumentParser(description="Merge external sarvASh_TIkAH into ekAgnikANDam/sarvASh_TIkAH.")
  parser.add_argument("--hugo-base-dir", default=DEFAULT_HUGO_BASE_DIR)
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args()
  summary = merge_and_refresh_all(args.hugo_base_dir, dry_run=args.dry_run)
  for k, v in summary.items():
    if isinstance(v, list):
      print(f"{k}: {len(v)}")
    elif isinstance(v, dict):
      print(f"{k}: {len(v)} entries")
    else:
      print(f"{k}: {v}")
