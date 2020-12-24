import logging

# Remove all handlers associated with the root logger object.
import os

from curation_utils import dir_helper
from indic_transliteration import sanscript

from doc_curation import text_data
from doc_curation.md_helper import MdFile
from doc_curation.scraping import html

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_file(outdir, url):
    os.makedirs(outdir, exist_ok=True)
    basename = os.path.basename(url)
    outfile_path = os.path.join(outdir, basename.replace(".", "_").replace("_xml", ".md"))
    import regex
    outfile_path = regex.sub("(mul|att|nrf|tik)(\\d)\\.", "\\g<1>0\\2.", outfile_path)
    html.dump_text_from_element(url=url, outfile_path=outfile_path, title_css_selector=".chapter", text_css_selector="p", heading_class="subhead")

def makedirs():
    tree = dir_helper.tree_from_file("/home/vvasuki/sanskrit-coders/doc_curation/curation_projects/tipiTikA/dirs.txt")
    tree.root.set_ordinals()
    logging.info(tree.root)
    tree.root.regularize_keys()
    logging.info(tree.root)
    tree.root.make_dirs(base_dir="/home/vvasuki/paali-bhaasaa/raw_etexts/", dry_run=False)

def dump_files():
    LINK_FILE_PATH = "/home/vvasuki/sanskrit-coders/doc_curation/curation_projects/tipiTikA/links.txt"
    with open(LINK_FILE_PATH) as linkfile:
        for line in linkfile.readlines():
            get_file(outdir="/home/vvasuki/paali-bhaasaa/raw_etexts/tipiTaka", url=line.strip())


# MdFile.fix_index_files(dir_path="/home/vvasuki/paali-bhaasaa/raw_etexts/", dry_run=False)
# MdFile.fix_title_numbering_in_path(dir_path="/home/vvasuki/paali-bhaasaa/raw_etexts/", dry_run=False)
# MdFile.fix_title_numbering_in_path(dir_path="/home/vvasuki/vvasuki-git/pALi/content/01_tipiTaka", dry_run=False)
MdFile.set_filenames_from_titles(dir_path="/home/vvasuki/vvasuki-git/tipiTaka/content/01_mUlam/02_suttapiTaka/04_anguttaranikAyo", transliteration_source=sanscript.DEVANAGARI, dry_run=False)