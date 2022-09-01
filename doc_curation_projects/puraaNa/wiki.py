from urllib.parse import urljoin

from doc_curation.scraping import wikisource
from doc_curation.scraping.wikisource import enumerated, serial
from indic_transliteration import sanscript

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

