import logging
import os

import pytest

from curation_utils.file_helper import clear_bad_chars
from doc_curation import tei
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper



def convert_and_compare(md_path_actual, md_path_original, tei_path, xsl_path):
  tei.dump_md(tei_path=tei_path, md_path=md_path_actual,
              xsl=xsl_path)
  tei.dump_md(tei_path=tei_path, md_path=md_path_actual.replace("local.md", "orig.local.md"),
              xsl=os.path.join(os.path.dirname(tei.__file__), "tei_xsl/markdown/tei_to_md_orig.xsl"))
  with open(md_path_original) as orig_md:
    with open(md_path_actual) as current_md:
      assert current_md.read() == orig_md.read()

# The below was not working on Github actions.
# @pytest.mark.skip(reason="Haven't figured out how to install saxon in CI system.")
def test_general():
  md_path_original = os.path.join(os.path.dirname(tei.__file__), "tei_xsl/Test/mdtest2.md")
  md_path_actual = os.path.join(os.path.dirname(tei.__file__), "tei_xsl/Test/mdtest2.local.md")
  tei_path = os.path.join(os.path.dirname(tei.__file__), "tei_xsl/Test/test.xml")
  xsl_path = os.path.join(os.path.dirname(tei.__file__), "tei_xsl/markdown/tei-to-markdown.xsl")
  # convert_and_compare(md_path_actual, md_path_original, tei_path, xsl_path)
