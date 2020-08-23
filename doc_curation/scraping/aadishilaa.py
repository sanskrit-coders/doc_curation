import logging
import os

import regex

from curation_utils import scraping, file_helper
from doc_curation import md_helper
from doc_curation.md_helper import MdFile


def get_text(url):
    soup = scraping.get_soup(url=url)
    text = soup.select_one("div.entry-content").text
    text = md_helper.markdownify_plain_text(text)
    title = regex.sub("[ -]*आदिशिला", "", soup.title.string).strip()
    return (title, text)


def dump_all_texts(dest_dir, overwrite=False):
    soup = scraping.get_soup(url="https://adishila.com/unicodetxt-htm/")
    links = soup.select("div.wp-block-group a")
    for link in links:
        (title, text) = get_text(link["href"])
        filename = file_helper.clean_file_path("%s.md" % title)
        dest_path = os.path.join(dest_dir, filename)
        if not overwrite and os.path.exists(dest_path):
            logging.warning("Skipping %s since it exists", dest_path)
            continue
        logging.info("Getting %s", link["href"])
        md_file = MdFile(file_path=dest_path, frontmatter_type=MdFile.TOML)
        md_file.dump_to_file(metadata={"title": title}, md=text, dry_run=False)