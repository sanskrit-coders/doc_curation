import regex
import textwrap

import doc_curation.md.content_processor.include_helper
from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation_projects.puraaNa import raamaayana
import logging
import os

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def update():
  # logging.debug(adhyaaya_to_mp3_map)
  base_dir = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/rAmAyaNam/TIkAH"
  dest_md_files = raamaayana.get_adhyaaya_md_files(md_file_path=base_dir)

  # logging.debug(dest_md_files)
  for md_file in dest_md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    file_path = str(md_file.file_path)
    adhyaaya_id = raamaayana.get_adhyaaya_id(file_path)
    target_content = ""

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=None, title="गोरक्षपुर-प्रस्तुतिः (हि)",
                                                        url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/audIchya-pAThaH/iitk/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=["collapsed"], title="IITK",
                                                        url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/audIchya-pAThaH/TIkA/bhUShaNa_sv/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=["collapsed"], title="भूषणम्",
                                                        url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/audIchya-pAThaH/TIkA/bhUShaNa_iitk/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=["collapsed"], title="भूषणम् (Alt)",
                                                        url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/audIchya-pAThaH/TIkA/shiromaNI_iitk/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=["collapsed"], title="शिरोमणी",
                                                        url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/audIchya-pAThaH/TIkA/tilaka_iitk/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=["collapsed"], title="तिलकम्", url=url).to_html_str()

    url = file_path.replace(base_dir, "/purANam_vaiShNavam/rAmAyaNam/drAviDapAThaH/")
    included_file_path = url.replace("/purANam_vaiShNavam", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static")
    if os.path.exists(included_file_path):
      classes = ["collapsed"]
      if adhyaaya_id >= "6":
        classes = None
      target_content += "%s\n" % include_helper.Include(field_names=None, classes=classes, title="द्राविडपाठः", url=url).to_html_str()
    # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
    md_file.replace_content_metadata(target_content, dry_run=False)
