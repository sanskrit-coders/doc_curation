import logging
import os

import regex
from doc_curation.md.file import MdFile

import doc_curation.md
from curation_utils import scraping, file_helper


def get_text(url):
    soup = scraping.get_soup(url=url)
    text = soup.select_one("div.entry-content").text
    text = doc_curation.md.markdownify_plain_text(text)
    title_p = soup.select_one("p[style=\"font-family:https://adishila.com/wpcontent/uploads/2021/06/AdishilaSanBoldB.ttf;font-size:40px;color:#23883D;text-align:center\"]")
    title = title_p.text
    text = text.replace("।।", "॥")
    return (title, text)


def dump_all_texts(dest_dir, overwrite=False):
    soup = scraping.get_soup(url="https://adishila.com/unicode-text/")
    links = soup.select("div.wp-block-file a")
    for link in links:
        (title, text) = get_text(link["href"])
        filename = file_helper.clean_file_path("%s.md" % title)
        dest_path = os.path.join(dest_dir, filename)
        if not overwrite and os.path.exists(dest_path):
            logging.warning("Skipping %s since it exists", dest_path)
            continue
        logging.info("Getting %s", link["href"])
        md_file = MdFile(file_path=dest_path, frontmatter_type=MdFile.TOML)
        md_file.dump_to_file(metadata={"title": title}, content=text, dry_run=False)