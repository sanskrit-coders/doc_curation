from urllib.parse import urljoin
import os

import regex

from doc_curation.md import library, content_processor

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

BASE_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/skanda-purANam"

def dump():
  from doc_curation.scraping import wikisource
  from doc_curation.scraping.wikisource import enumerated, serial
  from indic_transliteration import sanscript
  skanda_base_url = urljoin("https://sa.wikisource.org/wiki", "स्कन्दपुराणम्")
  # serial.dump_text(start_url="https://sa.wikisource.org/s/fue", out_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/4_kAshI-khaNDaH", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a', transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_८_(अम्बिकाखण्डः)/", num_parts=19, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/8_ambikA-khaNDaH/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_७_(प्रभासखण्डः)/द्वारकामाहात्म्यम्/अध्यायः", num_parts=44, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/7_prabhAsa-khaNDaH/4_dvArakA-mAhAtmyam/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_७_(प्रभासखण्डः)/अर्बुदखण्डम्/अध्यायः", num_parts=63, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/7_prabhAsa-khaNDaH/3_arbuda-khaNDam/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_७_(प्रभासखण्डः)/वस्त्रापथक्षेत्रमाहात्म्यम्/अध्यायः", num_parts=19, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/7_prabhAsa-khaNDaH/2_vastrApatha-xetra-mAhAtmyam/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_७_(प्रभासखण्डः)/प्रभासक्षेत्र_माहात्म्यम्/अध्यायः", num_parts=365, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/7_prabhAsa-khaNDaH/1_prabhAsa-xetra-mAhAtmyam/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः_६_(नागरखण्डः)/अध्यायः", num_parts=271, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/6_nAgara-khaNDaH/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ५ (अवन्तीखण्डः)/रेवा खण्डम्/अध्यायः", num_parts=232, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/5_avantI-khaNDaH/3_revA", url_id_padding="%03d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ५ (अवन्तीखण्डः)/अवन्तीस्थचतुरशीतिलिङ्गमाहात्म्यम्/अध्यायः", num_parts=84, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/5_avantI-khaNDaH/2_avantIstha-chaturashIti-linga-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ५ (अवन्तीखण्डः)/अवन्तीक्षेत्रमाहात्म्यम्/अध्यायः", num_parts=71, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/5_avantI-khaNDaH/1_avantI-xetra-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ४ (काशीखण्डः)/अध्यायः", num_parts=100, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/4_kAshI-khaNDaH", url_id_padding="%03d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ३ (ब्रह्मखण्डः)/ब्रह्मोत्तर खण्डः/अध्यायः", num_parts=22, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/3_brahma-khaNDaH/3_brahmottara-khaNDaH", url_id_padding="%d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ३ (ब्रह्मखण्डः)/धर्मारण्य खण्डः/अध्यायः", num_parts=40, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/3_brahma-khaNDaH/2_dharmAraNya-khaNDaH", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः ३ (ब्रह्मखण्डः)/सेतुखण्डः/अध्यायः", num_parts=52, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/3_brahma-khaNDaH/1_setu-khaNDaH", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/वासुदेवमाहात्म्यम्/अध्यायः", num_parts=32, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/9_vAsudeva-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/अयोध्यामाहात्म्यम्/अध्यायः", num_parts=10, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/8_ayodhyA-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/वैशाखमासमाहात्म्यम्/अध्यायः", num_parts=4, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/7_vaishAkha-mAsa-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/भागवतमाहात्म्यम्/अध्यायः", num_parts=4, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/6_bhAgavata-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/मार्गशीर्षमासमाहात्म्यम्/अध्यायः", num_parts=17, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/5_mArgashIrSha-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/कार्तिकमासमाहात्म्यम्/अध्यायः", num_parts=36, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/4_kArttika-mAsa-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/बदरिकाश्रममाहात्म्यम्/अध्यायः", num_parts=8, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/3_badarIkAshrama-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/पुरुषोत्तमजगन्नाथमाहात्म्यम्/अध्यायः", num_parts=49, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/2_puruShottama-jagannAtha-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)/वेङ्कटाचलमाहात्म्यम्/अध्यायः", num_parts=40, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/2_vaiShNava-khaNDaH/1_venkaTAchala-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः १ (माहेश्वरखण्डः)/अरुणाचलमाहात्म्यम् २/अध्यायः", num_parts=24, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/1_mAheshvara-khaNDaH/3b_aruNAchala-mAhAtmyam", url_id_padding="%02d")
  # enumerated.dump_text(url_base="स्कन्दपुराणम्/खण्डः १ (माहेश्वरखण्डः)/अरुणाचलमाहात्म्यम् १/अध्यायः", num_parts=13, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/1_mAheshvara-khaNDaH/3a_aruNAchala-mAhAtmyam", url_id_padding="%02d")
  # serial.dump_text(start_url="https://sa.wikisource.org/s/ggc", out_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/1_mAheshvara-khaNDaH/2_kaumArikA-khaNDaH", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a', transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  # serial.dump_text(start_url="https://sa.wikisource.org/s/gzf", out_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/1_mAheshvara-khaNDaH/1_kedAra-khaNDaH", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a', transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)


def fix_content(dir_path=BASE_DIR):
  pass
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["\[[^\]]+\]\(/w.+\).+\n+",], replacement=r"")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)[\d\*\. ←]+",], replacement=r"")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[०-९]) +(?=[०-९])",], replacement=r"")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"। *।",], replacement=r"॥")



def fix_names(dir_path, conclusion_pattern="इति.+ऽध्यायः"):
  pass
  # library.apply_function(fn=metadata_helper.transliterate_title, dir_path=dir_path)
  library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor=lambda x: metadata_helper.iti_naama_title_extractor(x, conclusion_pattern=conclusion_pattern))
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor= lambda x: metadata_helper.iti_saptamii_title_extractor(x, conclusion_pattern="इति.+महाभारते.+पर्वणि.+ \S+ .+ऽध्यायः"), dry_run=False)


# fix_content()
fix_names(dir_path=BASE_DIR, conclusion_pattern=r"इति .+ध्यायः")