
import logging
import os

from indic_transliteration import sanscript
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

from doc_curation import md_helper, text_data

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

opts = options.Options()
opts.headless = True
browser = webdriver.Chrome(options=opts)
browser.implicitly_wait(6)


def get_item_url_suffix(id, id_base, url_id_padding="%d", transliterate_id=True):
    import urllib.parse
    id = url_id_padding % id
    if transliterate_id:
        id = sanscript.transliterate(id, sanscript.SLP1, sanscript.DEVANAGARI)
    dashaka_id = "%s_%s" % (id_base, id)
    logging.info(dashaka_id)
    return urllib.parse.quote(dashaka_id)


def dump_item(title, item_url, outfile_path, get_collapsible_content):
    if os.path.exists(outfile_path):
        logging.info("skipping: %s - it exists already", outfile_path)
        return
    logging.info(item_url)
    browser.get(item_url)
    text = ""
    if not get_collapsible_content:
        try:
            text = browser.find_element_by_css_selector("div.poem").text
        except NoSuchElementException:
            content_element = browser.find_element_by_css_selector(".mw-parser-output")
            para_elements = content_element.find_elements_by_tag_name("p")
            text = "\n\n".join(map(lambda x : x.text, para_elements))
    else:
        text = browser.find_element_by_css_selector(".mw-collapsible-content").text
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    with open(outfile_path, "w") as outfile:
        outfile.writelines(text.replace("\n", "  \n"))
    md_file = md_helper.MdFile(file_path=outfile_path)
    md_file.set_title(title=title, dry_run=False)


def dump_text(url_base, num_parts, dir_path, url_id_padding="%d", get_collapsible_content=False, transliterate_id=True):
    for id in range(1, num_parts+1):
        outfile_path = os.path.join(dir_path, "%03d.md" % id)
        title = sanscript.transliterate("%03d" % id, sanscript.SLP1, sanscript.DEVANAGARI)
        item_url = "https://sa.wikisource.org/wiki/%s" % (get_item_url_suffix(id=id, url_id_padding=url_id_padding, id_base=url_base, transliterate_id=transliterate_id))
        dump_item(title=title, outfile_path=outfile_path, item_url=item_url, get_collapsible_content=get_collapsible_content)



def get_wiki_path(subunit_path, unit_data, url_id_padding="%2d"):
    logging.debug(list(zip(subunit_path, unit_data["unitNameListInSite"])))
    path_elements = []
    for (subunit, unitNameInSite) in zip(subunit_path, unit_data["unitNameListInSite"]):
        element_text = get_item_url_suffix(id=subunit, id_base=unitNameInSite, url_id_padding=url_id_padding)
        path_elements.append(element_text)
    return "/".join(path_elements)


def dump_deep_text(url_text_id, url_leaf_id_padding, dir_path, unit_info_file, get_collapsible_content=False, dry_run=False):
    unit_data = text_data.get_subunit_data(unit_info_file, [])
    for subunit_path in text_data.get_subunit_path_list(json_file=unit_info_file, unit_path_list=[]):
        relative_dir_path = "/".join(["%02d" % x for x in subunit_path[:-1]])
        outfile_path = os.path.join(dir_path, relative_dir_path, "%03d.md" % subunit_path[-1])
        import urllib
        item_url = "https://sa.wikisource.org/wiki/%s/%s" % (urllib.parse.quote(url_text_id), get_wiki_path(subunit_path=subunit_path, unit_data=unit_data, url_id_padding=url_leaf_id_padding))
        title = sanscript.transliterate("%03d" % subunit_path[-1], sanscript.SLP1, sanscript.DEVANAGARI)
        logging.info("Getting %s to %s with title %s", item_url, outfile_path, title)
        if not dry_run:
            dump_item(title=title, outfile_path=outfile_path, item_url=item_url, get_collapsible_content=get_collapsible_content)

