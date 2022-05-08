import itertools
import logging
import os

import regex

from curation_utils import scraping
from doc_curation.scraping.wikisource import enumerated

from doc_curation.md.file import MdFile

from doc_curation_projects.veda import Rk
from indic_transliteration import sanscript


def rv_wiki_dumper(url, outfile_path, dry_run=False, *args, **kwargs):
  pass
  outfile_path = outfile_path.replace('.md', '')
  mandala_id = outfile_path.split('/')[-2]
  suukta_id = outfile_path.split('/')[-1]
  logging.info("Dumping %s/%s: %s to %s", mandala_id, suukta_id, url, outfile_path)
  (suukta_comment, commentaries) = get_commentaries(url)

  if suukta_comment != "":
    md_file = MdFile(file_path=os.path.join(outfile_path, "_index.md"))
    md_file.dump_to_file(metadata={"title": suukta_id}, content=suukta_comment, dry_run=dry_run, silent=True)

  Rk_id_to_name_map = Rk.get_Rk_id_to_name_map_from_muulam()
  for rk_id, commentary in commentaries.items():
    full_rk_id = "%s/%s/%02d" % (mandala_id, suukta_id, rk_id)
    dest_path = os.path.join(outfile_path, Rk_id_to_name_map[full_rk_id] + ".md")
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(metadata={"title": rk_id}, content=commentary, dry_run=dry_run, silent=True)
  


def get_commentaries(url):
  soup = scraping.get_soup(url)
  bhaashya_tag = soup.select_one(".mw-collapsible-content")
  p_tags = bhaashya_tag.select("p")
  p_texts = [t.text.strip() for t in p_tags]
  is_unaccented = lambda x: not ("॒" in x or "॑" in x)
  suukta_comment = "\n\n".join(itertools.takewhile(is_unaccented, p_texts)).strip()
  p_texts = list(itertools.dropwhile(is_unaccented, p_texts))
  p_texts = [x for x in p_texts if x != ""]
  commentaries = {}
  current_rk_from_prior_para = 0
  current_rk_from_count = 0
  for p_text in p_texts:
    bold_texts = regex.findall("(?<=^| )([\"“v]([^\s।॥,;-]+))(?=[\s।॥,;-]|$)", p_text)
    if len(bold_texts) == 0:
      # saMhitA or padapATha with or without svaras
      terminal_number_match = regex.match(".+?([०-९]+)[॥। ]*$", p_text)
      if terminal_number_match and not is_unaccented(p_text):
        current_rk_dev = terminal_number_match.group(1)
        current_rk_from_prior_para = int(sanscript.transliterate(current_rk_dev, _from=sanscript.DEVANAGARI,
                                                             _to=sanscript.IAST))
      continue
    current_rk_from_count += 1
    for bold_text in bold_texts:
      p_text = p_text.replace(bold_text[0], "**%s**" % bold_text[1], 1)

    p_text = p_text.replace("।।", "॥")
    if current_rk_from_count != current_rk_from_prior_para:
      logging.warning("Check ref %d (count %d)", current_rk_from_prior_para, current_rk_from_count)
      current_rk_from_count = current_rk_from_prior_para
      if current_rk_from_prior_para in commentaries:
        commentaries[current_rk_from_prior_para] += "\n\n%s" % p_text
      else:
        commentaries[current_rk_from_prior_para] = p_text
    else:
      commentaries[current_rk_from_prior_para] = p_text
  return (suukta_comment, commentaries)


def url_maker(subunit_path, *args, **kwargs):
  import urllib
  subpath = "#".join([str(x) for x in subunit_path])
  subpath = sanscript.transliterate(subpath, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
  subpath = subpath.replace("#", ".")
  url = "https://sa.wikisource.org/wiki/%s" % (urllib.parse.quote("ऋग्वेदः_सूक्तं_%s" % subpath) )
  return url


def dump_from_wiki():
  # enumerated.dump_deep_text(url_maker=url_maker, dir_path="/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sAyaNaH/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/book_data/vedaH/shakala/saMhitA.json", dumper=rv_wiki_dumper, dry_run=False, start_path="10/175", end_path="10/175", wait_between_requests=5)
  
  paths_to_correct = ["01/059", "01/065", "01/066", "01/067", "01/068", "01/069", "01/105", "01/108", "01/133", "01/154", "01/164", "01/179",
                      "03/033", "05/051", "05/054", "08/051", "08/058", "08/072", "08/092", 
                      "10/012",]
  for path in paths_to_correct:
    enumerated.dump_deep_text(url_maker=url_maker, dir_path="/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sAyaNaH/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/book_data/vedaH/shakala/saMhitA.json", dumper=rv_wiki_dumper, dry_run=False, start_path="%s.md" % path, end_path="%s.md" % path, wait_between_requests=1)


## Warnings



if __name__ == '__main__':
  dump_from_wiki()