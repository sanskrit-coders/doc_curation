import itertools
import os
import shutil
from pathlib import Path

import regex
from bs4 import BeautifulSoup

from doc_curation_projects import veda
from doc_curation_projects.veda import suutra
from doc_curation import text_utils
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import section_helper, include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript

static_dir_base = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAnkhAyanam/sUtram/gRhyam"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "mUlam")


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  def deromanize(match):
    import roman
    return str(roman.fromRoman(match.group(1)))
  title = regex.sub("([IVX]+),", deromanize, title)
  subpath_parts = regex.sub("\D+", " ", title).strip().replace(" ", "_").split("_")
  subpath_parts = [int(x) for x in subpath_parts]
  subpath = "%d/%02d" % (subpath_parts[0], subpath_parts[-1])
  return os.path.join(base_dir, subpath + ".md")


def dump_oldenberg():
  # sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe29/sbe29002.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))
  
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/sankhayana-grihya-sutra/d/doc116455.html", base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"), dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"))

  # from doc_curation.scraping.sacred_texts import para_translation as para_translation_st
  # sacred_texts.dump(url="https://www.sacred-texts.com/hin/sbe29/sbe29093.htm", outfile_path=os.path.join(static_dir_base, "oldenberg/6", "01.md"), main_content_extractor=para_translation_st.get_main_content)
  # para_translation_st.split(base_dir=ref_dir.replace("mUlam", "oldenberg"))

  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "oldenberg"), ref_dir=ref_dir, insert_missign_ref_files=True)


def dump_muulam():
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam.md"))
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: content_processor.make_lines_end_with_pattern(c, ".+[०-९]+"), dir_path=os.path.join(content_dir_base, "mUlam.md"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam"))
  # shutil.move(os.path.join(content_dir_base, "mUlam"), os.path.join(content_dir_base, "sarva-prastutiH"))
  # library.shift_indices(dir_path=os.path.join(ref_dir, "1/26"), new_index_offset=-1, start_index=4)
  # library.shift_contents(dir_path=os.path.join(ref_dir, "6/02"), start_index=2, substitute_content_offset=-1, end_index=9)

  # 
  # metadata_helper.ensure_ordinal_in_title(dir_path=ref_dir, recursive=True, format="%02d")
  library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=3, dir_path=ref_dir)
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=ref_dir)
  # 


  pass

def set_content():
  suutra.set_basic_content(static_dir_base=static_dir_base)
  include_helper.include_core_with_commentaries(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"), alt_dirs=["oldenberg"])


if __name__ == '__main__':
  # dump_muulam()
  # dump_oldenberg()
  set_content()
  pass


'''
To fix:
1/13/15
1/14/01
1/14/05
1/14/07
1/14/14
1/14/15
1/15/07
1/15/08
1/15/09
1/15/19
1/15/20
1/15/22
1/16/02
1/16/04
1/16/06
1/16/08
1/16/11
1/21/02
1/22/02
1/22/08
1/22/10
1/22/12
1/22/15
1/23/01
1/24/07
1/25/03
1/25/09
1/25/11
1/26/03
1/26/17
1/26/18
1/26/19
1/26/22
1/26/24
1/27/03
1/27/04
1/27/05
1/27/07
1/27/08
1/28/04
1/28/06
1/28/08
1/28/12
1/28/15
1/28/17
1/28/18
2/01/01
2/01/05
2/01/07
2/01/08
2/01/10
2/01/11
2/01/12
2/01/13
2/01/14
2/01/16
2/01/19
2/02/04
2/02/09
2/03/05
2/05/08
2/05/09
2/05/10
2/05/11
2/06/06
2/06/07
2/07/09
2/07/10
2/07/12
2/07/13
2/07/22
2/07/23
2/07/24
2/07/25
2/07/26
2/07/28
2/09/02
2/10/02
2/10/03
2/10/04
2/10/05
2/11/02
2/11/08
2/12/04
2/12/06
2/12/07
2/12/11
2/12/13
2/12/14
2/13/02
2/13/05
2/14/01
2/14/02
2/14/05
2/14/07
2/14/16
2/14/21
2/14/22
2/14/23
2/14/24
2/15/05
2/15/06
2/15/09
2/15/11
3/01/01
3/01/03
3/01/04
3/01/06
3/01/16
3/01/17
3/02/03
3/02/08
3/04/03
3/09/03
3/11/06
3/11/13
3/12/03
3/13/04
3/14/01
3/14/03
4/01/02
4/01/03
4/01/06
4/03/07
4/05/02
4/05/04
4/05/05
4/05/06
4/05/10
4/05/12
4/06/01
4/06/06
4/06/08
4/07/08
4/07/18
4/07/37
4/07/50
4/08/02
4/08/06
4/08/07
4/08/11
4/08/14
4/09/02
4/09/03
4/11/02
4/11/07
4/11/12
4/11/14
4/11/15
4/11/16
4/12/04
4/12/10
4/12/19
4/12/23
4/12/24
4/12/25
4/14/01
4/15/04
4/15/13
4/16/01
4/16/02
4/17/03
4/19/02
4/19/03
5/01/01
5/01/04
5/01/06
5/02/08
5/04/01
5/05/04
5/05/08
5/07/01
5/10/01
5/10/02
5/11/01
5/11/02
6/01/01
6/01/02
6/01/05
6/02/13
6/03/06
6/04/07
6/04/08
6/04/12
6/04/13
6/05/04
6/05/05
6/06/05
6/06/06
6/06/09

Process finished with exit code 0

'''