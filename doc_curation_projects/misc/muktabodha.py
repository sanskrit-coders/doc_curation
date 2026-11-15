from doc_curation.scraping.misc_sites import muktabodha

MUKTA_BASE = "/home/vvasuki/gitland/sanskrit/raw_etexts_private/mixed/mukta"

if __name__ == '__main__':
  # Needs an extracted copy of the download (eg. ~/Downloads/mukta) and only adds etexts missing from the mirror.
  # muktabodha.scrape_from_json(out_dir="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta")
  # Reads the download zip directly; adds new etexts, and reports (or with update_existing=True refreshes) revised ones.
  muktabodha.update_from_download(zip_path="/home/vvasuki/Downloads/muktalib_IAST_download_2026-08-24.zip", out_dir="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta")
  pass
  # muktabodha.fix_lines(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/bheda-darshanam/siddhAntaH/tattvam/sadyo-jyotiH/tattva-saMgrahaH.md")
  # muktabodha.fix_footnotes(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pauShkara-saMhitA")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=MUKTA_BASE, patterns=[r"ए-तेxत्स् मय् बे विएwएद् ओन्ल्य् ओन्लिने ओर् दोwन्लोअदेद् फ़ोर् प्रिवते स्तुद्य्। *"], replacement="")
  
