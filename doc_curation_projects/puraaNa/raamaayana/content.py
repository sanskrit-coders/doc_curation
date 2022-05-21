import regex
import textwrap
from doc_curation.md import library
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
    base_dir = "/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH"
    dest_md_files = raamaayana.get_adhyaaya_md_files(md_file_path=base_dir)
    doc_data = raamaayana.get_doc_data()
    doc_data_drAviDam = raamaayana.get_doc_data(worksheet_name="द्राविडपाठः")

    # logging.debug(dest_md_files)
    for md_file in dest_md_files:
        # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
        file_path = str(md_file.file_path)
        adhyaaya_id = raamaayana.get_adhyaaya_id(file_path)
        target_content = ""
        (metadata, current_content) = md_file.read()
        # match = regex.search("<div class[^>]*div>", current_content)
        audio_url = doc_data.get_value(id=adhyaaya_id, column_name="Audio url")
        if adhyaaya_id >= "6":
            audio_url = doc_data_drAviDam.get_value(id=adhyaaya_id, column_name="Audio url")
        if audio_url is not None:
          audio_tag = '<div class="audioEmbed"  caption="श्रीराम-हरिसीताराममूर्ति-घनपाठिभ्यां वचनम्" src="%s"></div>' % (audio_url)
          target_content = "%s\n\n" % audio_tag

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            target_content += "%s\n" % library.get_include(field_names=None, classes=None, title="विश्वास-प्रस्तुतिः", url=url)

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/iitk/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            target_content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="IITK", url=url)

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/bhUShaNa_iitk/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            target_content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="भूषणम्", url=url)

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/shiromaNI_iitk/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            target_content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="शिरोमणी", url=url)

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/tilaka_iitk/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            target_content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="तिलकम्", url=url)

        url = file_path.replace(base_dir, "/purANam/rAmAyaNam/drAviDapAThaH/")
        included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
        if os.path.exists(included_file_path):
            classes = ["collapsed"]
            if adhyaaya_id >= "6":
                classes = None
            target_content += "%s\n" % library.get_include(field_names=None, classes=classes, title="द्राविडपाठः", url=url)
        # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
        md_file.replace_content_metadata(target_content, dry_run=False)