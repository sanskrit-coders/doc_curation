import regex

from curation_projects import raamaayana
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def reformat_audio_tag():
    adhyaaya_to_source_file_map = raamaayana.get_adhyaaya_to_source_file_map()
    # logging.debug(adhyaaya_to_mp3_map)
    dest_md_files = raamaayana.get_adhyaaya_md_files(md_file_path="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padyam/purANam/rAmAyaNam/AndhrapAThaH")
    logging.debug(dest_md_files)
    for md_file in dest_md_files:
        # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
        logging.debug(md_file.file_path)
        (kaanda, adhyaaya) = raamaayana.get_kaanda_adhyaaya(md_file)
        adhyaaya_id = "%s-%s" % (kaanda, adhyaaya)
        logging.debug(adhyaaya_id)
        (yml, current_content) = md_file._read_yml_md_file()
        audio_tag = regex.findall("<div class.*div>", current_content.replace("\n", " "))[0]
        (_, target_content) = adhyaaya_to_source_file_map[adhyaaya_id]._read_yml_md_file()
        # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
        md_file.replace_content("%s\n\n%s" % (audio_tag, target_content), dry_run=False)