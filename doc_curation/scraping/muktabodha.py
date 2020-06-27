import os

import regex
from indic_transliteration import sanscript

from curation_utils import scraping, file_helper


def get_docs(out_dir):
    soup = scraping.get_soup("https://etexts.muktabodha.org/DL_CATALOG_USER_INTERFACE/dl_user_interface_list_catalog_records_frameset.htm")
    links = soup.select("a")
    for link in links:
        [title_iast, author_iast, catalog_number] = link.text.split("-")
        title_iast = title_iast.replace("Part ", "").replace("Volume ", "").replace("volume ", "").replace("Vol. ", "").replace("with ", "").replace("text ", "").replace("version ", "").replace("by ", "").replace("commentary ", "").replace("commentaries ", "").replace("rescension ", "").strip()
        author_iast = author_iast.replace("anonymous", "").replace("attributed ", "").replace("to ", "").replace("to: ", "").replace("chapters ", "").replace("thru ", "").strip()
        title_optitrans = sanscript.transliterate(data=title_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
        author_optitrans = sanscript.transliterate(data=author_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
        file_path = "%s_%s_%s.md".format(title_optitrans, author_optitrans, catalog_number.strip())
        file_path = file_helper.clean_file_path(file_path=file_path)
        file_path = os.path.join(out_dir, file_path)
