from doc_curation.md_helper import MdFile
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


# MdFile.fix_index_files(dir_path="/home/vvasuki/vvasuki-git/saMskAra/content/sanskrit/shixaa/granthAH", dry_run=False)

# MdFile.set_titles_from_filenames(dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/history/history_of_the_indian_people", transliteration_target=None, dry_run=False)

MdFile(file_path="/home/vvasuki/vvasuki-git/saMskAra/content/mImAMsA/pUrvA/granthAH/tantravArtikam/tantravArtikam.md").split_to_bits(dry_run=False)