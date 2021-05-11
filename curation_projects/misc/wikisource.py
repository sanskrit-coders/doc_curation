from doc_curation.scraping import wikisource
from doc_curation.scraping.wikisource import enumerated, serial
from indic_transliteration import sanscript

if __name__ == '__main__':
    pass
    # logging.debug(get_item("http://sanskritabhyas.in/hi/Kridanta/View/%E0%A4%AD%E0%A5%82"))

    serial.dump_text(start_url="https://sa.wikisource.org/s/1r23", out_path="/home/vvasuki/sanskrit/raw_etexts/AyurvedaH/sUtram_yogAnanda-nAtha-bhAShya-sametam", transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)

    # serial.dump_text(start_url="https://sa.wikisource.org/wiki/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%81%E0%A4%A4%E0%A4%AC%E0%A5%8B%E0%A4%A7%E0%A4%83_(%E0%A4%AA%E0%A4%B0%E0%A5%80%E0%A4%95%E0%A5%8D%E0%A4%B7%E0%A5%8B%E0%A4%AA%E0%A4%95%E0%A4%BE%E0%A4%B0%E0%A4%BF%E0%A4%A3%E0%A5%80%E0%A4%9F%E0%A5%80%E0%A4%95%E0%A4%BE%E0%A4%B8%E0%A4%B9%E0%A4%BF%E0%A4%A4%E0%A4%83)", out_path="/home/vvasuki/vvasuki-git/kAvya/content/shAstram/shrutabodhaH/", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)



    # serial.dump_text(start_url="https://en.enumerated.org/wiki/Sanskrit_Grammar_(Whitney)", out_path="/home/vvasuki/vvasuki-git/sanskrit/content/vyAkaraNam/whitney", base_url="http://en.wikisource.org/", dry_run=False)
    # serial.dump_text(start_url="https://sa.wikisource.org/s/1wlz", out_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/saMskAraratnamAlA/01/", dry_run=False)
    # serial.dump_text(start_url="https://sa.wikisource.org/s/1y6k", out_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/saMskAraratnamAlA/02/", dry_run=False)
    # enumerated.dump_text(url_base="अग्निपुराणम्/अध्यायः", num_parts=383, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/agni-purANam/")
    # enumerated.dump_text(url_base="गरुडपुराणम्/आचारकाण्डः/अध्यायः", num_parts=240, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/garuDa-purANam/AchAra-kANDaH/")
    # enumerated.dump_text(url_base="गरुडपुराणम्/प्रेतकाण्डः_(धर्मकाण्डः)/अध्यायः", num_parts=49, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/garuDa-purANam/dharma-kANDaH/")
    # enumerated.dump_text(url_base="गरुडपुराणम्/ब्रह्मकाण्डः_(मोक्षकाण्डः)/अध्यायः", num_parts=29, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/garuDa-purANam/moxa-kANDaH/")
    # enumerated.dump_text(url_base="नारदपुराणम्-_पूर्वार्धः/अध्यायः", num_parts=125, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/nArada-purANam/01/")
    # enumerated.dump_text(url_base="नारदपुराणम्-_उत्तरार्धः/अध्यायः", num_parts=82, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/nArada-purANam/02/")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_१_(सृष्टिखण्डम्)/अध्यायः", num_parts=82, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/01/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_२_(भूमिखण्डः)/अध्यायः", num_parts=125, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/02/", url_id_padding="%03d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_३_(स्वर्गखण्डः)/अध्यायः", num_parts=62, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/03/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_४_(ब्रह्मखण्डः)/अध्यायः", num_parts=26, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/04/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_५_(पातालखण्डः)/अध्यायः", num_parts=117, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/05/", url_id_padding="%03d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_६_(उत्तरखण्डः)/अध्यायः", num_parts=255, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/06/", url_id_padding="%03d")
    # enumerated.dump_text(url_base="पद्मपुराणम्/खण्डः_७_(क्रियाखण्डः)/अध्यायः", num_parts=26, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/padma-purANam/07/", url_id_padding="%02d")

    # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_१_(ब्रह्मखण्डः)/अध्यायः", num_parts=30, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmavaivarta-purANam/01/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_२_(प्रकृतिखण्डः)/अध्यायः", num_parts=67, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmavaivarta-purANam/02/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_३_(गणपतिखण्डः)/अध्यायः", num_parts=46, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmavaivarta-purANam/03/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="ब्रह्मवैवर्तपुराणम्/खण्डः_४_(श्रीकृष्णजन्मखण्डः)/अध्यायः", num_parts=133, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmavaivarta-purANam/04/", url_id_padding="%03d")

    # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/पूर्वभागः/अध्यायः", num_parts=38, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmANDa-purANam/01/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/मध्यभागः/अध्यायः", num_parts=74, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmANDa-purANam/02/", url_id_padding="%d")
    # enumerated.dump_text(url_base="ब्रह्माण्डपुराणम्/उत्तरभागः/अध्यायः", num_parts=44, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/brahmANDa-purANam/03/", url_id_padding="%d")
    # enumerated.dump_text(url_base="मत्स्यपुराणम्/अध्यायः", num_parts=291, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/matsya-purANam/", url_id_padding="%d")
    # enumerated.dump_text(url_base="लिङ्गपुराणम्_-_पूर्वभागः/अध्यायः", num_parts=108, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/linga-purANam/01/", url_id_padding="%d")
    # enumerated.dump_text(url_base="लिङ्गपुराणम्_-_उत्तरभागः/अध्यायः", num_parts=55, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/linga-purANam/02/", url_id_padding="%d")
    # enumerated.dump_text(url_base="वायुपुराणम्/पूर्वार्धम्/अध्यायः", num_parts=61, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/vAyu-purANam/01/", url_id_padding="%d")
    # enumerated.dump_text(url_base="वायुपुराणम्/उत्तरार्धम्/अध्यायः", num_parts=50, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/vAyu-purANam/02/", url_id_padding="%d")
    # enumerated.dump_text(url_base="वराहपुराणम्/अध्यायः", num_parts=218, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/varAha-purANam/", url_id_padding="%03d")
    # enumerated.dump_text(url_base="कालिकापुराणम्/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/kAlikA-purANam/", url_id_padding="%d")
    # enumerated.dump_text(url_base="श्रीमद्भागवतपुराणम्/स्कन्धः_१०/पूर्वार्धः/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/bhAgavata-purANam/10/", url_id_padding="%d")
    # enumerated.dump_text(url_base="श्रीमद्भागवतपुराणम्/स्कन्धः_१०/उत्तरार्धः/अध्यायः", num_parts=90, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/bhAgavata-purANam/10/", url_id_padding="%d")

    # enumerated.dump_deep_text(url_text_id="श्रीमद्भागवतपुराणम्", url_leaf_id_padding="%d", dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/bhAgavata-purANam/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/text_data/puraana/bhaagavatam.json", dry_run=False)


    # enumerated.dump_text(url_base="पैप्पलादसंहिता/काण्डम्", num_parts=20, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/paippalAda/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="अथर्ववेदः/काण्डं", num_parts=20, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/shaunaka/visvara/")

    # enumerated.dump_text(url_base="ऋग्वेदः_खिलसूक्तानि/अध्यायः", num_parts=5, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/saMhitA/khilAni/visvara/", url_id_padding="%d")
    # enumerated.dump_text(url_base="शुक्लयजुर्वेदः/अध्यायः", num_parts=40, dir_path="/home/vvasuki/sanskrit/raw_etexts/veda/mAdhyandina/visvara/", url_id_padding="%02d")
    # enumerated.dump_text(url_base="वेतालपञ्चविंशति", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/kAvyam/vetAla-panchavimshatikA/", url_id_padding="%02d", transliterate_id=False)
    # enumerated.dump_deep_text(url_text_id="कथासरित्सागरः", url_leaf_id_padding="%d", dir_path="/home/vvasuki/sanskrit/raw_etexts/kAvyam/kathAsaritsAgaraH/", unit_info_file="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/text_data/kAvyam/kathAsaritsAgaraH.json", dry_run=False)
    # enumerated.dump_text(url_base="पञ्चविंशब्राह्मणम्/अध्यायः_", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/sAma/tANDyam/panchaviMsha-brAhmaNam/", url_id_padding="%d", transliterate_id=True)
    # enumerated.dump_text(url_base="पञ्चविंशब्राह्मणम्/अध्यायः_", num_parts=25, dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/sAma/kauthumam/brAhmaNam/ShaDviMsham/", url_id_padding="%d", transliterate_id=True)
