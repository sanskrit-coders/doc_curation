import codecs
import os

import regex
import logging

import yamldown
from indic_transliteration import sanscript
from lxml import html
import requests

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def set_titles_from_filenames(dir_path, file_pattern="**/*.md", dry_run=False):
    from pathlib import Path
    md_files = Path(dir_path).glob(file_pattern)
    for md_file in md_files:
        logging.info(md_file)
        if os.path.basename(md_file) == "_index.md":
            dir_name = os.path.basename(os.path.dirname(md_file)).replace(".md", "")
            title_optitrans = "+" + dir_name.replace("-", " ", 1)
        else:
            title_optitrans = os.path.basename(md_file).replace("-", " ", 1).replace(".md", "")
        title = sanscript.transliterate(data=title_optitrans, _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
        yml = {}
        md = ""
        with open(md_file, 'r') as file:
            (yml, md) = yamldown.load(file)
            logging.info((yml, md))
            if yml is None: yml = {}
        yml["title"] = title
        os.makedirs(os.path.dirname(md_file), exist_ok=True)
        if not dry_run:
            with codecs.open(md_file, "w", 'utf-8') as out_file_obj:
                out_file_obj.write(yamldown.dump(yml, md))
        else:
            logging.info(yml)
            logging.info(md)


set_titles_from_filenames(dir_path="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/mahAbhArata/01/007-sambhava", dry_run=False)
