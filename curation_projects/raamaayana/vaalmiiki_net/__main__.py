import codecs
import os

import regex
import logging

import yamldown
from lxml import html
import requests

from doc_curation import text_data

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_sarga_shlokas(kaanda_id1, kaanda_id2, sarga):
    page = requests.get("https://www.valmikiramayan.net/utf8/{}/sarga{}/{}sans{}.htm".format(kaanda_id1, sarga, kaanda_id2, sarga))
    tree = html.fromstring(page.content)
    shloka_items = tree.xpath('//p[@class="SanSloka"]/text()')
    def clean_shloka_line(shloka_line):
        shloka_line = regex.sub("\s+", " ", shloka_line.strip(), flags=regex.UNICODE)
        return shloka_line.replace("||", "॥").replace("|", "।")
    shloka_items = map(clean_shloka_line, shloka_items)
    shloka_items = filter(lambda x: x != "", shloka_items)
    return shloka_items


def get_sarga_titles(kaanda_id1, kaanda_id2, chapter_title_xpath):
    page = requests.get("https://www.valmikiramayan.net/utf8/{}/{}_contents.htm".format(kaanda_id1, kaanda_id2))
    tree = html.fromstring(page.content)
    titles = tree.xpath(chapter_title_xpath)
    titles = [title for title in titles if "sarga/chapter" not in title ]
    sarga_ids = [int(regex.sub("[^0-9]", "", regex.split(" :\.", title)[0].strip()))  for title in titles]
    # for title in titles:
    #     logging.debug(title)
    titles = [regex.sub("\P{Letter}+", " ", " ".join(title.split(" ")[1:]).strip()).strip() for title in titles]
    return dict(zip(sarga_ids, titles))


def dump_sarga(title, shloka_items, output_path):
    yml = {
        "title": title,
        "title_english": title
    }
    md = "  \n".join(shloka_items)
    logging.info(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with codecs.open(output_path, "w", 'utf-8') as out_file_obj:
        out_file_obj.write(yamldown.dump(yml, md))


def dump_kaanda(kaanda, kaanda_index, output_directory_base):
    kaanda_id1 = None
    kaanda_id2 = None
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "raamaayana_andhra.json")
    sarga_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[kaanda_index])
    kaanda_id2_chapter_index = None
    chapter_title_xpath = '//div[@class="chpt"]/text()'
    if kaanda == "bAla":
        kaanda_id1 = "baala"
        kaanda_id2 = "bala"
        kaanda_id2_chapter_index = kaanda_id1
        chapter_title_xpath = '//div[@class="style1"]/text()'
    if kaanda == "ayodhyA":
        kaanda_id1 = "ayodhya"
        kaanda_id2 = "ayodhya"
        chapter_title_xpath = '//a[@class="nav"]/text()'
    if kaanda == "araNya":
        kaanda_id1 = "aranya"
        kaanda_id2 = "aranya"
    if kaanda == "kiShkindhA":
        kaanda_id1 = "kish"
        kaanda_id2 = "kishkindha"
        kaanda_id2_chapter_index = kaanda_id2
    if kaanda == "sundara":
        kaanda_id1 = "sundara"
        kaanda_id2 = "sundara"
    if kaanda == "yuddha":
        kaanda_id1 = "yuddha"
        kaanda_id2 = "yuddha"
    kaanda_id2_chapter_index = kaanda_id2_chapter_index or kaanda_id1
    sarga_to_title = get_sarga_titles(kaanda_id1=kaanda_id1, kaanda_id2=kaanda_id2_chapter_index, chapter_title_xpath=chapter_title_xpath)
    # logging.info(sarga_to_title)
    for sarga in sarga_list:
        title = "{:03d} {}".format(sarga, sarga_to_title[sarga])
        shloka_items = get_sarga_shlokas(kaanda_id1, kaanda_id2, sarga)
        output_path = os.path.join(output_directory_base, "{}_{}".format(kaanda_index, kaanda), "{}.md".format(title.replace(" ", "_")))
        dump_sarga(title=title, shloka_items=shloka_items, output_path=output_path)


base_dir = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa"
dump_kaanda("bAla", 1, base_dir)
dump_kaanda("ayodhyA", 2, base_dir)
dump_kaanda("araNya", 3, base_dir)
dump_kaanda("kiShkindhA", 4, base_dir)
dump_kaanda("sundara", 5, base_dir)
dump_kaanda("yuddha", 6, base_dir)
