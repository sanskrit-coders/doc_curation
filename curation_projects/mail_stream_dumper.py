from doc_curation.mail_stream import mailman



if __name__ == '__main__':
  pass
  # mailman.scrape_messages(url="https://list.indology.info/pipermail/indology/", list_id="[INDOLOGY] ", dest_dir_base="/home/vvasuki/sanskrit/raw_etexts_english/mail_streams/indology/", dry_run=False)
  mailman.scrape_messages(url="https://lists.advaita-vedanta.org/archives/advaita-l/", list_id="[Advaita-l] ", dest_dir_base="/home/vvasuki/sanskrit/raw_etexts_english/mail_streams/advaita-l/", dry_run=False)