import regex

from curation_projects import mahaabhaarata
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def reformat_audio_tag():
    adhyaaya_to_source_file_map = mahaabhaarata.get_adhyaaya_to_source_file_map()
    # logging.debug(adhyaaya_to_mp3_map)
    dest_md_files = mahaabhaarata.get_adhyaaya_md_files(md_file_path="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/mahAbhArata")
    logging.debug(dest_md_files)
    for md_file in dest_md_files:
        # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
        logging.debug(md_file.file_path)
        (parva, adhyaaya) = mahaabhaarata.get_parva_adhyaaya(md_file)
        adhyaaya_id = "%s-%s" % (parva, adhyaaya)
        logging.debug(adhyaaya_id)
        (yml, current_content) = md_file._read_yml_md_file()
        audio_tag = next(iter(regex.findall("<div class.*div>", current_content.replace("\n", " "))), '')
        (_, target_content) = adhyaaya_to_source_file_map[adhyaaya_id]._read_yml_md_file()
        # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
        md_file.replace_content("%s\n\n%s" % (audio_tag, target_content), dry_run=False)