from doc_curation.mail_stream import mailman



if __name__ == '__main__':
  pass
  mailman.scrape_messages(url="https://list.indology.info/pipermail/indology/", list_id="[INDOLOGY] ", dest_dir_base="/home/vvasuki/sanskrit/raw_etexts_english/mail_streams/indology/", dry_run=False)