import regex
import textwrap
from doc_curation.md import library
from curation_projects import raamaayana
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def update():
    adhyaaya_to_source_file_map = raamaayana.get_adhyaaya_to_source_file_map()
    # logging.debug(adhyaaya_to_mp3_map)
    base_dir = "/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/"
    dest_md_files = raamaayana.get_adhyaaya_md_files(md_file_path=base_dir)
    doc_data = raamaayana.get_doc_data()

    # logging.debug(dest_md_files)
    for md_file in dest_md_files:
        # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
        file_path = str(md_file.file_path)
        adhyaaya_id = raamaayana.get_adhyaaya_id(file_path)
        audio_tag = '<div class="audioEmbed"  caption="श्रीराम-हरिसीताराममूर्ति-घनपाठिभ्यां वचनम्" src="%s"></div>' % (doc_data.get_value(id=adhyaaya_id, column_name="Audio url"))
        (metadata, current_content) = md_file.read_md_file()
        match = regex.search("<div class[^>]*div>", current_content)
        target_content = textwrap.dedent("""
        %s
        %s
        %s
        %s
        %s
        %s
        """) % (
            library.get_include(field_names=None, classes=None, title="विश्वास-प्रस्तुतिः", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH/")),
            library.get_include(field_names=None, classes=["collapsed"], title="IITK", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/iitk")),
            library.get_include(field_names=None, classes=["collapsed"], title="भूषणम्", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/bhUShaNa_iitk")),
            library.get_include(field_names=None, classes=["collapsed"], title="शिरोमणी", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/shiromaNI_iitk")),
            library.get_include(field_names=None, classes=["collapsed"], title="तिलकम्", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/audIchya-pAThaH/TIkA/tilaka_iitk")),
            library.get_include(field_names=None, classes=["collapsed"], title="द्राविडपाठः", url=file_path.replace(base_dir, "/purANam/rAmAyaNam/drAviDapAThaH")),
        )
        # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
        md_file.replace_content("%s\n\n%s" % (audio_tag, target_content), dry_run=False)