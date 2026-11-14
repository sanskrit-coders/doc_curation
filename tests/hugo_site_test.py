import pytest

from doc_curation.hugo_site import get_catalog_source_path
from doc_curation.hugo_site.appscript_client import (
  _rows_to_delete_requests, clear_pending, delete_sheet_rows)


def test_grantha_absolute_paths_get_vv_pdfs_prefix():
  assert get_catalog_source_path(
    "/media/vvasuki/vData/text/granthasangrahaH/AgamaH/book.pdf") == "vv-pdfs:AgamaH/book.pdf"
  assert get_catalog_source_path(
    "/home/vvasuki/Documents/books/granthasangrahaH/vedAH/x.pdf") == "vv-pdfs:vedAH/x.pdf"


def test_bare_relative_paths_get_vv_pdfs_prefix():
  assert get_catalog_source_path("AgamaH/book.pdf") == "vv-pdfs:AgamaH/book.pdf"


def test_already_prefixed_paths_are_idempotent():
  assert get_catalog_source_path("vv-pdfs:AgamaH/book.pdf") == "vv-pdfs:AgamaH/book.pdf"
  assert get_catalog_source_path("vv-pdfs:/AgamaH/book.pdf") == "vv-pdfs:AgamaH/book.pdf"
  assert get_catalog_source_path("ut-dharma:manava") == "ut-dharma:manava"
  assert get_catalog_source_path("muktabodha:M00001") == "muktabodha:M00001"


def test_utexas_dharmasastra_urls_get_ut_dharma_prefix():
  assert get_catalog_source_path(
    "https://sites.utexas.edu/sanskrit/resources/dharmasastra/manava/") == "ut-dharma:manava"
  assert get_catalog_source_path(
    "https://sites.utexas.edu/sanskrit/resources/dharmasastra/mitak%E1%B9%A3ara/?x=1") == "ut-dharma:mitakṣara"
  # The library index page itself names no text: leave it alone.
  assert get_catalog_source_path(
    "https://sites.utexas.edu/sanskrit/resources/dharmasastra/") == "https://sites.utexas.edu/sanskrit/resources/dharmasastra/"


def test_muktabodha_urls_get_muktabodha_prefix():
  assert get_catalog_source_path(
    "https://muktabodha-digital-library.org/texts/DEV/M00001") == "muktabodha:M00001"
  assert get_catalog_source_path(
    "https://muktalib7.com/DL_CATALOG_ROOT/MUKTABODHA-LIBRARY-DEVANAGARI/M00002.html") == "muktabodha:M00002"


def test_unrelated_inputs_pass_through():
  assert get_catalog_source_path("") == ""
  assert get_catalog_source_path("   ") == ""
  assert get_catalog_source_path(
    "https://archive.org/details/some-item") == "https://archive.org/details/some-item"
  assert get_catalog_source_path("/tmp/x.pdf") == "/tmp/x.pdf"


def test_rows_to_delete_requests_merges_contiguous_and_runs_bottom_up():
  reqs = _rows_to_delete_requests(123, [2, 3, 4, 10, 4102, 4104, 4103])
  ranges = [r["deleteDimension"]["range"] for r in reqs]
  assert [(x["startIndex"], x["endIndex"]) for x in ranges] == [(4101, 4104), (9, 10), (1, 4)]
  assert all(x["sheetId"] == 123 and x["dimension"] == "ROWS" for x in ranges)


def test_rows_to_delete_requests_empty():
  assert _rows_to_delete_requests(123, []) == []


def test_delete_sheet_rows_refuses_header_and_supports_dry_run():
  with pytest.raises(ValueError):
    delete_sheet_rows([1, 5], dry_run=True)
  assert delete_sheet_rows([5, 5, 6], dry_run=True) == {
    "ok": True, "dry_run": True, "rows": [5, 6]}


def test_clear_pending_dry_run_whole_column():
  assert clear_pending(dry_run=True) == {
    "ok": True, "dry_run": True, "ranges": ["map!E2:E"]}
