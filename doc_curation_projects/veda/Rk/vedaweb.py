import logging
import os

import regex
from ordered_set import OrderedSet

from doc_curation_projects.veda import Rk
from curation_utils import scraping
from doc_curation.md.file import MdFile

strata_meanings = {
  "A": "Archaic",
  "a": "Archaic on metrical evidence alone",
  "S": "Strophic",
  "s": "Strophic on metrical evidence alone",
  "N": "Normal",
  "n": "Normal on metrical evidence alone",
  "C": "Cretic",
  "c": "Cretic on metrical evidence alone",
  "P": "Popular for linguistic reasons, and possibly also for non-linguistic reasons",
  "p": "Popular for non-linguistic reasons",
 }

pada_labels = {
  "D": "genre D",
  "E2": "epic anuṣṭubh (424)",
  "R": "repeated line",
  "E3a": "epic anuṣṭubh (292)",
  "H": "12 = 5+7, ending LHX",
  "S": "line affected by realignment",
  "V": "Vālakhilya",
  "M": "genre M",
  "4": "12 = 8+4",
  "5": "pentad (decasyllabic), including Arnold’s “pure” and “mixed”; see Oldenberg (1888) 95–8 and Arnold (1905) 238–40.",
  "B": "bhārgavī; see Arnold (1905) 240–1.",
  "h": "11 = 4+7, ending HLX",
  "G": "gautamī; see Arnold (1905) 240–1",
  "O": "Oldenberg's gāyatrī-corpus, cf. Oldenberg (1888: 9f.).",
  "T": "Trochaic gāyatrī; see Oldenberg (1888) 25 and Vedic Metre (Arnold, 1905) 165.",
  "U": "uneven lyric; see Arnold (1905) 154, 244 (Appendix III).",
  "4b": "11 = 8+3",
  "v": "virāṭsthānā; see Oldenberg (1888) 86–95 and Arnold (1905) 240–1, 246.",
  "P": "popular",
  "E1": "epic anuṣṭubh (525)",
  "E3b": "epic anuṣṭubh (380)",
}


def get_paada_labels(label_str):
  label_keys = sorted(pada_labels, key=lambda x: -len(x))
  labels = []
  while label_str != "":
    for label_key in label_keys:
      if regex.match(label_key, label_str):
        labels.append(pada_labels[label_key])
        label_str = label_str.replace(label_key, "", 1)

  return labels

def dump_Rk(Rk_id, dest_subpath):  
  title = Rk_id.split("/")[-1]
  url = f"https://vedaweb.uni-koeln.de/rigveda/api/export/doc/{Rk_id.replace('/', '')}/xml"
  soup = scraping.get_post_soup(url, timeout=60.0)
  
  def dump_commentary(text_id):
    commentary = soup.select_one(f"lg[source={text_id}]")
    if commentary is not None:
      commentary = commentary.text.strip().replace("\n", "  \n")
      dest_path = os.path.join(Rk.SAMHITA_DIR_STATIC, text_id, dest_subpath)
      md_file = MdFile(file_path=dest_path)
      md_file.dump_to_file(metadata={"title": title}, content=commentary, dry_run=False)

  dump_commentary(text_id="geldner")
  dump_commentary(text_id="grassmann")
  dump_commentary(text_id="macdonell")
  dump_commentary(text_id="oldenberg")
  dump_commentary(text_id="elizarenkova")

  strata_text = ", ".join(OrderedSet([strata_meanings[x.text] for x in soup.select('f[name="strata"]')]))
  label_text = "  \n".join([";; ".join(get_paada_labels(x.text)) for x in soup.select('f[name="label"]')])
  vedaweb_annotation = f"## Strata\n{strata_text}\n\n## Pāda-label\n{label_text}\n"
  dest_path = os.path.join(Rk.SAMHITA_DIR_STATIC, "vedaweb_annotation", dest_subpath)
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=vedaweb_annotation, dry_run=False)


def dump_all():
  Rk_id_to_name_map = Rk.get_Rk_id_to_name_map_from_muulam()
  for Rk_id, name in Rk_id_to_name_map.items():
    dest_subpath = os.path.join(os.path.dirname(Rk_id), f"{name}.md")
    if os.path.exists(os.path.join(Rk.SAMHITA_DIR_STATIC, "vedaweb_annotation", dest_subpath)):
      logging.info(f"Skipping {Rk_id}")
      continue
    dump_Rk(Rk_id=Rk_id, dest_subpath=dest_subpath)


if __name__ == '__main__':
  dump_all()