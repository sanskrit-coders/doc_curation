import codecs
import logging
import os
from pathlib import Path

import regex
from curation_utils import file_helper
from indic_transliteration import sanscript

from bs4 import BeautifulSoup

from doc_curation import md_helper
from doc_curation.md_helper import MdFile


def get_text(src_file):
    with codecs.open(src_file, "r", 'utf-8') as file_in:
        contents = file_in.read()
        soup = BeautifulSoup(contents, 'lxml')
        content_elements = soup.select("pre#content")
        if len(content_elements) == 0:
            logging.warning("No stotra elements found in %s  - Returning empty string", src_file)
            return ""
        texts = [content_element.text for content_element in content_elements]
        text = "\n\n".join(texts)
        text = md_helper.markdownify_plain_text(text)
        return text


def get_metadata(src_file):
    metadata = {}
    with codecs.open(src_file, "r", 'utf-8') as file_in:
        try:
            contents = file_in.read()
        except UnicodeDecodeError:
            logging.warning("Invalid character in file %s", src_file)
            return {}
        soup = BeautifulSoup(contents, 'lxml')
        info_elements = soup.select("pre.inf")
        if len(info_elements) == 0:
            logging.warning("No metadata found for %s", src_file)
            return {}
        info_text = info_elements[0].text
        info_text = info_text.replace("% ", "")
        for item in info_text.split("\n"):
            if ":" in item:
                (key, value) = item.split(":", maxsplit=1)
                metadata[key.strip()] = value.strip()
    return metadata


def dump_markdown(src_file, dest_file):
    logging.info("Processing %s to %s", src_file, dest_file)
    metadata = get_metadata(src_file=src_file)
    text = get_text(src_file=src_file)
    metadata["title"] = sanscript.transliterate(data=metadata["itxtitle"], _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
    md_file = MdFile(file_path=dest_file, frontmatter_type=MdFile.TOML)
    md_file.dump_to_file(metadata=metadata, md=text, dry_run=False)


def markdownify_all(src_dir, dest_dir):
    file_paths = sorted(Path(src_dir).glob("**/doc_*/*.html"))
    for src_path in file_paths:
        metadata = get_metadata(src_file=src_path)
        if metadata == {}:
            logging.warning("No metadata found for %s", src_path)
            continue
        filename = metadata["itxtitle"].strip() + ".md"
        dest_path = os.path.join(
            os.path.dirname(str(src_path).replace(src_dir, dest_dir)), 
            filename)
        dest_path = file_helper.clean_file_path(dest_path)
        dump_markdown(src_file=src_path, dest_file=dest_path)