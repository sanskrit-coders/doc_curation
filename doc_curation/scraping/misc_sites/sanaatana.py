import os

import regex
import tqdm
from torch._export.db import logging

from curation_utils import scraping
from doc_curation.md import markdownify_plain_text
from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile
from doc_curation.md.library.arrangement import fix_index_files
from doc_curation.scraping.html_scraper import souper
from doc_curation.utils import sanskrit_helper
from doc_curation_projects.general_tasks import content
from indic_transliteration import sanscript
import logging


def dump_mbh(dest_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/nIla-kaNTha-chatur-dharaH"):
  parva_to_upaparva_count = {"adi": 19, "sabha": 10, "vana": 22, "virata": 5, "udyoga": 10, "bhishma": 4, "drona": 8, "karna": 1, "shalya": 3, "sauptika": 2, "stri": 3, "shanti": 3, "anushasana": 2, "ashwamedhika": 2, "mausala": 1, "mahaprasthanika": 1, "swargarohana": 2, "harivamsha": 3}
  parva_to_names = {"adi": "Adi", "sabha": "sabhA", "vana": "vana", "virata": "virATa", "udyoga": "udyoga", "bhishma": "bhIShma", "drona": "droNa", "karna": "karNa", "shalya": "shalya", "sauptika": "sauptika", "stri": "strI", "shanti": "shAnti", "anushasana": "anushAsana", "ashwamedhika": "Ashvamedhika", "mausala": "mausala", "mahaprasthanika": "mahA-prasthAnika", "swargarohana": "svargArohaNa", "harivamsha": "hari-vaMsha"}
  for parva, upaparva_count in tqdm.tqdm(parva_to_upaparva_count.items(), desc="parva"):
    parva_name = parva_to_names[parva]
    for upaparva_id_url in tqdm.tqdm(range(1, upaparva_count + 1), desc="upaparva"):
      url = f"https://sanatana.in/mahabharata/listing/getParvaByPage/{parva}{"parva" if parva != "harivamsha" else ""}?page={upaparva_id_url}"
      (soup, _) = scraping.get_soup(url=url)
      upaparva_title = soup.select_one(".upaparva_title")
      
      upaparva_name_dev = upaparva_title.text.strip()
      upaparva_name_dev = sanskrit_helper.fix_anunaasikaadi(upaparva_name_dev)
      upaparva_name_dev = regex.sub("[।॥]", "", upaparva_name_dev)
      upaparva_name = sanscript.transliterate(upaparva_name_dev, _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS)
      upaparva_name = regex.sub("parva$", "-parva", upaparva_name)
      adhyayas = soup.select(".adhyaya")
      for adhyaya in tqdm.tqdm(adhyayas, desc="adhyAyas"):
        id = adhyaya.get_html("id")
        for subid in id.split("_"):
          if subid.startswith("P"):
            parva_id = subid[1:]
          if subid.startswith("U"):
            upaparva_id = subid[1:]
          if subid.startswith("A"):
            adhyaaya_id = subid[1:]
        details = []
        for shloka in adhyaya.select(".shloka"):
          shloka_text = shloka.select_one(".shloka_text")
          shloka_id = shloka.get_html("id").split("_")[-1][1:]
          def fix_text(text):
            text = regex.sub(r"\s*\n\s*([।॥])", r"\1  \n", text)
            text = markdownify_plain_text(text)
            return text
          if shloka_text is None:
            text = "TODO: MISSING"
            logging.warning(f"{text} {shloka.get_html('id')}")
          else:
            text = fix_text(shloka_text.text)
          detail = Detail(title=f"मूलम् - {shloka_id}", content=text)
          details.append(detail.to_md_html(attributes_str="open"))
          comment = shloka.select_one(".bhavadeepa")
          if comment is not None:
            detail = Detail(title=f"नील-कण्ठ–चतुर्-धरः - {shloka_id}", content=fix_text(comment.text))
            details.append(detail.to_md_html())
        content = "\n\n".join(details)
        content = sanskrit_helper.fix_anunaasikaadi(content)
        adhyaaya_path = f"{dest_path}/{parva_id:02}_{parva_name}-parva/"
        if upaparva_count > 1:
          adhyaaya_path += f"{upaparva_id:02}_{upaparva_name}/"
        adhyaaya_path += f"{adhyaaya_id}.md"
        os.makedirs(os.path.dirname(adhyaaya_path), exist_ok=True)
        md_file = MdFile(adhyaaya_path)
        md_file.dump_to_file(metadata={"title": adhyaaya_id}, content=content, dry_run=False)
  fix_index_files(dest_path, dry_run=False)

if __name__ == '__main__':
  dump_mbh()