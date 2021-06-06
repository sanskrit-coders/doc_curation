import logging

from doc_curation.md.file import MdFile
from doc_curation.md import library
# Remove all handlers associated with the root logger object.
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")
logging.getLogger('charsetgroupprober').setLevel(logging.WARNING)
logging.getLogger("charsetgroupprober").propagate = False
logging.getLogger('sbcharsetprober').setLevel(logging.WARNING)
logging.getLogger("sbcharsetprober").propagate = False
# advaita_shaaradaa.dump_texts(dest_dir="/home/vvasuki/sanskrit/raw_etexts/vedAntam/advaitam/advaita-shAradA")

# wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path="/home/vvasuki/sanskrit/raw_etexts_english/blogs/manasataramgini")
# wordpress.fix_paths(dir_path="/home/vvasuki/sanskrit/raw_etexts_english/blogs/manasataramgini", dry_run=False)
# wordpress.fix_paths(dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/history/paganology/Aryan/indo-iranian/indo-aryan/persons/brAhma/sage-bloodlines/bhRguH/dvitIyajanmani_bhRguH/chyavanaH/ApnavAna/aurvaH/jamadagniH/MT_charitram/", dry_run=False)

# library.apply_function(fn=MdFile.transliterate_content, dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/ekAgnikANDam/haradatta-TIkA", source_scheme=sanscript.IAST)


# MdFile.fix_index_files(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/taittirIyam/sUtram/ApastambaH/gRhyam/TIkA", overwrite=True, dry_run=False)
# 
# library.apply_function(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/sAma/kauthumam", fn=MdFile.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

# library.apply_function(dir_path="/home/vvasuki/vvasuki-git/pALi/content", fn=MdFile.ensure_ordinal_in_title, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

# MdFile.set_titles_from_filenames(dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/history/history_of_the_indian_people", transliteration_target=None, dry_run=False)

# MdFile.set_filenames_from_titles(dir_path="/home/vvasuki/vvasuki-git/sanskrit/content/vyAkaraNam/whitney", transliteration_source=sanscript.DEVANAGARI, dry_run=False)

# library.apply_function(fn=MdFile.prepend_file_index_to_title, dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/books/vivekAnanda", dry_run=False)

# doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
 
# library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, indexed_title_pattern=None, bits_dir_url="/vedAH/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA")

library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/haradatta-TIkA/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, indexed_title_pattern=None)

# library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/ekAgnikANDam/haradatta-TIkA/", dry_run=False, source_script=None,  indexed_title_pattern=None)

# library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/infection/viral/wuhan_epidemic/treatment.md", dry_run=False, source_script=None,  indexed_title_pattern=None)

# library.fix_index_files(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/sAma/paravastu-saama/devaH", overwrite=False, dry_run=False)
# library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

# MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/contagion/vaccination.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, indexed_title_pattern=None)
#  , indexed_title_pattern=None

# md_helper.import_md_recursive(source_dir="/home/vvasuki/Downloads/peterFreund", file_extension="txt")
# file_helper.copy_file_tree(source_dir="/home/vvasuki/Downloads/peterFreund", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/peterFreund", file_pattern="**/*.md")

# library.apply_function(fn=MdFile.fix_lazy_anusvaara, dir_path="/home/vvasuki/vvasuki-git/kAvya/content/shAstram/alankAraH/alankAra-maNihAraH", dry_run=False, ignore_padaanta=True, omit_yrl=True)

# library.apply_function(fn=MdFile.add_init_words_to_section_titles, dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False, num_words=2)

# library.defolderify(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False)