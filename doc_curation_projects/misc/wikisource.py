import os.path

from doc_curation.md import library, content_processor
from doc_curation.scraping import wikisource
from doc_curation.scraping.wikisource import enumerated, serial
from indic_transliteration import sanscript


def paancharaatra():
  pass
  # serial.dump_text(start_url="https://sa.wikisource.org/s/6yv",
  #                  out_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/prakAshasaMhitA/1/",
  #                  next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',
  #                  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  # enumerated.dump_text(url_base="परमपुरुषसंहिता/अध्यायः_", num_parts=10, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/paramapuruSha-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="अहिर्बुध्नसंहिता/अध्यायः_", num_parts=36, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/ahirbudhnya-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="पुरुषोत्तमसंहिता/अध्यायः", num_parts=33, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/puruShottama-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="प्रश्नसंहिता/अध्यायः", num_parts=53, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/prashna-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="विष्णुसंहिता/पटलः", num_parts=30, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/viShNu-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="सात्त्वतसंहिता/अध्यायः", num_parts=25, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/sAttvata-saMhitA/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="भार्गवतन्त्रम्/अध्यायः", num_parts=25, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/bhArgava-tantram/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="लक्ष्मीतन्त्रम्/अध्यायः", num_parts=57, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/laxmI-tantram/", url_id_padding="%d", transliterate_id=True)
  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH", transliteration_target=sanscript.DEVANAGARI, overwrite=False, dry_run=False)


def vaikhaanasa():
  pass
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/vaikhAnasaH/"
  # serial.dump_text(start_url="https://sa.wikisource.org/s/2mn5",
  #                  out_path=os.path.join(base_dir, "AgamaH/kriyAdhikAraH/"),
  #                  next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',
  #                  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  # serial.dump_text(start_url="https://sa.wikisource.org/s/2moh",
  #                  out_path=os.path.join(base_dir, "AgamaH/yajJNAdhikAraH/"),
  #                  next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',
  #                  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  serial.dump_text(start_url="https://sa.wikisource.org/s/7pe",
                   out_path=os.path.join(base_dir, "bhRgu-saMhitA/"),
                   next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',
                   transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  # serial.dump_text(start_url="https://sa.wikisource.org/s/1tzr",
  #                  out_path=os.path.join(base_dir, "vishvAmitra-saMhitA/"),
  #                  next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',
  #                  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  library.apply_function(fn=content_processor.replace_texts, dir_path=base_dir, patterns=["[^\n]+\/wiki\/[^\n]+"], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=base_dir, patterns=["[^\n]+\[लेखकः[^\n]+"], replacement="")
  library.fix_index_files(dir_path=base_dir, transliteration_target=sanscript.DEVANAGARI, overwrite=False, dry_run=False)


if __name__ == '__main__':
  pass
  # paancharaatra()
  vaikhaanasa()
  # logging.debug(get_item("http://sanskritabhyas.in/hi/Kridanta/View/%E0%A4%AD%E0%A5%82"))

  # serial.dump_text(start_url="https://en.enumerated.org/wiki/Sanskrit_Grammar_(Whitney)", out_path="/home/vvasuki/vvasuki-git/sanskrit/content/vyAkaraNam/whitney", base_url="http://en.wikisource.org/", dry_run=False)
  # serial.dump_text(start_url="https://sa.wikisource.org/s/1wlz", out_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/saMskAraratnamAlA/01/", dry_run=False)
  # serial.dump_text(start_url="https://sa.wikisource.org/s/1y6k", out_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/saMskAraratnamAlA/02/", dry_run=False)

  # enumerated.dump_text(url_base="पैप्पलादसंहिता/काण्डम्", num_parts=20, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/paippalAda/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="अथर्ववेदः/काण्डं", num_parts=20, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/shaunaka/visvara/")

  # enumerated.dump_text(url_base="ऋग्वेदः_खिलसूक्तानि/अध्यायः", num_parts=5, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/saMhitA/khilAni/visvara/", url_id_padding="%d")
  # enumerated.dump_text(url_base="शुक्लयजुर्वेदः/अध्यायः", num_parts=40, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/mAdhyandina/visvara/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="वेतालपञ्चविंशति", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/kAvyam/vetAla-panchavimshatikA/", url_id_padding="%02d", transliterate_id=False)
  # enumerated.dump_deep_text(url_text_id="कथासरित्सागरः", url_leaf_id_padding="%d", dir_path="/home/vvasuki/sanskrit/raw_etexts/kAvyam/kathAsaritsAgaraH/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/book_data/kAvyam/kathAsaritsAgaraH.json", dry_run=False)
  # enumerated.dump_text(url_base="पञ्चविंशब्राह्मणम्/अध्यायः_", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/sAma/tANDyam/panchaviMsha-brAhmaNam/", url_id_padding="%d", transliterate_id=True)
  # enumerated.dump_text(url_base="पञ्चविंशब्राह्मणम्/अध्यायः_", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/sAma/kauthumam/brAhmaNam/ShaDviMsham/", url_id_padding="%d", transliterate_id=True)
