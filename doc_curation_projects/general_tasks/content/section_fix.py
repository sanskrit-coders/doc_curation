import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript, aksharamukha_helper


def migrate_and_include_sections():
  text_processor = lambda x: regex.sub("## .+?\n", "", x)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/", text_patterns = ["## सूत्रम्\s*?\n[\\s\\S]+?(?=\n#|$)"], destination_path_maker=lambda title, original_path: include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", "sUtra-pAThaH": "sUtra-pAThaH/vishvAsa-prastutiH"}), migrated_text_processor=text_processor, replacement_maker=lambda x: include_helper.vishvAsa_include_maker(x, h1_level=4, classes=["collapsed"], title="विश्वास-प्रस्तुतिः"),
                         title_maker=lambda text, index, file_title: file_title, dry_run=False)


def section_fix():
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/kentum/mediterranian/articles/durant_caesar_and_christ", content_transformer=lambda x, y: section_helper.derominize_section_numbers(x))

  base_dir = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/mahAbhAratam/goraxapura-pAThaH/hindy-anuvAdaH/13_anushAsanaparva/01_dAna-dharma-parva/149_viShNu-sahasra-nAma-stotram/TIkA/sarva-prastutiH"
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(base_dir, "_index.md"), start_index=1)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(base_dir), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 

  # section_helper.merge_sections(md_files=[MdFile(file_path=os.path.join(base_dir, "en.md")), MdFile(file_path=os.path.join(base_dir, "bhagavadguNadarpaNam.md")), ], section_hasher=section_helper.section_hash_by_index)

  title_post_processor = None
  # title_post_processor = lambda x: regex.sub("^मन्त्रः +", "", x)
  # title_post_processor = lambda x: regex.sub("[०-९]", "", x)
  # library.apply_function(fn=section_helper.add_init_words_to_section_titles, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/1/4/8.md", dry_run=False, title_post_processor=title_post_processor, num_words=2)


