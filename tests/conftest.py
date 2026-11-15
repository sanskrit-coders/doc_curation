"""Shared pytest configuration.

Some tests exercise code paths that shell out to a pandoc binary (HTML -> Markdown
conversion in the scraping / mail-stream dumpers). CI installs the package with
`pip install .` only, so pandoc is absent there and those tests are skipped
instead of failing. Mark them with ``@pytest.mark.needs_pandoc``.
"""
import shutil

import pytest


def _pandoc_available():
  if shutil.which("pandoc"):
    return True
  try:
    import pypandoc
    pypandoc.get_pandoc_version()
  except Exception:
    return False
  return True


def pytest_configure(config):
  config.addinivalue_line(
    "markers", "needs_pandoc: test requires a pandoc binary (install pandoc or set PYPANDOC_PANDOC).")


def pytest_collection_modifyitems(config, items):
  if _pandoc_available():
    return
  skip = pytest.mark.skip(
    reason="pandoc binary not installed; install pandoc (or set PYPANDOC_PANDOC) to run this test")
  for item in items:
    if "needs_pandoc" in item.keywords:
      item.add_marker(skip)
