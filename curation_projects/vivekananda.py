import logging
import os
import urllib

import regex

from doc_curation import md_helper
from curation_utils import scraping, file_helper


logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def dump_doc(url, out_dir, index, dry_run=False):
    out_file_path = regex.sub("/([^/]+).htm", "/%03d_\\1.md" %index, url)
    out_file_path = os.path.join(out_dir, out_file_path)
    if os.path.exists(out_file_path):
        logging.info("Skipping Dumping %s to %s", url, out_file_path)
        return 
    logging.info("Dumping %s to %s", url, out_file_path)
    full_url = "http://www.ramakrishnavivekananda.info/vivekananda/" + url
    soup = scraping.get_soup(full_url)
    metadata = {}
    title_elements = soup.select("h2")
    if len(title_elements) > 0:
        metadata["title"] = title_elements[0].text
    else:
        metadata["title"] = regex.sub("/([^/]+).htm", "\\1", url).replace("_", " ")
    body_element = soup.select("body")
    if len(body_element) == 0:
        logging.warning("Could not get text form %s with soup", full_url)
        filehandle = urllib.request.urlopen(full_url)
        content = filehandle.read().decode("utf8")
        filehandle.close()
    else:
        content = body_element[0].decode_contents()
    md_file = md_helper.MdFile(file_path=out_file_path)
    md_file.import_content_with_pandoc(content=content, source_format="html", dry_run=dry_run, metadata=metadata)


def dump_docs(out_dir, dry_run=False):
    index_url = "https://www.ramakrishnavivekananda.info/vivekananda/master_index.htm"
    soup = scraping.get_soup(index_url)
    links = soup.select("a")
    for index, link in enumerate(links[3:]):
        dump_doc(url=link["href"], out_dir=out_dir, index=index, dry_run=dry_run)


if __name__ == '__main__':
    dump_docs(out_dir="/home/vvasuki/sanskrit/raw_etexts_english/vivekAnanda/", dry_run=False)