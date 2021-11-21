import codecs
import itertools
import logging
import os

import regex
from bs4 import BeautifulSoup
from indic_transliteration import sanscript

from curation_utils import file_helper
from doc_curation.md.file import MdFile


def get_filename(source_html):
    logging.info("Getting file name for %s", source_html)
    with codecs.open(source_html, "r", 'utf-8', errors='ignore') as file_in:
        contents = file_in.read()
        soup = BeautifulSoup(contents, 'lxml')
        title = soup.title.string
        if title == None:
            return os.path.basename(source_html).replace("htm", "md")
        title = sanscript.transliterate(title, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
        filename = "%s.md" % title.strip()
        return file_helper.clean_file_path(filename.strip())


def dump_devanaagarii(source_html, dest_file, overwrite=False):
    if os.path.exists(dest_file) and not overwrite:
        logging.warning("Skipping %s as it exists", dest_file)
        return 
    logging.info("Processing %s to %s", source_html, dest_file)
    with codecs.open(source_html, "r", 'utf-8', errors='ignore') as file_in:
        contents = file_in.read()
        soup = BeautifulSoup(contents, 'lxml')
        metadata = {}
        metadata["title"] = soup.title.text.strip()
        lines = soup.text.split("\n")
        english_lines = itertools.takewhile(lambda x: x.strip() != "http://gretil.sub.uni-goettingen.de/gretil.htm", lines)
        intro = "\n\n## Intro\n%s" % ("  \n".join(english_lines))
        iast_lines = itertools.dropwhile(lambda x: x.strip() != "http://gretil.sub.uni-goettingen.de/gretil.htm", lines)
        text = "  \n".join(list(iast_lines)[1:])
        text = regex.sub("(  \n){3,}", "\n\n", text)
        text = sanscript.transliterate(data=text, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
        text = sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(text, omit_sam=False, omit_yrl=True, ignore_padaanta=True)
        text = "%s\n\n## पाठः\n%s" % (intro, text)
        out_file = MdFile(file_path=dest_file, frontmatter_type="toml")
        out_file.dump_to_file(metadata=metadata, content=text, dry_run=False)


