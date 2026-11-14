"""Optional (extras-only) deps must never break imports or CI collection.

CI installs ``pip install .`` plus a few test-only packages (see the pytest
step in pythonpackage.yml), so every module imported by the test-suite must
import without the heavy PDF/scraping packages below. Those stay usable via
function-level imports that fail only when actually called without the extra
installed.
"""
import subprocess
import sys
from pathlib import Path

# Extras-only packages (absent after a bare `pip install .`): importing any
# module below must not require them.
BLOCKED_TOP_LEVELS = [
  "pypdf",
  "pymupdf",
  "pikepdf",
  "img2pdf",
  "pdf2image",
  "rarfile",
  "fpdf",
  "reportlab",
  "feedparser",
  "trafilatura",
]

# Modules imported (transitively) by the test-suite that previously pulled in
# the blocked packages at import time. google_groups is covered through
# doc_curation.ebook (it launches browsers at import, so it cannot be
# imported in a bare subprocess).
IMPORTS_MUST_WORK = [
  "doc_curation.pdf",
  "doc_curation.ebook",
  "doc_curation.ebook.calibre_helper",
  "doc_curation.ebook.epub",
  "doc_curation.ebook.pdf_book",
  "doc_curation.ebook.pdf_book.pdf_maker",
  "doc_curation.blog",
  "doc_curation.blog.rss",
  "doc_curation.scraping.misc_sites.sambhashana_sandesha",
]

_CHILD_SCRIPT = """
import sys

blocked = set(%r)

class _Blocker:
  def find_spec(self, name, path=None, target=None):
    if name.split(".")[0] in blocked:
      raise ModuleNotFoundError("No module named %%r (blocked for test)" %% name)
    return None

sys.meta_path.insert(0, _Blocker())
for mod in %r:
  __import__(mod)
leaked = sorted(m for m in blocked if m in sys.modules)
assert not leaked, "blocked modules got imported: %%s" %% leaked
print("imports ok without extras")
""" % (BLOCKED_TOP_LEVELS, IMPORTS_MUST_WORK)


def test_imports_work_without_optional_deps():
  repo_root = Path(__file__).resolve().parent.parent
  proc = subprocess.run(
    [sys.executable, "-c", _CHILD_SCRIPT],
    cwd=str(repo_root), capture_output=True, text=True, timeout=300)
  assert proc.returncode == 0, "stdout:\n%s\nstderr:\n%s" % (proc.stdout, proc.stderr)
  assert "imports ok without extras" in proc.stdout


def test_ci_installs_test_only_deps():
  # The mail_stream tests import selenium and lxml directly, but those stay
  # out of requirements.txt (extras only); the CI pytest step must install
  # them explicitly instead of relying on transitive deps.
  workflow = Path(__file__).resolve().parent.parent / ".github/workflows/pythonpackage.yml"
  test_step = workflow.read_text().split("Test with pytest", 1)[1]
  assert "selenium" in test_step and "lxml" in test_step
