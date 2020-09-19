import logging
import os
import urllib

import regex

from doc_curation import md_helper
from curation_utils import scraping, file_helper

from doc_curation.md_helper import MdFile

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def fix_text(text):
    return regex.sub("[\r\n ]+", " ", text).replace("�", "'").replace("­", "")


def dump_content(soup, out_file_path, metadata, dry_run):
    content_elements = soup.select("td[width=\"60%\"]") + soup.select("td[width=\"80%\"]") + soup.select("body")
    content = fix_text(content_elements[0].decode_contents(formatter="html"))
    md_file = md_helper.MdFile(file_path=out_file_path)
    md_file.import_content_with_pandoc(content=content, source_format="html", dry_run=dry_run, metadata=metadata)
    if metadata == {}:
        md_file.set_title_from_filename(transliteration_target=None, dry_run=dry_run)


def get_metadata(soup, index, url):
    metadata = {}
    h2_elements = soup.select("h2")
    heading_elements = soup.select(".heading")
    center_elements = soup.select("center")
    msoTitle_elements = soup.select(".MsoTitle")
    msoNormal_elements = soup.select(".MsoNormal")
    all_title_elments = h2_elements + heading_elements + msoTitle_elements + msoNormal_elements + center_elements
    index_str = "%02d " % index
    if len(all_title_elments) > 0:
        metadata["title"] = index_str + fix_text(all_title_elments[0].text)
    else:
        metadata["title"] = regex.sub(".+/([^/]+).html?", "\\1", url).replace("_", " ")
    return metadata


def dump_doc(url, out_dir, index, dry_run=False):
    out_file_path = regex.sub(".+/([^/]+).html?", "%02d_\\1.md" %index, url)
    out_file_path = os.path.join(out_dir, out_file_path)
    if os.path.exists(out_file_path):
        logging.info("Skipping Dumping %s to %s", url, out_file_path)
        return
    logging.info("Dumping %s to %s", url, out_file_path)
    soup = scraping.get_soup(url)
    if "Not Found" in soup.text:
        logging.warning("%s not found!", url)
        return
    metadata = get_metadata(soup=soup, index=index, url=url)
    dump_content(soup=soup, out_file_path=out_file_path, metadata=metadata, dry_run=dry_run)

def dump_docs(index_url, out_dir, dry_run=False):
    soup = scraping.get_soup(index_url)
    out_file_path = os.path.join(out_dir, "_index.md")
    if not os.path.exists(out_file_path):
        dump_content(soup=soup, out_file_path=out_file_path, metadata={}, dry_run=dry_run)

    links = soup.select("a")
    for index, link in enumerate(links):
        href = link.get("href", None)
        text = fix_text(link.text)
        if href and "Back to" not in text and href not in ["http://voiceofdharma.org"]:
            if href.startswith("http"):
                url = link["href"]
            else:
                url = index_url + link["href"]
            dump_doc(url= url, out_dir=out_dir, index=index, dry_run=dry_run)


def misc(base_dir):
    # dump_docs(index_url="http://voiceofdharma.org/books/tipu/", out_dir=base_dir+"misc/tipu", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/tfst/", out_dir=base_dir+"misc/Stock_taking_of_sangh_parivAr", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/jihad/", out_dir=base_dir+"misc/jihAd", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/jtsi/", out_dir=base_dir+"misc/jizyAH", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/mla/", out_dir=base_dir+"misc/muslim_attack_punjab", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/ir/", out_dir=base_dir+"misc/aurobindo_India_rebirth", dry_run=False)
    # MdFile.set_titles_from_filenames(dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/books/misc/aurobindo_India_rebirth", transliteration_target=None, dry_run=False)
    dump_docs(index_url="http://voiceofdharma.org/books/tfc/", out_dir=base_dir+"misc/gautier_ferengi_columns", dry_run=False)


