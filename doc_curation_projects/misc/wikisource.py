from doc_curation.scraping import wikisource
from doc_curation.scraping.wikisource import enumerated, serial
from indic_transliteration import sanscript




if __name__ == '__main__':
    pass
    # logging.debug(get_item("http://sanskritabhyas.in/hi/Kridanta/View/%E0%A4%AD%E0%A5%82"))

    # serial.dump_text(start_url="https://sa.wikisource.org/wiki/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%81%E0%A4%A4%E0%A4%AC%E0%A5%8B%E0%A4%A7%E0%A4%83_(%E0%A4%AA%E0%A4%B0%E0%A5%80%E0%A4%95%E0%A5%8D%E0%A4%B7%E0%A5%8B%E0%A4%AA%E0%A4%95%E0%A4%BE%E0%A4%B0%E0%A4%BF%E0%A4%A3%E0%A5%80%E0%A4%9F%E0%A5%80%E0%A4%95%E0%A4%BE%E0%A4%B8%E0%A4%B9%E0%A4%BF%E0%A4%A4%E0%A4%83)", out_path="/home/vvasuki/vvasuki-git/kAvya/content/shAstram/shrutabodhaH/", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a',  transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)



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
