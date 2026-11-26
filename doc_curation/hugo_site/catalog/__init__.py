"""Source-to-site-page catalog tooling for vishvAsa Hugo sites."""

from urllib.parse import unquote

VV_PDFS_PREFIX = "vv-pdfs:"
UT_DHARMA_PREFIX = "ut-dharma:"
MUKTABODHA_PREFIX = "muktabodha:"

GRANTHA_MARKER = "granthasangraha"
UT_SANSKRIT_MARKER = "sites.utexas.edu/sanskrit"


def _last_url_segment(url):
  base = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
  seg = base.rsplit("/", 1)[-1].strip()
  try:
    seg = unquote(seg)
  except Exception:
    pass
  return seg.strip()


def get_catalog_source_path(source_path):
  """Normalize a source location to its catalog `source_path` key.

  - PDF locations under granthasangrahaH (absolute local paths or
    granthasangrahaH-relative paths as stored in the sheet) become
    ``vv-pdfs:<path-relative-to-granthasangrahaH/>``.
  - UT-Austin Sanskrit dharmashAstra etexts
    (https://sites.utexas.edu/sanskrit/resources/dharmasastra/...)
    become ``ut-dharma:<text-slug>``.
  - Muktabodha etexts become ``muktabodha:<catalog-code-or-slug>``.
  Already-prefixed keys pass through unchanged, as do unrelated inputs
  (other URLs, absolute non-granthasangraha paths, "").
  """
  sp = (source_path or "").strip()
  if not sp:
    return ""
  for prefix in (VV_PDFS_PREFIX, UT_DHARMA_PREFIX, MUKTABODHA_PREFIX):
    if sp.startswith(prefix):
      body = sp[len(prefix):].strip()
      if prefix == VV_PDFS_PREFIX:
        body = body.lstrip("/")
      return prefix + body
  low = sp.lower()
  if UT_SANSKRIT_MARKER in low:
    slug = _last_url_segment(sp)
    if slug and slug.lower() not in ("dharmasastra", "sanskrit", "resources"):
      return UT_DHARMA_PREFIX + slug
    return sp
  if "muktabodha" in low or "muktalib" in low:
    name = _last_url_segment(sp)
    if "." in name:
      stem, ext = name.rsplit(".", 1)
      if ext.lower() in ("md", "html", "htm", "txt") and stem:
        name = stem
    if name:
      return MUKTABODHA_PREFIX + name
    return sp
  marker_idx = low.find(GRANTHA_MARKER)
  if marker_idx >= 0:
    rest = sp[marker_idx + len(GRANTHA_MARKER):]
    if rest[:1] in ("H", "h") and (len(rest) == 1 or rest[1] == "/"):
      rest = rest[1:]
    rest = rest.lstrip("/").strip()
    if rest:
      return VV_PDFS_PREFIX + rest
    return sp
  if "://" in sp or sp.startswith(("/", "\\", "~")) or (len(sp) > 2 and sp[1] == ":"):
    return sp
  return VV_PDFS_PREFIX + sp.lstrip("/")


from . import appscript_client  # noqa: F401, E402
from . import vv_pdf_library  # noqa: F401, E402