def goel(base_dir):
    # dump_docs(index_url="http://voiceofdharma.org/books/muslimsep/", out_dir=base_dir+"goel_sitArAm/muslim_separatism", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/pipp/", out_dir=base_dir+"goel_sitArAm/perversion_of_paralance", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/tcqp/", out_dir=base_dir+"goel_sitArAm/calcutta_quran_petition", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/siii/", out_dir=base_dir+"goel_sitArAm/islamic_imperialism_india", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/htemples1/", out_dir=base_dir+"goel_sitArAm/hindu_temples_1", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/htemples2/", out_dir=base_dir+"goel_sitArAm/hindu_temples_2", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/hindusoc/", out_dir=base_dir+"goel_sitArAm/hindu_society_defence", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/hhrmi/", out_dir=base_dir+"goel_sitArAm/hindu_resistance_to_muslims", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/hsus/", out_dir=base_dir+"goel_sitArAm/hindu_society_under_seige", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/hhce/", out_dir=base_dir+"goel_sitArAm/hindu_christian_encounters", dry_run=False)
    # dump_docs(index_url="http://voiceofdharma.org/books/hibh/", out_dir=base_dir+"goel_sitArAm/How_I_Became_Hindu", dry_run=False)
    dump_docs(index_url="http://voiceofdharma.org/books/gagon/", out_dir=base_dir+"goel_sitArAm/nehruism_genesis", dry_run=False)


def elst(base_dir):
    # dump_docs(index_url="http://www.bharatvani.org/books/demogislam/", out_dir=base_dir+"elst/demographic_seige", dry_run=False)
    # dump_docs(index_url="http://www.bharatvani.org/books/bjp/", out_dir=base_dir+"elst/bjp_and_hindu_resurgence", dry_run=False)
    # dump_docs(index_url="http://www.bharatvani.org/books/acat/", out_dir=base_dir+"elst/ayodhya_case_against_temple", dry_run=False)
    # dump_docs(index_url="http://www.bharatvani.org/books/ayodhya/", out_dir=base_dir+"elst/ayodhya_and_after", dry_run=False)
    # dump_docs(index_url="http://www.bharatvani.org/books/wiah/", out_dir=base_dir+"elst/who_is_a_hindu", dry_run=False)
    # dump_docs(index_url="http://www.bharatvani.org/books/negaind/", out_dir=base_dir+"elst/negationism_in_india", dry_run=False)
    dump_docs(index_url="http://voiceofdharma.org/books/pp/", out_dir=base_dir+"elst/psychology_of_prophetism", dry_run=False)


def lal(base_dir):
    # dump_docs(index_url="http://www.voiceofdharma.org/books/mssmi/", out_dir=base_dir+"lal_ks/muslim_slave_system", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/imwat/", out_dir=base_dir+"lal_ks/indian_muslims", dry_run=False)
    dump_docs(index_url="http://www.voiceofdharma.org/books/tpmsi/", out_dir=base_dir+"lal_ks/muslim_state_theory_practice", dry_run=False)


def ram_swarup(base_dir):
    # dump_docs(index_url="http://www.voiceofdharma.org/books/ohrr/", out_dir=base_dir+"ram_swarup/on_hinduism", dry_run=False)
    # dump_docs(index_url="http://www.voiceofdharma.org/books/uith/", out_dir=base_dir+"ram_swarup/understanding_islam_through_hadis", dry_run=False)
    dump_docs(index_url="http://www.voiceofdharma.org/books/ca/", out_dir=base_dir+"ram_swarup/catholic_Ashrams", dry_run=False)
    dump_docs(index_url="http://www.voiceofdharma.org/books/ca/", out_dir=base_dir+"ram_swarup/catholic_Ashrams", dry_run=False)
    dump_docs(index_url="http://www.voiceofdharma.org/books/foe/", out_dir=base_dir+"ram_swarup/freedom_of_expression", dry_run=False)


def rajaram(base_dir):
    dump_docs(index_url="http://www.voiceofdharma.org/books/dist/", out_dir=base_dir+"rAjArAm_ns/history_distortions", dry_run=False)


if __name__ == '__main__':
    base_dir = ""
    # ram_swarup(base_dir=base_dir)
    goel(base_dir=base_dir)