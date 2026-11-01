import os
import re
import unicodedata
import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import include as include_helper
from doc_curation_projects.veda.yajuH import taittiriiyam

def migrate_and_include_mantras(dir_path, title_pattern="विश्वास-प्रस्तुतिः - ऋक्", mantra_dir="Rk"):
  library.apply_function(fn=taittiriiyam.migrate_and_include_mantra_details, dir_path=dir_path, dry_run=False, title_pattern=title_pattern, mantra_dir=mantra_dir)
  include_helper.prefill_includes(dir_path=dir_path)

def fix_includes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover, url_to_exclude=".+vishvAsa.+"))
  def include_fixer(x, current_file_path, *args):
    return include_helper.alt_include_adder(x, current_file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["mUlam","sarvASh_TIkAH"])

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_fixer))
  include_helper.prefill_includes(dir_path=dir_path)


def _normalize_for_anchor(text):
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\u0900-\u097F]+", "", text)
    return text


def insert_sayaNa(content):
    """Insert ``content["text"]`` as a सायणटीका block in ``content["target_file"]`` after the line matching ``content["anchor"]``."""
    target_file = content["target_file"]
    text = content["text"]
    anchor = content.get("anchor")
    md_file = MdFile(file_path=target_file)
    metadata, body = md_file.read()
    lines = body.split("\n")
    block = ["<details><summary>सायणटीका</summary>", "", text.strip(), "</details>", ""]
    if anchor:
        anchor_norm = _normalize_for_anchor(anchor)
        matched_end = None
        for start in range(len(lines)):
            window = ""
            for end in range(start, min(len(lines), start + 10)):
                window += _normalize_for_anchor(lines[end])
                if anchor_norm in window:
                    matched_end = end
                if len(window) > len(anchor_norm) + 200:
                    break
        if matched_end is not None:
            close_index = matched_end + 1
            while close_index < len(lines) and lines[close_index].strip() != "</details>":
                close_index += 1
            insert_index = close_index + 1 if close_index < len(lines) else len(lines)
            lines[insert_index:insert_index] = block
        else:
            lines.extend(block)
    else:
        lines.extend(block)
    md_file.replace_content_metadata(new_content="\n".join(lines))


if __name__ == '__main__':
  # fix_includes(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/sarva-prastutiH/1/5/08_atharva-shira-iShTakAH_indro_dadhIcho.md")
  migrate_and_include_mantras(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sarva-prastutiH/07_pravargyAdi/84_agne_vratapate.md", title_pattern="विश्वास-प्रस्तुतिः.*", mantra_dir="yajuH")
  # migrate_and_include_mantras(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/sarva-prastutiH/2/8_kAmya-pashavaH/1_vAyavyAdi-pashu-sUktAni/02_prajApatiH.md", title_pattern="विश्वास-प्रस्तुतिः - ऋक्", mantra_dir="Rk")

  # include_helper.prefill_includes(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sarva-prastutiH/03_chAturhotra-chayanAdi/39-40_adbhyas_sambhUtaH.md")
  pass
