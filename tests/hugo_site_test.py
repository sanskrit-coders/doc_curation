import doc_curation.hugo_site as hugo_site
from doc_curation.hugo_site import SITE_BASE, md_to_site_path


def test_md_to_site_path_regular_and_index_files():
  assert md_to_site_path("") == ""
  assert md_to_site_path("   ") == ""
  assert md_to_site_path(
    "AgamaH_vaiShNavaH/content/vaikhAnasaH/AgamaH/atri-saMhitA/samUrtArchanAdhikaraNam.md"
  ) == (
    f"{SITE_BASE}AgamaH_vaiShNavaH/vaikhAnasaH/AgamaH/atri-saMhitA/"
    "samUrtArchanAdhikaraNam/"
  )
  assert md_to_site_path("vedAH/content/yajuH/goldman/_index.md") == (
    f"{SITE_BASE}vedAH/yajuH/goldman/"
  )
  assert md_to_site_path("vedAH/content/yajuH/goldman/index.md") == (
    f"{SITE_BASE}vedAH/yajuH/goldman/"
  )
  assert md_to_site_path("/vedAH/yajuH/goldman", site_base="https://example.org/") == (
    "https://example.org/vedAH/yajuH/goldman/"
  )


def test_catalog_symbols_live_in_catalog_subpackage():
  assert not hasattr(hugo_site, "get_catalog_source_path")
  assert not hasattr(hugo_site, "appscript_client")
  assert not hasattr(hugo_site, "vv_pdf_library")
  assert hasattr(hugo_site.catalog, "get_catalog_source_path")
  assert hasattr(hugo_site.catalog, "appscript_client")
  assert hasattr(hugo_site.catalog, "vv_pdf_library")
