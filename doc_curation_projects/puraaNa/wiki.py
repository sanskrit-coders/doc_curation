from urllib.parse import urljoin

from doc_curation.scraping import wikisource
from doc_curation.scraping.wikisource import enumerated, serial
from indic_transliteration import sanscript


def skanda():
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


if __name__ == '__main__':
    skanda()


def remainder():
  pass
  # enumerated.dump_text(url_base="अग्निपुराणम्/अध्यायः", num_parts=383, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/agni-purANam/")
  # enumerated.dump_text(url_base="गरुडपुराणम्/आचारकाण्डः/अध्यायः", num_parts=240, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/garuDa-purANam/AchAra-kANDaH/")
  # enumerated.dump_text(url_base="गरुडपुराणम्/प्रेतकाण्डः_(धर्मकाण्डः)/अध्यायः", num_parts=49, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/garuDa-purANam/dharma-kANDaH/")
  # enumerated.dump_text(url_base="गरुडपुराणम्/ब्रह्मकाण्डः_(मोक्षकाण्डः)/अध्यायः", num_parts=29, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/garuDa-purANam/moxa-kANDaH/")
  # enumerated.dump_text(url_base="नारदपुराणम्-_पूर्वार्धः/अध्यायः", num_parts=125, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/nArada-purANam/01/")
  # enumerated.dump_text(url_base="नारदपुराणम्-_उत्तरार्धः/अध्यायः", num_parts=82, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/nArada-purANam/02/")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_१_(सृष्टिखण्डम्)/अध्यायः", num_parts=82, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/01/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_२_(भूमिखण्डः)/अध्यायः", num_parts=125, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/02/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_३_(स्वर्गखण्डः)/अध्यायः", num_parts=62, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/03/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_४_(ब्रह्मखण्डः)/अध्यायः", num_parts=26, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/04/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_५_(पातालखण्डः)/अध्यायः", num_parts=117, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/05/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_६_(उत्तरखण्डः)/अध्यायः", num_parts=255, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/06/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_७_(क्रियाखण्डः)/अध्यायः", num_parts=26, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/padma-purANam/07/", url_id_padding="%02d")

  # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_१_(ब्रह्मखण्डः)/अध्यायः", num_parts=30, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmavaivarta-purANam/01/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_२_(प्रकृतिखण्डः)/अध्यायः", num_parts=67, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmavaivarta-purANam/02/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_३_(गणपतिखण्डः)/अध्यायः", num_parts=46, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmavaivarta-purANam/03/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_४_(श्रीकृष्णजन्मखण्डः)/अध्यायः", num_parts=133, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmavaivarta-purANam/04/", url_id_padding="%03d")

  # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/पूर्वभागः/अध्यायः", num_parts=38, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmANDa-purANam/01/", url_id_padding="%02d")
  # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/मध्यभागः/अध्यायः", num_parts=74, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmANDa-purANam/02/", url_id_padding="%d")
  # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/उत्तरभागः/अध्यायः", num_parts=44, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/brahmANDa-purANam/03/", url_id_padding="%d")
  # enumerated.dump_text(url_base="मत्स्यपुराणम्/अध्यायः", num_parts=291, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/matsya-purANam/", url_id_padding="%d")
  # enumerated.dump_text(url_base="लिङ्गपुराणम्_-_पूर्वभागः/अध्यायः", num_parts=108, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/linga-purANam/01/", url_id_padding="%d")
  # enumerated.dump_text(url_base="लिङ्गपुराणम्_-_उत्तरभागः/अध्यायः", num_parts=55, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/linga-purANam/02/", url_id_padding="%d")
  # enumerated.dump_text(url_base="वायुपुराणम्/पूर्वार्धम्/अध्यायः", num_parts=61, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/vAyu-purANam/01/", url_id_padding="%d")
  # enumerated.dump_text(url_base="वायुपुराणम्/उत्तरार्धम्/अध्यायः", num_parts=50, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/vAyu-purANam/02/", url_id_padding="%d")
  # enumerated.dump_text(url_base="वराहपुराणम्/अध्यायः", num_parts=218, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/varAha-purANam/", url_id_padding="%03d")
  # enumerated.dump_text(url_base="कालिकापुराणम्/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/kAlikA-purANam/", url_id_padding="%d")
  # enumerated.dump_text(url_base="श्रीमद्भागवतपुराणम्/स्कन्धः_१०/पूर्वार्धः/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/bhAgavata-purANam/10/", url_id_padding="%d")
  # enumerated.dump_text(url_base="श्रीमद्भागवतपुराणम्/स्कन्धः_१०/उत्तरार्धः/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/bhAgavata-purANam/10/", url_id_padding="%d")

  # enumerated.dump_deep_text(url_text_id="श्रीमद्भागवतपुराणम्", url_leaf_id_padding="%d", dir_path="/home/vvasuki/sanskrit/raw_etexts/purANam/bhAgavata-purANam/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/book_data/puraana/bhaagavatam.json", dry_run=False)

