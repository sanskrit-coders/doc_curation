import logging
import urllib.parse

from indic_transliteration import sanscript


def get_url_suffix(id, id_base, url_id_padding="%d", transliterate_id=True):
    import urllib.parse
    id = url_id_padding % id
    if transliterate_id:
        id = sanscript.transliterate(id, sanscript.SLP1, sanscript.DEVANAGARI)
    if id_base.endswith("/"):
        full_id = "%s%s" % (id_base, id)
    else:
        full_id = "%s_%s" % (id_base, id)
    logging.info(full_id)
    return urllib.parse.quote(full_id)


def get_wiki_path(subunit_path, unit_data, url_id_padding="%2d"):
    logging.debug(list(zip(subunit_path, unit_data["unitNameListInSite"])))
    path_elements = []
    for (subunit, unit_name_in_site) in zip(subunit_path, unit_data["unitNameListInSite"]):
        element_text = get_url_suffix(id=subunit, id_base=unit_name_in_site, url_id_padding=url_id_padding)
        path_elements.append(element_text)
    return "/".join(path_elements)


def generic_url_maker(subunit_path, unit_data, url_text_id="", url_leaf_id_padding="%2d"):
  import urllib
  url = "https://sa.wikisource.org/wiki/%s/%s" % (urllib.parse.quote(url_text_id), get_wiki_path(subunit_path=subunit_path, unit_data=unit_data, url_id_padding=url_leaf_id_padding))
  url = url.replace("wiki//", "")
  return url