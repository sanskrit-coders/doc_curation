import logging

from indic_transliteration import sanscript

from curation_utils import file_helper
from doc_curation import md_helper
from doc_curation.md_helper import MdFile

# Remove all handlers associated with the root logger object.

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# advaita_shaaradaa.dump_texts(dest_dir="/home/vvasuki/sanskrit/raw_etexts/vedAntam/advaitam/advaita-shAradA")

# MdFile.apply_function(fn=MdFile.transliterate_content, dir_path="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-markdown", source_scheme=sanscript.IAST)


# MdFile.fix_index_files(dir_path="/home/vvasuki/vvasuki-git/saMskAra/content/sanskrit/shixaa/granthAH", dry_run=False)

# MdFile.set_filenames_from_titles(dir_path="/home/vvasuki/vvasuki-git/pALi/content", transliteration_source=sanscript.DEVANAGARI, file_name_filter=lambda x: not str(x).endswith("_index.md"), dry_run=False)

# MdFile.apply_function(dir_path="/home/vvasuki/vvasuki-git/pALi/content", fn=MdFile.ensure_ordinal_in_title, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

# MdFile.set_titles_from_filenames(dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/history/history_of_the_indian_people", transliteration_target=None, dry_run=False)

# doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
# MdFile(file_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/polity/sick-india/orgs/rss/bunch_of_thoughts_golwalkar/05_Part_Four_-_Moulding_Men.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None)

# MdFile(file_path="/home/vvasuki/sanskrit/raw_etexts/mixed/peterFreund/AyurvedaH/sharngadhara_samhita.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=sanscript.DEVANAGARI)
# MdFile.split_all_to_bits(dir_path="/home/vvasuki/vvasuki-git/tipiTaka/content/01_mUlam/02_suttapiTaka/03_saMyutta-nikAyo/05_mahAvaggo", dry_run=False)


MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/artha/materials/cloth.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, indexed_title_pattern=None)

# md_helper.import_md_recursive(source_dir="/home/vvasuki/Downloads/peterFreund", file_extension="txt")
# file_helper.copy_file_tree(source_dir="/home/vvasuki/Downloads/peterFreund", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/peterFreund", file_pattern="**/*.md")